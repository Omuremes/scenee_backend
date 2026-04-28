import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.main import app
from app.routers import series as series_router_module
from app.services.series import SeriesService


def _build_series(series_id=None):
    series_id = series_id or uuid4()
    category = SimpleNamespace(id=uuid4(), name="Sci-Fi", slug="sci-fi")
    episode = SimpleNamespace(
        id=uuid4(),
        movie_id=series_id,
        season_number=1,
        episode_number=1,
        title="Pilot",
        description=None,
        video_url=None,
        duration=42,
    )
    poster = SimpleNamespace(
        id=uuid4(),
        movie_id=series_id,
        url="https://cdn.example.com/poster.jpg",
        storage_path="posters/poster.jpg",
        is_primary=True,
    )
    return SimpleNamespace(
        id=series_id,
        name="Dark Matter",
        description="Mystery in space",
        duration=48,
        seasons_count=2,
        average_rating=8.7,
        created_at="2026-04-26T10:00:00",
        updated_at=None,
        category_id=category.id,
        category=category,
        categories=[category],
        actors=[],
        posters=[poster],
        episodes=[episode],
        primary_poster=poster,
    )


@pytest.mark.asyncio
async def test_public_series_routes_expose_detail_and_episodes(monkeypatch):
    series = _build_series()

    async def fake_get_db():
        yield object()

    async def fake_get_series_with_details(self, series_id):
        return series if series_id == series.id else None

    async def fake_get_season_episodes(self, series_id, season_number):
        assert series_id == series.id
        assert season_number == 1
        return series.episodes

    async def fake_get_cache(key: str):
        return None

    async def fake_set_cache(key: str, value: str, expire: int):
        return True

    monkeypatch.setattr(SeriesService, "get_series_with_details", fake_get_series_with_details)
    monkeypatch.setattr(SeriesService, "get_season_episodes", fake_get_season_episodes)
    monkeypatch.setattr(series_router_module, "get_cache", fake_get_cache)
    monkeypatch.setattr(series_router_module, "set_cache", fake_set_cache)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            detail_response = await client.get(f"/v1/series/{series.id}")
            episodes_response = await client.get(f"/v1/series/{series.id}/seasons/1/episodes")

        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == str(series.id)
        assert detail_response.json()["seasons_count"] == 2
        assert episodes_response.status_code == 200
        assert episodes_response.json()[0]["episode_number"] == 1
        assert episodes_response.json()[0]["duration"] == 42
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_series_routes_support_list_and_delete(monkeypatch):
    series = _build_series()

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_list_series(self, query, category_id, skip, limit):
        return [series], 1

    async def fake_delete(self, series_id):
        return series_id == series.id

    async def fake_invalidate_cache():
        return None

    monkeypatch.setattr(SeriesService, "list_series", fake_list_series)
    monkeypatch.setattr(SeriesService, "delete", fake_delete)
    monkeypatch.setattr(series_router_module, "_invalidate_public_series_cache", fake_invalidate_cache)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            list_response = await client.get("/v1/admin/series/")
            delete_response = await client.delete(f"/v1/admin/series/{series.id}")

        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["name"] == "Dark Matter"
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.clear()
