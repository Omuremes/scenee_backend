from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema


class ReviewUserResponse(BaseSchema):
    id: UUID
    username: Optional[str] = None
    avatar_url: Optional[str] = None


class ReviewBase(BaseSchema):
    rating: float = Field(..., ge=1.0, le=10.0)
    text: Optional[str] = None


class ReviewCreate(ReviewBase):
    movie_id: UUID


class ReviewUpdate(BaseSchema):
    rating: Optional[float] = Field(None, ge=1.0, le=10.0)
    text: Optional[str] = None


class ReviewResponse(ReviewBase):
    id: UUID
    movie_id: UUID
    user_id: UUID
    created_at: datetime
    user: ReviewUserResponse
