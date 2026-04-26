import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.main import app
from app.routers import movies as movies_router_module
from app.services.movie import MovieCategoryService, MovieService


def _build_movie(movie_id=None):
    movie_id = movie_id or uuid4()
    category = SimpleNamespace(id=uuid4(), name="Drama", slug="drama")
    poster = SimpleNamespace(
        id=uuid4(),
        movie_id=movie_id,
        url="https://cdn.example.com/poster.jpg",
        storage_path="posters/poster.jpg",
        is_primary=True,
    )
    return SimpleNamespace(
        id=movie_id,
        name="Arrival",
        description="First contact",
        is_series=False,
        average_rating=8.9,
        created_at="2026-04-26T10:00:00",
        updated_at=None,
        category_id=category.id,
        category=category,
        actors=[],
        posters=[poster],
        episodes=[],
        primary_poster=poster,
    )


@pytest.mark.asyncio
async def test_public_movies_returns_paginated_payload_and_sets_cache(monkeypatch):
    captured_cache = {}
    movie = _build_movie()

    async def fake_get_db():
        yield object()

    async def fake_get_cache(key: str):
        captured_cache["key"] = key
        return None

    async def fake_set_cache(key: str, value: str, expire: int):
        captured_cache["stored_key"] = key
        captured_cache["stored_value"] = json.loads(value)
        captured_cache["expire"] = expire
        return True

    async def fake_list_movies(self, query, category_id, is_series, skip, limit):
        assert query == "arrival"
        assert skip == 10
        assert limit == 5
        return [movie], 16

    monkeypatch.setattr(movies_router_module, "get_cache", fake_get_cache)
    monkeypatch.setattr(movies_router_module, "set_cache", fake_set_cache)
    monkeypatch.setattr(MovieService, "list_movies", fake_list_movies)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/public/movies/?q=arrival&offset=10&limit=5")
        assert response.status_code == 200
        assert response.json()["total"] == 16
        assert response.json()["offset"] == 10
        assert response.json()["limit"] == 5
        assert response.json()["has_more"] is True
        assert response.json()["items"][0]["name"] == "Arrival"
        assert captured_cache["expire"] == movies_router_module.PUBLIC_MOVIE_LIST_TTL_SECONDS
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_movies_uses_cached_payload(monkeypatch):
    cached_payload = {
        "items": [],
        "total": 0,
        "offset": 0,
        "limit": 20,
        "has_more": False,
    }

    async def fake_get_db():
        yield object()

    async def fake_get_cache(key: str):
        return json.dumps(cached_payload)

    async def fail_list_movies(self, *args, **kwargs):
        raise AssertionError("Service should not be called when cache is warm")

    monkeypatch.setattr(movies_router_module, "get_cache", fake_get_cache)
    monkeypatch.setattr(MovieService, "list_movies", fail_list_movies)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/public/movies/")
        assert response.status_code == 200
        assert response.json() == cached_payload
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_movie_routes_support_list_detail_category_and_delete(monkeypatch):
    movie = _build_movie()

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_list_movies(self, query, category_id, is_series, skip, limit):
        return [movie], 1

    async def fake_get_movie_with_details(self, movie_id):
        return movie if movie_id == movie.id else None

    async def fake_create_category(self, category_data):
        return SimpleNamespace(id=uuid4(), name=category_data.name, slug="drama")

    async def fake_delete(self, movie_id):
        return movie_id == movie.id

    async def fake_invalidate_cache():
        return None

    monkeypatch.setattr(MovieService, "list_movies", fake_list_movies)
    monkeypatch.setattr(MovieService, "get_movie_with_details", fake_get_movie_with_details)
    monkeypatch.setattr(MovieService, "delete", fake_delete)
    monkeypatch.setattr(MovieCategoryService, "create_category", fake_create_category)
    monkeypatch.setattr(movies_router_module, "_invalidate_public_movie_cache", fake_invalidate_cache)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            list_response = await client.get("/v1admin/movies/")
            detail_response = await client.get(f"/v1admin/movies/{movie.id}")
            category_response = await client.post("/v1admin/movies/categories", json={"name": "Drama"})
            delete_response = await client.delete(f"/v1admin/movies/{movie.id}")

        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == str(movie.id)
        assert category_response.status_code == 201
        assert category_response.json()["slug"] == "drama"
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.clear()
