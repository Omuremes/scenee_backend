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

    @validator("photo_url", pre=True, allow_reuse=True)
    def normalize_photo_url(cls, value):
        return to_public_url(value)


class ActorCreate(ActorBase):
    pass


class ActorUpdate(BaseSchema):
    full_name: Optional[str] = Field(None, max_length=255)
    photo_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = None

    @validator("photo_url", pre=True, allow_reuse=True)
    def normalize_photo_url(cls, value):
        return to_public_url(value)


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

    @validator("url", pre=True, allow_reuse=True)
    def normalize_url(cls, value):
        return to_public_url(value) or value


class PosterResponse(PosterBase):
    id: UUID
    movie_id: UUID


class MovieBase(BaseSchema):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1, description="Movie duration in minutes")
    poster_key: Optional[str] = None
    video_file_key: Optional[str] = None


class MovieCreate(MovieBase):
    poster: Optional[str] = Field(None, max_length=1000, description="Poster URL when JSON payload is used")
    actors: List[UUID] = Field(default_factory=list)
    categories: List[UUID] = Field(default_factory=list)

    @validator("poster", pre=True, allow_reuse=True)
    def normalize_poster_url(cls, value):
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Poster URL cannot be empty")
        return to_public_url(normalized) or normalized


class MovieUpdate(BaseSchema):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=1, description="Movie duration in minutes")
    poster: Optional[str] = Field(None, max_length=1000, description="Poster URL when JSON payload is used")
    actors: Optional[List[UUID]] = None
    categories: Optional[List[UUID]] = None

    @validator("poster", pre=True, allow_reuse=True)
    def normalize_poster_url(cls, value):
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Poster URL cannot be empty")
        return to_public_url(normalized) or normalized


class MovieResponse(MovieBase):
    id: UUID
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime]
    category: Optional[MovieCategoryResponse] = None
    categories: List[MovieCategoryResponse] = Field(default_factory=list)
    actors: List[ActorResponse] = Field(default_factory=list)
    posters: List[PosterResponse] = Field(default_factory=list)
    primary_poster: Optional[PosterResponse] = None
    poster_url: Optional[str] = None
    video_url: Optional[str] = None


class MovieListResponse(BaseSchema):
    id: UUID
    name: str
    duration: Optional[int] = None
    average_rating: float
    category: Optional[MovieCategoryResponse] = None
    categories: List[MovieCategoryResponse] = Field(default_factory=list)
    poster_url: Optional[str] = None
    created_at: datetime


class MoviePageResponse(BaseSchema):
    items: List[MovieListResponse] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool
