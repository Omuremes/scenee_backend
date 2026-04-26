from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import EventCreate, EventListResponse, EventResponse, EventType, EventUpdate
from app.services import EventService

public_router = APIRouter(prefix="/public/events", tags=["events"])
admin_router = APIRouter(prefix="/v1admin/events", tags=["admin-events"])


@public_router.get("/", response_model=List[EventListResponse])
async def get_events(
    city: Optional[str] = Query(None, description="Filter by city"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    events = await event_service.get_upcoming_events(
        city,
        event_type.value if event_type else None,
        skip,
        limit,
    )
    return [EventListResponse.model_validate(event) for event in events]


@public_router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.get_event_with_details(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse.model_validate(event)


@admin_router.post("/", response_model=EventResponse)
async def create_event(
    event_data: EventCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.create_event(event_data)
    return EventResponse.model_validate(event)


@admin_router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    event_data: EventUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.update_event(event_id, event_data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse.model_validate(event)
