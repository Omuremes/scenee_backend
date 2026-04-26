from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import ReviewRepository, EventReviewRepository
from app.services.base import BaseService
from app.schemas import ReviewCreate, ReviewUpdate, EventReviewCreate, EventReviewUpdate


class ReviewService(BaseService[ReviewRepository]):
    def __init__(self, db: AsyncSession):
        repository = ReviewRepository(db)
        super().__init__(repository)

    async def create_review(self, user_id: UUID, review_data: ReviewCreate) -> dict:
        create_data = review_data.model_dump()
        create_data["user_id"] = user_id
        review = await self.repository.create(create_data)

        # Обновляем средний рейтинг фильма
        await self.repository.update_movie_rating(review_data.movie_id)

        return review

    async def update_review(self, review_id: UUID, user_id: UUID, review_data: ReviewUpdate) -> Optional[dict]:
        # Проверяем, что отзыв принадлежит пользователю
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return None

        update_data = review_data.model_dump(exclude_unset=True)
        if not update_data:
            return None

        updated_review = await self.repository.update(review_id, update_data)

        # Обновляем средний рейтинг фильма
        await self.repository.update_movie_rating(review.movie_id)

        return updated_review

    async def delete_review(self, review_id: UUID, user_id: UUID) -> bool:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return False

        deleted = await self.repository.delete(review_id)

        if deleted:
            # Обновляем средний рейтинг фильма
            await self.repository.update_movie_rating(review.movie_id)

        return deleted

    async def get_movie_reviews(self, movie_id: UUID, skip: int = 0, limit: int = 20) -> List[dict]:
        return await self.repository.get_movie_reviews(movie_id, skip, limit)


class EventReviewService(BaseService[EventReviewRepository]):
    def __init__(self, db: AsyncSession):
        repository = EventReviewRepository(db)
        super().__init__(repository)

    async def create_event_review(self, user_id: UUID, review_data: EventReviewCreate) -> dict:
        create_data = review_data.model_dump()
        create_data["user_id"] = user_id
        review = await self.repository.create(create_data)

        # Обновляем средний рейтинг мероприятия
        await self.repository.update_event_rating(review_data.event_id)

        return review

    async def update_event_review(self, review_id: UUID, user_id: UUID, review_data: EventReviewUpdate) -> Optional[dict]:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return None

        update_data = review_data.model_dump(exclude_unset=True)
        if not update_data:
            return None

        updated_review = await self.repository.update(review_id, update_data)

        # Обновляем средний рейтинг мероприятия
        await self.repository.update_event_rating(review.event_id)

        return updated_review

    async def delete_event_review(self, review_id: UUID, user_id: UUID) -> bool:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return False

        deleted = await self.repository.delete(review_id)

        if deleted:
            # Обновляем средний рейтинг мероприятия
            await self.repository.update_event_rating(review.event_id)

        return deleted

    async def get_event_reviews(self, event_id: UUID, skip: int = 0, limit: int = 20) -> List[dict]:
        return await self.repository.get_event_reviews(event_id, skip, limit)