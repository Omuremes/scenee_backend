from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.models.booking import BookingStatus as ModelBookingStatus
from app.schemas.booking import BookingResponse, BookingStatus as SchemaBookingStatus


def test_booking_response_accepts_model_status_enum():
    booking = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        event_id=uuid4(),
        session_id=None,
        seat_id=None,
        seats_count=2,
        total_price=500.0,
        status=ModelBookingStatus.CONFIRMED,
        booking_reference="ABC12345",
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    response = BookingResponse.model_validate(booking)

    assert ModelBookingStatus is SchemaBookingStatus
    assert response.status == SchemaBookingStatus.CONFIRMED
