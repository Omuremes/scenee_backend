from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.serial import Serial
from app.repositories.serial import SerialRepository
from app.repositories.serial_review import SerialReviewRepository
from app.schemas.serial_review import SerialReviewCreate, SerialReviewUpdate
from app.services.base import BaseService


def _normalize_review_payload(payload: dict) -> dict:
    if "text" in payload and payload["text"] is not None:
        normalized_text = payload["text"].strip()
        payload["text"] = normalized_text or None
    return payload


class SerialReviewService(BaseService[SerialReviewRepository]):
    def __init__(self, db: AsyncSession):
        repository = SerialReviewRepository(db)
        super().__init__(repository)
        self.serial_repository = SerialRepository(db)

    async def create_or_update_serial_review(self, user_id: UUID, review_data: SerialReviewCreate):
        serial = await self.serial_repository.get_by_id(review_data.serial_id)
        if not serial:
            raise ValueError("Serial not found")

        payload = _normalize_review_payload(review_data.model_dump())
        existing = await self.repository.get_by_serial_and_user(review_data.serial_id, user_id)
        if existing:
            await self.repository.update(existing.id, {"rating": payload["rating"], "text": payload.get("text")})
            review = await self.repository.get_with_user(existing.id)
        else:
            payload["user_id"] = user_id
            review = await self.repository.create(payload)
            review = await self.repository.get_with_user(review.id)

        await self.repository.update_serial_rating(review_data.serial_id)
        return review

    async def update_serial_review(self, review_id: UUID, user_id: UUID, review_data: SerialReviewUpdate):
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return None

        payload = _normalize_review_payload(review_data.model_dump(exclude_unset=True))
        if not payload:
            return await self.repository.get_with_user(review_id)

        updated = await self.repository.update(review_id, payload)
        if not updated:
            return None

        await self.repository.update_serial_rating(updated.serial_id)
        return await self.repository.get_with_user(review_id)

    async def delete_serial_review(self, review_id: UUID, user_id: UUID) -> bool:
        review = await self.repository.get_by_id(review_id)
        if not review or review.user_id != user_id:
            return False

        serial_id = review.serial_id
        success = await self.repository.delete(review_id)
        if success:
            await self.repository.update_serial_rating(serial_id)
        return success

    async def get_serial_reviews(self, serial_id: UUID, skip: int = 0, limit: int = 20) -> List[dict]:
        serial = await self.serial_repository.get_by_id(serial_id)
        if not serial:
            raise ValueError("Serial not found")
        return await self.repository.get_serial_reviews(serial_id, skip, limit)