from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.base import BaseSchema


class FavoriteBase(BaseSchema):
    movie_id: Optional[UUID] = None
    event_id: Optional[UUID] = None


class FavoriteCreate(FavoriteBase):
    pass


class FavoriteResponse(FavoriteBase):
    id: UUID
    user_id: UUID
    created_at: datetime
