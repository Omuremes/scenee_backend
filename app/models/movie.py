import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


movie_actors = Table(
    "movie_actors",
    Base.metadata,
    Column("movie_id", UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("actor_id", UUID(as_uuid=True), ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(255), nullable=True),
)

movie_category_links = Table(
    "movie_category_links",
    Base.metadata,
    Column("movie_id", UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("movie_categories.id", ondelete="CASCADE"), primary_key=True),
)


class MovieCategory(Base):
    __tablename__ = "movie_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True)

    movies = relationship("Movie", secondary=movie_category_links, back_populates="categories")
    primary_movies = relationship("Movie", back_populates="category", foreign_keys="Movie.category_id")


class Actor(Base):
    __tablename__ = "actors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    photo_url = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)

    movies = relationship("Movie", secondary=movie_actors, back_populates="actors")


class Movie(Base):
    __tablename__ = "movies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    average_rating = Column(Float, default=0.0, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("movie_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    poster_key = Column(String(1000), nullable=True)
    video_file_key = Column(String(1000), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("MovieCategory", back_populates="primary_movies", foreign_keys=[category_id])
    categories = relationship("MovieCategory", secondary=movie_category_links, back_populates="movies")
    actors = relationship("Actor", secondary=movie_actors, back_populates="movies")
    posters = relationship("Poster", back_populates="movie", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="movie", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="movie", cascade="all, delete-orphan")

    @property
    def duration(self):
        return self.duration_minutes

    @property
    def primary_poster(self):
        loaded_posters = self.__dict__.get("posters") or []
        if not loaded_posters:
            return None
        return next((poster for poster in loaded_posters if poster.is_primary), loaded_posters[0])

    @property
    def poster_url(self):
        from app.core.config import settings
        from app.core.minio import build_public_object_url, to_public_url

        primary_poster = self.primary_poster
        if primary_poster:
            return to_public_url(primary_poster.url) or primary_poster.url

        if self.poster_key:
            return build_public_object_url(settings.MINIO_BUCKET_NAME, self.poster_key)
        return None

    @property
    def video_url(self):
        from app.core.config import settings
        from app.core.minio import get_presigned_url_sync
        if self.video_file_key:
            return get_presigned_url_sync(settings.MINIO_BUCKET_NAME, self.video_file_key, expires=3600)
        return None



class Poster(Base):
    __tablename__ = "posters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1000), nullable=False)
    storage_path = Column(String(1000), nullable=True)
    is_primary = Column(Boolean, default=False)

    movie = relationship("Movie", back_populates="posters")
