from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import ActorRepository
from app.schemas import ActorCreate, ActorUpdate
from app.services.base import BaseService


class ActorService(BaseService[ActorRepository]):
    def __init__(self, db: AsyncSession):
        repository = ActorRepository(db)
        super().__init__(repository)

    async def list_actors(self, query: Optional[str] = None, skip: int = 0, limit: int = 20):
        items = await self.repository.list_actors(query=query, skip=skip, limit=limit)
        total = await self.repository.count_actors(query=query)
        return items, total

    async def create_actor(self, actor_data: ActorCreate):
        payload = actor_data.model_dump()
        payload["full_name"] = payload["full_name"].strip()
        if not payload["full_name"]:
            raise ValueError("Actor full_name is required")
        return await self.repository.create(payload)

    async def update_actor(self, actor_id: UUID, actor_data: ActorUpdate):
        payload = actor_data.model_dump(exclude_unset=True)
        if "full_name" in payload:
            payload["full_name"] = payload["full_name"].strip()
            if not payload["full_name"]:
                raise ValueError("Actor full_name is required")
        if not payload:
            return await self.repository.get_by_id(actor_id)
        return await self.repository.update(actor_id, payload)
