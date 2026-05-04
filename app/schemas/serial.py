from typing import List, Optional
from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.base import BaseSchema
from app.schemas.movie import ActorResponse, MovieCategoryResponse
from app.schemas.serial_review import SerialReviewResponse


class EpisodeFileBase(BaseSchema):
    minio_bucket: str
    minio_object_key: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class EpisodeFileResponse(EpisodeFileBase):
    id: UUID
    episode_id: UUID
    video_url: Optional[str] = None


class SerialEpisodeBase(BaseSchema):
    episode_number: int = Field(..., ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=0)


class SerialEpisodeCreate(SerialEpisodeBase):
    pass


class SerialEpisodeUpdate(BaseSchema):
    episode_number: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=0)


class SerialEpisodeResponse(SerialEpisodeBase):
    id: UUID
    season_id: UUID
    episode_file: Optional[EpisodeFileResponse] = None


class SeasonBase(BaseSchema):
    season_number: int = Field(..., ge=1)
    title: Optional[str] = Field(None, max_length=255)
    release_year: Optional[int] = Field(None)


class SeasonCreate(SeasonBase):
    episodes: List[SerialEpisodeCreate] = Field(default_factory=list)


class SeasonUpdate(BaseSchema):
    season_number: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=255)
    release_year: Optional[int] = Field(None)


class SeasonResponse(SeasonBase):
    id: UUID
    serial_id: UUID
    episodes: List[SerialEpisodeResponse] = Field(default_factory=list)


class SerialBase(BaseSchema):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None


class SerialCreate(SerialBase):
    poster_key: Optional[str] = None
    trailer_video_key: Optional[str] = None
    actors: List[UUID] = Field(default_factory=list)
    categories: List[UUID] = Field(default_factory=list)
    seasons: List[SeasonCreate] = Field(default_factory=list)


class SerialUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    poster_key: Optional[str] = None
    trailer_video_key: Optional[str] = None
    actors: Optional[List[UUID]] = None
    categories: Optional[List[UUID]] = None


class SerialResponse(SerialBase):
    id: UUID
    poster_key: Optional[str] = None
    poster_url: Optional[str] = None
    trailer_video_key: Optional[str] = None
    trailer_url: Optional[str] = None
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime] = None
    categories: List[MovieCategoryResponse] = Field(default_factory=list)
    actors: List[ActorResponse] = Field(default_factory=list)
    seasons: List[SeasonResponse] = Field(default_factory=list)
    reviews: List[SerialReviewResponse] = Field(default_factory=list)


class SerialListResponse(BaseSchema):
    id: UUID
    name: str
    poster_key: Optional[str] = None
    poster_url: Optional[str] = None
    trailer_url: Optional[str] = None
    average_rating: float
    created_at: datetime
    categories: List[MovieCategoryResponse] = Field(default_factory=list)

class SerialPageResponse(BaseSchema):
    items: List[SerialListResponse] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool
