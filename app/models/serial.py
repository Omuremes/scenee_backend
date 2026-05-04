import uuid
import logging
from sqlalchemy import CheckConstraint, Column, String, Integer, ForeignKey, Text, Table, UniqueConstraint, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from datetime import datetime

from app.core.database import Base


logger = logging.getLogger(__name__)


serial_actors = Table(
    "serial_actors",
    Base.metadata,
    Column("serial_id", UUID(as_uuid=True), ForeignKey("serials.id", ondelete="CASCADE"), primary_key=True),
    Column("actor_id", UUID(as_uuid=True), ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True),
)

serial_category_links = Table(
    "serial_category_links",
    Base.metadata,
    Column("serial_id", UUID(as_uuid=True), ForeignKey("serials.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("movie_categories.id", ondelete="CASCADE"), primary_key=True),
)


class Serial(Base):
    __tablename__ = "serials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    poster_key = Column(String(1000), nullable=True)
    trailer_video_key = Column(String(1000), nullable=True)
    average_rating = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    actors = relationship("Actor", secondary=serial_actors, backref="serials")
    categories = relationship("MovieCategory", secondary=serial_category_links, backref="serials")
    seasons = relationship("Season", back_populates="serial", cascade="all, delete-orphan", order_by="Season.season_number")
    reviews = relationship("SerialReview", back_populates="serial", cascade="all, delete-orphan")

    @property
    def poster_url(self):
        from app.core.config import settings
        from app.core.minio import build_public_object_url

        if self.poster_key:
            return build_public_object_url(settings.MINIO_BUCKET_NAME, self.poster_key)
        return None

    @property
    def trailer_url(self):
        from app.core.config import settings
        from app.core.minio import get_presigned_url_sync

        if self.trailer_video_key:
            try:
                return get_presigned_url_sync(settings.MINIO_BUCKET_NAME, self.trailer_video_key, expires=3600)
            except ValueError as exc:
                logger.warning(
                    "Could not generate trailer URL for serial_id=%s bucket=%s key=%s: %s",
                    self.id,
                    settings.MINIO_BUCKET_NAME,
                    self.trailer_video_key,
                    exc,
                )
                return None
        return None


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("serial_id", "season_number", name="uq_season_serial_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_id = Column(UUID(as_uuid=True), ForeignKey("serials.id", ondelete="CASCADE"), nullable=False)
    season_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    release_year = Column(Integer, nullable=True)

    serial = relationship("Serial", back_populates="seasons")
    episodes = relationship("SerialEpisode", back_populates="season", cascade="all, delete-orphan", order_by="SerialEpisode.episode_number")


class SerialEpisode(Base):
    __tablename__ = "serial_episodes"
    __table_args__ = (
        UniqueConstraint("season_id", "episode_number", name="uq_serial_episode_season_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    season_id = Column(UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # in seconds

    season = relationship("Season", back_populates="episodes")
    episode_file = relationship("EpisodeFile", back_populates="episode", uselist=False, cascade="all, delete-orphan")


class EpisodeFile(Base):
    __tablename__ = "episode_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    episode_id = Column(UUID(as_uuid=True), ForeignKey("serial_episodes.id", ondelete="CASCADE"), unique=True, nullable=False)
    minio_bucket = Column(String(255), nullable=False)
    minio_object_key = Column(String(1000), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)

    episode = relationship("SerialEpisode", back_populates="episode_file")

    @property
    def video_url(self):
        from app.core.minio import get_presigned_url_sync
        if self.minio_bucket and self.minio_object_key:
            try:
                return get_presigned_url_sync(self.minio_bucket, self.minio_object_key, expires=3600)
            except ValueError as exc:
                logger.warning(
                    "Could not generate episode file URL for episode_file_id=%s bucket=%s key=%s: %s",
                    self.id,
                    self.minio_bucket,
                    self.minio_object_key,
                    exc,
                )
                return None
        return None


class SerialReview(Base):
    __tablename__ = "serial_reviews"
    __table_args__ = (
        CheckConstraint("rating >= 1.0 AND rating <= 5.0", name="ck_serial_review_rating"),
        UniqueConstraint("serial_id", "user_id", name="uq_serial_review_serial_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    serial_id = Column(UUID(as_uuid=True), ForeignKey("serials.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Float, nullable=False)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    serial = relationship("Serial", back_populates="reviews")
    user = relationship("User", back_populates="serial_reviews")
