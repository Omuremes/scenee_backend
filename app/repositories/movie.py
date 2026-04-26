from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
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
                selectinload(Movie.reviews),
            )
            .where(Movie.id == movie_id)
        )
        return result.scalar_one_or_none()

    def _apply_filters(
        self,
        stmt,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
    ):
        if category_id:
            stmt = stmt.where(Movie.category_id == category_id)
        if is_series is not None:
            stmt = stmt.where(Movie.is_series == is_series)

        normalized_query = query.strip() if query else None
        if not normalized_query:
            return stmt, None

        stmt = stmt.outerjoin(MovieCategory, Movie.category_id == MovieCategory.id)
        search_document = func.concat_ws(
            " ",
            func.coalesce(Movie.name, ""),
            func.coalesce(Movie.description, ""),
            func.coalesce(MovieCategory.name, ""),
            func.coalesce(MovieCategory.slug, ""),
        )
        search_vector = func.to_tsvector("simple", search_document)
        search_query = func.websearch_to_tsquery("simple", normalized_query)
        rank = func.ts_rank_cd(search_vector, search_query)

        stmt = stmt.where(
            or_(
                search_vector.op("@@")(search_query),
                Movie.name.ilike(f"%{normalized_query}%"),
                Movie.description.ilike(f"%{normalized_query}%"),
                MovieCategory.name.ilike(f"%{normalized_query}%"),
                MovieCategory.slug.ilike(f"%{normalized_query}%"),
            )
        )
        return stmt, rank

    async def search_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Movie]:
        stmt = select(Movie).options(
            selectinload(Movie.category),
            selectinload(Movie.posters),
        )
        stmt, rank = self._apply_filters(stmt, query, category_id, is_series)
        if rank is not None:
            stmt = stmt.order_by(rank.desc(), Movie.average_rating.desc(), Movie.created_at.desc(), Movie.id.desc())
        else:
            stmt = stmt.order_by(Movie.created_at.desc(), Movie.id.desc())

        result = await self.db.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()

    async def count_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
    ) -> int:
        stmt = select(func.count(func.distinct(Movie.id))).select_from(Movie)
        stmt, _ = self._apply_filters(stmt, query, category_id, is_series)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def get_popular_movies(self, limit: int = 10) -> List[Movie]:
        result = await self.db.execute(
            select(Movie)
            .options(selectinload(Movie.category), selectinload(Movie.posters))
            .order_by(Movie.average_rating.desc(), Movie.created_at.desc(), Movie.id.desc())
            .limit(limit)
        )
        return result.scalars().all()


class MovieCategoryRepository(BaseRepository[MovieCategory]):
    def __init__(self, db: AsyncSession):
        super().__init__(MovieCategory, db)

    async def get_by_slug(self, slug: str) -> Optional[MovieCategory]:
        result = await self.db.execute(select(MovieCategory).where(MovieCategory.slug == slug))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[MovieCategory]:
        result = await self.db.execute(select(MovieCategory).where(MovieCategory.name == name))
        return result.scalar_one_or_none()
