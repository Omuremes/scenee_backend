from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import SeriesRepository
from app.schemas import EpisodeCreate, SeriesCreate, SeriesUpdate
from app.services.content import BaseContentService


class SeriesService(BaseContentService):
    def __init__(self, db: AsyncSession):
        super().__init__(SeriesRepository(db), is_series=True)

    async def get_series_with_details(self, series_id: UUID):
        return await self.get_content_with_details(series_id)

    async def list_series(self, query=None, category_id=None, skip: int = 0, limit: int = 20):
        return await self.list_content(query=query, category_id=category_id, skip=skip, limit=limit)

    async def get_popular_series(self, limit: int = 10):
        return await self.get_popular_content(limit)

    async def get_new_series(self, limit: int = 10):
        return await self.get_new_content(limit)

    async def get_season_episodes(self, series_id: UUID, season_number: int):
        series = await self.repository.get_content_by_id(series_id)
        if not series:
            return None
        return await self.repository.get_season_episodes(series_id, season_number)

    async def create_series(self, series_data: SeriesCreate, poster_payload: dict | None = None):
        actor_ids = self._dedupe_ids(series_data.actors)
        category_ids = self._dedupe_ids(series_data.categories)
        actors = await self._validate_actor_ids(actor_ids)
        categories = await self._validate_category_ids(category_ids)
        payload = self._build_content_payload(series_data, partial=False)
        episodes = self._build_episode_payloads(series_data.episodes)
        series = await self.repository.create_series(
            payload,
            actors=actors,
            categories=categories,
            episodes=episodes,
            poster_payload=poster_payload,
        )
        return await self.repository.get_with_details(series.id)

    async def update_series(
        self,
        series_id: UUID,
        series_data: SeriesUpdate,
        poster_payload: dict | None = None,
        poster_provided: bool = False,
    ):
        current_series = await self.repository.get_with_details(series_id)
        if not current_series:
            return None

        update_data = series_data.model_dump(exclude_unset=True)
        actors = categories = episodes = None

        if "actors" in update_data:
            actors = await self._validate_actor_ids(self._dedupe_ids(update_data.pop("actors") or []))
        if "categories" in update_data:
            categories = await self._validate_category_ids(self._dedupe_ids(update_data.pop("categories") or []))
        if "episodes" in update_data:
            raw_episodes = update_data.pop("episodes") or []
            episode_models = [EpisodeCreate.model_validate(item) for item in raw_episodes]
            episodes = self._build_episode_payloads(episode_models)

        if not update_data and actors is None and categories is None and episodes is None and not poster_provided:
            return current_series

        payload = self._build_content_payload(
            update_data,
            partial=True,
            default_seasons_count=current_series.seasons_count or 1,
        )
        if episodes is not None and "seasons_count" not in payload:
            payload["seasons_count"] = self._resolve_seasons_count(
                current_series.seasons_count,
                episodes,
                default_value=current_series.seasons_count or 1,
            )

        series = await self.repository.update_series_with_relations(
            series_id,
            payload,
            actors=actors,
            categories=categories,
            episodes=episodes,
            poster_payload=poster_payload,
            poster_provided=poster_provided,
        )
        if not series:
            return None
        return await self.repository.get_with_details(series.id)
