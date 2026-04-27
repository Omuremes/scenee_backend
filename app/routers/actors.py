import json
import os
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import delete_cache_by_prefix, get_cache, set_cache
from app.core.config import settings
from app.core.database import get_db
from app.core.minio import to_public_url, upload_file
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import ActorCreate, ActorPageResponse, ActorResponse, ActorUpdate
from app.services import ActorService

public_router = APIRouter(prefix="/v1/actors", tags=["actors"])
admin_router = APIRouter(prefix="/v1/admin/actors", tags=["admin-actors"])

ADMIN_ACTOR_CACHE_PREFIX = "admin:actors:"
ADMIN_ACTOR_LIST_TTL_SECONDS = 300


def _model_openapi_schema(schema_type) -> dict:
    if hasattr(schema_type, "model_json_schema"):
        return schema_type.model_json_schema()
    return schema_type.schema()


def _actor_multipart_openapi_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "full_name": {"type": "string", "maxLength": 255},
            "bio": {"type": "string"},
            "photo": {
                "oneOf": [
                    {"type": "string", "format": "binary"},
                    {"type": "string", "format": "uri"},
                ],
                "description": "Upload actor photo file or provide a direct URL",
            },
        },
        "required": ["full_name"],
    }


ACTOR_CREATE_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": _model_openapi_schema(ActorCreate),
            },
            "multipart/form-data": {
                "schema": _actor_multipart_openapi_schema(),
            },
        },
    }
}


def _serialize_cache_payload(payload) -> str:
    return json.dumps(jsonable_encoder(payload), separators=(",", ":"), sort_keys=True)


def _normalize_query(query: Optional[str], alias_query: Optional[str]) -> Optional[str]:
    value = alias_query if alias_query is not None else query
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _invalidate_admin_actor_cache() -> None:
    await delete_cache_by_prefix(ADMIN_ACTOR_CACHE_PREFIX)


def _ensure_actor_validation_error(exc: ValidationError):
    raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors()))


def _photo_from_url(url: str) -> str:
    normalized_url = url.strip()
    if not normalized_url:
        raise HTTPException(status_code=400, detail="Photo URL cannot be empty")
    return to_public_url(normalized_url) or normalized_url


async def _upload_actor_photo(photo_file: UploadFile) -> str:
    suffix = Path(photo_file.filename or "actor-photo").suffix or ".bin"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await photo_file.read())
            temp_path = temp_file.name

        object_name = f"actors/{uuid4()}{suffix}"
        return await upload_file(
            settings.MINIO_BUCKET_NAME,
            object_name,
            temp_path,
            content_type=photo_file.content_type or "application/octet-stream",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


async def _parse_actor_create_request(request: Request) -> ActorCreate:
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            payload = await request.json()
            return ActorCreate.model_validate(payload)
        except ValidationError as exc:
            _ensure_actor_validation_error(exc)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON payload: {exc}") from exc

    if "multipart/form-data" in content_type:
        form = await request.form()
        raw_payload = {
            "full_name": form.get("full_name"),
            "bio": form.get("bio"),
        }

        photo_values = form.getlist("photo")
        photo_file = next(
            (
                value
                for value in photo_values
                if hasattr(value, "filename") and hasattr(value, "read") and getattr(value, "filename", None)
            ),
            None,
        )
        photo_text = next((value for value in photo_values if isinstance(value, str) and value.strip()), None)

        if photo_file is not None:
            raw_payload["photo_url"] = await _upload_actor_photo(photo_file)
        elif photo_text is not None:
            raw_payload["photo_url"] = _photo_from_url(photo_text)
        elif "photo_url" in form and isinstance(form.get("photo_url"), str) and form.get("photo_url").strip():
            raw_payload["photo_url"] = _photo_from_url(form.get("photo_url"))

        try:
            return ActorCreate.model_validate(raw_payload)
        except ValidationError as exc:
            _ensure_actor_validation_error(exc)

    raise HTTPException(
        status_code=415,
        detail="Supported content types are application/json and multipart/form-data",
    )


@public_router.get("/", response_model=ActorPageResponse)
async def get_actors(
    query: Optional[str] = Query(None, description="Search by actor name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    actors, total = await actor_service.list_actors(query=query, skip=offset, limit=limit)
    return ActorPageResponse(
        items=[ActorResponse.model_validate(actor) for actor in actors],
        total=total,
        offset=offset,
        limit=limit,
        has_more=offset + limit < total,
    )


@public_router.get("/{actor_id}", response_model=ActorResponse)
async def get_actor(
    actor_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    actor = await actor_service.get_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    return ActorResponse.model_validate(actor)


@admin_router.get("/", response_model=ActorPageResponse)
async def admin_get_actors(
    query: Optional[str] = Query(None, description="Search by actor name"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_query = _normalize_query(query, q)
    cache_key = f"{ADMIN_ACTOR_CACHE_PREFIX}list:query={resolved_query or ''}:offset={offset}:limit={limit}"
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    actor_service = ActorService(db)
    actors, total = await actor_service.list_actors(query=resolved_query, skip=offset, limit=limit)
    response_payload = ActorPageResponse(
        items=[ActorResponse.model_validate(actor) for actor in actors],
        total=total,
        offset=offset,
        limit=limit,
        has_more=offset + limit < total,
    )
    await set_cache(cache_key, _serialize_cache_payload(response_payload), expire=ADMIN_ACTOR_LIST_TTL_SECONDS)
    return response_payload


@admin_router.get("/{actor_id}", response_model=ActorResponse)
async def admin_get_actor(
    actor_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    actor = await actor_service.get_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    return ActorResponse.model_validate(actor)


@admin_router.post(
    "/",
    response_model=ActorResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=ACTOR_CREATE_OPENAPI,
)
async def create_actor(
    request: Request,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_data = await _parse_actor_create_request(request)
    actor_service = ActorService(db)
    try:
        actor = await actor_service.create_actor(actor_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _invalidate_admin_actor_cache()
    return ActorResponse.model_validate(actor)


@admin_router.patch("/{actor_id}", response_model=ActorResponse)
async def update_actor(
    actor_id: UUID,
    actor_data: ActorUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    try:
        actor = await actor_service.update_actor(actor_id, actor_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    await _invalidate_admin_actor_cache()
    return ActorResponse.model_validate(actor)


@admin_router.delete("/{actor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_actor(
    actor_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    deleted = await actor_service.delete(actor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Actor not found")
    await _invalidate_admin_actor_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
