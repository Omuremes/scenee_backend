from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import Field, validator

from app.core.minio import to_public_url
from app.schemas.base import BaseSchema


class MovieCategoryBase(BaseSchema):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)


class MovieCategoryCreate(BaseSchema):
    name: str = Field(..., max_length=100)
    slug: Optional[str] = Field(None, max_length=100)


class MovieCategoryUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=100)
    slug: Optional[str] = Field(None, max_length=100)


class MovieCategoryResponse(MovieCategoryBase):
    id: UUID


class MovieCategoryPageResponse(BaseSchema):
    items: List[MovieCategoryResponse] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool


class ActorBase(BaseSchema):
    full_name: str = Field(..., max_length=255)
    photo_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = None


class ActorCreate(ActorBase):
    pass


class ActorUpdate(BaseSchema):
    full_name: Optional[str] = Field(None, max_length=255)
    photo_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = None


class ActorResponse(ActorBase):
    id: UUID


class ActorPageResponse(BaseSchema):
    items: List[ActorResponse] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool


class PosterBase(BaseSchema):
    url: str = Field(..., max_length=1000)
    storage_path: Optional[str] = Field(None, max_length=1000)
    is_primary: bool = False


class PosterResponse(PosterBase):
    id: UUID
    movie_id: UUID

    @validator("url", pre=True, allow_reuse=True)
    def normalize_poster_url(cls, value):
        return to_public_url(value)


class EpisodeBase(BaseSchema):
    season_number: int = Field(default=1, ge=1)
    episode_number: int = Field(default=1, ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    video_url: Optional[str] = Field(None, max_length=1000)
    duration: Optional[int] = Field(None, ge=0)


class EpisodeCreate(EpisodeBase):
    pass


class EpisodeUpdate(BaseSchema):
    season_number: Optional[int] = Field(None, ge=1)
    episode_number: Optional[int] = Field(None, ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    video_url: Optional[str] = Field(None, max_length=1000)
    duration: Optional[int] = Field(None, ge=0)


class EpisodeResponse(EpisodeBase):
    id: UUID
    movie_id: UUID


class MovieBase(BaseSchema):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_series: bool = False
    duration: Optional[int] = Field(None, ge=1, description="Movie duration in minutes")
    seasons_count: int = Field(default=1, ge=1)


class MovieCreate(MovieBase):
    poster: Optional[str] = Field(None, max_length=1000, description="Poster URL when JSON payload is used")
    actors: List[UUID] = Field(default_factory=list)
    categories: List[UUID] = Field(default_factory=list)
    episodes: List[EpisodeCreate] = Field(default_factory=list)


class MovieUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_series: Optional[bool] = None
    duration: Optional[int] = Field(None, ge=1, description="Movie duration in minutes")
    seasons_count: Optional[int] = Field(None, ge=1)
    poster: Optional[str] = Field(None, max_length=1000, description="Poster URL when JSON payload is used")
    actors: Optional[List[UUID]] = None
    categories: Optional[List[UUID]] = None
    episodes: Optional[List[EpisodeCreate]] = None


class MovieResponse(MovieBase):
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


class MovieListResponse(BaseSchema):
    id: UUID
    name: str
    is_series: bool
    duration: Optional[int] = None
    seasons_count: int
    average_rating: float
    category: Optional[MovieCategoryResponse] = None
    categories: List[MovieCategoryResponse] = Field(default_factory=list)
    primary_poster: Optional[PosterResponse] = None
    created_at: datetime


class MoviePageResponse(BaseSchema):
    items: List[MovieListResponse] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool
