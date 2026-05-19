import os
import tempfile
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.minio import build_public_object_url, upload_file
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import (
    EventCategoryCreate,
    EventCategoryPageResponse,
    EventCategoryResponse,
    EventCategoryUpdate,
    EventCreate,
    EventListResponse,
    EventPageResponse,
    EventReviewResponse,
    EventReviewsSummaryResponse,
    EventResponse,
    EventSeatCreate,
    EventSeatResponse,
    EventSeatUpdate,
    EventSessionCreate,
    EventSessionResponse,
    EventSessionUpdate,
    EventType,
    EventUpdate,
)
from app.schemas.event import _storage_path_from_url, normalize_event_type
from app.services import EventCategoryService, EventReviewService, EventService

public_router = APIRouter(prefix="/v1/events", tags=["events"])
admin_router = APIRouter(prefix="/v1/admin/events", tags=["admin-events"])


def _resolve_offset(offset: int, skip: Optional[int]) -> int:
    return skip if skip is not None else offset


def _to_event_list_response(event) -> EventListResponse:
    upcoming_sessions = sorted(getattr(event, "sessions", []) or [], key=lambda item: item.starts_at)
    next_session = upcoming_sessions[0] if upcoming_sessions else None
    seat_prices = [
        seat.price
        for session in upcoming_sessions
        if session.pricing_type == "per_seat"
        for seat in (session.seats or [])
    ]
    min_price = min(seat_prices) if seat_prices else min(
        (session.base_price for session in upcoming_sessions),
        default=getattr(event, "price", None),
    )

    return EventListResponse(
        id=event.id,
        title=event.title,
        type=event.type,
        event_type=event.event_type or event.type,
        poster_url=event.poster_url or event.image_url,
        image_url=event.image_url or event.poster_url,
        storage_path=getattr(event, "storage_path", None),
        city=event.city,
        category=EventCategoryResponse.model_validate(event.category) if event.category else None,
        next_session_at=next_session.starts_at if next_session else getattr(event, "start_datetime", None),
        min_price=min_price,
        average_rating=event.average_rating,
        is_active=event.is_active,
        start_datetime=getattr(event, "start_datetime", None),
        venue=event.venue,
        price=getattr(event, "price", None),
        available_seats=getattr(event, "available_seats", None),
    )


def _normalize_type_filter(type_filter: Optional[EventType], event_type: Optional[EventType]) -> Optional[str]:
    selected = type_filter or event_type
    return normalize_event_type(selected.value) if selected else None


def _event_media_url(event) -> Optional[str]:
    storage_path = getattr(event, "storage_path", None)
    if storage_path:
        return build_public_object_url(settings.MINIO_BUCKET_NAME, storage_path)

    poster_url = getattr(event, "poster_url", None) or getattr(event, "image_url", None)
    if not poster_url:
        return None

    inferred_storage_path = _storage_path_from_url(poster_url)
    if inferred_storage_path:
        return build_public_object_url(settings.MINIO_BUCKET_NAME, inferred_storage_path)

    return poster_url


@public_router.get("/", response_model=list[EventListResponse])
async def get_events(
    city: Optional[str] = Query(None, description="Filter by city"),
    query: Optional[str] = Query(None, description="Search query"),
    type_filter: Optional[EventType] = Query(None, alias="type", description="Filter by event type"),
    event_type: Optional[EventType] = Query(None, description="Deprecated alias for type"),
    category_id: Optional[UUID] = Query(None, description="Filter by category id"),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    skip: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    events = await event_service.get_upcoming_events(
        city=city,
        query=query,
        event_type=_normalize_type_filter(type_filter, event_type),
        category_id=category_id,
        category_slug=category,
        skip=skip,
        limit=limit,
    )
    return [_to_event_list_response(event) for event in events]


@public_router.get("/sessions/{session_id}/seats", response_model=list[EventSeatResponse])
async def get_session_seats(
    session_id: UUID,
    only_available: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    seats = await event_service.get_session_seats(session_id, only_available=only_available)
    return [EventSeatResponse.model_validate(seat) for seat in seats]


@public_router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.get_event_with_details(event_id)
    if not event or not event.is_active:
        raise HTTPException(status_code=404, detail="Event not found")
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


@public_router.get("/{event_id}/seats", response_model=list[EventSeatResponse])
async def get_event_seats(
    event_id: UUID,
    session_id: Optional[UUID] = Query(None),
    only_available: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.get_event_with_details(event_id)
    if not event or not event.is_active:
        raise HTTPException(status_code=404, detail="Event not found")

    if session_id:
        seats = await event_service.get_session_seats(session_id, only_available=only_available)
        return [EventSeatResponse.model_validate(seat) for seat in seats]

    responses = []
    for session in event.sessions:
        for seat in session.seats:
            if not only_available or seat.is_available:
                responses.append(EventSeatResponse.model_validate(seat))
    return responses


@public_router.get("/{event_id}/reviews", response_model=list[EventReviewResponse])
async def get_cinema_event_reviews(
    event_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.get_event_with_details(event_id)
    if not event or not event.is_active:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.type != "cinema":
        raise HTTPException(status_code=400, detail="Reviews are only available for cinema events")

    review_service = EventReviewService(db)
    reviews = await review_service.get_event_reviews(event_id, skip, limit)
    return [EventReviewResponse.model_validate(review) for review in reviews]


@public_router.get("/{event_id}/reviews/summary", response_model=EventReviewsSummaryResponse)
async def get_cinema_event_reviews_summary(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.get_event_with_details(event_id)
    if not event or not event.is_active:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.type != "cinema":
        raise HTTPException(status_code=400, detail="Reviews are only available for cinema events")
    return EventReviewsSummaryResponse(
        average_rating=event.average_rating,
        reviews_count=len(event.reviews or []),
    )


@admin_router.get("/categories", response_model=EventCategoryPageResponse)
async def list_event_categories(
    query: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Alias for query"),
    offset: int = Query(0, ge=0),
    skip: Optional[int] = Query(None, ge=0, description="Deprecated alias for offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = EventCategoryService(db)
    resolved_query = q if q is not None else query
    resolved_offset = _resolve_offset(offset, skip)
    items, total = await category_service.list_categories(
        query=resolved_query,
        skip=resolved_offset,
        limit=limit,
    )
    return EventCategoryPageResponse(
        items=[EventCategoryResponse.model_validate(item) for item in items],
        total=total,
        offset=resolved_offset,
        limit=limit,
        has_more=resolved_offset + limit < total,
    )


@admin_router.post("/categories", response_model=EventCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_event_category(
    category_data: EventCategoryCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = EventCategoryService(db)
    try:
        category = await category_service.create_category(category_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventCategoryResponse.model_validate(category)


@admin_router.patch("/categories/{category_id}", response_model=EventCategoryResponse)
async def update_event_category(
    category_id: UUID,
    category_data: EventCategoryUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = EventCategoryService(db)
    try:
        category = await category_service.update_category(category_id, category_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not category:
        raise HTTPException(status_code=404, detail="Event category not found")
    return EventCategoryResponse.model_validate(category)


@admin_router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_category(
    category_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    category_service = EventCategoryService(db)
    deleted = await category_service.delete(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Event category not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/sessions/{session_id}/seats", response_model=list[EventSeatResponse])
async def admin_get_session_seats(
    session_id: UUID,
    only_available: bool = Query(False),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    seats = await event_service.get_session_seats(session_id, only_available=only_available)
    return [EventSeatResponse.model_validate(seat) for seat in seats]


@admin_router.post("/sessions/{session_id}/seats", response_model=EventSeatResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_seat(
    session_id: UUID,
    seat_data: EventSeatCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    try:
        seat = await event_service.create_seat(session_id, seat_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventSeatResponse.model_validate(seat)


@admin_router.post("/sessions/{session_id}/seats/bulk", response_model=list[EventSeatResponse], status_code=status.HTTP_201_CREATED)
async def admin_bulk_create_seats(
    session_id: UUID,
    seats_data: list[EventSeatCreate],
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    try:
        seats = await event_service.bulk_create_seats(session_id, seats_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [EventSeatResponse.model_validate(s) for s in seats]


@admin_router.patch("/seats/{seat_id}", response_model=EventSeatResponse)
async def admin_update_seat(
    seat_id: UUID,
    seat_data: EventSeatUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    seat = await event_service.update_seat(seat_id, seat_data)
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    return EventSeatResponse.model_validate(seat)


@admin_router.delete("/seats/{seat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_seat(
    seat_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    deleted = await event_service.delete_seat(seat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Seat not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@admin_router.get("/", response_model=EventPageResponse)
async def admin_get_events(
    type_filter: Optional[EventType] = Query(None, alias="type"),
    event_type: Optional[EventType] = Query(None, description="Deprecated alias for type"),
    city: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    skip: Optional[int] = Query(None, ge=0, description="Deprecated alias for offset"),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    resolved_offset = _resolve_offset(offset, skip)
    event_service = EventService(db)
    events, total = await event_service.list_events(
        event_type=_normalize_type_filter(type_filter, event_type),
        city=city,
        query=query,
        category_id=category_id,
        skip=resolved_offset,
        limit=limit,
    )
    return EventPageResponse(
        items=[_to_event_list_response(event) for event in events],
        total=total,
        offset=resolved_offset,
        limit=limit,
        has_more=resolved_offset + limit < total,
    )


@admin_router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    try:
        event = await event_service.create_event(event_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


@admin_router.post("/{event_id}/poster", response_model=EventResponse)
async def upload_event_poster(
    event_id: UUID,
    poster: UploadFile = File(...),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if poster.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid poster format. Use image/jpeg, image/png or image/webp")

    suffix = Path(poster.filename or "").suffix or ".jpg"
    poster_key = f"events/posters/{uuid4()}{suffix}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await poster.read())
        temp_path = temp_file.name

    try:
        poster_url = await upload_file(settings.MINIO_BUCKET_NAME, poster_key, temp_path, content_type=poster.content_type)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    event_service = EventService(db)
    event = await event_service.update_event(event_id, EventUpdate(storage_path=poster_key, poster_url=poster_url))
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


@admin_router.post("/{event_id}/trailer", response_model=EventResponse)
async def upload_event_trailer(
    event_id: UUID,
    trailer: UploadFile = File(...),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if trailer.content_type not in ["video/mp4", "video/x-matroska"]:
        raise HTTPException(status_code=400, detail="Invalid trailer format. Use video/mp4 or video/x-matroska")

    suffix = Path(trailer.filename or "").suffix or ".mp4"
    trailer_key = f"events/trailers/{uuid4()}{suffix}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(await trailer.read())
        temp_path = temp_file.name

    try:
        trailer_url = await upload_file(settings.MINIO_BUCKET_NAME, trailer_key, temp_path, content_type=trailer.content_type)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    event_service = EventService(db)
    event = await event_service.update_event(event_id, EventUpdate(trailer_url=trailer_url))
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


@admin_router.get("/{event_id}/sessions", response_model=list[EventSessionResponse])
async def admin_get_event_sessions(
    event_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    sessions = await event_service.get_event_sessions(event_id)
    return [EventSessionResponse.model_validate(session) for session in sessions]


@admin_router.post("/{event_id}/sessions", response_model=EventSessionResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_session(
    event_id: UUID,
    session_data: EventSessionCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    try:
        session = await event_service.create_session(event_id, session_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventSessionResponse.model_validate(session)


@admin_router.patch("/sessions/{session_id}", response_model=EventSessionResponse)
async def admin_update_session(
    session_id: UUID,
    session_data: EventSessionUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    session = await event_service.update_session(session_id, session_data)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return EventSessionResponse.model_validate(session)


@admin_router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_session(
    session_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    deleted = await event_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


@admin_router.put("/{event_id}", response_model=EventResponse)
@admin_router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    event_data: EventUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    try:
        event = await event_service.update_event(event_id, event_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


@admin_router.patch("/{event_id}/status", response_model=EventResponse)
async def update_event_status(
    event_id: UUID,
    is_active: bool,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    event_service = EventService(db)
    event = await event_service.set_active(event_id, is_active)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    response = EventResponse.model_validate(event)
    media_url = _event_media_url(event)
    if media_url:
        response.poster_url = media_url
        response.image_url = media_url
    return response


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
