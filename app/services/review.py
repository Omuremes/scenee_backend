from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import EventRepository, EventReviewRepository, MovieRepository, ReviewRepository
from app.schemas import EventReviewCreate, EventReviewUpdate, ReviewCreate, ReviewUpdate
from app.services.base import BaseService


def _normalize_review_payload(payload: dict) -> dict:
    if "text" in payload and payload["text"] is not None:
        normalized_text = payload["text"].strip()
        payload["text"] = normalized_text or None
    return payload


class ReviewService(BaseService[ReviewRepository]):
    def __init__(self, db: AsyncSession):
        repository = ReviewRepository(db)
        super().__init__(repository)
        self.movie_repository = MovieRepository(db)

    async def create_review(self, user_id: UUID, review_data: ReviewCreate):
        if not await self.movie_repository.exists(review_data.movie_id):
            raise ValueError("Movie not found")

        if await self.repository.get_by_movie_and_user(review_data.movie_id, user_id):
            raise ValueError("User has already reviewed this movie")

        create_data = _normalize_review_payload(review_data.model_dump())
        create_data["user_id"] = user_id
        review = await self.repository.create(create_data)
        await self.repository.update_movie_rating(review_data.movie_id)
        return await self.repository.get_with_user(review.id)

    async def update_review(self, review_id: UUID, user_id: UUID, review_data: ReviewUpdate):
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return None

        update_data = _normalize_review_payload(review_data.model_dump(exclude_unset=True))
        if not update_data:
            return await self.repository.get_with_user(review_id)

        await self.repository.update(review_id, update_data)
        await self.repository.update_movie_rating(review.movie_id)
        return await self.repository.get_with_user(review_id)

    async def delete_review(self, review_id: UUID, user_id: UUID) -> bool:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return False

        deleted = await self.repository.delete(review_id)
        if deleted:
            await self.repository.update_movie_rating(review.movie_id)
        return deleted

    async def get_movie_reviews(self, movie_id: UUID, skip: int = 0, limit: int = 20) -> List[dict]:
        return await self.repository.get_movie_reviews(movie_id, skip, limit)


class EventReviewService(BaseService[EventReviewRepository]):
    def __init__(self, db: AsyncSession):
        repository = EventReviewRepository(db)
        super().__init__(repository)
        self.event_repository = EventRepository(db)

    async def create_event_review(self, user_id: UUID, review_data: EventReviewCreate):
        if not await self.event_repository.exists(review_data.event_id):
            raise ValueError("Event not found")

        if await self.repository.get_by_event_and_user(review_data.event_id, user_id):
            raise ValueError("User has already reviewed this event")

        create_data = _normalize_review_payload(review_data.model_dump())
        create_data["user_id"] = user_id
        review = await self.repository.create(create_data)
        await self.repository.update_event_rating(review_data.event_id)
        return await self.repository.get_with_user(review.id)

    async def update_event_review(self, review_id: UUID, user_id: UUID, review_data: EventReviewUpdate) -> Optional[dict]:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return None

        update_data = _normalize_review_payload(review_data.model_dump(exclude_unset=True))
        if not update_data:
            return await self.repository.get_with_user(review_id)

        await self.repository.update(review_id, update_data)
        await self.repository.update_event_rating(review.event_id)
        return await self.repository.get_with_user(review_id)

    async def delete_event_review(self, review_id: UUID, user_id: UUID) -> bool:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return False

        deleted = await self.repository.delete(review_id)
        if deleted:
            await self.repository.update_event_rating(review.event_id)
        return deleted

    async def get_event_reviews(self, event_id: UUID, skip: int = 0, limit: int = 20) -> List[dict]:
        return await self.repository.get_event_reviews(event_id, skip, limit)
