import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.minio import ensure_media_bucket
from app.routers import (
    admin_events_router,
    admin_actors_router,
    admin_movie_categories_router,
    admin_movies_router,
    admin_serials_router,
    actors_router,
    auth_router,
    bookings_router,
    events_router,
    favorites_router,
    movies_router,
    serials_router,
    reviews_router,
)

logger = logging.getLogger(__name__)


app = FastAPI(
    title="CineScope API",
    description="Backend API for CineScope mobile app - movies and events search",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(actors_router)
app.include_router(admin_actors_router)
app.include_router(admin_movie_categories_router)
app.include_router(movies_router)
app.include_router(admin_movies_router)
app.include_router(serials_router)
app.include_router(admin_serials_router)
app.include_router(events_router)
app.include_router(admin_events_router)
app.include_router(bookings_router)
app.include_router(favorites_router)
app.include_router(reviews_router)


@app.on_event("startup")
async def configure_media_storage():
    try:
        ensure_media_bucket()
    except Exception as exc:
        logger.warning("Could not configure MinIO media bucket: %s", exc)


@app.get("/")
async def root():
    return {"message": "CineScope API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
