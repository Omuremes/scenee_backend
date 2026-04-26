from datetime import datetime, timedelta
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import case, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Actor, Episode, Movie, MovieCategory, Poster, Review
from app.repositories.base import BaseRepository


class MovieRepository(BaseRepository[Movie]):
    def __init__(self, db: AsyncSession):
        super().__init__(Movie, db)

    @staticmethod
    def _detail_options():
        return (
            selectinload(Movie.category),
            selectinload(Movie.categories),
            selectinload(Movie.actors),
            selectinload(Movie.posters),
            selectinload(Movie.episodes),
            selectinload(Movie.reviews),
        )

    async def get_with_details(self, movie_id: UUID) -> Optional[Movie]:
        result = await self.db.execute(
            select(Movie)
            .options(*self._detail_options())
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
            stmt = stmt.where(
                or_(
                    Movie.category_id == category_id,
                    Movie.categories.any(MovieCategory.id == category_id),
                )
            )

        if is_series is not None:
            stmt = stmt.where(Movie.is_series == is_series)

        normalized_query = query.strip() if query else None
        if not normalized_query:
            return stmt

        ilike_query = f"%{normalized_query}%"
        return stmt.where(
            or_(
                Movie.name.ilike(ilike_query),
                Movie.description.ilike(ilike_query),
                Movie.category.has(
                    or_(
                        MovieCategory.name.ilike(ilike_query),
                        MovieCategory.slug.ilike(ilike_query),
                    )
                ),
                Movie.categories.any(
                    or_(
                        MovieCategory.name.ilike(ilike_query),
                        MovieCategory.slug.ilike(ilike_query),
                    )
                ),
            )
        )

    async def search_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Movie]:
        stmt = (
            select(Movie)
            .options(
                selectinload(Movie.category),
                selectinload(Movie.categories),
                selectinload(Movie.posters),
            )
            .order_by(Movie.created_at.desc(), Movie.average_rating.desc(), Movie.id.desc())
        )
        stmt = self._apply_filters(stmt, query, category_id, is_series)
        result = await self.db.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()

    async def count_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
    ) -> int:
        stmt = select(func.count(Movie.id))
        stmt = self._apply_filters(stmt, query, category_id, is_series)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def _review_count_subquery(self):
        return (
            select(Review.movie_id.label("movie_id"), func.count(Review.id).label("review_count"))
            .group_by(Review.movie_id)
            .subquery()
        )

    async def get_popular_movies(self, limit: int = 10) -> List[Movie]:
        review_counts = await self._review_count_subquery()
        result = await self.db.execute(
            select(Movie)
            .outerjoin(review_counts, review_counts.c.movie_id == Movie.id)
            .options(selectinload(Movie.category), selectinload(Movie.categories), selectinload(Movie.posters))
            .order_by(
                Movie.average_rating.desc(),
                desc(func.coalesce(review_counts.c.review_count, 0)),
                Movie.created_at.desc(),
                Movie.id.desc(),
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def get_new_movies(self, limit: int = 10) -> List[Movie]:
        review_counts = await self._review_count_subquery()
        now = datetime.utcnow()
        freshness_rank = case(
            (Movie.created_at >= now - timedelta(days=7), 3),
            (Movie.created_at >= now - timedelta(days=30), 2),
            else_=1,
        )
        result = await self.db.execute(
            select(Movie)
            .outerjoin(review_counts, review_counts.c.movie_id == Movie.id)
            .options(selectinload(Movie.category), selectinload(Movie.categories), selectinload(Movie.posters))
            .order_by(
                freshness_rank.desc(),
                Movie.created_at.desc(),
                Movie.average_rating.desc(),
                desc(func.coalesce(review_counts.c.review_count, 0)),
                Movie.id.desc(),
            )
            .limit(limit)
        )
        return result.scalars().all()

    async def get_season_episodes(self, movie_id: UUID, season_number: int) -> List[Episode]:
        result = await self.db.execute(
            select(Episode)
            .where(Episode.movie_id == movie_id, Episode.season_number == season_number)
            .order_by(Episode.episode_number.asc(), Episode.id.asc())
        )
        return result.scalars().all()

    async def create_movie(
        self,
        movie_data: dict,
        *,
        actors: Iterable[Actor],
        categories: Iterable[MovieCategory],
        episodes: Iterable[dict],
        poster_payload: Optional[dict] = None,
    ) -> Movie:
        movie = Movie(**movie_data)
        movie.actors = list(actors)
        movie.categories = list(categories)
        movie.category_id = movie.categories[0].id if movie.categories else None
        movie.episodes = [Episode(**episode_data) for episode_data in episodes]
        if poster_payload:
            movie.posters = [Poster(**poster_payload)]

        self.db.add(movie)
        await self.db.commit()
        await self.db.refresh(movie)
        return movie

    async def update_movie_with_relations(
        self,
        movie_id: UUID,
        movie_data: dict,
        *,
        actors: Optional[Iterable[Actor]] = None,
        categories: Optional[Iterable[MovieCategory]] = None,
        episodes: Optional[Iterable[dict]] = None,
        poster_payload: Optional[dict] = None,
        poster_provided: bool = False,
    ) -> Optional[Movie]:
        movie = await self.get_with_details(movie_id)
        if not movie:
            return None

        for key, value in movie_data.items():
            setattr(movie, key, value)

        if actors is not None:
            movie.actors = list(actors)

        if categories is not None:
            movie.categories = list(categories)
            movie.category_id = movie.categories[0].id if movie.categories else None

        if episodes is not None:
            movie.episodes = [Episode(**episode_data) for episode_data in episodes]

        if poster_provided:
            movie.posters = [Poster(**poster_payload)] if poster_payload else []

        await self.db.commit()
        await self.db.refresh(movie)
        return movie


class MovieCategoryRepository(BaseRepository[MovieCategory]):
    def __init__(self, db: AsyncSession):
        super().__init__(MovieCategory, db)

    def _apply_query(self, stmt, query: Optional[str]):
        normalized_query = query.strip() if query else None
        if not normalized_query:
            return stmt

        search_document = func.concat_ws(
            " ",
            func.coalesce(MovieCategory.name, ""),
            func.coalesce(MovieCategory.slug, ""),
        )
        search_vector = func.to_tsvector("simple", search_document)
        search_query = func.websearch_to_tsquery("simple", normalized_query)
        ilike_query = f"%{normalized_query}%"

        return stmt.where(
            or_(
                search_vector.op("@@")(search_query),
                MovieCategory.name.ilike(ilike_query),
                MovieCategory.slug.ilike(ilike_query),
            )
        )

    async def get_by_slug(self, slug: str) -> Optional[MovieCategory]:
        result = await self.db.execute(select(MovieCategory).where(MovieCategory.slug == slug))
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[MovieCategory]:
        result = await self.db.execute(select(MovieCategory).where(MovieCategory.name == name))
        return result.scalar_one_or_none()

    async def get_by_ids(self, category_ids: Iterable[UUID]) -> List[MovieCategory]:
        category_ids = list(category_ids)
        if not category_ids:
            return []
        result = await self.db.execute(select(MovieCategory).where(MovieCategory.id.in_(category_ids)))
        return result.scalars().all()

    async def list_categories(
        self,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[MovieCategory]:
        stmt = select(MovieCategory).order_by(MovieCategory.name.asc(), MovieCategory.id.asc())
        stmt = self._apply_query(stmt, query)
        result = await self.db.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()

    async def count_categories(self, query: Optional[str] = None) -> int:
        stmt = select(func.count(MovieCategory.id))
        stmt = self._apply_query(stmt, query)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def touch_primary_category(self, movie_id: UUID, category_id: Optional[UUID]) -> None:
        await self.db.execute(update(Movie).where(Movie.id == movie_id).values(category_id=category_id))
        await self.db.commit()
