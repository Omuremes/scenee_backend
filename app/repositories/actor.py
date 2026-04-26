from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Actor
from app.repositories.base import BaseRepository


class ActorRepository(BaseRepository[Actor]):
    def __init__(self, db: AsyncSession):
        super().__init__(Actor, db)

    async def get_by_ids(self, actor_ids: Iterable[UUID]) -> List[Actor]:
        actor_ids = list(actor_ids)
        if not actor_ids:
            return []
        result = await self.db.execute(select(Actor).where(Actor.id.in_(actor_ids)))
        return result.scalars().all()

    async def list_actors(
        self,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Actor]:
        stmt = select(Actor).order_by(Actor.full_name.asc(), Actor.id.asc())
        if query:
            stmt = stmt.where(Actor.full_name.ilike(f"%{query.strip()}%"))
        result = await self.db.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()

    async def count_actors(self, query: Optional[str] = None) -> int:
        stmt = select(func.count(Actor.id))
        if query:
            stmt = stmt.where(Actor.full_name.ilike(f"%{query.strip()}%"))
        result = await self.db.execute(stmt)
        return int(result.scalar_one())
