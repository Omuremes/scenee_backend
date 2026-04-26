from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.firebase import verify_firebase_token
from app.core.rate_limit import enforce_rate_limit, get_client_identifier
from app.core.security import create_access_token, get_current_user, security
from app.models import User
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse, UserSync
from app.services import UserService

router = APIRouter(prefix="/public/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
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
        return UserResponse.model_validate(result["user"])
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
    user = await user_service.authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        {"sub": str(user.id), "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


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
