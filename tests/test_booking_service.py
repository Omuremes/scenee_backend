from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.booking import BookingCreate
from app.services.booking import BookingService


class FakeBookingRepository:
    def __init__(self):
        self.created_payload = None

    async def create(self, data):
        self.created_payload = data
        return SimpleNamespace(id=uuid4(), **data)


class FakeEventService:
    def __init__(self, event):
        self.event = event
        self.updated = None

    async def get_event_with_details(self, event_id):
        return self.event if self.event.id == event_id else None

    async def update_available_seats(self, event_id, seats_booked):
        self.updated = (event_id, seats_booked)
        return True


class FakeSeatRepository:
    def __init__(self):
        self.reserved = []

    async def reserve_seat(self, seat_id):
        self.reserved.append(seat_id)
        return SimpleNamespace(id=seat_id, is_available=False)


def build_event(event_type, *, base_price=500.0, seat_price=900.0, seat_available=True, with_seat=True):
    event_id = uuid4()
    session_id = uuid4()
    seat = SimpleNamespace(id=uuid4(), session_id=session_id, price=seat_price, is_available=seat_available)
    session = SimpleNamespace(
        id=session_id,
        starts_at=datetime.utcnow(),
        base_price=base_price,
        seats=[seat] if with_seat else [],
    )
    event = SimpleNamespace(
        id=event_id,
        type=event_type,
        available_seats=3,
        sessions=[session],
    )
    return event, session, seat


@pytest.mark.asyncio
async def test_cinema_booking_reserves_seat_but_uses_ticket_price():
    event, session, seat = build_event("cinema", base_price=450.0, seat_price=1200.0)
    repository = FakeBookingRepository()
    service = object.__new__(BookingService)
    service.repository = repository
    service.event_service = FakeEventService(event)
    service.seat_repository = FakeSeatRepository()

    booking = await service.create_booking(
        uuid4(),
        BookingCreate(event_id=event.id, session_id=session.id, seat_id=seat.id, seats_count=1),
    )

    assert booking.total_price == 450.0
    assert repository.created_payload["seat_id"] == seat.id
    assert service.seat_repository.reserved == [seat.id]


@pytest.mark.asyncio
async def test_standup_booking_uses_selected_seat_price_and_rejects_taken_seat():
    event, session, seat = build_event("stand-up", base_price=700.0, seat_price=1300.0)
    repository = FakeBookingRepository()
    service = object.__new__(BookingService)
    service.repository = repository
    service.event_service = FakeEventService(event)
    service.seat_repository = FakeSeatRepository()

    booking = await service.create_booking(
        uuid4(),
        BookingCreate(event_id=event.id, session_id=session.id, seat_id=seat.id, seats_count=1),
    )

    assert booking.total_price == 1300.0

    seat.is_available = False
    blocked = await service.create_booking(
        uuid4(),
        BookingCreate(event_id=event.id, session_id=session.id, seat_id=seat.id, seats_count=1),
    )

    assert blocked is None


@pytest.mark.asyncio
async def test_kids_booking_sells_ticket_quantity_without_seat():
    event, session, seat = build_event("kids", base_price=300.0, with_seat=False)
    repository = FakeBookingRepository()
    service = object.__new__(BookingService)
    service.repository = repository
    service.event_service = FakeEventService(event)
    service.seat_repository = FakeSeatRepository()

    booking = await service.create_booking(
        uuid4(),
        BookingCreate(event_id=event.id, session_id=session.id, seats_count=2),
    )

    assert booking.total_price == 600.0
    assert repository.created_payload["seat_id"] is None
    assert service.seat_repository.reserved == []

    blocked = await service.create_booking(
        uuid4(),
        BookingCreate(event_id=event.id, session_id=session.id, seat_id=seat.id, seats_count=1),
    )

    assert blocked is None
