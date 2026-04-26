from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import EventCreate, EventListResponse, EventPageResponse, EventResponse, EventType, EventUpdate
from app.services import EventService

public_router = APIRouter(prefix="/public/events", tags=["events"])
admin_router = APIRouter(prefix="/v1admin/events", tags=["admin-events"])


def _resolve_offset(offset: int, skip: Optional[int]) -> int:
    return skip if skip is not None else offset


@public_router.get("/", response_model=list[EventListResponse])
async def get_events(
    city: Optional[str] = Query(None, description="Filter by city"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
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


@admin_router.get("/", response_model=EventPageResponse)
async def admin_get_events(
    offset: int = Query(0, ge=0, description="Pagination offset"),
    skip: Optional[int] = Query(None, ge=0, description="Deprecated alias for offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_offset = _resolve_offset(offset, skip)
    event_service = EventService(db)
    events, total = await event_service.list_events(resolved_offset, limit)
    return EventPageResponse(
        items=[EventListResponse.model_validate(event) for event in events],
        total=total,
        offset=resolved_offset,
        limit=limit,
        has_more=resolved_offset + limit < total,
    )


@admin_router.get("/{event_id}", response_model=EventResponse)
async def admin_get_event(
    event_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.get_event_with_details(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse.model_validate(event)


@admin_router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.create_event(event_data)
    return EventResponse.model_validate(event)


@admin_router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    event_data: EventUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.update_event(event_id, event_data)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventResponse.model_validate(event)


@admin_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    deleted = await event_service.delete(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
