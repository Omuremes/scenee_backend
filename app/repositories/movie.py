from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Movie, MovieCategory
from app.repositories.base import BaseRepository


class MovieRepository(BaseRepository[Movie]):
    def __init__(self, db: AsyncSession):
        super().__init__(Movie, db)

    async def get_with_details(self, movie_id: UUID) -> Optional[Movie]:
        result = await self.db.execute(
            select(Movie)
            .options(
                selectinload(Movie.category),
                selectinload(Movie.actors),
                selectinload(Movie.posters),
                selectinload(Movie.episodes),
                selectinload(Movie.reviews)
            )
            .where(Movie.id == movie_id)
        )
        return result.scalar_one_or_none()

    async def search_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[Movie]:
        stmt = select(Movie).options(
            selectinload(Movie.category),
            selectinload(Movie.posters)
        )

        if query:
            stmt = stmt.where(Movie.name.ilike(f"%{query}%"))
        if category_id:
            stmt = stmt.where(Movie.category_id == category_id)
        if is_series is not None:
            stmt = stmt.where(Movie.is_series == is_series)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_popular_movies(self, limit: int = 10) -> List[Movie]:
        result = await self.db.execute(
            select(Movie)
            .options(selectinload(Movie.category), selectinload(Movie.posters))
            .order_by(Movie.average_rating.desc())
            .limit(limit)
        )
        return result.scalars().all()


class MovieCategoryRepository(BaseRepository[MovieCategory]):
    def __init__(self, db: AsyncSession):
        super().__init__(MovieCategory, db)