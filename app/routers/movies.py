import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import delete_cache_by_prefix, get_cache, set_cache
from app.core.config import settings
from app.core.database import get_db
from app.core.minio import upload_file
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import (
    EpisodeResponse,
    MovieCategoryCreate,
    MovieCategoryResponse,
    MovieCreate,
    MovieListResponse,
    MoviePageResponse,
    MovieResponse,
    MovieUpdate,
)
from app.services import MovieCategoryService, MovieService

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


def _parse_json_list(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if not normalized:
            return []
        return json.loads(normalized)
    return raw_value


def _ensure_movie_validation_error(exc: ValidationError):
    raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors()))


async def _upload_poster(poster_file: UploadFile) -> dict:
    suffix = Path(poster_file.filename or "poster").suffix or ".bin"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await poster_file.read())
            temp_path = temp_file.name

        object_name = f"movies/{uuid4()}{suffix}"
        poster_url = await upload_file(
            settings.MINIO_BUCKET_NAME,
            object_name,
            temp_path,
            content_type=poster_file.content_type or "application/octet-stream",
        )
        return {
            "url": poster_url,
            "storage_path": object_name,
            "is_primary": True,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _poster_from_url(url: str) -> dict:
    normalized_url = url.strip()
    if not normalized_url:
        raise HTTPException(status_code=400, detail="Poster URL cannot be empty")
    return {"url": normalized_url, "storage_path": None, "is_primary": True}


async def _parse_movie_request(request: Request, partial: bool = False) -> Tuple[MovieCreate | MovieUpdate, Optional[dict], bool]:
    content_type = request.headers.get("content-type", "")
    schema_class = MovieUpdate if partial else MovieCreate
    poster_payload = None
    poster_provided = False

    if "application/json" in content_type:
        try:
            payload = await request.json()
            movie_payload = schema_class.model_validate(payload)
        except ValidationError as exc:
            _ensure_movie_validation_error(exc)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON payload: {exc}") from exc
        poster_url = payload.get("poster")
        if poster_url is not None:
            poster_payload = _poster_from_url(poster_url)
            poster_provided = True
        return movie_payload, poster_payload, poster_provided

    if "multipart/form-data" in content_type:
        form = await request.form()
        raw_payload = {}

        for field in ("name", "description", "is_series", "duration", "seasons_count"):
            if field in form:
                raw_payload[field] = form.get(field)

        if "actors" in form:
            raw_payload["actors"] = form.getlist("actors")
        elif not partial:
            raw_payload["actors"] = []

        if "categories" in form:
            raw_payload["categories"] = form.getlist("categories")
        elif not partial:
            raw_payload["categories"] = []

        if "episodes" in form:
            raw_payload["episodes"] = _parse_json_list(form.get("episodes"))
        elif not partial:
            raw_payload["episodes"] = []

        poster_values = form.getlist("poster")
        poster_file = next(
            (
                value
                for value in poster_values
                if hasattr(value, "filename") and hasattr(value, "read") and getattr(value, "filename", None)
            ),
            None,
        )
        poster_text = next((value for value in poster_values if isinstance(value, str) and value.strip()), None)

        if poster_file is not None:
            poster_payload = await _upload_poster(poster_file)
            poster_provided = True
        elif poster_text is not None:
            raw_payload["poster"] = poster_text
            poster_payload = _poster_from_url(poster_text)
            poster_provided = True

        try:
            movie_payload = schema_class.model_validate(raw_payload)
        except ValidationError as exc:
            _ensure_movie_validation_error(exc)

        return movie_payload, poster_payload, poster_provided

    raise HTTPException(
        status_code=415,
        detail="Supported content types are application/json and multipart/form-data",
    )


@public_router.get("/", response_model=MoviePageResponse)
async def get_movies(
    query: Optional[str] = Query(None, description="Search query"),
    q: Optional[str] = Query(None, description="Alias for search query"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    is_series: Optional[bool] = Query(None, description="Filter by series/movies"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    skip: Optional[int] = Query(None, ge=0, description="Deprecated alias for offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    resolved_query = _normalize_query(query, q)
    resolved_offset = _resolve_offset(offset, skip)
    cache_key = (
        f"{PUBLIC_MOVIE_CACHE_PREFIX}list:"
        f"query={resolved_query or ''}:category={category_id or ''}:"
        f"is_series={is_series}:offset={resolved_offset}:limit={limit}"
    )
    cached_payload = await get_cache(cache_key)
    if cached_payload:
        return json.loads(cached_payload)

    movie_service = MovieService(db)
    movies, total = await movie_service.list_movies(
        query=resolved_query,
        category_id=category_id,
        is_series=is_series,
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


@public_router.get("/{movie_id}/seasons/{season_number}/episodes", response_model=List[EpisodeResponse])
async def get_movie_season_episodes(
    movie_id: UUID,
    season_number: int,
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    episodes = await movie_service.get_season_episodes(movie_id, season_number)
    if episodes is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return [EpisodeResponse.model_validate(episode) for episode in episodes]


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
    is_series: Optional[bool] = Query(None, description="Filter by series/movies"),
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
        is_series=is_series,
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


@admin_router.post("/categories", response_model=MovieCategoryResponse, status_code=status.HTTP_201_CREATED)
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

    await _invalidate_public_movie_cache()
    return MovieCategoryResponse.model_validate(category)


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


@admin_router.post("/", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
async def create_movie(
    request: Request,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_data, poster_payload, _poster_provided = await _parse_movie_request(request, partial=False)
    movie_service = MovieService(db)
    try:
        movie = await movie_service.create_movie(movie_data, poster_payload=poster_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await _invalidate_public_movie_cache()
    return MovieResponse.model_validate(movie)


@admin_router.patch("/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: UUID,
    request: Request,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_data, poster_payload, poster_provided = await _parse_movie_request(request, partial=True)
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
