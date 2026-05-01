from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.movie import Movie, Poster
from app.core import minio as minio_module
from app.schemas.movie import MovieCreate, MovieResponse


def test_movie_response_normalizes_stale_minio_poster_urls(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_BUCKET_NAME", "cinescope-media")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.124:9000")

    movie_id = uuid4()
    movie = Movie(
        name="Arrival",
        description="First contact",
        duration_minutes=116,
        average_rating=8.9,
    )
    movie.id = movie_id
    movie.created_at = datetime.utcnow()

    poster = Poster(
        url="http://192.168.68.150:9000/cinescope-media/posters/arrival.jpg",
        storage_path="movies/arrival.jpg",
        is_primary=True,
    )
    poster.id = uuid4()
    poster.movie_id = movie_id
    movie.posters = [poster]

    payload = MovieResponse.model_validate(movie)

    assert payload.posters[0].url == "http://192.168.68.124:9000/cinescope-media/posters/arrival.jpg"
    assert payload.primary_poster is not None
    assert payload.primary_poster.url == "http://192.168.68.124:9000/cinescope-media/posters/arrival.jpg"


def test_movie_create_strips_and_validates_poster_url():
    payload = MovieCreate(
        name="Arrival",
        poster="  https://cdn.example.com/poster.jpg  ",
        actors=[],
        categories=[],
    )

    assert payload.poster == "https://cdn.example.com/poster.jpg"


def test_movie_create_rejects_blank_poster_url():
    with pytest.raises(ValidationError, match="Poster URL cannot be empty"):
        MovieCreate(
            name="Arrival",
            poster="   ",
            actors=[],
            categories=[],
        )
