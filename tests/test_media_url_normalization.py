from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.schemas import ActorCreate, ActorUpdate, EventCreate, EventUpdate, EventListResponse, EventResponse
from app.core import minio as minio_module
from app.core.minio import normalize_media_fields


def test_actor_urls_are_normalized_before_storage(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150:9000")

    actor_create = ActorCreate(full_name="Amy Adams", photo_url="http://minio:9000/cinescope-media/actors/amy.jpg")
    actor_update = ActorUpdate(photo_url="http://minio:9000/cinescope-media/actors/amy.jpg")

    assert actor_create.photo_url == "http://192.168.68.150:9000/cinescope-media/actors/amy.jpg"
    assert actor_update.photo_url == "http://192.168.68.150:9000/cinescope-media/actors/amy.jpg"


def test_event_urls_are_normalized_before_storage(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150:9000")

    event_create = EventCreate(
        title="Premiere",
        description="Opening night",
        event_type="movie_screening",
        start_datetime=datetime.utcnow(),
        end_datetime=None,
        venue_id=uuid4(),
        price=10.0,
        max_capacity=200,
        image_url="http://minio:9000/cinescope-media/events/event.jpg",
    )
    event_update = EventUpdate(image_url="http://minio:9000/cinescope-media/events/event.jpg")

    assert event_create.image_url == "http://192.168.68.150:9000/cinescope-media/events/event.jpg"
    assert event_update.image_url == "http://192.168.68.150:9000/cinescope-media/events/event.jpg"


def test_response_models_preserve_already_public_urls():
    venue = SimpleNamespace(
        id=uuid4(),
        name="Cinema Hall",
        address="123 Main St",
        city="Bishkek",
        latitude=None,
        longitude=None,
        capacity=200,
    )
    event_id = uuid4()
    public_url = "http://192.168.68.150:9000/cinescope-media/events/event.jpg"

    event_detail = EventResponse.model_validate(
        SimpleNamespace(
            id=event_id,
            title="Premiere",
            description="Opening night",
            event_type="movie_screening",
            start_datetime=datetime.utcnow(),
            end_datetime=None,
            venue_id=venue.id,
            price=10.0,
            max_capacity=200,
            image_url=public_url,
            storage_path="events/event.jpg",
            available_seats=180,
            average_rating=4.8,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=None,
            venue=venue,
        )
    )
    event_list = EventListResponse.model_validate(
        SimpleNamespace(
            id=event_id,
            title="Premiere",
            event_type="movie_screening",
            start_datetime=datetime.utcnow(),
            venue=venue,
            price=10.0,
            available_seats=180,
            average_rating=4.8,
            image_url=public_url,
        )
    )

    assert event_detail.image_url == public_url
    assert event_list.image_url == public_url


def test_normalize_media_fields_updates_write_payloads(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150:9000")

    payload = normalize_media_fields(
        {
            "photo_url": "http://minio:9000/cinescope-media/actors/amy.jpg",
            "image_url": "http://minio:9000/cinescope-media/events/event.jpg",
            "url": "http://minio:9000/cinescope-media/movies/poster.jpg",
            "other": "keep-me",
        },
        ("photo_url", "image_url", "url"),
    )

    assert payload["photo_url"] == "http://192.168.68.150:9000/cinescope-media/actors/amy.jpg"
    assert payload["image_url"] == "http://192.168.68.150:9000/cinescope-media/events/event.jpg"
    assert payload["url"] == "http://192.168.68.150:9000/cinescope-media/movies/poster.jpg"
    assert payload["other"] == "keep-me"
