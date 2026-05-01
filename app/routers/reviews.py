from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas import (
    EventReviewCreate,
    EventReviewResponse,
    EventReviewUpdate,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
)
from app.services import EventReviewService, ReviewService

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


@router.post("/movies", response_model=ReviewResponse)
async def create_movie_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review_service = ReviewService(db)
    try:
        review = await review_service.create_review(current_user.id, review_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ReviewResponse.model_validate(review)


@router.put("/movies/{review_id}", response_model=ReviewResponse)
async def update_movie_review(
    review_id: UUID,
    review_data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review_service = ReviewService(db)
    review = await review_service.update_review(review_id, current_user.id, review_data)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found or access denied")
    return ReviewResponse.model_validate(review)


@router.delete("/movies/{review_id}", response_model=dict)
async def delete_movie_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review_service = ReviewService(db)
    success = await review_service.delete_review(review_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Review not found or access denied")
    return {"message": "Review deleted"}


@router.get("/movies/{movie_id}", response_model=List[ReviewResponse])
async def get_movie_reviews(
    movie_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    review_service = ReviewService(db)
    reviews = await review_service.get_movie_reviews(movie_id, skip, limit)
    return [ReviewResponse.model_validate(review) for review in reviews]


@router.post("/events", response_model=EventReviewResponse)
async def create_event_review(
    review_data: EventReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_review_service = EventReviewService(db)
    try:
        review = await event_review_service.create_event_review(current_user.id, review_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EventReviewResponse.model_validate(review)


@router.put("/events/{review_id}", response_model=EventReviewResponse)
async def update_event_review(
    review_id: UUID,
    review_data: EventReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_review_service = EventReviewService(db)
    review = await event_review_service.update_event_review(review_id, current_user.id, review_data)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found or access denied")
    return EventReviewResponse.model_validate(review)


@router.delete("/events/{review_id}", response_model=dict)
async def delete_event_review(
    review_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event_review_service = EventReviewService(db)
    success = await event_review_service.delete_event_review(review_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Review not found or access denied")
    return {"message": "Review deleted"}


@router.get("/events/{event_id}", response_model=List[EventReviewResponse])
async def get_event_reviews(
    event_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    event_review_service = EventReviewService(db)
    try:
        reviews = await event_review_service.get_event_reviews(event_id, skip, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [EventReviewResponse.model_validate(review) for review in reviews]
