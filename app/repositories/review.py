from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Event, EventReview, Movie, Review
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession):
        super().__init__(Review, db)

    async def get_with_user(self, review_id: UUID) -> Optional[Review]:
        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user))
            .where(Review.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_by_movie_and_user(self, movie_id: UUID, user_id: UUID) -> Optional[Review]:
        result = await self.db.execute(
            select(Review).where(Review.movie_id == movie_id, Review.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_movie_reviews(self, movie_id: UUID, skip: int = 0, limit: int = 20) -> List[Review]:
        result = await self.db.execute(
            select(Review)
            .options(selectinload(Review.user))
            .where(Review.movie_id == movie_id)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_user_reviews(self, user_id: UUID) -> List[Review]:
        result = await self.db.execute(select(Review).where(Review.user_id == user_id))
        return result.scalars().all()

    async def update_movie_rating(self, movie_id: UUID) -> None:
        result = await self.db.execute(select(func.avg(Review.rating)).where(Review.movie_id == movie_id))
        avg_rating = float(result.scalar_one_or_none() or 0.0)
        await self.db.execute(update(Movie).where(Movie.id == movie_id).values(average_rating=avg_rating))
        await self.db.commit()


class EventReviewRepository(BaseRepository[EventReview]):
    def __init__(self, db: AsyncSession):
        super().__init__(EventReview, db)

    async def get_with_user(self, review_id: UUID) -> Optional[EventReview]:
        result = await self.db.execute(
            select(EventReview)
            .options(selectinload(EventReview.user))
            .where(EventReview.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_by_event_and_user(self, event_id: UUID, user_id: UUID) -> Optional[EventReview]:
        result = await self.db.execute(
            select(EventReview).where(EventReview.event_id == event_id, EventReview.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_event_reviews(self, event_id: UUID, skip: int = 0, limit: int = 20) -> List[EventReview]:
        result = await self.db.execute(
            select(EventReview)
            .options(selectinload(EventReview.user))
            .where(EventReview.event_id == event_id)
            .order_by(EventReview.created_at.desc(), EventReview.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_user_event_reviews(self, user_id: UUID) -> List[EventReview]:
        result = await self.db.execute(select(EventReview).where(EventReview.user_id == user_id))
        return result.scalars().all()

    async def update_event_rating(self, event_id: UUID) -> None:
        result = await self.db.execute(select(func.avg(EventReview.rating)).where(EventReview.event_id == event_id))
        avg_rating = float(result.scalar_one_or_none() or 0.0)
        await self.db.execute(update(Event).where(Event.id == event_id).values(average_rating=avg_rating))
        await self.db.commit()
