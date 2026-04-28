from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.movie import (
    ActorResponse,
    EpisodeCreate,
    EpisodeResponse,
    MovieCategoryResponse,
    PosterResponse,
)


class SeriesBase(BaseSchema):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1, description="Series duration in minutes")
    seasons_count: int = Field(default=1, ge=1)


class SeriesCreate(SeriesBase):
    poster: Optional[str] = Field(None, max_length=1000, description="Poster URL when JSON payload is used")
    actors: List[UUID] = Field(default_factory=list)
    categories: List[UUID] = Field(default_factory=list)
    episodes: List[EpisodeCreate] = Field(default_factory=list)


class SeriesUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1, description="Series duration in minutes")
    seasons_count: Optional[int] = Field(None, ge=1)
    poster: Optional[str] = Field(None, max_length=1000, description="Poster URL when JSON payload is used")
    actors: Optional[List[UUID]] = None
    categories: Optional[List[UUID]] = None
    episodes: Optional[List[EpisodeCreate]] = None


class SeriesResponse(SeriesBase):
    id: UUID
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime]
    category: Optional[MovieCategoryResponse] = None
    categories: List[MovieCategoryResponse] = Field(default_factory=list)
    actors: List[ActorResponse] = Field(default_factory=list)
    posters: List[PosterResponse] = Field(default_factory=list)
    episodes: List[EpisodeResponse] = Field(default_factory=list)
    primary_poster: Optional[PosterResponse] = None


class SeriesListResponse(BaseSchema):
    id: UUID
    name: str
    duration: Optional[int] = None
    seasons_count: int
    average_rating: float
    category: Optional[MovieCategoryResponse] = None
    categories: List[MovieCategoryResponse] = Field(default_factory=list)
    primary_poster: Optional[PosterResponse] = None
    created_at: datetime


class SeriesPageResponse(BaseSchema):
    items: List[SeriesListResponse] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool
