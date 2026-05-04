from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.serial import Serial, SerialReview
from app.repositories.base import BaseRepository


class SerialReviewRepository(BaseRepository[SerialReview]):
    def __init__(self, db: AsyncSession):
        super().__init__(SerialReview, db)

    async def get_with_user(self, review_id: UUID) -> Optional[SerialReview]:
        result = await self.db.execute(
            select(SerialReview)
            .options(selectinload(SerialReview.user))
            .where(SerialReview.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_by_serial_and_user(self, serial_id: UUID, user_id: UUID) -> Optional[SerialReview]:
        result = await self.db.execute(
            select(SerialReview).where(SerialReview.serial_id == serial_id, SerialReview.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_user(self, review_id: UUID) -> Optional[SerialReview]:
        result = await self.db.execute(
            select(SerialReview)
            .options(selectinload(SerialReview.user))
            .where(SerialReview.id == review_id)
        )
        return result.scalar_one_or_none()

    async def get_serial_reviews(self, serial_id: UUID, skip: int = 0, limit: int = 20) -> List[SerialReview]:
        result = await self.db.execute(
            select(SerialReview)
            .options(selectinload(SerialReview.user))
            .where(SerialReview.serial_id == serial_id)
            .order_by(SerialReview.created_at.desc(), SerialReview.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def update_serial_rating(self, serial_id: UUID) -> None:
        result = await self.db.execute(select(func.avg(SerialReview.rating)).where(SerialReview.serial_id == serial_id))
        avg_rating = float(result.scalar_one_or_none() or 0.0)
        await self.db.execute(update(Serial).where(Serial.id == serial_id).values(average_rating=avg_rating))
        await self.db.commit()
