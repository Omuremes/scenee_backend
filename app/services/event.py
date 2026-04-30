import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    EventCategoryRepository,
    EventRepository,
    EventSeatRepository,
    EventSessionRepository,
    VenueRepository,
)
from app.schemas import (
    EventCategoryCreate,
    EventCategoryUpdate,
    EventCreate,
    EventSeatCreate,
    EventSeatUpdate,
    EventSessionCreate,
    EventSessionUpdate,
    EventUpdate,
)
from app.schemas.event import normalize_event_type
from app.services.base import BaseService


SEATING_EVENT_TYPES = {"concerts", "stand-up", "sports"}
NON_SEATING_EVENT_TYPES = {"kids", "events"}


def _dump_schema(schema) -> dict:
    return schema.model_dump(exclude_unset=True) if hasattr(schema, "model_dump") else schema.dict(exclude_unset=True)


class EventCategoryService(BaseService[EventCategoryRepository]):
    def __init__(self, db: AsyncSession):
        repository = EventCategoryRepository(db)
        super().__init__(repository)

    @staticmethod
    def _normalize_slug(name: str, slug: Optional[str]) -> str:
        source = (slug or name).strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "-", source).strip("-")
        if not normalized:
            raise ValueError("Category slug cannot be empty")
        return normalized[:100]

    async def create_category(self, category_data: EventCategoryCreate):
        name = category_data.name.strip()
        if not name:
            raise ValueError("Category name is required")
        slug = self._normalize_slug(name, category_data.slug)
        if await self.repository.get_by_name(name):
            raise ValueError("Event category with this name already exists")
        if await self.repository.get_by_slug(slug):
            raise ValueError("Event category with this slug already exists")
        return await self.repository.create({"name": name, "slug": slug})

    async def list_categories(self, query: Optional[str] = None, skip: int = 0, limit: int = 20):
        items = await self.repository.list_categories(query=query, skip=skip, limit=limit)
        total = await self.repository.count_categories(query=query)
        return items, total

    async def update_category(self, category_id: UUID, category_data: EventCategoryUpdate):
        current = await self.repository.get_by_id(category_id)
        if not current:
            return None

        payload = category_data.model_dump(exclude_unset=True)
        if not payload:
            return current

        name = current.name
        slug = current.slug
        if "name" in payload:
            name = payload["name"].strip()
            if not name:
                raise ValueError("Category name is required")
            existing = await self.repository.get_by_name(name)
            if existing and existing.id != category_id:
                raise ValueError("Event category with this name already exists")

        if "slug" in payload or "name" in payload:
            slug = self._normalize_slug(name, payload.get("slug", slug))
            existing = await self.repository.get_by_slug(slug)
            if existing and existing.id != category_id:
                raise ValueError("Event category with this slug already exists")

        return await self.repository.update(category_id, {"name": name, "slug": slug})


class EventService(BaseService[EventRepository]):
    def __init__(self, db: AsyncSession):
        repository = EventRepository(db)
        super().__init__(repository)
        self.category_repository = EventCategoryRepository(db)
        self.session_repository = EventSessionRepository(db)
        self.seat_repository = EventSeatRepository(db)

    async def get_event_with_details(self, event_id: UUID):
        return await self.repository.get_with_details(event_id)

    async def get_upcoming_events(
        self,
        city: Optional[str] = None,
        event_type: Optional[str] = None,
        category_id: Optional[UUID] = None,
        category_slug: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[dict]:
        normalized_type = normalize_event_type(event_type)
        return await self.repository.get_upcoming_events(
            city=city,
            event_type=normalized_type,
            category_id=category_id,
            category_slug=category_slug,
            skip=skip,
            limit=limit,
        )

    async def list_events(
        self,
        event_type: Optional[str] = None,
        city: Optional[str] = None,
        category_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[List[dict], int]:
        normalized_type = normalize_event_type(event_type)
        events = await self.repository.list_events(normalized_type, city, category_id, skip, limit)
        total = await self.repository.count_events(normalized_type, city, category_id)
        return events, total

    async def create_event(self, event_data: EventCreate) -> dict:
        if event_data.category_id and not await self.category_repository.exists(event_data.category_id):
            raise ValueError("Event category not found")

        payload = event_data.model_dump(exclude={"sessions"})
        payload = self._normalize_event_payload(payload)
        sessions = event_data.sessions or []
        self._validate_sessions(payload["type"], sessions)
        self._apply_legacy_session_fields(payload, sessions)

        event = await self.repository.create(payload)
        for session_data in sessions:
            await self.create_session(event.id, session_data)
        return await self.repository.get_with_details(event.id)

    async def update_event(self, event_id: UUID, event_data: EventUpdate) -> Optional[dict]:
        if event_data.category_id and not await self.category_repository.exists(event_data.category_id):
            raise ValueError("Event category not found")

        payload = event_data.model_dump(exclude_unset=True)
        if not payload:
            return await self.repository.get_with_details(event_id)
        payload = self._normalize_event_payload(payload, partial=True)
        event = await self.repository.update(event_id, payload)
        if not event:
            return None
        return await self.repository.get_with_details(event.id)

    async def set_active(self, event_id: UUID, is_active: bool):
        event = await self.repository.update(event_id, {"is_active": is_active})
        if not event:
            return None
        return await self.repository.get_with_details(event.id)

    async def create_session(self, event_id: UUID, session_data: EventSessionCreate):
        event = await self.repository.get_by_id(event_id)
        if not event:
            raise ValueError("Event not found")
        self._validate_sessions(event.type, [session_data])

        payload = session_data.model_dump(exclude={"seats"})
        if "pricing_type" in payload and hasattr(payload["pricing_type"], "value"):
            payload["pricing_type"] = payload["pricing_type"].value
        payload["event_id"] = event_id
        session = await self.session_repository.create(payload)
        for seat_data in session_data.seats:
            await self.create_seat(session.id, seat_data)
        await self._sync_legacy_event_from_sessions(event_id)
        return await self.session_repository.get_with_details(session.id)

    async def update_session(self, session_id: UUID, session_data: EventSessionUpdate):
        payload = session_data.model_dump(exclude_unset=True)
        if not payload:
            return await self.session_repository.get_with_details(session_id)
        if "pricing_type" in payload and hasattr(payload["pricing_type"], "value"):
            payload["pricing_type"] = payload["pricing_type"].value
        session = await self.session_repository.update(session_id, payload)
        if not session:
            return None
        await self._sync_legacy_event_from_sessions(session.event_id)
        return await self.session_repository.get_with_details(session.id)

    async def delete_session(self, session_id: UUID) -> bool:
        session = await self.session_repository.get_by_id(session_id)
        if not session:
            return False
        event_id = session.event_id
        deleted = await self.session_repository.delete(session_id)
        if deleted:
            await self._sync_legacy_event_from_sessions(event_id)
        return deleted

    async def get_event_sessions(self, event_id: UUID):
        return await self.session_repository.get_event_sessions(event_id)

    async def create_seat(self, session_id: UUID, seat_data: EventSeatCreate):
        session = await self.session_repository.get_with_details(session_id)
        if not session:
            raise ValueError("Session not found")
        if session.event.type not in SEATING_EVENT_TYPES:
            raise ValueError("Seats are only supported for concerts, stand-up, and sports events")
        payload = seat_data.model_dump()
        payload["session_id"] = session_id
        return await self.seat_repository.create(payload)

    async def update_seat(self, seat_id: UUID, seat_data: EventSeatUpdate):
        payload = seat_data.model_dump(exclude_unset=True)
        if not payload:
            return await self.seat_repository.get_by_id(seat_id)
        return await self.seat_repository.update(seat_id, payload)

    async def delete_seat(self, seat_id: UUID) -> bool:
        return await self.seat_repository.delete(seat_id)

    async def get_session_seats(self, session_id: UUID, only_available: bool = False):
        return await self.seat_repository.get_session_seats(session_id, only_available)

    async def update_available_seats(self, event_id: UUID, seats_booked: int) -> bool:
        event = await self.repository.get_by_id(event_id)
        if not event:
            return False

        available = event.available_seats or 0
        if seats_booked > 0 and available < seats_booked:
            return False

        await self.repository.update(event_id, {"available_seats": available - seats_booked})
        return True

    @staticmethod
    def _normalize_event_payload(payload: dict, partial: bool = False) -> dict:
        if "type" in payload and payload["type"] is not None:
            payload["type"] = normalize_event_type(payload["type"])
            payload["event_type"] = payload["type"]
        elif "event_type" in payload and payload["event_type"] is not None:
            payload["type"] = normalize_event_type(payload["event_type"])
            payload["event_type"] = payload["type"]

        if "poster_url" in payload and payload["poster_url"] is not None:
            payload["image_url"] = payload["poster_url"]
        elif "image_url" in payload and payload["image_url"] is not None:
            payload["poster_url"] = payload["image_url"]

        if not partial:
            payload.setdefault("city", "")
            payload.setdefault("is_active", True)
            payload.setdefault("available_seats", payload.get("max_capacity") or 0)
            payload.setdefault("price", 0.0)
            payload.setdefault("max_capacity", 0)

        return payload

    @staticmethod
    def _validate_sessions(event_type: str, sessions: List[EventSessionCreate]) -> None:
        for session in sessions:
            if event_type in NON_SEATING_EVENT_TYPES and session.seats:
                raise ValueError("Kids and events sessions cannot contain seats")
            if event_type == "cinema" and session.pricing_type == "per_seat" and not session.seats:
                raise ValueError("Per-seat cinema sessions must define seats")

    @staticmethod
    def _apply_legacy_session_fields(payload: dict, sessions: List[EventSessionCreate]) -> None:
        if not sessions:
            payload.setdefault("start_datetime", datetime.utcnow())
            payload.setdefault("price", payload.get("price") or 0.0)
            return

        first_session = sorted(sessions, key=lambda item: item.starts_at)[0]
        payload["start_datetime"] = first_session.starts_at
        payload["end_datetime"] = first_session.ends_at
        payload["price"] = first_session.base_price
        payload["max_capacity"] = sum(len(session.seats) for session in sessions) or payload.get("max_capacity") or 0
        payload["available_seats"] = sum(
            1 for session in sessions for seat in session.seats if seat.is_available
        ) or payload["max_capacity"]

    async def _sync_legacy_event_from_sessions(self, event_id: UUID) -> None:
        sessions = await self.session_repository.get_event_sessions(event_id)
        if not sessions:
            return
        first_session = sessions[0]
        max_capacity = sum(len(session.seats) for session in sessions)
        available = sum(1 for session in sessions for seat in session.seats if seat.is_available)
        await self.repository.update(
            event_id,
            {
                "start_datetime": first_session.starts_at,
                "end_datetime": first_session.ends_at,
                "price": first_session.base_price,
                "max_capacity": max_capacity,
                "available_seats": available or max_capacity,
            },
        )


class VenueService(BaseService[VenueRepository]):
    def __init__(self, db: AsyncSession):
        repository = VenueRepository(db)
        super().__init__(repository)

    async def get_venues_by_city(self, city: str) -> List[dict]:
        return await self.repository.get_by_city(city)
