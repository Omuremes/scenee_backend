import secrets
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import BookingRepository, EventSeatRepository
from app.schemas import BookingCreate, BookingStatus
from app.services.base import BaseService
from app.services.event import EventService, PER_SEAT_EVENT_TYPES, SEATED_EVENT_TYPES


class BookingService(BaseService[BookingRepository]):
    def __init__(self, db: AsyncSession):
        repository = BookingRepository(db)
        self.event_service = EventService(db)
        self.seat_repository = EventSeatRepository(db)
        super().__init__(repository)

    async def create_booking(self, user_id: UUID, booking_data: BookingCreate) -> Optional[dict]:
        event = await self.event_service.get_event_with_details(booking_data.event_id)
        if not event:
            return None

        session = self._resolve_session(event, booking_data.session_id)
        if not session:
            return None

        seat = self._resolve_seat(session, booking_data.seat_id)
        requires_seat = event.type in SEATED_EVENT_TYPES and bool(session.seats)
        if requires_seat and (not seat or booking_data.seats_count != 1):
            return None
        if not requires_seat and booking_data.seat_id:
            return None
        if seat and not seat.is_available:
            return None
        if (event.available_seats or 0) < booking_data.seats_count:
            return None

        total_price = self._calculate_total_price(event.type, session, seat, booking_data.seats_count)
        if total_price is None:
            return None

        if seat and not await self.seat_repository.reserve_seat(seat.id):
            return None

        create_data = booking_data.model_dump()
        create_data["user_id"] = user_id
        create_data["session_id"] = session.id
        create_data["seat_id"] = seat.id if seat else None
        create_data["total_price"] = total_price
        create_data["booking_reference"] = self._generate_reference()

        booking = await self.repository.create(create_data)
        await self.event_service.update_available_seats(event.id, booking_data.seats_count)
        booking.event = event
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

        if booking.seat_id:
            await self.seat_repository.release_seat(booking.seat_id)
        await self.event_service.update_available_seats(booking.event_id, -booking.seats_count)
        await self.repository.update(booking_id, {"status": BookingStatus.CANCELLED})
        return True

    @staticmethod
    def _resolve_session(event, session_id: Optional[UUID]):
        sessions = sorted(getattr(event, "sessions", []) or [], key=lambda item: item.starts_at)
        if session_id:
            return next((session for session in sessions if session.id == session_id), None)
        return sessions[0] if sessions else None

    @staticmethod
    def _resolve_seat(session, seat_id: Optional[UUID]):
        if not seat_id:
            return None
        return next((seat for seat in (session.seats or []) if seat.id == seat_id), None)

    @staticmethod
    def _calculate_total_price(event_type: str, session, seat, seats_count: int) -> Optional[float]:
        if event_type in PER_SEAT_EVENT_TYPES:
            return seat.price if seat else None
        return session.base_price * seats_count

    def _generate_reference(self) -> str:
        return secrets.token_hex(8).upper()
