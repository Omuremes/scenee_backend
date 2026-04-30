from .auth import router as auth_router
from .actors import public_router as actors_router, admin_router as admin_actors_router
from .movie_categories import router as admin_movie_categories_router
from .movies import public_router as movies_router, admin_router as admin_movies_router
from .serials import public_router as serials_router, admin_router as admin_serials_router
from .events import public_router as events_router, admin_router as admin_events_router
from .bookings import router as bookings_router
from .favorites import router as favorites_router
from .reviews import router as reviews_router

__all__ = [
    "auth_router",
    "actors_router",
    "admin_actors_router",
    "admin_movie_categories_router",
    "movies_router",
    "admin_movies_router",
    "serials_router",
    "admin_serials_router",
    "events_router",
    "admin_events_router",
    "bookings_router",
    "favorites_router",
    "reviews_router",
]
