from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import MovieRepository, MovieCategoryRepository
from app.services.base import BaseService
from app.schemas import MovieCreate, MovieUpdate


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
        limit: int = 20
    ) -> List[dict]:
        return await self.repository.search_movies(query, category_id, is_series, skip, limit)

    async def get_popular_movies(self, limit: int = 10) -> List[dict]:
        return await self.repository.get_popular_movies(limit)

    async def create_movie(self, movie_data: MovieCreate) -> dict:
        return await self.repository.create(movie_data.model_dump())

    async def update_movie(self, movie_id: UUID, movie_data: MovieUpdate) -> Optional[dict]:
        update_data = movie_data.model_dump(exclude_unset=True)
        if not update_data:
            return None
        return await self.repository.update(movie_id, update_data)


class MovieCategoryService(BaseService[MovieCategoryRepository]):
    def __init__(self, db: AsyncSession):
        repository = MovieCategoryRepository(db)
        super().__init__(repository)