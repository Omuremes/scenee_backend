from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Event, EventCategory, EventSeat, EventSession, Venue
from app.repositories.base import BaseRepository


def _event_details_options():
    return (
        selectinload(Event.category),
        selectinload(Event.venue),
        selectinload(Event.sessions).selectinload(EventSession.seats),
        selectinload(Event.reviews),
    )


class EventCategoryRepository(BaseRepository[EventCategory]):
    def __init__(self, db: AsyncSession):
        super().__init__(EventCategory, db)

    async def get_by_name(self, name: str) -> Optional[EventCategory]:
        result = await self.db.execute(select(EventCategory).where(func.lower(EventCategory.name) == name.lower()))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[EventCategory]:
        result = await self.db.execute(select(EventCategory).where(EventCategory.slug == slug))
        return result.scalar_one_or_none()

    async def list_categories(self, query: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[EventCategory]:
        stmt = select(EventCategory)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(EventCategory.name.ilike(pattern) | EventCategory.slug.ilike(pattern))
        result = await self.db.execute(stmt.order_by(EventCategory.name.asc()).offset(skip).limit(limit))
        return result.scalars().all()

    async def count_categories(self, query: Optional[str] = None) -> int:
        stmt = select(func.count(EventCategory.id))
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(EventCategory.name.ilike(pattern) | EventCategory.slug.ilike(pattern))
        result = await self.db.execute(stmt)
        return int(result.scalar_one())


class EventRepository(BaseRepository[Event]):
    def __init__(self, db: AsyncSession):
        super().__init__(Event, db)

    @staticmethod
    def _apply_query(stmt, query: Optional[str]):
        if not query:
            return stmt
        pattern = f"%{query}%"
        return stmt.where(
            Event.title.ilike(pattern)
            | Event.description.ilike(pattern)
            | Event.city.ilike(pattern)
            | Event.category.has(
                EventCategory.name.ilike(pattern) | EventCategory.slug.ilike(pattern)
            )
        )

    async def get_with_details(self, event_id: UUID) -> Optional[Event]:
        result = await self.db.execute(
            select(Event)
            .options(*_event_details_options())
            .where(Event.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_upcoming_events(
        self,
        city: Optional[str] = None,
        query: Optional[str] = None,
        event_type: Optional[str] = None,
        category_id: Optional[UUID] = None,
        category_slug: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Event]:
        stmt = (
            select(Event)
            .options(*_event_details_options())
            .where(Event.is_active.is_(True))
            .where(Event.sessions.any(EventSession.starts_at >= datetime.utcnow()))
        )

        stmt = self._apply_query(stmt, query)
        if city:
            stmt = stmt.where(Event.city.ilike(f"%{city}%"))
        if event_type:
            stmt = stmt.where(Event.type == event_type)
        if category_id:
            stmt = stmt.where(Event.category_id == category_id)
        if category_slug:
            stmt = stmt.where(Event.category.has(EventCategory.slug == category_slug))

        result = await self.db.execute(
            stmt.order_by(Event.created_at.desc(), Event.id.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def list_events(
        self,
        event_type: Optional[str] = None,
        city: Optional[str] = None,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Event]:
        stmt = select(Event).options(*_event_details_options())
        stmt = self._apply_query(stmt, query)
        if event_type:
            stmt = stmt.where(Event.type == event_type)
        if city:
            stmt = stmt.where(Event.city.ilike(f"%{city}%"))
        if category_id:
            stmt = stmt.where(Event.category_id == category_id)
        result = await self.db.execute(
            stmt.order_by(Event.created_at.desc(), Event.id.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count_events(
        self,
        event_type: Optional[str] = None,
        city: Optional[str] = None,
        query: Optional[str] = None,
        category_id: Optional[UUID] = None,
    ) -> int:
        stmt = select(func.count(Event.id))
        stmt = self._apply_query(stmt, query)
        if event_type:
            stmt = stmt.where(Event.type == event_type)
        if city:
            stmt = stmt.where(Event.city.ilike(f"%{city}%"))
        if category_id:
            stmt = stmt.where(Event.category_id == category_id)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def get_events_by_venue(self, venue_id: UUID) -> List[Event]:
        result = await self.db.execute(select(Event).where(Event.venue_id == venue_id))
        return result.scalars().all()


class EventSessionRepository(BaseRepository[EventSession]):
    def __init__(self, db: AsyncSession):
        super().__init__(EventSession, db)

    async def get_with_details(self, session_id: UUID) -> Optional[EventSession]:
        result = await self.db.execute(
            select(EventSession)
            .options(selectinload(EventSession.event), selectinload(EventSession.seats))
            .where(EventSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_event_sessions(self, event_id: UUID) -> List[EventSession]:
        result = await self.db.execute(
            select(EventSession)
            .options(selectinload(EventSession.seats))
            .where(EventSession.event_id == event_id)
            .order_by(EventSession.starts_at.asc(), EventSession.id.desc())
        )
        return result.scalars().all()


class EventSeatRepository(BaseRepository[EventSeat]):
    def __init__(self, db: AsyncSession):
        super().__init__(EventSeat, db)

    async def get_session_seats(self, session_id: UUID, only_available: bool = False) -> List[EventSeat]:
        stmt = select(EventSeat).where(EventSeat.session_id == session_id)
        if only_available:
            stmt = stmt.where(EventSeat.is_available.is_(True))
        result = await self.db.execute(stmt.order_by(EventSeat.label.asc()))
        return result.scalars().all()

    async def reserve_seat(self, seat_id: UUID) -> Optional[EventSeat]:
        result = await self.db.execute(
            update(EventSeat)
            .where(EventSeat.id == seat_id, EventSeat.is_available.is_(True))
            .values(is_available=False)
            .returning(EventSeat)
        )
        await self.db.commit()
        return result.scalar_one_or_none()

    async def release_seat(self, seat_id: UUID) -> Optional[EventSeat]:
        result = await self.db.execute(
            update(EventSeat)
            .where(EventSeat.id == seat_id)
            .values(is_available=True)
            .returning(EventSeat)
        )
        await self.db.commit()
        return result.scalar_one_or_none()


class VenueRepository(BaseRepository[Venue]):
    def __init__(self, db: AsyncSession):
        super().__init__(Venue, db)

    async def get_by_city(self, city: str) -> List[Venue]:
        result = await self.db.execute(select(Venue).where(Venue.city.ilike(f"%{city}%")))
        return result.scalars().all()
