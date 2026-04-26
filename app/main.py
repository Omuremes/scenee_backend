from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    admin_events_router,
    admin_actors_router,
    admin_movies_router,
    actors_router,
    auth_router,
    bookings_router,
    events_router,
    favorites_router,
    movies_router,
    reviews_router,
)


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
app.include_router(movies_router)
app.include_router(admin_movies_router)
app.include_router(events_router)
app.include_router(admin_events_router)
app.include_router(bookings_router)
app.include_router(favorites_router)
app.include_router(reviews_router)


@app.get("/")
async def root():
    return {"message": "CineScope API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
