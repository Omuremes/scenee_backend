import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class EventType(enum.Enum):
    MOVIE_SCREENING = "movie_screening"
    CONCERT = "concert"
    THEATER = "theater"
    STANDUP = "standup"
    SPORT = "sport"


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    event_type = Column(Enum(EventType), nullable=False)
    start_datetime = Column(DateTime, nullable=False, index=True)
    end_datetime = Column(DateTime, nullable=True)
    venue_id = Column(UUID(as_uuid=True), ForeignKey("venues.id"), nullable=False)
    price = Column(Float, nullable=False)  # базовая цена билета
    max_capacity = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    image_url = Column(String(1000), nullable=True)  # URL из MinIO
    storage_path = Column(String(1000), nullable=True)  # путь в MinIO
    average_rating = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    venue = relationship("Venue", back_populates="events")
    bookings = relationship("Booking", back_populates="event", cascade="all, delete-orphan")
    reviews = relationship("EventReview", back_populates="event", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="event", cascade="all, delete-orphan")


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