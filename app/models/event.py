import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EventType(enum.Enum):
    CINEMA = "cinema"
    CONCERTS = "concerts"
    SPORTS = "sports"
    STAND_UP = "stand-up"
    KIDS = "kids"
    EVENTS = "events"


class SessionPricingType(enum.Enum):
    FIXED = "fixed"
    PER_SEAT = "per_seat"
    DAILY = "daily"
    EVENING = "evening"
    ALL = "all"


class EventCategory(Base):
    __tablename__ = "event_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("Event", back_populates="category")


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(50), nullable=False, index=True)
    poster_url = Column(String(1000), nullable=True)
    trailer_url = Column(String(1000), nullable=True)
    city = Column(String(100), nullable=False, index=True)
    category_id = Column(UUID(as_uuid=True), ForeignKey("event_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    average_rating = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Legacy columns kept mapped for compatibility with existing migrations/API clients.
    event_type = Column(String(50), nullable=True)
    start_datetime = Column(DateTime, nullable=True, index=True)
    end_datetime = Column(DateTime, nullable=True)
    venue_id = Column(UUID(as_uuid=True), ForeignKey("venues.id"), nullable=True)
    price = Column(Float, nullable=True)
    max_capacity = Column(Integer, nullable=True)
    available_seats = Column(Integer, nullable=True)
    image_url = Column(String(1000), nullable=True)
    storage_path = Column(String(1000), nullable=True)

    category = relationship("EventCategory", back_populates="events")
    sessions = relationship(
        "EventSession",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventSession.starts_at",
    )
    venue = relationship("Venue", back_populates="events")
    bookings = relationship("Booking", back_populates="event", cascade="all, delete-orphan")
    reviews = relationship("EventReview", back_populates="event", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="event", cascade="all, delete-orphan")


class EventSession(Base):
    __tablename__ = "event_sessions"
    __table_args__ = (
        CheckConstraint("base_price >= 0", name="ck_event_session_base_price"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=True)
    base_price = Column(Float, nullable=False, default=0.0)
    pricing_type = Column(String(20), nullable=False, default=SessionPricingType.FIXED.value)
    cinema_name = Column(String(255), nullable=True)
    hall_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    event = relationship("Event", back_populates="sessions")
    seats = relationship(
        "EventSeat",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="EventSeat.label",
    )
    bookings = relationship("Booking", back_populates="session")


class EventSeat(Base):
    __tablename__ = "event_seats"
    __table_args__ = (
        UniqueConstraint("session_id", "label", name="uq_event_seat_session_label"),
        CheckConstraint("price >= 0", name="ck_event_seat_price"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("event_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(100), nullable=False)
    zone = Column(String(100), nullable=True)
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("EventSession", back_populates="seats")
    bookings = relationship("Booking", back_populates="seat")


class Venue(Base):
    __tablename__ = "venues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    capacity = Column(Integer, nullable=True)

    events = relationship("Event", back_populates="venue", cascade="all, delete-orphan")
