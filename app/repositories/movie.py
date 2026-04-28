from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.content import BaseContentRepository, MovieCategoryRepository


class MovieRepository(BaseContentRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db, is_series=False)

    async def search_movies(self, query=None, category_id=None, skip: int = 0, limit: int = 20):
        return await self.search_content(query=query, category_id=category_id, skip=skip, limit=limit)

    async def count_movies(self, query=None, category_id=None) -> int:
        return await self.count_content(query=query, category_id=category_id)

    async def get_popular_movies(self, limit: int = 10):
        return await self.get_popular_content(limit)

    async def get_new_movies(self, limit: int = 10):
        return await self.get_new_content(limit)

    async def create_movie(self, movie_data: dict, **kwargs):
        return await self.create_content(movie_data, **kwargs)

    async def update_movie_with_relations(self, movie_id, movie_data: dict, **kwargs):
        return await self.update_content_with_relations(movie_id, movie_data, **kwargs)

    async def delete_movie(self, movie_id) -> bool:
        return await self.delete_content(movie_id)
