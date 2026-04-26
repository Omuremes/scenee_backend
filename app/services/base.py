from typing import Generic, TypeVar, Optional, List, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import BaseRepository

RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class BaseService(Generic[RepositoryType]):
    def __init__(self, repository: RepositoryType):
        self.repository = repository

    async def get_by_id(self, id: UUID) -> Optional[Any]:
        return await self.repository.get_by_id(id)

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Any]:
        return await self.repository.get_all(skip, limit)

    async def create(self, obj_in: dict) -> Any:
        return await self.repository.create(obj_in)

    async def update(self, id: UUID, obj_in: dict) -> Optional[Any]:
        return await self.repository.update(id, obj_in)

    async def delete(self, id: UUID) -> bool:
        return await self.repository.delete(id)