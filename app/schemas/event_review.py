from pydantic import Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.base import BaseSchema


class EventReviewBase(BaseSchema):
    rating: int = Field(..., ge=1, le=10)
    text: Optional[str] = None


class EventReviewCreate(EventReviewBase):
    event_id: UUID


class EventReviewUpdate(EventReviewBase):
    pass


class EventReviewResponse(EventReviewBase):
    id: UUID
    event_id: UUID
    user_id: UUID
    created_at: datetime
