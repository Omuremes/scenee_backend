import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Float,
    Integer, ForeignKey, DateTime, Table
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.core.database import Base


# Промежуточная таблица фильм ↔ актёр
movie_actors = Table(
    "movie_actors",
    Base.metadata,
    Column("movie_id", UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("actor_id", UUID(as_uuid=True), ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(255), nullable=True),  # роль персонажа
)


class MovieCategory(Base):
    __tablename__ = "movie_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)   # "Комедия"
    slug = Column(String(100), nullable=False, unique=True)   # "comedy"

    movies = relationship("Movie", back_populates="category")


class Actor(Base):
    __tablename__ = "actors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    photo_url = Column(String(500), nullable=True)    # URL из Firebase Storage
    bio = Column(Text, nullable=True)

    movies = relationship("Movie", secondary=movie_actors, back_populates="actors")


class Movie(Base):
    __tablename__ = "movies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_series = Column(Boolean, default=False, nullable=False)
    average_rating = Column(Float, default=0.0, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("movie_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Связи
    category = relationship("MovieCategory", back_populates="movies")
    actors = relationship("Actor", secondary=movie_actors, back_populates="movies")
    posters = relationship("Poster", back_populates="movie", cascade="all, delete-orphan")
    episodes = relationship("Episode", back_populates="movie", cascade="all, delete-orphan", order_by="Episode.season_number, Episode.episode_number")
    reviews = relationship("Review", back_populates="movie", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="movie", cascade="all, delete-orphan")

    @property
    def primary_poster(self):
        for poster in self.posters:
            if poster.is_primary:
                return poster
        return self.posters[0] if self.posters else None


class Poster(Base):
    """Постеры фильма/сериала — хранятся в Firebase Storage, здесь только URL"""
    __tablename__ = "posters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1000), nullable=False)          # публичный CDN URL
    storage_path = Column(String(1000), nullable=False) # путь в Firebase Storage
    is_primary = Column(Boolean, default=False)         # главный постер

    movie = relationship("Movie", back_populates="posters")


class Episode(Base):
    """Серии сериала. Для обычного фильма — одна запись (season=1, episode=1)"""
    __tablename__ = "episodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    season_number = Column(Integer, default=1, nullable=False)
    episode_number = Column(Integer, default=1, nullable=False)
    title = Column(String(255), nullable=True)           # "Пилот"
    description = Column(Text, nullable=True)
    video_url = Column(String(1000), nullable=True)      # signed URL Firebase Storage
    duration_sec = Column(Integer, nullable=True)        # длительность в секундах

    movie = relationship("Movie", back_populates="episodes")
