from typing import Iterable, List, Optional
from uuid import UUID

from app.repositories import ActorRepository, MovieCategoryRepository
from app.schemas.movie import EpisodeCreate
from app.services.base import BaseService


class BaseContentService(BaseService):
    def __init__(self, repository, *, is_series: bool):
        super().__init__(repository)
        self.is_series = is_series

    async def get_content_with_details(self, content_id: UUID):
        return await self.repository.get_with_details(content_id)

    async def list_content(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        items = await self.repository.search_content(query=query, category_id=category_id, skip=skip, limit=limit)
        total = await self.repository.count_content(query=query, category_id=category_id)
        return items, total

    async def get_popular_content(self, limit: int = 10):
        return await self.repository.get_popular_content(limit)

    async def get_new_content(self, limit: int = 10):
        return await self.repository.get_new_content(limit)

    async def delete(self, id: UUID) -> bool:
        return await self.repository.delete_content(id)

    @staticmethod
    def _dedupe_ids(values: Iterable[UUID]) -> List[UUID]:
        seen = set()
        deduped: List[UUID] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    @staticmethod
    def _resolve_seasons_count(
        seasons_count: Optional[int],
        episodes: Iterable[dict],
        default_value: int = 1,
    ) -> int:
        episode_seasons = [episode["season_number"] for episode in episodes]
        inferred_count = max(episode_seasons, default=default_value)
        if seasons_count is None:
            return inferred_count
        return max(seasons_count, inferred_count)

    def _build_content_payload(self, content_data, partial: bool = False, default_seasons_count: int = 1) -> dict:
        if hasattr(content_data, "model_dump"):
            raw_data = content_data.model_dump(exclude_unset=partial)
        else:
            raw_data = dict(content_data)

        payload = {}
        for key, value in raw_data.items():
            if key in {"poster", "actors", "categories", "episodes"}:
                continue
            if key == "duration":
                payload["duration_minutes"] = value
            else:
                payload[key] = value

        if self.is_series:
            episodes = raw_data.get("episodes") or []
            episode_payloads = self._build_episode_payloads([EpisodeCreate.model_validate(item) for item in episodes]) if episodes else []
            should_recalculate = not partial or "seasons_count" in raw_data or "episodes" in raw_data
            if should_recalculate:
                payload["seasons_count"] = self._resolve_seasons_count(
                    payload.get("seasons_count"),
                    episode_payloads,
                    default_value=default_seasons_count,
                )
        else:
            payload["seasons_count"] = 1

        return payload

    @staticmethod
    def _build_episode_payloads(episodes: Iterable[EpisodeCreate]) -> List[dict]:
        payloads = []
        for episode in episodes:
            payload = episode.model_dump()
            duration = payload.pop("duration", None)
            payload["duration_minutes"] = duration
            payloads.append(payload)
        return payloads

    async def _validate_category_ids(self, category_ids: List[UUID]):
        category_repository = MovieCategoryRepository(self.repository.db)
        categories = await category_repository.get_by_ids(category_ids)
        if len(categories) != len(category_ids):
            raise ValueError("One or more movie categories were not found")
        categories_by_id = {category.id: category for category in categories}
        return [categories_by_id[category_id] for category_id in category_ids]

    async def _validate_actor_ids(self, actor_ids: List[UUID]):
        actor_repository = ActorRepository(self.repository.db)
        actors = await actor_repository.get_by_ids(actor_ids)
        if len(actors) != len(actor_ids):
            raise ValueError("One or more actors were not found")
        actors_by_id = {actor.id: actor for actor in actors}
        return [actors_by_id[actor_id] for actor_id in actor_ids]
