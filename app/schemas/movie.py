from pydantic import Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.schemas.base import BaseSchema


class MovieCategoryBase(BaseSchema):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)


class MovieCategoryResponse(MovieCategoryBase):
    id: UUID


class ActorBase(BaseSchema):
    full_name: str = Field(..., max_length=255)
    photo_url: Optional[str] = Field(None, max_length=500)
    bio: Optional[str] = None


class ActorResponse(ActorBase):
    id: UUID


class PosterBase(BaseSchema):
    url: str = Field(..., max_length=1000)
    storage_path: str = Field(..., max_length=1000)
    is_primary: bool = False


class PosterResponse(PosterBase):
    id: UUID
    movie_id: UUID


class EpisodeBase(BaseSchema):
    season_number: int = Field(default=1, ge=1)
    episode_number: int = Field(default=1, ge=1)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    video_url: Optional[str] = Field(None, max_length=1000)
    duration_sec: Optional[int] = Field(None, ge=0)


class EpisodeResponse(EpisodeBase):
    id: UUID
    movie_id: UUID


class MovieBase(BaseSchema):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    is_series: bool = False
    category_id: Optional[UUID] = None


class MovieCreate(MovieBase):
    pass


class MovieUpdate(MovieBase):
    pass


class MovieResponse(MovieBase):
    id: UUID
    average_rating: float
    created_at: datetime
    updated_at: Optional[datetime]
    category: Optional[MovieCategoryResponse]
    actors: List[ActorResponse] = []
    posters: List[PosterResponse] = []
    episodes: List[EpisodeResponse] = []


class MovieListResponse(BaseSchema):
    id: UUID
    name: str
    is_series: bool
    average_rating: float
    category: Optional[MovieCategoryResponse]
    primary_poster: Optional[PosterResponse]
