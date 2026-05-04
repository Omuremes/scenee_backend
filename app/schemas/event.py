from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import Field, root_validator, validator

from app.core.minio import to_public_url
from app.schemas.base import BaseSchema


class EventType(str, Enum):
    CINEMA = "cinema"
    CONCERTS = "concerts"
    SPORTS = "sports"
    STAND_UP = "stand-up"
    KIDS = "kids"
    EVENTS = "events"
    MOVIE_SCREENING = "movie_screening"
    CONCERT = "concert"
    THEATER = "theater"
    STANDUP = "standup"
    SPORT = "sport"


class SessionPricingType(str, Enum):
    FIXED = "fixed"
    PER_SEAT = "per_seat"
    DAILY = "daily"
    EVENING = "evening"
    ALL = "all"


EVENT_TYPE_ALIASES = {
    "movie_screening": EventType.CINEMA.value,
    "concert": EventType.CONCERTS.value,
    "theater": EventType.EVENTS.value,
    "standup": EventType.STAND_UP.value,
    "stand_up": EventType.STAND_UP.value,
    "sport": EventType.SPORTS.value,
}


def normalize_event_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw_value = value.value if isinstance(value, Enum) else value
    normalized = str(raw_value).strip().lower()
    return EVENT_TYPE_ALIASES.get(normalized, normalized)


class VenueBase(BaseSchema):
    name: str = Field(..., max_length=255)
    address: str = Field(..., max_length=500)
    city: str = Field(..., max_length=100)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: Optional[int] = Field(None, ge=0)


class VenueResponse(VenueBase):
    id: UUID


class EventCategoryBase(BaseSchema):
    name: str = Field(..., max_length=100)
    slug: Optional[str] = Field(None, max_length=100)


class EventCategoryCreate(EventCategoryBase):
    pass


class EventCategoryUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = Field(None, max_length=100)


class EventCategoryResponse(BaseSchema):
    id: UUID
    name: str
    slug: str


class EventCategoryPageResponse(BaseSchema):
    items: List[EventCategoryResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class EventSeatBase(BaseSchema):
    label: str = Field(..., min_length=1, max_length=100)
    zone: Optional[str] = Field(None, max_length=100)
    price: float = Field(..., ge=0)
    is_available: bool = True

    @validator("label")
    def normalize_label(cls, value):
        normalized = value.strip()
        if not normalized:
            raise ValueError("Seat label is required")
        return normalized


class EventSeatCreate(EventSeatBase):
    pass


class EventSeatUpdate(BaseSchema):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    zone: Optional[str] = Field(None, max_length=100)
    price: Optional[float] = Field(None, ge=0)
    is_available: Optional[bool] = None

    @validator("label")
    def normalize_label(cls, value):
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Seat label is required")
        return normalized


class EventSeatResponse(EventSeatBase):
    id: UUID
    session_id: UUID
    created_at: datetime
    updated_at: Optional[datetime]


class EventSessionBase(BaseSchema):
    starts_at: datetime
    ends_at: Optional[datetime] = None
    base_price: float = Field(..., ge=0)
    pricing_type: SessionPricingType = SessionPricingType.FIXED
    cinema_name: Optional[str] = Field(None, max_length=255)
    hall_name: Optional[str] = Field(None, max_length=100)

    @root_validator
    def validate_interval(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("Session end time must be after start time")
        return values


class EventSessionCreate(EventSessionBase):
    seats: List[EventSeatCreate] = Field(default_factory=list)


class EventSessionUpdate(BaseSchema):
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    base_price: Optional[float] = Field(None, ge=0)
    pricing_type: Optional[SessionPricingType] = None
    cinema_name: Optional[str] = Field(None, max_length=255)
    hall_name: Optional[str] = Field(None, max_length=100)

    @root_validator
    def validate_interval(cls, values):
        starts_at = values.get("starts_at")
        ends_at = values.get("ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise ValueError("Session end time must be after start time")
        return values


class EventSessionResponse(EventSessionBase):
    id: UUID
    event_id: UUID
    seats: List[EventSeatResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime]


class EventBase(BaseSchema):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    type: Optional[EventType] = None
    event_type: Optional[EventType] = None
    poster_url: Optional[str] = Field(None, max_length=1000)
    image_url: Optional[str] = Field(None, max_length=1000)
    trailer_url: Optional[str] = Field(None, max_length=1000)
    city: Optional[str] = Field(None, max_length=100)
    category_id: Optional[UUID] = None
    is_active: bool = True

    # Legacy single-session fields accepted for older clients/tests.
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    venue_id: Optional[UUID] = None
    price: Optional[float] = Field(None, ge=0)
    max_capacity: Optional[int] = Field(None, ge=0)
    available_seats: Optional[int] = Field(None, ge=0)
    storage_path: Optional[str] = Field(None, max_length=1000)

    @root_validator(pre=True)
    def normalize_legacy_fields(cls, values):
        if not isinstance(values, dict):
            return values
        event_type = values.get("type") or values.get("event_type")
        if event_type is not None:
            normalized_type = normalize_event_type(event_type)
            values["type"] = normalized_type
            values.setdefault("event_type", normalized_type)

        poster_url = values.get("poster_url") or values.get("image_url")
        if poster_url is not None:
            values["poster_url"] = poster_url
            values.setdefault("image_url", poster_url)
        return values

    @validator("type", "event_type", pre=True, allow_reuse=True)
    def normalize_type_value(cls, value):
        return normalize_event_type(value)

    @validator("poster_url", "image_url", pre=True, allow_reuse=True)
    def normalize_image_url(cls, value):
        return to_public_url(value)

    @validator("city")
    def normalize_city(cls, value):
        if value is None:
            return value
        normalized = value.strip()
        return normalized


class EventCreate(EventBase):
    sessions: List[EventSessionCreate] = Field(default_factory=list)

    @root_validator
    def validate_event_create(cls, values):
        if not values.get("type"):
            raise ValueError("Event type is required")
        if not values.get("city"):
            values["city"] = ""
        return values


class EventUpdate(BaseSchema):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    type: Optional[EventType] = None
    event_type: Optional[EventType] = None
    poster_url: Optional[str] = Field(None, max_length=1000)
    image_url: Optional[str] = Field(None, max_length=1000)
    trailer_url: Optional[str] = Field(None, max_length=1000)
    city: Optional[str] = Field(None, max_length=100)
    category_id: Optional[UUID] = None
    is_active: Optional[bool] = None

    # Legacy update fields.
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    venue_id: Optional[UUID] = None
    price: Optional[float] = Field(None, ge=0)
    max_capacity: Optional[int] = Field(None, ge=0)
    available_seats: Optional[int] = Field(None, ge=0)
    storage_path: Optional[str] = Field(None, max_length=1000)

    @root_validator(pre=True)
    def normalize_legacy_fields(cls, values):
        if not isinstance(values, dict):
            return values
        event_type = values.get("type") or values.get("event_type")
        if event_type is not None:
            normalized_type = normalize_event_type(event_type)
            values["type"] = normalized_type
            values.setdefault("event_type", normalized_type)

        poster_url = values.get("poster_url") or values.get("image_url")
        if poster_url is not None:
            values["poster_url"] = poster_url
            values.setdefault("image_url", poster_url)
        return values

    @validator("type", "event_type", pre=True, allow_reuse=True)
    def normalize_type_value(cls, value):
        return normalize_event_type(value)

    @validator("poster_url", "image_url", pre=True, allow_reuse=True)
    def normalize_image_url(cls, value):
        return to_public_url(value)

    @validator("city")
    def normalize_city(cls, value):
        if value is None:
            return value
        normalized = value.strip()
        return normalized


class EventResponse(EventBase):
    id: UUID
    type: EventType = EventType.EVENTS
    event_type: Optional[EventType] = None
    city: str = ""
    average_rating: float
    is_active: bool = True
    category: Optional[EventCategoryResponse] = None
    sessions: List[EventSessionResponse] = Field(default_factory=list)
    venue: Optional[VenueResponse] = None
    created_at: datetime
    updated_at: Optional[datetime]


class EventListResponse(BaseSchema):
    id: UUID
    title: str
    type: EventType = EventType.EVENTS
    event_type: Optional[EventType] = None
    poster_url: Optional[str]
    image_url: Optional[str] = None
    city: str = ""
    category: Optional[EventCategoryResponse] = None
    next_session_at: Optional[datetime] = None
    min_price: Optional[float] = None
    average_rating: float
    is_active: bool = True

    # Legacy response fields for older clients.
    start_datetime: Optional[datetime] = None
    venue: Optional[VenueResponse] = None
    price: Optional[float] = None
    available_seats: Optional[int] = None


class EventPageResponse(BaseSchema):
    items: List[EventListResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class EventReviewsSummaryResponse(BaseSchema):
    average_rating: float
    reviews_count: int
