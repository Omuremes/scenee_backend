from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import FavoriteRepository
from app.services.base import BaseService
from app.schemas import FavoriteCreate


class FavoriteService(BaseService[FavoriteRepository]):
    def __init__(self, db: AsyncSession):
        repository = FavoriteRepository(db)
        super().__init__(repository)

    async def add_favorite(self, user_id: UUID, favorite_data: FavoriteCreate) -> Optional[dict]:
        # Проверяем, не добавлено ли уже в избранное
        if await self.repository.is_favorited(user_id, favorite_data.movie_id, favorite_data.event_id):
            return None

        create_data = favorite_data.model_dump()
        create_data["user_id"] = user_id
        return await self.repository.create(create_data)

    async def remove_favorite(self, user_id: UUID, movie_id: Optional[UUID] = None, event_id: Optional[UUID] = None) -> bool:
        return await self.repository.remove_favorite(user_id, movie_id, event_id)

    async def get_user_favorites(self, user_id: UUID) -> List[dict]:
        return await self.repository.get_user_favorites(user_id)

    async def is_favorited(self, user_id: UUID, movie_id: Optional[UUID] = None, event_id: Optional[UUID] = None) -> bool:
        return await self.repository.is_favorited(user_id, movie_id, event_id)