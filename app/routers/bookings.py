from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas import BookingCreate, BookingResponse
from app.services import BookingService

router = APIRouter(prefix="/v1/bookings", tags=["bookings"])


@router.post("/", response_model=BookingResponse)
async def create_booking(
    booking_data: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    booking_service = BookingService(db)
    booking = await booking_service.create_booking(current_user.id, booking_data)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough seats available or event not found",
        )
    return BookingResponse.model_validate(booking)


@router.get("/me", response_model=List[BookingResponse])
async def get_user_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    booking_service = BookingService(db)
    bookings = await booking_service.get_user_bookings(current_user.id)
    return [BookingResponse.model_validate(booking) for booking in bookings]


@router.get("/{booking_reference}", response_model=BookingResponse)
async def get_booking_by_reference(
    booking_reference: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    booking_service = BookingService(db)
    booking = await booking_service.get_booking_by_reference(booking_reference)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse.model_validate(booking)


@router.put("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    booking_service = BookingService(db)
    success = await booking_service.cancel_booking(booking_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel booking",
        )

    booking = await booking_service.get_by_id(booking_id)
    return BookingResponse.model_validate(booking)
