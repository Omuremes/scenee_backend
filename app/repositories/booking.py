from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Booking, Event
from app.repositories.base import BaseRepository


class BookingRepository(BaseRepository[Booking]):
    def __init__(self, db: AsyncSession):
        super().__init__(Booking, db)

    async def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
        result = await self.db.execute(
            select(Booking)
            .options(
                selectinload(Booking.event),
                selectinload(Booking.session),
                selectinload(Booking.seat),
            )
            .where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, id: UUID) -> Optional[Booking]:
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.event))
            .where(Booking.id == id)
        )
        return result.scalar_one_or_none()

    async def get_user_bookings(self, user_id: UUID) -> List[Booking]:
        result = await self.db.execute(
            select(Booking)
            .options(
                selectinload(Booking.event).selectinload(Event.venue),
                selectinload(Booking.session),
                selectinload(Booking.seat),
            )
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_reference(self, reference: str) -> Optional[Booking]:
        result = await self.db.execute(
            select(Booking)
            .options(
                selectinload(Booking.event),
                selectinload(Booking.session),
                selectinload(Booking.seat),
            )
            .where(Booking.booking_reference == reference)
        )
        return result.scalar_one_or_none()

    async def get_event_bookings(self, event_id: UUID) -> List[Booking]:
        result = await self.db.execute(
            select(Booking).where(Booking.event_id == event_id)
        )
        return result.scalars().all()

    async def get_by_id(self, booking_id: UUID) -> Optional[Booking]:
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.event))
            .where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()
