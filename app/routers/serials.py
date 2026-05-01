import tempfile
import os
from pathlib import Path
from typing import List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.core.config import settings
from app.core.minio import upload_file
from app.models.user import User
from app.schemas.serial import (
    SerialCreate, SerialUpdate, SerialResponse, 
    SeasonCreate, SeasonUpdate, SeasonResponse,
    SerialEpisodeCreate, SerialEpisodeUpdate, SerialEpisodeResponse,
    SerialPageResponse, SerialListResponse
)
from app.services.serial import SerialService

public_router = APIRouter(prefix="/v1/serials", tags=["serials"])
admin_router = APIRouter(prefix="/v1/admin/serials", tags=["admin-serials"])

@public_router.get("/", response_model=SerialPageResponse)
async def get_serials(
    query: str | None = None,
    category_id: UUID | None = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    items, total = await service.list_serials(query=query, category_id=category_id, skip=skip, limit=limit)
    return SerialPageResponse(
        items=[SerialListResponse.model_validate(item) for item in items],
        total=total,
        offset=skip,
        limit=limit,
        has_more=skip + limit < total
    )

@public_router.get("/popular", response_model=List[SerialListResponse])
async def get_popular_serials(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    items = await service.get_popular_serials(limit=limit)
    return [SerialListResponse.model_validate(item) for item in items]

@public_router.get("/new", response_model=List[SerialListResponse])
async def get_new_serials(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    items = await service.get_new_serials(limit=limit)
    return [SerialListResponse.model_validate(item) for item in items]

@public_router.get("/{serial_id}", response_model=SerialResponse)
async def get_serial_detail(
    serial_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    serial = await service.get_by_id(serial_id)
    if not serial:
        raise HTTPException(status_code=404, detail="Serial not found")
    return SerialResponse.model_validate(serial)

@public_router.get("/{serial_id}/seasons/{season_number}/episodes", response_model=List[SerialEpisodeResponse])
async def get_serial_season_episodes(
    serial_id: UUID,
    season_number: int,
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    episodes = await service.get_season_episodes(serial_id, season_number)
    if episodes is None:
        raise HTTPException(status_code=404, detail="Serial or season not found")
    return [SerialEpisodeResponse.model_validate(ep) for ep in episodes]


# Admin Routes

@admin_router.post("/", response_model=SerialResponse, status_code=status.HTTP_201_CREATED)
async def create_serial(
    data: SerialCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    return await service.create(data)

@admin_router.get("/{serial_id}", response_model=SerialResponse)
async def get_serial(
    serial_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    serial = await service.get_by_id(serial_id)
    if not serial:
        raise HTTPException(status_code=404, detail="Serial not found")
    return serial

@admin_router.patch("/{serial_id}", response_model=SerialResponse)
async def update_serial(
    serial_id: UUID,
    data: SerialUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    serial = await service.update(serial_id, data)
    if not serial:
        raise HTTPException(status_code=404, detail="Serial not found")
    return serial

@admin_router.delete("/{serial_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_serial(
    serial_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    if not await service.delete(serial_id):
        raise HTTPException(status_code=404, detail="Serial not found")

@admin_router.post("/{serial_id}/seasons/", response_model=SeasonResponse, status_code=status.HTTP_201_CREATED)
async def add_season(
    serial_id: UUID,
    data: SeasonCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    return await service.add_season(serial_id, data)

@admin_router.patch("/{serial_id}/seasons/{season_id}", response_model=SeasonResponse)
async def update_season(
    serial_id: UUID,
    season_id: UUID,
    data: SeasonUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    season = await service.update_season(season_id, data)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    return season

@admin_router.delete("/{serial_id}/seasons/{season_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_season(
    serial_id: UUID,
    season_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    if not await service.delete_season(season_id):
        raise HTTPException(status_code=404, detail="Season not found")

@admin_router.post("/seasons/{season_id}/episodes/", response_model=SerialEpisodeResponse, status_code=status.HTTP_201_CREATED)
async def add_episode(
    season_id: UUID,
    data: SerialEpisodeCreate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    return await service.add_episode(season_id, data)

@admin_router.patch("/seasons/{season_id}/episodes/{episode_id}", response_model=SerialEpisodeResponse)
async def update_episode(
    season_id: UUID,
    episode_id: UUID,
    data: SerialEpisodeUpdate,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    episode = await service.update_episode(episode_id, data)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode

@admin_router.delete("/seasons/{season_id}/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode(
    season_id: UUID,
    episode_id: UUID,
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    if not await service.delete_episode(episode_id):
        raise HTTPException(status_code=404, detail="Episode not found")

@admin_router.post("/episodes/{episode_id}/upload")
async def upload_episode_file(
    episode_id: UUID,
    video_file: UploadFile = File(...),
    _current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    service = SerialService(db)
    episode = await service.repo.get_episode_by_id(episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    season = await service.repo.get_season_by_id(episode.season_id)
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    if video_file.content_type not in ["video/mp4", "video/x-matroska"]:
        raise HTTPException(status_code=400, detail="Invalid video format. Use video/mp4 or video/x-matroska")
        
    suffix = Path(video_file.filename or "video").suffix or ".mp4"
        
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await video_file.read())
            temp_path = temp_file.name

        bucket = settings.MINIO_BUCKET_NAME
        object_key = f"episodes/{season.serial_id}/{season.season_number}/{episode_id}{suffix}"
        
        await upload_file(
            bucket,
            object_key,
            temp_path,
            content_type=video_file.content_type or "video/mp4",
        )
        file_size = os.path.getsize(temp_path)
        
        episode_file = await service.save_episode_file(
            episode_id, bucket, object_key, file_size, video_file.content_type
        )
        
        return {"status": "success", "file_id": episode_file.id}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
