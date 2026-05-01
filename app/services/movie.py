import re
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import MovieCategoryRepository, MovieRepository
from app.schemas import MovieCategoryCreate, MovieCategoryUpdate, MovieCreate, MovieUpdate
from app.services.base import BaseService
from app.services.content import BaseContentService


class MovieService(BaseContentService):
    def __init__(self, db: AsyncSession):
        super().__init__(MovieRepository(db))

    async def get_movie_with_details(self, movie_id: UUID):
        return await self.get_content_with_details(movie_id)

    async def list_movies(self, query: Optional[str] = None, category_id: Optional[UUID] = None, skip: int = 0, limit: int = 20):
        return await self.list_content(query=query, category_id=category_id, skip=skip, limit=limit)

    async def get_popular_movies(self, limit: int = 10):
        return await self.get_popular_content(limit)

    async def get_new_movies(self, limit: int = 10):
        return await self.get_new_content(limit)

    async def create_movie(
        self, 
        movie_data: MovieCreate, 
        poster_payload: Optional[dict] = None,
        movie_id: Optional[UUID] = None,
        poster_key: Optional[str] = None,
        video_file_key: Optional[str] = None
    ):
        actor_ids = self._dedupe_ids(movie_data.actors)
        category_ids = self._dedupe_ids(movie_data.categories)
        actors = await self._validate_actor_ids(actor_ids)
        categories = await self._validate_category_ids(category_ids)
        payload = self._build_content_payload(movie_data)
        
        if movie_id:
            payload["id"] = movie_id
        if poster_key:
            payload["poster_key"] = poster_key
        if video_file_key:
            payload["video_file_key"] = video_file_key
            
        movie = await self.repository.create_movie(
            payload,
            actors=actors,
            categories=categories,
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
        actors = categories = None

        if "actors" in update_data:
            actors = await self._validate_actor_ids(self._dedupe_ids(update_data.pop("actors") or []))
        if "categories" in update_data:
            categories = await self._validate_category_ids(self._dedupe_ids(update_data.pop("categories") or []))

        if not update_data and actors is None and categories is None and not poster_provided:
            return current_movie

        payload = self._build_content_payload(update_data, partial=True)
        if poster_provided and poster_payload and "storage_path" in poster_payload:
            payload["poster_key"] = poster_payload["storage_path"]

        movie = await self.repository.update_movie_with_relations(
            movie_id,
            payload,
            actors=actors,
            categories=categories,
            poster_payload=poster_payload,
            poster_provided=poster_provided,
        )
        if not movie:
            return None
        return await self.repository.get_with_details(movie.id)


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

    async def list_categories(
        self,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ):
        items = await self.repository.list_categories(query=query, skip=skip, limit=limit)
        total = await self.repository.count_categories(query=query)
        return items, total

    async def update_category(self, category_id: UUID, category_data: MovieCategoryUpdate):
        current_category = await self.repository.get_by_id(category_id)
        if not current_category:
            return None

        payload = category_data.model_dump(exclude_unset=True)
        if not payload:
            return current_category

        normalized_name = current_category.name
        normalized_slug = current_category.slug

        if "name" in payload:
            normalized_name = payload["name"].strip()
            if not normalized_name:
                raise ValueError("Category name is required")
            existing_name = await self.repository.get_by_name(normalized_name)
            if existing_name and existing_name.id != category_id:
                raise ValueError("Movie category with this name already exists")

        if "slug" in payload or "name" in payload:
            normalized_slug = self._normalize_slug(normalized_name, payload.get("slug", normalized_slug))
            existing_slug = await self.repository.get_by_slug(normalized_slug)
            if existing_slug and existing_slug.id != category_id:
                raise ValueError("Movie category with this slug already exists")

        return await self.repository.update(
            category_id,
            {
                "name": normalized_name,
                "slug": normalized_slug,
            },
        )
