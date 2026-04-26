from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Event, Venue
from app.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    def __init__(self, db: AsyncSession):
        super().__init__(Event, db)

    async def get_with_details(self, event_id: UUID) -> Optional[Event]:
        result = await self.db.execute(
            select(Event)
            .options(
                selectinload(Event.venue),
                selectinload(Event.reviews),
            )
            .where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_upcoming_events(
        self,
        city: Optional[str] = None,
        event_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Event]:
        stmt = select(Event).options(selectinload(Event.venue)).where(
            and_(
                Event.start_datetime > datetime.utcnow(),
                Event.is_active.is_(True),
            )
        )

        if city:
            stmt = stmt.where(Event.venue.has(Venue.city.ilike(f"%{city}%")))
        if event_type:
            stmt = stmt.where(Event.event_type == event_type)

        result = await self.db.execute(
            stmt.order_by(Event.start_datetime, Event.id.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def get_events_by_venue(self, venue_id: UUID) -> List[Event]:
        result = await self.db.execute(select(Event).where(Event.venue_id == venue_id))
        return result.scalars().all()

    async def list_events(self, skip: int = 0, limit: int = 20) -> List[Event]:
        result = await self.db.execute(
            select(Event)
            .options(selectinload(Event.venue))
            .order_by(Event.start_datetime.desc(), Event.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_events(self) -> int:
        result = await self.db.execute(select(func.count(Event.id)))
        return int(result.scalar_one())


class VenueRepository(BaseRepository[Venue]):
    def __init__(self, db: AsyncSession):
        super().__init__(Venue, db)

    async def get_by_city(self, city: str) -> List[Venue]:
        result = await self.db.execute(select(Venue).where(Venue.city.ilike(f"%{city}%")))
        return result.scalars().all()
