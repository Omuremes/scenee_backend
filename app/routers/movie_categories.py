import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import delete_cache_by_prefix, get_cache, set_cache
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import (
    MovieCategoryCreate,
    MovieCategoryPageResponse,
    MovieCategoryResponse,
    MovieCategoryUpdate,
)
from app.services import MovieCategoryService

ADMIN_MOVIE_CATEGORY_CACHE_PREFIX = "admin:movie-categories:"
ADMIN_MOVIE_CATEGORY_LIST_TTL_SECONDS = 300

router = APIRouter(prefix="/v1/admin/movies/categories", tags=["admin-movie-categories"])


def _serialize_cache_payload(payload) -> str:
    return json.dumps(jsonable_encoder(payload), separators=(",", ":"), sort_keys=True)


def _normalize_query(query: Optional[str], alias_query: Optional[str]) -> Optional[str]:
    value = alias_query if alias_query is not None else query
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def _invalidate_movie_category_cache() -> None:
    await delete_cache_by_prefix(ADMIN_MOVIE_CATEGORY_CACHE_PREFIX)
    await delete_cache_by_prefix("movies:public:")


@router.get("/", response_model=MovieCategoryPageResponse)
async def list_movie_categories(
    query: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_query = _normalize_query(query, q)
    cache_key = f"{ADMIN_MOVIE_CATEGORY_CACHE_PREFIX}list:query={resolved_query or ''}:offset={offset}:limit={limit}"
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    category_service = MovieCategoryService(db)
    categories, total = await category_service.list_categories(query=resolved_query, skip=offset, limit=limit)
    response_payload = MovieCategoryPageResponse(
        items=[MovieCategoryResponse.model_validate(category) for category in categories],
        total=total,
        offset=offset,
        limit=limit,
        has_more=offset + limit < total,
    )
    await set_cache(cache_key, _serialize_cache_payload(response_payload), expire=ADMIN_MOVIE_CATEGORY_LIST_TTL_SECONDS)
    return response_payload


@router.get("/{category_id}", response_model=MovieCategoryResponse)
async def get_movie_category(
    category_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = MovieCategoryService(db)
    category = await category_service.get_by_id(category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Movie category not found")
    return MovieCategoryResponse.model_validate(category)


@router.post("/", response_model=MovieCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_movie_category(
    category_data: MovieCategoryCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = MovieCategoryService(db)
    try:
        category = await category_service.create_category(category_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await _invalidate_movie_category_cache()
    return MovieCategoryResponse.model_validate(category)


@router.patch("/{category_id}", response_model=MovieCategoryResponse)
async def update_movie_category(
    category_id: UUID,
    category_data: MovieCategoryUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = MovieCategoryService(db)
    try:
        category = await category_service.update_category(category_id, category_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not category:
        raise HTTPException(status_code=404, detail="Movie category not found")

    await _invalidate_movie_category_cache()
    return MovieCategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie_category(
    category_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = MovieCategoryService(db)
    deleted = await category_service.delete(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Movie category not found")

    await _invalidate_movie_category_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
