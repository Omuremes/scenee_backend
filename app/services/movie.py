import re
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import ActorRepository, MovieCategoryRepository, MovieRepository
from app.schemas import EpisodeCreate, MovieCategoryCreate, MovieCreate, MovieUpdate
from app.services.base import BaseService


class MovieService(BaseService[MovieRepository]):
    def __init__(self, db: AsyncSession):
        repository = MovieRepository(db)
        super().__init__(repository)

    async def get_movie_with_details(self, movie_id: UUID):
        return await self.repository.get_with_details(movie_id)

    async def search_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        return await self.repository.search_movies(query, category_id, is_series, skip, limit)

    async def count_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
    ) -> int:
        return await self.repository.count_movies(query, category_id, is_series)

    async def list_movies(
        self,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        is_series: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        movies = await self.search_movies(query, category_id, is_series, skip, limit)
        total = await self.count_movies(query, category_id, is_series)
        return movies, total

    async def get_popular_movies(self, limit: int = 10):
        return await self.repository.get_popular_movies(limit)

    async def get_new_movies(self, limit: int = 10):
        return await self.repository.get_new_movies(limit)

    async def get_season_episodes(self, movie_id: UUID, season_number: int):
        movie = await self.repository.get_by_id(movie_id)
        if not movie:
            return None
        return await self.repository.get_season_episodes(movie_id, season_number)

    async def create_movie(self, movie_data: MovieCreate, poster_payload: Optional[dict] = None):
        if not movie_data.is_series and movie_data.episodes:
            raise ValueError("Movies cannot have episodes. Set is_series=True to add episodes.")

        actor_ids = self._dedupe_ids(movie_data.actors)
        category_ids = self._dedupe_ids(movie_data.categories)
        actors = await self._validate_actor_ids(actor_ids)
        categories = await self._validate_category_ids(category_ids)
        payload = self._build_movie_payload(movie_data)
        episodes = self._build_episode_payloads(movie_data.episodes)
        movie = await self.repository.create_movie(
            payload,
            actors=actors,
            categories=categories,
            episodes=episodes,
            poster_payload=poster_payload,
        )
        return await self.repository.get_with_details(movie.id)

    async def update_movie(
        self,
        movie_id: UUID,
        movie_data: MovieUpdate,
        poster_payload: Optional[dict] = None,
        poster_provided: bool = False,
    ):
        current_movie = await self.repository.get_with_details(movie_id)
        if not current_movie:
            return None

        update_data = movie_data.model_dump(exclude_unset=True)

        # Validate that movies don't have episodes
        is_series_after_update = update_data.get("is_series", current_movie.is_series)
        has_episodes_in_update = "episodes" in update_data and update_data["episodes"]
        
        if not is_series_after_update:
            if has_episodes_in_update:
                raise ValueError("Movies cannot have episodes. Set is_series=True to add episodes.")
            
            # If changing from series to movie, and no new episodes are provided but old ones exist
            if not current_movie.is_series is False and current_movie.episodes and update_data.get("is_series") is False:
                # We could either delete them or block. Blocking is safer.
                raise ValueError("Cannot convert series to movie while it has episodes. Delete episodes first.")

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
            return current_movie

        payload = self._build_movie_payload(update_data, partial=True, default_is_series=current_movie.is_series)
        if "is_series" in payload and payload["is_series"] is False:
            payload["seasons_count"] = 1
        elif episodes is not None:
            payload["seasons_count"] = self._resolve_seasons_count(
                bool(payload.get("is_series", current_movie.is_series)),
                payload.get("seasons_count"),
                episodes,
            )

        movie = await self.repository.update_movie_with_relations(
            movie_id,
            payload,
            actors=actors,
            categories=categories,
            episodes=episodes,
            poster_payload=poster_payload,
            poster_provided=poster_provided,
        )
        if not movie:
            return None
        return await self.repository.get_with_details(movie.id)

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
        is_series: bool,
        seasons_count: Optional[int],
        episodes: Iterable[dict],
    ) -> int:
        if not is_series:
            return 1

        episode_seasons = [episode["season_number"] for episode in episodes]
        inferred_count = max(episode_seasons, default=1)
        if seasons_count is None:
            return inferred_count
        return max(seasons_count, inferred_count)

    def _build_movie_payload(self, movie_data, partial: bool = False, default_is_series: Optional[bool] = None) -> dict:
        if hasattr(movie_data, "model_dump"):
            raw_data = movie_data.model_dump(exclude_unset=partial)
        else:
            raw_data = dict(movie_data)

        payload = {}
        for key, value in raw_data.items():
            if key in {"poster", "actors", "categories", "episodes"}:
                continue
            if key == "duration":
                payload["duration_minutes"] = value
            else:
                payload[key] = value

        is_series = payload.get("is_series")
        episodes = raw_data.get("episodes") or []
        should_recalculate_seasons = not partial or any(key in raw_data for key in {"is_series", "seasons_count", "episodes"})
        if should_recalculate_seasons:
            payload["seasons_count"] = self._resolve_seasons_count(
                bool(
                    is_series
                    if is_series is not None
                    else raw_data.get("is_series", default_is_series if default_is_series is not None else False)
                ),
                payload.get("seasons_count"),
                self._build_episode_payloads([EpisodeCreate.model_validate(item) for item in episodes]) if episodes else [],
            )
        if payload.get("is_series") is False:
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


class MovieCategoryService(BaseService[MovieCategoryRepository]):
    def __init__(self, db: AsyncSession):
        repository = MovieCategoryRepository(db)
        super().__init__(repository)

    @staticmethod
    def _normalize_slug(name: str, slug: Optional[str]) -> str:
        source = (slug or name).strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "-", source)
        normalized = normalized.strip("-")
        if not normalized:
            raise ValueError("Category slug cannot be empty")
        return normalized[:100]

    async def create_category(self, category_data: MovieCategoryCreate):
        normalized_name = category_data.name.strip()
        if not normalized_name:
            raise ValueError("Category name is required")

        normalized_slug = self._normalize_slug(normalized_name, category_data.slug)
        existing_name = await self.repository.get_by_name(normalized_name)
        if existing_name:
            raise ValueError("Movie category with this name already exists")

        existing_slug = await self.repository.get_by_slug(normalized_slug)
        if existing_slug:
            raise ValueError("Movie category with this slug already exists")

        return await self.repository.create({"name": normalized_name, "slug": normalized_slug})
