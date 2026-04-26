from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import EventRepository, VenueRepository
from app.schemas import EventCreate, EventUpdate
from app.services.base import BaseService


class EventService(BaseService[EventRepository]):
    def __init__(self, db: AsyncSession):
        repository = EventRepository(db)
        super().__init__(repository)

    async def get_event_with_details(self, event_id: UUID) -> Optional[dict]:
        return await self.repository.get_with_details(event_id)

    async def get_upcoming_events(
        self,
        city: Optional[str] = None,
        event_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[dict]:
        return await self.repository.get_upcoming_events(city, event_type, skip, limit)

    async def list_events(self, skip: int = 0, limit: int = 20) -> tuple[List[dict], int]:
        events = await self.repository.list_events(skip, limit)
        total = await self.repository.count_events()
        return events, total

    async def create_event(self, event_data: EventCreate) -> dict:
        create_data = event_data.model_dump()
        create_data["available_seats"] = event_data.max_capacity
        event = await self.repository.create(create_data)
        return await self.repository.get_with_details(event.id)

    async def update_event(self, event_id: UUID, event_data: EventUpdate) -> Optional[dict]:
        update_data = event_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.repository.get_with_details(event_id)

        event = await self.repository.update(event_id, update_data)
        if not event:
            return None
        return await self.repository.get_with_details(event.id)

    async def update_available_seats(self, event_id: UUID, seats_booked: int) -> bool:
        event = await self.repository.get_by_id(event_id)
        if not event or event.available_seats < seats_booked:
            return False

        await self.repository.update(event_id, {"available_seats": event.available_seats - seats_booked})
        return True


class VenueService(BaseService[VenueRepository]):
    def __init__(self, db: AsyncSession):
        repository = VenueRepository(db)
        super().__init__(repository)

    async def get_venues_by_city(self, city: str) -> List[dict]:
        return await self.repository.get_by_city(city)
