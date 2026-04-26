import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class EventReview(Base):
    __tablename__ = "event_reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1.0 AND rating <= 10.0", name="ck_event_review_rating"),
        UniqueConstraint("event_id", "user_id", name="uq_event_review_event_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Float, nullable=False)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event", back_populates="reviews")
    user = relationship("User", back_populates="event_reviews")
