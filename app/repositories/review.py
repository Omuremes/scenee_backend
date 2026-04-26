from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Review, EventReview
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, db: AsyncSession):
        super().__init__(Review, db)

    async def get_movie_reviews(self, movie_id: UUID, skip: int = 0, limit: int = 20) -> List[Review]:
        result = await self.db.execute(
            select(Review)
            .where(Review.movie_id == movie_id)
            .order_by(Review.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_user_reviews(self, user_id: UUID) -> List[Review]:
        result = await self.db.execute(
            select(Review).where(Review.user_id == user_id)
        )
        return result.scalars().all()

    async def update_movie_rating(self, movie_id: UUID) -> None:
        # Обновляем средний рейтинг фильма
        result = await self.db.execute(
            select(func.avg(Review.rating)).where(Review.movie_id == movie_id)
        )
        avg_rating = result.scalar_one_or_none() or 0.0

        from app.models import Movie
        await self.db.execute(
            select(Movie).where(Movie.id == movie_id).update({"average_rating": avg_rating})
        )
        await self.db.commit()


class EventReviewRepository(BaseRepository[EventReview]):
    def __init__(self, db: AsyncSession):
        super().__init__(EventReview, db)

    async def get_event_reviews(self, event_id: UUID, skip: int = 0, limit: int = 20) -> List[EventReview]:
        result = await self.db.execute(
            select(EventReview)
            .where(EventReview.event_id == event_id)
            .order_by(EventReview.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_user_event_reviews(self, user_id: UUID) -> List[EventReview]:
        result = await self.db.execute(
            select(EventReview).where(EventReview.user_id == user_id)
        )
        return result.scalars().all()

    async def update_event_rating(self, event_id: UUID) -> None:
        # Обновляем средний рейтинг мероприятия
        result = await self.db.execute(
            select(func.avg(EventReview.rating)).where(EventReview.event_id == event_id)
        )
        avg_rating = result.scalar_one_or_none() or 0.0

        from app.models import Event
        await self.db.execute(
            select(Event).where(Event.id == event_id).update({"average_rating": avg_rating})
        )
        await self.db.commit()