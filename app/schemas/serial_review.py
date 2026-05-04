from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.review import ReviewUserResponse


class SerialReviewBase(BaseSchema):
    rating: float = Field(..., ge=1.0, le=5.0)
    text: Optional[str] = None


class SerialReviewCreate(SerialReviewBase):
    serial_id: UUID


class SerialReviewUpdate(BaseSchema):
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    text: Optional[str] = None


class SerialReviewResponse(SerialReviewBase):
    id: UUID
    serial_id: UUID
    user_id: UUID
    created_at: datetime
    user: ReviewUserResponse