from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models import User
from app.schemas import ActorCreate, ActorPageResponse, ActorResponse, ActorUpdate
from app.services import ActorService

public_router = APIRouter(prefix="/v1/actors", tags=["actors"])
admin_router = APIRouter(prefix="/v1/admin/actors", tags=["admin-actors"])


@public_router.get("/", response_model=ActorPageResponse)
async def get_actors(
    query: Optional[str] = Query(None, description="Search by actor name"),
    offset: int = Query(0, ge=0),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    actors, total = await actor_service.list_actors(query=query, skip=offset, limit=limit)
    return ActorPageResponse(
        items=[ActorResponse.model_validate(actor) for actor in actors],
        total=total,
        offset=offset,
        limit=limit,
        has_more=offset + limit < total,
    )


@public_router.get("/{actor_id}", response_model=ActorResponse)
async def get_actor(
    actor_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    actor = await actor_service.get_by_id(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    return ActorResponse.model_validate(actor)


@admin_router.post("/", response_model=ActorResponse, status_code=status.HTTP_201_CREATED)
async def create_actor(
    actor_data: ActorCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    try:
        actor = await actor_service.create_actor(actor_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ActorResponse.model_validate(actor)


@admin_router.patch("/{actor_id}", response_model=ActorResponse)
async def update_actor(
    actor_id: UUID,
    actor_data: ActorUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    try:
        actor = await actor_service.update_actor(actor_id, actor_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    return ActorResponse.model_validate(actor)


@admin_router.delete("/{actor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_actor(
    actor_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    actor_service = ActorService(db)
    deleted = await actor_service.delete(actor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Actor not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
