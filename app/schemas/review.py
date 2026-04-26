from pydantic import Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.base import BaseSchema


class ReviewBase(BaseSchema):
    rating: int = Field(..., ge=1, le=10)
    text: Optional[str] = None


class ReviewCreate(ReviewBase):
    movie_id: UUID


class ReviewUpdate(ReviewBase):
    pass


class ReviewResponse(ReviewBase):
    id: UUID
    movie_id: UUID
    user_id: UUID
    created_at: datetime
