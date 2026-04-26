from pydantic import Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from enum import Enum
from app.schemas.base import BaseSchema


class EventType(str, Enum):
    MOVIE_SCREENING = "movie_screening"
    CONCERT = "concert"
    THEATER = "theater"
    STANDUP = "standup"
    SPORT = "sport"


class VenueBase(BaseSchema):
    name: str = Field(..., max_length=255)
    address: str = Field(..., max_length=500)
    city: str = Field(..., max_length=100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = Field(None, ge=0)


class VenueResponse(VenueBase):
    id: UUID


class EventBase(BaseSchema):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    event_type: EventType
    start_datetime: datetime
    end_datetime: Optional[datetime] = None
    venue_id: UUID
    price: float = Field(..., ge=0)
    max_capacity: int = Field(..., ge=0)
    image_url: Optional[str] = Field(None, max_length=1000)
    storage_path: Optional[str] = Field(None, max_length=1000)


class EventCreate(EventBase):
    pass


class EventUpdate(BaseSchema):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    event_type: Optional[EventType] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    venue_id: Optional[UUID] = None
    price: Optional[float] = Field(None, ge=0)
    max_capacity: Optional[int] = Field(None, ge=0)
    image_url: Optional[str] = Field(None, max_length=1000)
    storage_path: Optional[str] = Field(None, max_length=1000)


class EventResponse(EventBase):
    id: UUID
    available_seats: int
    average_rating: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]
    venue: VenueResponse


class EventListResponse(BaseSchema):
    id: UUID
    title: str
    event_type: EventType
    start_datetime: datetime
    venue: VenueResponse
    price: float
    available_seats: int
    average_rating: float
    image_url: Optional[str]


class EventPageResponse(BaseSchema):
    items: list[EventListResponse]
    total: int
    offset: int
    limit: int
    has_more: bool
