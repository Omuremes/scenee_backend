from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.content import BaseContentRepository


class SeriesRepository(BaseContentRepository):
    def __init__(self, db: AsyncSession):
        super().__init__(db, is_series=True)

    async def search_series(self, query=None, category_id=None, skip: int = 0, limit: int = 20):
        return await self.search_content(query=query, category_id=category_id, skip=skip, limit=limit)

    async def count_series(self, query=None, category_id=None) -> int:
        return await self.count_content(query=query, category_id=category_id)

    async def get_popular_series(self, limit: int = 10):
        return await self.get_popular_content(limit)

    async def get_new_series(self, limit: int = 10):
        return await self.get_new_content(limit)

    async def create_series(self, series_data: dict, **kwargs):
        return await self.create_content(series_data, **kwargs)

    async def update_series_with_relations(self, series_id, series_data: dict, **kwargs):
        return await self.update_content_with_relations(series_id, series_data, **kwargs)

    async def delete_series(self, series_id) -> bool:
        return await self.delete_content(series_id)
