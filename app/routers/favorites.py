from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas import FavoriteCreate, FavoriteResponse
from app.services import FavoriteService

router = APIRouter(prefix="/v1/favorites", tags=["favorites"])


@router.post("/", response_model=FavoriteResponse)
async def add_favorite(
    favorite_data: FavoriteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorite_service = FavoriteService(db)
    favorite = await favorite_service.add_favorite(current_user.id, favorite_data)
    if not favorite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already in favorites or item not found",
        )
    return FavoriteResponse.model_validate(favorite)


@router.delete("/", response_model=dict)
async def remove_favorite(
    movie_id: UUID = None,
    event_id: UUID = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not movie_id and not event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either movie_id or event_id must be provided",
        )

    favorite_service = FavoriteService(db)
    success = await favorite_service.remove_favorite(current_user.id, movie_id, event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Favorite not found")

    return {"message": "Removed from favorites"}


@router.get("/me", response_model=List[FavoriteResponse])
async def get_user_favorites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorite_service = FavoriteService(db)
    favorites = await favorite_service.get_user_favorites(current_user.id)
    return [FavoriteResponse.model_validate(favorite) for favorite in favorites]
