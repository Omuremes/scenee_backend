from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.serial import Serial, Season, SerialEpisode, EpisodeFile, SerialReview
from app.models.movie import Actor, MovieCategory
from sqlalchemy import or_, desc, case
from datetime import datetime, timedelta


class SerialRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, serial_id: UUID) -> Optional[Serial]:
        stmt = (
            select(Serial)
            .options(
                selectinload(Serial.actors),
                selectinload(Serial.categories),
                selectinload(Serial.seasons).selectinload(Season.episodes).selectinload(SerialEpisode.episode_file),
                selectinload(Serial.reviews).selectinload(SerialReview.user),
            )
            .where(Serial.id == serial_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    def _apply_filters(self, stmt, query: Optional[str] = None, category_id: Optional[UUID] = None):
        if category_id:
            stmt = stmt.where(
                Serial.categories.any(MovieCategory.id == category_id)
            )

        normalized_query = query.strip() if query else None
        if not normalized_query:
            return stmt

        ilike_query = f"%{normalized_query}%"
        return stmt.where(
            or_(
                Serial.name.ilike(ilike_query),
                Serial.description.ilike(ilike_query),
                Serial.categories.any(
                    or_(
                        MovieCategory.name.ilike(ilike_query),
                        MovieCategory.slug.ilike(ilike_query),
                    )
                ),
            )
        )

    async def list_serials(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Serial], int]:
        count_stmt = self._apply_filters(select(sa.func.count(Serial.id)), query, category_id)
        total = await self.db.scalar(count_stmt)

        stmt = select(Serial).options(
            selectinload(Serial.categories)
        ).order_by(Serial.created_at.desc(), Serial.average_rating.desc(), Serial.id.desc())
        
        stmt = self._apply_filters(stmt, query, category_id)
        result = await self.db.execute(stmt.offset(skip).limit(limit))
        return list(result.scalars().all()), total or 0

    async def get_popular_serials(self, limit: int = 10) -> List[Serial]:
        stmt = (
            select(Serial)
            .options(selectinload(Serial.categories))
            .order_by(Serial.average_rating.desc(), Serial.created_at.desc(), Serial.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_new_serials(self, limit: int = 10) -> List[Serial]:
        now = datetime.utcnow()
        freshness_rank = case(
            (Serial.created_at >= now - timedelta(days=7), 3),
            (Serial.created_at >= now - timedelta(days=30), 2),
            else_=1,
        )
        stmt = (
            select(Serial)
            .options(selectinload(Serial.categories))
            .order_by(freshness_rank.desc(), Serial.created_at.desc(), Serial.average_rating.desc(), Serial.id.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict, actors: List[Actor], categories: List[MovieCategory]) -> Serial:
        serial = Serial(
            name=data.get("name"),
            description=data.get("description"),
            poster_key=data.get("poster_key"),
            trailer_poster_key=data.get("trailer_poster_key"),
            trailer_video_key=data.get("trailer_video_key")
        )
        serial.actors = actors
        serial.categories = categories
        self.db.add(serial)
        await self.db.flush()
        return serial

    async def update(self, serial: Serial, data: dict, actors: Optional[List[Actor]] = None, categories: Optional[List[MovieCategory]] = None) -> Serial:
        if "name" in data:
            serial.name = data["name"]
        if "description" in data:
            serial.description = data["description"]
        if "poster_key" in data:
            serial.poster_key = data["poster_key"]
        if "trailer_poster_key" in data:
            serial.trailer_poster_key = data["trailer_poster_key"]
        if "trailer_video_key" in data:
            serial.trailer_video_key = data["trailer_video_key"]
        
        if actors is not None:
            serial.actors = actors
        if categories is not None:
            serial.categories = categories
            
        await self.db.flush()
        return serial

    async def delete(self, serial: Serial) -> None:
        await self.db.delete(serial)
        await self.db.flush()

    # Seasons
    async def get_season_by_id(self, season_id: UUID) -> Optional[Season]:
        stmt = (
            select(Season)
            .options(selectinload(Season.episodes).selectinload(SerialEpisode.episode_file))
            .where(Season.id == season_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def add_season(self, serial_id: UUID, data: dict) -> Season:
        season = Season(
            serial_id=serial_id,
            season_number=data["season_number"],
            title=data.get("title"),
            release_year=data.get("release_year")
        )
        self.db.add(season)
        await self.db.flush()
        return season

    async def update_season(self, season: Season, data: dict) -> Season:
        if "season_number" in data:
            season.season_number = data["season_number"]
        if "title" in data:
            season.title = data["title"]
        if "release_year" in data:
            season.release_year = data["release_year"]
        await self.db.flush()
        return season

    async def delete_season(self, season: Season) -> None:
        await self.db.delete(season)
        await self.db.flush()

    # Episodes
    async def get_episode_by_id(self, episode_id: UUID) -> Optional[SerialEpisode]:
        stmt = (
            select(SerialEpisode)
            .options(selectinload(SerialEpisode.episode_file))
            .where(SerialEpisode.id == episode_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def add_episode(self, season_id: UUID, data: dict) -> SerialEpisode:
        episode = SerialEpisode(
            season_id=season_id,
            episode_number=data["episode_number"],
            title=data.get("title"),
            description=data.get("description"),
            duration=data.get("duration")
        )
        self.db.add(episode)
        await self.db.flush()
        return episode

    async def update_episode(self, episode: SerialEpisode, data: dict) -> SerialEpisode:
        if "episode_number" in data:
            episode.episode_number = data["episode_number"]
        if "title" in data:
            episode.title = data["title"]
        if "description" in data:
            episode.description = data["description"]
        if "duration" in data:
            episode.duration = data["duration"]
        await self.db.flush()
        return episode

    async def delete_episode(self, episode: SerialEpisode) -> None:
        await self.db.delete(episode)
        await self.db.flush()

    # Episode File
    async def save_episode_file(self, episode_id: UUID, bucket: str, key: str, size: int, mime: str) -> EpisodeFile:
        stmt = select(EpisodeFile).where(EpisodeFile.episode_id == episode_id)
        result = await self.db.execute(stmt)
        file = result.scalars().first()

        if file:
            file.minio_bucket = bucket
            file.minio_object_key = key
            file.file_size = size
            file.mime_type = mime
        else:
            file = EpisodeFile(
                episode_id=episode_id,
                minio_bucket=bucket,
                minio_object_key=key,
                file_size=size,
                mime_type=mime
            )
            self.db.add(file)
        
        await self.db.flush()
        return file
