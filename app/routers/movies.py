import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status, Request, Form
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import delete_cache_by_prefix, get_cache, set_cache
from app.core.config import settings
from app.core.database import get_db
from app.core.minio import to_public_url, upload_file
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import MovieCreate, MovieListResponse, MoviePageResponse, MovieResponse, MovieUpdate
from app.services import MovieService

PUBLIC_MOVIE_CACHE_PREFIX = "movies:public:"
PUBLIC_MOVIE_LIST_TTL_SECONDS = 300
PUBLIC_MOVIE_DETAIL_TTL_SECONDS = 300
PUBLIC_MOVIE_POPULAR_TTL_SECONDS = 600
PUBLIC_MOVIE_NEW_TTL_SECONDS = 300

public_router = APIRouter(prefix="/v1/movies", tags=["movies"])
admin_router = APIRouter(prefix="/v1/admin/movies", tags=["admin-movies"])


def _normalize_query(query: Optional[str], alias_query: Optional[str]) -> Optional[str]:
    value = alias_query if alias_query is not None else query
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_offset(offset: int, skip: Optional[int]) -> int:
    return skip if skip is not None else offset


def _serialize_cache_payload(payload) -> str:
    return json.dumps(jsonable_encoder(payload), separators=(",", ":"), sort_keys=True)


async def _invalidate_public_movie_cache() -> None:
    await delete_cache_by_prefix(PUBLIC_MOVIE_CACHE_PREFIX)


async def _upload_poster(poster: UploadFile) -> dict:
    if poster.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Invalid poster format. Use image/jpeg or image/png")

    suffix = Path(poster.filename or "").suffix or ".jpg"
    poster_key = f"movies/posters/{uuid4()}{suffix}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await poster.read())
        temp_path = temp_file.name

    try:
        poster_url = await upload_file(settings.MINIO_BUCKET_NAME, poster_key, temp_path, content_type=poster.content_type)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    return {"storage_path": poster_key, "url": poster_url, "is_primary": True}


def _poster_from_url(url: str) -> dict:
    return {"url": to_public_url(url) or url, "storage_path": None, "is_primary": True}


def _poster_payload_from_value(url: Optional[str]) -> Optional[dict]:
    if url is None:
        return None
    return _poster_from_url(url)


def _field_was_provided(schema, field_name: str) -> bool:
    field_set = getattr(schema, "model_fields_set", None)
    if field_set is None:
        field_set = getattr(schema, "__fields_set__", set())
    return field_name in field_set


@public_router.get("/", response_model=MoviePageResponse)
async def get_movies(
    query: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    skip: Optional[int] = Query(None, ge=0, description="Deprecated alias for offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    resolved_query = _normalize_query(query, q)
    resolved_offset = _resolve_offset(offset, skip)
    cache_key = (
        f"{PUBLIC_MOVIE_CACHE_PREFIX}list:"
        f"query={resolved_query or ''}:category={category_id or ''}:offset={resolved_offset}:limit={limit}"
    )
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    movie_service = MovieService(db)
    movies, total = await movie_service.list_movies(
        query=resolved_query,
        category_id=category_id,
        skip=resolved_offset,
        limit=limit,
    )
    response_payload = MoviePageResponse(
        items=[MovieListResponse.model_validate(movie) for movie in movies],
        total=total,
        offset=resolved_offset,
        limit=limit,
        has_more=resolved_offset + limit < total,
    )
    await set_cache(cache_key, _serialize_cache_payload(response_payload), expire=PUBLIC_MOVIE_LIST_TTL_SECONDS)
    return response_payload


@public_router.get("/popular", response_model=List[MovieListResponse])
async def get_popular_movies(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"{PUBLIC_MOVIE_CACHE_PREFIX}popular:limit={limit}"
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    movie_service = MovieService(db)
    movies = await movie_service.get_popular_movies(limit)
    response_payload = [MovieListResponse.model_validate(movie) for movie in movies]
    await set_cache(cache_key, _serialize_cache_payload(response_payload), expire=PUBLIC_MOVIE_POPULAR_TTL_SECONDS)
    return response_payload


@public_router.get("/new", response_model=List[MovieListResponse])
async def get_new_movies(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"{PUBLIC_MOVIE_CACHE_PREFIX}new:limit={limit}"
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    movie_service = MovieService(db)
    movies = await movie_service.get_new_movies(limit)
    response_payload = [MovieListResponse.model_validate(movie) for movie in movies]
    await set_cache(cache_key, _serialize_cache_payload(response_payload), expire=PUBLIC_MOVIE_NEW_TTL_SECONDS)
    return response_payload


@public_router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(
    movie_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"{PUBLIC_MOVIE_CACHE_PREFIX}detail:{movie_id}"
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    movie_service = MovieService(db)
    movie = await movie_service.get_movie_with_details(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    response_payload = MovieResponse.model_validate(movie)
    await set_cache(cache_key, _serialize_cache_payload(response_payload), expire=PUBLIC_MOVIE_DETAIL_TTL_SECONDS)
    return response_payload


@admin_router.get("/", response_model=MoviePageResponse)
async def admin_get_movies(
    query: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    skip: Optional[int] = Query(None, ge=0, description="Deprecated alias for offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_query = _normalize_query(query, q)
    resolved_offset = _resolve_offset(offset, skip)
    movie_service = MovieService(db)
    movies, total = await movie_service.list_movies(
        query=resolved_query,
        category_id=category_id,
        skip=resolved_offset,
        limit=limit,
    )
    return MoviePageResponse(
        items=[MovieListResponse.model_validate(movie) for movie in movies],
        total=total,
        offset=resolved_offset,
        limit=limit,
        has_more=resolved_offset + limit < total,
    )


@admin_router.get("/{movie_id}", response_model=MovieResponse)
async def admin_get_movie(
    movie_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    movie = await movie_service.get_movie_with_details(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return MovieResponse.model_validate(movie)


@admin_router.post(
    "/",
    response_model=MovieResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_movie(
    movie_data: MovieCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    poster_payload = _poster_payload_from_value(movie_data.poster)
    try:
        movie = await movie_service.create_movie(movie_data, poster_payload=poster_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await _invalidate_public_movie_cache()
    return MovieResponse.model_validate(movie)


@admin_router.patch(
    "/{movie_id}",
    response_model=MovieResponse,
)
async def update_movie(
    movie_id: UUID,
    movie_data: MovieUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    poster_provided = _field_was_provided(movie_data, "poster")
    poster_payload = _poster_payload_from_value(movie_data.poster)
    movie_service = MovieService(db)
    try:
        movie = await movie_service.update_movie(
            movie_id,
            movie_data,
            poster_payload=poster_payload,
            poster_provided=poster_provided,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    await _invalidate_public_movie_cache()
    return MovieResponse.model_validate(movie)


@admin_router.post(
    "/{movie_id}/poster",
    response_model=MovieResponse,
)
async def upload_movie_poster(
    movie_id: UUID,
    poster: UploadFile = File(...),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    poster_payload = await _upload_poster(poster)
    movie_service = MovieService(db)
    movie = await movie_service.update_movie(
        movie_id,
        MovieUpdate(),
        poster_payload=poster_payload,
        poster_provided=True,
    )
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    await _invalidate_public_movie_cache()
    return MovieResponse.model_validate(movie)


@admin_router.post(
    "/{movie_id}/video",
    response_model=MovieResponse,
)
async def upload_movie_video(
    movie_id: UUID,
    video_file: UploadFile = File(...),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if video_file.content_type not in ["video/mp4", "video/x-matroska"]:
        raise HTTPException(status_code=400, detail="Invalid video format. Use video/mp4 or video/x-matroska")
        
    suffix = Path(video_file.filename).suffix or ".mp4"
    video_key = f"movies/{movie_id}/video{suffix}"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await video_file.read())
        temp_path = temp_file.name
        
    try:
        await upload_file(settings.MINIO_BUCKET_NAME, video_key, temp_path, content_type=video_file.content_type)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    movie_service = MovieService(db)
    movie = await movie_service.repository.get_with_details(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    movie = await movie_service.repository.update_movie_with_relations(movie_id, {"video_file_key": video_key})
    
    await _invalidate_public_movie_cache()
    return MovieResponse.model_validate(movie)

@admin_router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
    movie_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    deleted = await movie_service.delete(movie_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Movie not found")

    await _invalidate_public_movie_cache()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
