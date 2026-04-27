from datetime import datetime
from uuid import uuid4

from app.core import minio as minio_module
from app.models.movie import Movie, Poster
from app.schemas.movie import MovieResponse


def test_movie_response_serializes_posters_from_orm(monkeypatch):
    monkeypatch.setattr(minio_module.settings, "MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setattr(minio_module.settings, "MINIO_PUBLIC_BASE_URL", "http://192.168.68.150")
    monkeypatch.setattr(minio_module.settings, "MINIO_SECURE", False)

    movie_id = uuid4()
    movie = Movie(
        name="Arrival",
        description="First contact",
        is_series=False,
        duration_minutes=116,
        seasons_count=1,
        average_rating=8.9,
    )
    movie.id = movie_id
    movie.created_at = datetime.utcnow()

    poster = Poster(
        url="http://minio:9000/cinescope-media/posters/arrival.jpg",
        storage_path="movies/arrival.jpg",
        is_primary=True,
    )
    poster.id = uuid4()
    poster.movie_id = movie_id
    movie.posters = [poster]

    payload = MovieResponse.model_validate(movie)

    assert payload.posters[0].url == "http://192.168.68.150/cinescope-media/posters/arrival.jpg"
    assert payload.primary_poster is not None
    assert payload.primary_poster.url == "http://192.168.68.150/cinescope-media/posters/arrival.jpg"
