import os
import shutil
import tempfile
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.core.minio import upload_file
from app.core.rate_limit import enforce_rate_limit, get_client_identifier
from app.core.security import create_access_token, create_refresh_token, get_current_user, verify_refresh_token
from app.models import User
from app.schemas import RefreshTokenRequest, RegisterResponse, TokenResponse, UserLogin, UserRegister, UserResponse, UserSync, UserUpdate
from app.services import UserService

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _build_token_response(user: User) -> TokenResponse:
    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(
        {"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@router.post("/register", response_model=RegisterResponse)
async def register_user(
    user_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        await enforce_rate_limit(
            "auth:register",
            f"{get_client_identifier(request)}:{user_data.email}",
            limit=5,
            window_seconds=3600,
        )
        user_service = UserService(db)
        result = await user_service.create_user(user_data)
        user = result["user"]
        token_response = _build_token_response(user)
        return RegisterResponse(
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            token_type=token_response.token_type,
            expires_in=token_response.expires_in,
            refresh_expires_in=token_response.refresh_expires_in,
            user=UserResponse.model_validate(user),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        "auth:login",
        f"{get_client_identifier(request)}:{login_data.email}",
        limit=10,
        window_seconds=900,
    )

    user_service = UserService(db)
    existing_user = await user_service.get_user_by_email(login_data.email)
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email was not found",
        )

    user = await user_service.authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    payload: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        "auth:refresh",
        get_client_identifier(request),
        limit=30,
        window_seconds=60,
    )

    try:
        token_payload = verify_refresh_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _build_token_response(user)


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_service = UserService(db)
    updated_user = await user_service.update_user(current_user.id, user_data)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update failed",
        )
    return UserResponse.model_validate(updated_user)


@router.post("/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    suffix = os.path.splitext(file.filename)[1] if file.filename else ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        object_name = f"avatars/{current_user.id}{suffix}"
        avatar_url = await upload_file(
            settings.MINIO_BUCKET_NAME,
            object_name,
            tmp_path,
            content_type=file.content_type
        )

        user_service = UserService(db)
        updated_user = await user_service.update_user(current_user.id, UserUpdate(avatar_url=avatar_url))
        if not updated_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update user avatar")
        
        return UserResponse.model_validate(updated_user)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/sync", response_model=UserResponse)
async def sync_user(
    request: Request,
    user_data: UserSync | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        "auth:sync",
        get_client_identifier(request),
        limit=30,
        window_seconds=60,
    )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be a Bearer token",
        )

    token = authorization[len("Bearer ") :].strip()
    try:
        decoded_token = await verify_firebase_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
        )

    firebase_uid = decoded_token.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token did not contain a UID",
        )

    try:
        user_service = UserService(db)
        result = await user_service.get_or_create_user(
            firebase_uid=firebase_uid,
            user_data=user_data,
            firebase_email=decoded_token.get("email"),
            email_verified=bool(decoded_token.get("email_verified")),
        )
        return UserResponse.model_validate(result["user"])
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication failed",
        )
