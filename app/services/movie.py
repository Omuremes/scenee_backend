import re
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import MovieCategoryRepository, MovieRepository
from app.schemas import MovieCategoryCreate, MovieCreate, MovieUpdate
from app.services.base import BaseService


class MovieService(BaseService[MovieRepository]):
    def __init__(self, db: AsyncSession):
        repository = MovieRepository(db)
        super().__init__(repository)

    async def get_movie_with_details(self, movie_id: UUID) -> Optional[dict]:
        return await self.repository.get_with_details(movie_id)

    async def search_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[dict]:
        return await self.repository.search_movies(query, category_id, is_series, skip, limit)

    async def count_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
    ) -> int:
        return await self.repository.count_movies(query, category_id, is_series)

    async def list_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[dict], int]:
        movies = await self.search_movies(query, category_id, is_series, skip, limit)
        total = await self.count_movies(query, category_id, is_series)
        return movies, total

    async def get_popular_movies(self, limit: int = 10) -> List[dict]:
        return await self.repository.get_popular_movies(limit)

    async def create_movie(self, movie_data: MovieCreate) -> dict:
        await self._validate_category_id(movie_data.category_id)
        movie = await self.repository.create(movie_data.model_dump())
        return await self.repository.get_with_details(movie.id)

    async def update_movie(self, movie_id: UUID, movie_data: MovieUpdate) -> Optional[dict]:
        update_data = movie_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.repository.get_with_details(movie_id)

        if "category_id" in update_data:
            await self._validate_category_id(update_data["category_id"])

        movie = await self.repository.update(movie_id, update_data)
        if not movie:
            return None
        return await self.repository.get_with_details(movie.id)

    async def _validate_category_id(self, category_id: Optional[UUID]) -> None:
        if category_id is None:
            return

        category_repository = MovieCategoryRepository(self.repository.db)
        category = await category_repository.get_by_id(category_id)
        if not category:
            raise ValueError("Movie category not found")


class MovieCategoryService(BaseService[MovieCategoryRepository]):
    def __init__(self, db: AsyncSession):
        repository = MovieCategoryRepository(db)
        super().__init__(repository)

    @staticmethod
    def _normalize_slug(name: str, slug: Optional[str]) -> str:
        source = (slug or name).strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "-", source)
        normalized = normalized.strip("-")
        if not normalized:
            raise ValueError("Category slug cannot be empty")
        return normalized[:100]

    async def create_category(self, category_data: MovieCategoryCreate):
        normalized_name = category_data.name.strip()
        if not normalized_name:
            raise ValueError("Category name is required")

        normalized_slug = self._normalize_slug(normalized_name, category_data.slug)
        existing_name = await self.repository.get_by_name(normalized_name)
        if existing_name:
            raise ValueError("Movie category with this name already exists")

        existing_slug = await self.repository.get_by_slug(normalized_slug)
        if existing_slug:
            raise ValueError("Movie category with this slug already exists")

        return await self.repository.create(
            {
                "name": normalized_name,
                "slug": normalized_slug,
            }
        )
