from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Actor
from app.repositories.base import BaseRepository


class ActorRepository(BaseRepository[Actor]):
    def __init__(self, db: AsyncSession):
        super().__init__(Actor, db)

    def _apply_query(self, stmt, query: Optional[str]):
        normalized_query = query.strip() if query else None
        if not normalized_query:
            return stmt

        search_document = func.concat_ws(
            " ",
            func.coalesce(Actor.full_name, ""),
            func.coalesce(Actor.bio, ""),
        )
        search_vector = func.to_tsvector("simple", search_document)
        search_query = func.websearch_to_tsquery("simple", normalized_query)
        ilike_query = f"%{normalized_query}%"

        return stmt.where(
            or_(
                search_vector.op("@@")(search_query),
                Actor.full_name.ilike(ilike_query),
                Actor.bio.ilike(ilike_query),
            )
        )

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
        stmt = self._apply_query(stmt, query)
        result = await self.db.execute(stmt.offset(skip).limit(limit))
        return result.scalars().all()

    async def count_actors(self, query: Optional[str] = None) -> int:
        stmt = select(func.count(Actor.id))
        stmt = self._apply_query(stmt, query)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())
