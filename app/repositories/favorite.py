from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models import Favorite, Movie, Event
from app.repositories.base import BaseRepository


class FavoriteRepository(BaseRepository[Favorite]):
    def __init__(self, db: AsyncSession):
        super().__init__(Favorite, db)

    async def get_user_favorites(self, user_id: UUID) -> List[Favorite]:
        result = await self.db.execute(
            select(Favorite)
            .options(
                selectinload(Favorite.movie).selectinload(Movie.category),
                selectinload(Favorite.event).selectinload(Event.venue)
            )
            .where(Favorite.user_id == user_id)
            .order_by(Favorite.created_at.desc())
        )
        return result.scalars().all()

    async def is_favorited(self, user_id: UUID, movie_id: Optional[UUID] = None, event_id: Optional[UUID] = None) -> bool:
        conditions = [Favorite.user_id == user_id]
        if movie_id:
            conditions.append(Favorite.movie_id == movie_id)
        if event_id:
            conditions.append(Favorite.event_id == event_id)

        result = await self.db.execute(
            select(Favorite.id).where(and_(*conditions))
        )
        return result.scalar_one_or_none() is not None

    async def remove_favorite(self, user_id: UUID, movie_id: Optional[UUID] = None, event_id: Optional[UUID] = None) -> bool:
        conditions = [Favorite.user_id == user_id]
        if movie_id:
            conditions.append(Favorite.movie_id == movie_id)
        if event_id:
            conditions.append(Favorite.event_id == event_id)

        result = await self.db.execute(
            select(Favorite).where(and_(*conditions))
        )
        favorite = result.scalar_one_or_none()
        if favorite:
            await self.db.delete(favorite)
            await self.db.commit()
            return True
        return False