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
    UniqueConstraint,
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
    is_series = Column(Boolean, default=False, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    seasons_count = Column(Integer, default=1, nullable=False)
    average_rating = Column(Float, default=0.0, nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("movie_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("MovieCategory", back_populates="primary_movies", foreign_keys=[category_id])
    categories = relationship("MovieCategory", secondary=movie_category_links, back_populates="movies")
    actors = relationship("Actor", secondary=movie_actors, back_populates="movies")
    posters = relationship("Poster", back_populates="movie", cascade="all, delete-orphan")
    episodes = relationship(
        "Episode",
        back_populates="movie",
        cascade="all, delete-orphan",
        order_by="Episode.season_number, Episode.episode_number",
    )
    reviews = relationship("Review", back_populates="movie", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="movie", cascade="all, delete-orphan")

    @property
    def duration(self):
        return self.duration_minutes

    @property
    def primary_poster(self):
        for poster in self.posters:
            if poster.is_primary:
                return poster
        return self.posters[0] if self.posters else None


class Poster(Base):
    __tablename__ = "posters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1000), nullable=False)
    storage_path = Column(String(1000), nullable=True)
    is_primary = Column(Boolean, default=False)

    movie = relationship("Movie", back_populates="posters")


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("movie_id", "season_number", "episode_number", name="uq_episode_movie_season_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movie_id = Column(UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    season_number = Column(Integer, default=1, nullable=False)
    episode_number = Column(Integer, default=1, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    video_url = Column(String(1000), nullable=True)
    duration_sec = Column(Integer, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    movie = relationship("Movie", back_populates="episodes")

    @property
    def duration(self):
        if self.duration_minutes is not None:
            return self.duration_minutes
        if self.duration_sec is not None:
            return self.duration_sec // 60
        return None
