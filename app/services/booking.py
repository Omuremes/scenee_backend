import secrets
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import BookingRepository
from app.services.base import BaseService
from app.services.event import EventService
from app.schemas import BookingCreate, BookingUpdate, BookingStatus


class BookingService(BaseService[BookingRepository]):
    def __init__(self, db: AsyncSession):
        repository = BookingRepository(db)
        self.event_service = EventService(db)
        super().__init__(repository)

    async def create_booking(self, user_id: UUID, booking_data: BookingCreate) -> Optional[dict]:
        event = await self.event_service.get_by_id(booking_data.event_id)
        if not event:
            return None

        # Проверяем доступность мест
        if event.available_seats < booking_data.seats_count:
            return None

        # Создаем бронирование
        create_data = booking_data.model_dump()
        create_data["user_id"] = user_id
        create_data["total_price"] = event.price * booking_data.seats_count
        create_data["booking_reference"] = self._generate_reference()

        booking = await self.repository.create(create_data)

        # Обновляем доступные места
        await self.event_service.update_available_seats(booking_data.event_id, booking_data.seats_count)

        return booking

    async def get_user_bookings(self, user_id: UUID) -> List[dict]:
        return await self.repository.get_user_bookings(user_id)

    async def get_booking_by_reference(self, reference: str) -> Optional[dict]:
        return await self.repository.get_by_reference(reference)

    async def update_booking_status(self, booking_id: UUID, status: BookingStatus) -> Optional[dict]:
        return await self.repository.update(booking_id, {"status": status})

    async def cancel_booking(self, booking_id: UUID, user_id: UUID) -> bool:
        booking = await self.repository.get_by_id(booking_id)
        if not booking or booking.user_id != user_id or booking.status == BookingStatus.CANCELLED:
            return False

        # Возвращаем места
        await self.event_service.update_available_seats(booking.event_id, -booking.seats_count)

        # Отменяем бронирование
        await self.repository.update(booking_id, {"status": BookingStatus.CANCELLED})
        return True

    def _generate_reference(self) -> str:
        """Генерируем уникальный код бронирования"""
        return secrets.token_hex(8).upper()