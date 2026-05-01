"""Seed the local database with realistic test data.

Run from the project root:
    python scripts/seed_database.py

The script is idempotent: running it again updates the same seed records instead
of creating duplicate users, categories, movies, events, or serials.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import AsyncSessionLocal
from app.models import (
    Actor,
    Booking,
    Event,
    EventCategory,
    EventReview,
    EventSeat,
    EventSession,
    Favorite,
    Movie,
    MovieCategory,
    Poster,
    Review,
    Season,
    Serial,
    SerialEpisode,
    User,
    Venue,
)
from app.models.booking import BookingStatus

ModelT = TypeVar("ModelT")


POSTER_BASE_URL = "https://placehold.co"


async def get_one(session: AsyncSession, model: type[ModelT], **filters: Any) -> ModelT | None:
    stmt = select(model).filter_by(**filters)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_movie(session: AsyncSession, name: str) -> Movie | None:
    stmt = (
        select(Movie)
        .where(Movie.name == name)
        .options(
            selectinload(Movie.actors),
            selectinload(Movie.categories),
            selectinload(Movie.posters),
            selectinload(Movie.episodes),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_event(session: AsyncSession, title: str) -> Event | None:
    stmt = (
        select(Event)
        .where(Event.title == title)
        .options(selectinload(Event.sessions).selectinload(EventSession.seats))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_serial(session: AsyncSession, name: str) -> Serial | None:
    stmt = (
        select(Serial)
        .where(Serial.name == name)
        .options(
            selectinload(Serial.actors),
            selectinload(Serial.categories),
            selectinload(Serial.seasons).selectinload(Season.episodes),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_by(session: AsyncSession, model: type[ModelT], lookup: dict[str, Any], values: dict[str, Any]) -> ModelT:
    instance = await get_one(session, model, **lookup)
    if instance is None:
        instance = model(**lookup, **values)
        session.add(instance)
    else:
        for key, value in values.items():
            setattr(instance, key, value)
    return instance


async def seed_users(session: AsyncSession) -> dict[str, User]:
    users = {
        "admin": {
            "firebase_uid": "seed-admin-firebase-uid",
            "email": "admin@cinescope.test",
            "role": "admin",
            "username": "CineScope Admin",
            "avatar_url": f"{POSTER_BASE_URL}/160x160/111827/FFFFFF?text=Admin",
        },
        "alisa": {
            "firebase_uid": "seed-alisa-firebase-uid",
            "email": "alisa@cinescope.test",
            "role": "user",
            "username": "Alisa",
            "avatar_url": f"{POSTER_BASE_URL}/160x160/1D4ED8/FFFFFF?text=A",
        },
        "timur": {
            "firebase_uid": "seed-timur-firebase-uid",
            "email": "timur@cinescope.test",
            "role": "user",
            "username": "Timur",
            "avatar_url": f"{POSTER_BASE_URL}/160x160/047857/FFFFFF?text=T",
        },
    }

    seeded: dict[str, User] = {}
    for key, payload in users.items():
        email = payload.pop("email")
        seeded[key] = await upsert_by(session, User, {"email": email}, payload)
    return seeded


async def seed_movie_catalog(session: AsyncSession) -> tuple[list[Movie], list[Serial]]:
    categories = {
        "action": await upsert_by(session, MovieCategory, {"slug": "action"}, {"name": "Action"}),
        "drama": await upsert_by(session, MovieCategory, {"slug": "drama"}, {"name": "Drama"}),
        "sci-fi": await upsert_by(session, MovieCategory, {"slug": "sci-fi"}, {"name": "Sci-Fi"}),
        "family": await upsert_by(session, MovieCategory, {"slug": "family"}, {"name": "Family"}),
    }

    actors = {
        "mira": await upsert_by(
            session,
            Actor,
            {"full_name": "Mira Volkov"},
            {
                "photo_url": f"{POSTER_BASE_URL}/300x300/0F766E/FFFFFF?text=Mira",
                "bio": "Lead actor for seed dramas and science fiction stories.",
            },
        ),
        "dan": await upsert_by(
            session,
            Actor,
            {"full_name": "Dan Arlen"},
            {
                "photo_url": f"{POSTER_BASE_URL}/300x300/7C2D12/FFFFFF?text=Dan",
                "bio": "Action and adventure performer.",
            },
        ),
        "leila": await upsert_by(
            session,
            Actor,
            {"full_name": "Leila Park"},
            {
                "photo_url": f"{POSTER_BASE_URL}/300x300/581C87/FFFFFF?text=Leila",
                "bio": "Family cinema and series actor.",
            },
        ),
    }
    await session.flush()

    movies_payload = [
        {
            "name": "Neon Horizon",
            "description": "A detective follows a signal across a future city before the last train leaves.",
            "duration_minutes": 124,
            "average_rating": 8.7,
            "poster_key": "seed/posters/neon-horizon.jpg",
            "video_file_key": "seed/movies/neon-horizon.mp4",
            "categories": [categories["sci-fi"], categories["action"]],
            "actors": [actors["mira"], actors["dan"]],
            "poster": f"{POSTER_BASE_URL}/600x900/111827/FFFFFF?text=Neon+Horizon",
        },
        {
            "name": "Silent Orchard",
            "description": "A quiet family drama about a return home, old letters, and a harvest festival.",
            "duration_minutes": 101,
            "average_rating": 8.1,
            "poster_key": "seed/posters/silent-orchard.jpg",
            "video_file_key": "seed/movies/silent-orchard.mp4",
            "categories": [categories["drama"], categories["family"]],
            "actors": [actors["mira"], actors["leila"]],
            "poster": f"{POSTER_BASE_URL}/600x900/14532D/FFFFFF?text=Silent+Orchard",
        },
        {
            "name": "Rally Point",
            "description": "A tense sports thriller built around one impossible night race.",
            "duration_minutes": 116,
            "average_rating": 7.6,
            "poster_key": "seed/posters/rally-point.jpg",
            "video_file_key": "seed/movies/rally-point.mp4",
            "categories": [categories["action"]],
            "actors": [actors["dan"]],
            "poster": f"{POSTER_BASE_URL}/600x900/991B1B/FFFFFF?text=Rally+Point",
        },
    ]

    movies: list[Movie] = []
    for payload in movies_payload:
        relation_values = {
            "categories": payload.pop("categories"),
            "actors": payload.pop("actors"),
            "poster": payload.pop("poster"),
        }
        movie = await get_movie(session, payload["name"])
        if movie is None:
            movie = Movie(**payload)
            session.add(movie)
        else:
            for key, value in payload.items():
                setattr(movie, key, value)
        movie.categories = relation_values["categories"]
        movie.category = relation_values["categories"][0]
        movie.actors = relation_values["actors"]
        if not movie.posters:
            movie.posters.append(Poster(url=relation_values["poster"], storage_path=movie.poster_key, is_primary=True))
        else:
            movie.posters[0].url = relation_values["poster"]
            movie.posters[0].storage_path = movie.poster_key
            movie.posters[0].is_primary = True
        movies.append(movie)

    serial = await get_serial(session, "Borderless")
    serial_created = serial is None
    if serial is None:
        serial = Serial(
            name="Borderless",
            description="Anthology series about people whose lives cross at airports, stations, and hotels.",
            poster_key="seed/posters/borderless.jpg",
            average_rating=8.4,
        )
        session.add(serial)
    else:
        serial.description = "Anthology series about people whose lives cross at airports, stations, and hotels."
        serial.poster_key = "seed/posters/borderless.jpg"
        serial.average_rating = 8.4

    serial.categories = [categories["drama"], categories["sci-fi"]]
    serial.actors = [actors["mira"], actors["leila"]]
    await session.flush()

    if serial_created or not serial.seasons:
        season = Season(serial=serial, season_number=1, title="Departures", release_year=2026)
        season.episodes = [
            SerialEpisode(episode_number=1, title="Gate A12", description="A missed flight changes two plans.", duration=2760),
            SerialEpisode(episode_number=2, title="Night Transfer", description="A courier waits out a storm.", duration=2880),
            SerialEpisode(episode_number=3, title="The Last Room", description="A hotel clerk recognizes an old guest.", duration=2940),
        ]
        session.add(season)

    return movies, [serial]


def build_seats(session_obj: EventSession, base_price: float) -> None:
    if session_obj.seats:
        return
    rows = ("A", "B", "C")
    for row in rows:
        for number in range(1, 7):
            zone = "vip" if row == "A" else "standard"
            price = base_price + 250 if zone == "vip" else base_price
            session_obj.seats.append(EventSeat(label=f"{row}{number}", zone=zone, price=price, is_available=True))


async def seed_events(session: AsyncSession) -> list[Event]:
    categories = {
        "cinema": await upsert_by(session, EventCategory, {"slug": "cinema"}, {"name": "Cinema"}),
        "concerts": await upsert_by(session, EventCategory, {"slug": "concerts"}, {"name": "Concerts"}),
        "kids": await upsert_by(session, EventCategory, {"slug": "kids"}, {"name": "Kids"}),
    }
    venues = {
        "central": await upsert_by(
            session,
            Venue,
            {"name": "Central Cinema"},
            {"address": "Chuy Ave 120", "city": "Bishkek", "latitude": 42.8746, "longitude": 74.5698, "capacity": 180},
        ),
        "arena": await upsert_by(
            session,
            Venue,
            {"name": "Oak Arena"},
            {"address": "Aaly Tokombaev 45", "city": "Bishkek", "latitude": 42.833, "longitude": 74.61, "capacity": 900},
        ),
    }

    now = datetime.utcnow().replace(microsecond=0)
    payloads = [
        {
            "title": "Neon Horizon Premiere",
            "description": "Opening night screening with reserved seats.",
            "type": "cinema",
            "poster_url": f"{POSTER_BASE_URL}/600x900/1E3A8A/FFFFFF?text=Premiere",
            "trailer_url": "https://example.com/trailers/neon-horizon",
            "city": "Bishkek",
            "category": categories["cinema"],
            "venue": venues["central"],
            "average_rating": 9.0,
            "sessions": [
                (now + timedelta(days=1, hours=18), 450.0, "Hall 1"),
                (now + timedelta(days=2, hours=20), 500.0, "Hall 2"),
            ],
        },
        {
            "title": "City Lights Live",
            "description": "Outdoor concert with evening and standard ticket options.",
            "type": "concerts",
            "poster_url": f"{POSTER_BASE_URL}/600x900/7E22CE/FFFFFF?text=City+Lights",
            "trailer_url": "https://example.com/trailers/city-lights",
            "city": "Bishkek",
            "category": categories["concerts"],
            "venue": venues["arena"],
            "average_rating": 8.2,
            "sessions": [(now + timedelta(days=4, hours=19), 1200.0, "Main Stage")],
        },
        {
            "title": "Little Inventors Workshop",
            "description": "Weekend science show for kids and parents.",
            "type": "kids",
            "poster_url": f"{POSTER_BASE_URL}/600x900/047857/FFFFFF?text=Inventors",
            "trailer_url": None,
            "city": "Bishkek",
            "category": categories["kids"],
            "venue": venues["central"],
            "average_rating": 7.9,
            "sessions": [(now + timedelta(days=3, hours=11), 350.0, "Studio")],
        },
    ]

    events: list[Event] = []
    for payload in payloads:
        session_payloads = payload.pop("sessions")
        event_category = payload.pop("category")
        venue = payload.pop("venue")
        event = await get_event(session, payload["title"])
        event_created = event is None
        if event is None:
            event = Event(**payload)
            session.add(event)
        else:
            for key, value in payload.items():
                setattr(event, key, value)
        event.event_type = event.type
        event.category = event_category
        event.venue = venue
        event.image_url = event.poster_url
        event.start_datetime = session_payloads[0][0]
        event.end_datetime = session_payloads[0][0] + timedelta(hours=2)
        event.price = session_payloads[0][1]
        event.max_capacity = 18 * len(session_payloads)
        event.available_seats = 18 * len(session_payloads)
        event.is_active = True
        await session.flush()

        existing_sessions = [] if event_created else list(event.sessions)
        for index, (starts_at, price, hall_name) in enumerate(session_payloads):
            if index < len(existing_sessions):
                event_session = existing_sessions[index]
                event_session.starts_at = starts_at
                event_session.ends_at = starts_at + timedelta(hours=2)
                event_session.base_price = price
                event_session.pricing_type = "per_seat"
                event_session.cinema_name = venue.name
                event_session.hall_name = hall_name
                build_seats(event_session, price)
            else:
                event_session = EventSession(
                    event=event,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(hours=2),
                    base_price=price,
                    pricing_type="per_seat",
                    cinema_name=venue.name,
                    hall_name=hall_name,
                )
                build_seats(event_session, price)
                session.add(event_session)
        events.append(event)

    return events


async def seed_social_data(session: AsyncSession, users: dict[str, User], movies: list[Movie], events: list[Event]) -> None:
    await session.flush()

    review_payloads = [
        (movies[0], users["alisa"], 9.0, "Great pacing and a strong visual identity."),
        (movies[0], users["timur"], 8.5, "Good test movie for popular and detail endpoints."),
        (movies[1], users["alisa"], 8.0, "Warm, quiet, and easy to recommend."),
    ]
    for movie, user, rating, text in review_payloads:
        review = await get_one(session, Review, movie_id=movie.id, user_id=user.id)
        if review is None:
            session.add(Review(movie_id=movie.id, user_id=user.id, rating=rating, text=text))
        else:
            review.rating = rating
            review.text = text

    event_review = await get_one(session, EventReview, event_id=events[0].id, user_id=users["alisa"].id)
    if event_review is None:
        session.add(EventReview(event_id=events[0].id, user_id=users["alisa"].id, rating=9.0, text="Seat map works well."))
    else:
        event_review.rating = 9.0
        event_review.text = "Seat map works well."

    favorite_payloads = [
        {"user_id": users["alisa"].id, "movie_id": movies[0].id, "event_id": None},
        {"user_id": users["alisa"].id, "movie_id": None, "event_id": events[0].id},
        {"user_id": users["timur"].id, "movie_id": movies[1].id, "event_id": None},
    ]
    for payload in favorite_payloads:
        favorite = await get_one(session, Favorite, **payload)
        if favorite is None:
            session.add(Favorite(**payload))

    await session.flush()

    event = await get_event(session, events[0].title)
    if event and event.sessions and event.sessions[0].seats:
        seat = event.sessions[0].seats[0]
        booking = await get_one(session, Booking, booking_reference="SEED-BOOK-001")
        if booking is None:
            session.add(
                Booking(
                    user_id=users["alisa"].id,
                    event_id=event.id,
                    session_id=event.sessions[0].id,
                    seat_id=seat.id,
                    seats_count=1,
                    total_price=seat.price,
                    status=BookingStatus.CONFIRMED,
                    booking_reference="SEED-BOOK-001",
                )
            )
        else:
            booking.user_id = users["alisa"].id
            booking.event_id = event.id
            booking.session_id = event.sessions[0].id
            booking.seat_id = seat.id
            booking.seats_count = 1
            booking.total_price = seat.price
            booking.status = BookingStatus.CONFIRMED
        seat.is_available = False


def print_summary(users: dict[str, User], movies: Iterable[Movie], serials: Iterable[Serial], events: Iterable[Event]) -> None:
    print("Seed complete.")
    print("Users:")
    for key, user in users.items():
        print(f"  - {key}: {user.email} ({user.role})")
    print("Movies:")
    for movie in movies:
        print(f"  - {movie.name}: {movie.id}")
    print("Serials:")
    for serial in serials:
        print(f"  - {serial.name}: {serial.id}")
    print("Events:")
    for event in events:
        print(f"  - {event.title}: {event.id}")
    print("Booking reference: SEED-BOOK-001")


async def main() -> None:
    async with AsyncSessionLocal() as session:
        users = await seed_users(session)
        movies, serials = await seed_movie_catalog(session)
        events = await seed_events(session)
        await seed_social_data(session, users, movies, events)
        await session.commit()
        print_summary(users, movies, serials, events)


if __name__ == "__main__":
    asyncio.run(main())
