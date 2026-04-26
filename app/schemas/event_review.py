from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.review import ReviewUserResponse


class EventReviewBase(BaseSchema):
    rating: float = Field(..., ge=1.0, le=10.0)
    text: Optional[str] = None


class EventReviewCreate(EventReviewBase):
    event_id: UUID


class EventReviewUpdate(BaseSchema):
    rating: Optional[float] = Field(None, ge=1.0, le=10.0)
    text: Optional[str] = None


class EventReviewResponse(EventReviewBase):
    id: UUID
    event_id: UUID
    user_id: UUID
    created_at: datetime
    user: ReviewUserResponse
