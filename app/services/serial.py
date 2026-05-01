from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories.serial import SerialRepository
from app.models.movie import Actor, MovieCategory
from app.models.serial import Serial, Season, SerialEpisode
from app.schemas.serial import SerialCreate, SerialUpdate, SeasonCreate, SeasonUpdate, SerialEpisodeCreate, SerialEpisodeUpdate
from app.core.minio import to_public_url, build_public_object_url

class SerialService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SerialRepository(db)

    async def _get_actors(self, actor_ids: List[UUID]) -> List[Actor]:
        if not actor_ids:
            return []
        stmt = select(Actor).where(Actor.id.in_(actor_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_categories(self, category_ids: List[UUID]) -> List[MovieCategory]:
        if not category_ids:
            return []
        stmt = select(MovieCategory).where(MovieCategory.id.in_(category_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, serial_id: UUID) -> Optional[Serial]:
        return await self.repo.get_by_id(serial_id)

    async def list_serials(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[Serial], int]:
        return await self.repo.list_serials(query, category_id, skip, limit)

    async def get_popular_serials(self, limit: int = 10) -> List[Serial]:
        return await self.repo.get_popular_serials(limit)

    async def get_new_serials(self, limit: int = 10) -> List[Serial]:
        return await self.repo.get_new_serials(limit)

    async def get_season_episodes(self, serial_id: UUID, season_number: int) -> Optional[List[SerialEpisode]]:
        serial = await self.get_by_id(serial_id)
        if not serial:
            return None
        for season in serial.seasons:
            if season.season_number == season_number:
                return season.episodes
        return None

    async def create(self, data: SerialCreate) -> Serial:
        actors = await self._get_actors(data.actors)
        categories = await self._get_categories(data.categories)
        
        serial = await self.repo.create(data.dict(exclude={"actors", "categories", "seasons"}), actors, categories)
        
        for season_data in data.seasons:
            season = await self.repo.add_season(serial.id, season_data.dict(exclude={"episodes"}))
            for episode_data in season_data.episodes:
                await self.repo.add_episode(season.id, episode_data.dict())
                
        await self.db.commit()
        
        # Reload to get all relations
        return await self.repo.get_by_id(serial.id)

    async def update(self, serial_id: UUID, data: SerialUpdate) -> Optional[Serial]:
        serial = await self.repo.get_by_id(serial_id)
        if not serial:
            return None
            
        actors = await self._get_actors(data.actors) if data.actors is not None else None
        categories = await self._get_categories(data.categories) if data.categories is not None else None
        
        await self.repo.update(serial, data.dict(exclude_unset=True, exclude={"actors", "categories"}), actors, categories)
        
        await self.db.commit()
        return await self.repo.get_by_id(serial.id)

    async def delete(self, serial_id: UUID) -> bool:
        serial = await self.repo.get_by_id(serial_id)
        if not serial:
            return False
        await self.repo.delete(serial)
        await self.db.commit()
        return True

    # Seasons
    async def add_season(self, serial_id: UUID, data: SeasonCreate) -> Season:
        season = await self.repo.add_season(serial_id, data.dict(exclude={"episodes"}))
        for episode_data in data.episodes:
            await self.repo.add_episode(season.id, episode_data.dict())
        await self.db.commit()
        return await self.repo.get_season_by_id(season.id)

    async def update_season(self, season_id: UUID, data: SeasonUpdate) -> Optional[Season]:
        season = await self.repo.get_season_by_id(season_id)
        if not season:
            return None
        await self.repo.update_season(season, data.dict(exclude_unset=True))
        await self.db.commit()
        return await self.repo.get_season_by_id(season.id)

    async def delete_season(self, season_id: UUID) -> bool:
        season = await self.repo.get_season_by_id(season_id)
        if not season:
            return False
        await self.repo.delete_season(season)
        await self.db.commit()
        return True

    # Episodes
    async def add_episode(self, season_id: UUID, data: SerialEpisodeCreate) -> SerialEpisode:
        episode = await self.repo.add_episode(season_id, data.dict())
        await self.db.commit()
        return await self.repo.get_episode_by_id(episode.id)

    async def update_episode(self, episode_id: UUID, data: SerialEpisodeUpdate) -> Optional[SerialEpisode]:
        episode = await self.repo.get_episode_by_id(episode_id)
        if not episode:
            return None
        await self.repo.update_episode(episode, data.dict(exclude_unset=True))
        await self.db.commit()
        return await self.repo.get_episode_by_id(episode.id)

    async def delete_episode(self, episode_id: UUID) -> bool:
        episode = await self.repo.get_episode_by_id(episode_id)
        if not episode:
            return False
        await self.repo.delete_episode(episode)
        await self.db.commit()
        return True

    # Episode File
    async def save_episode_file(self, episode_id: UUID, bucket: str, key: str, size: int, mime: str):
        file = await self.repo.save_episode_file(episode_id, bucket, key, size, mime)
        await self.db.commit()
        return file
