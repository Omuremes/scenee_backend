from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import MovieCreate, MovieListResponse, MovieResponse, MovieUpdate
from app.services import MovieService

public_router = APIRouter(prefix="/public/movies", tags=["movies"])
admin_router = APIRouter(prefix="/v1admin/movies", tags=["admin-movies"])


@public_router.get("/", response_model=List[MovieListResponse])
async def get_movies(
    query: Optional[str] = Query(None, description="Search query"),
    category_id: Optional[UUID] = Query(None, description="Filter by category"),
    is_series: Optional[bool] = Query(None, description="Filter by series/movies"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    movies = await movie_service.search_movies(query, category_id, is_series, skip, limit)
    return [MovieListResponse.model_validate(movie) for movie in movies]


@public_router.get("/popular", response_model=List[MovieListResponse])
async def get_popular_movies(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    movies = await movie_service.get_popular_movies(limit)
    return [MovieListResponse.model_validate(movie) for movie in movies]


@public_router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(
    movie_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    movie = await movie_service.get_movie_with_details(movie_id)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return MovieResponse.model_validate(movie)


@admin_router.post("/", response_model=MovieResponse)
async def create_movie(
    movie_data: MovieCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    movie = await movie_service.create_movie(movie_data)
    return MovieResponse.model_validate(movie)


@admin_router.put("/{movie_id}", response_model=MovieResponse)
async def update_movie(
    movie_id: UUID,
    movie_data: MovieUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    movie_service = MovieService(db)
    movie = await movie_service.update_movie(movie_id, movie_data)
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return MovieResponse.model_validate(movie)
