from pydantic import Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
from app.schemas.base import BaseSchema


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class BookingBase(BaseSchema):
    event_id: UUID
    seats_count: int = Field(..., ge=1)


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseSchema):
    status: Optional[BookingStatus] = None


class BookingResponse(BookingBase):
    id: UUID
    user_id: UUID
    total_price: float
    status: BookingStatus
    booking_reference: str
    created_at: datetime
    updated_at: Optional[datetime]
