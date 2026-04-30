from uuid import uuid4
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.main import app
from app.services.serial import SerialService

def _build_serial(serial_id=None):
    serial_id = serial_id or uuid4()
    category = SimpleNamespace(id=uuid4(), name="Sci-Fi", slug="sci-fi")
    episode = SimpleNamespace(
        id=uuid4(),
        season_id=uuid4(),
        episode_number=1,
        title="Pilot",
        description=None,
        duration=42,
        episode_file=None
    )
    season = SimpleNamespace(
        id=uuid4(),
        serial_id=serial_id,
        season_number=1,
        title="Season 1",
        release_year=2026,
        episodes=[episode]
    )
    return SimpleNamespace(
        id=serial_id,
        name="Dark Matter",
        description="Mystery in space",
        poster_key="posters/dark-matter.jpg",
        average_rating=8.7,
        created_at="2026-04-26T10:00:00",
        updated_at=None,
        categories=[category],
        actors=[],
        seasons=[season],
        poster_url="https://minio.example.com/posters/dark-matter.jpg"
    )


@pytest.mark.asyncio
async def test_public_serials_routes_expose_detail_and_episodes(monkeypatch):
    serial = _build_serial()

    async def fake_get_db():
        yield object()

    async def fake_get_by_id(self, serial_id):
        return serial if serial_id == serial.id else None

    async def fake_get_season_episodes(self, serial_id, season_number):
        assert serial_id == serial.id
        assert season_number == 1
        return serial.seasons[0].episodes

    monkeypatch.setattr(SerialService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(SerialService, "get_season_episodes", fake_get_season_episodes)
    app.dependency_overrides[get_db] = fake_get_db

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            detail_response = await client.get(f"/v1/serials/{serial.id}")
            episodes_response = await client.get(f"/v1/serials/{serial.id}/seasons/1/episodes")

        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == str(serial.id)
        assert len(detail_response.json()["seasons"]) == 1
        
        assert episodes_response.status_code == 200
        assert episodes_response.json()[0]["episode_number"] == 1
        assert episodes_response.json()[0]["duration"] == 42
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_serials_routes_support_list_and_delete(monkeypatch):
    serial = _build_serial()

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_list_serials(self, query, category_id, skip, limit):
        return [serial], 1

    async def fake_delete(self, serial_id):
        return serial_id == serial.id

    monkeypatch.setattr(SerialService, "list_serials", fake_list_serials)
    monkeypatch.setattr(SerialService, "delete", fake_delete)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            list_response = await client.get("/v1/serials/")
            delete_response = await client.delete(f"/v1/admin/serials/{serial.id}")

        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["name"] == "Dark Matter"
        assert delete_response.status_code == 204
    finally:
        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_admin_serials_routes_support_create(monkeypatch):
    serial = _build_serial()

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_create(self, data):
        return serial

    monkeypatch.setattr(SerialService, "create", fake_create)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            payload = {
                "name": "New Serial",
                "description": "Test",
                "actors": [],
                "categories": [],
                "seasons": []
            }
            create_response = await client.post("/v1/admin/serials/", json=payload)

        assert create_response.status_code == 201
        assert create_response.json()["name"] == "Dark Matter"
    finally:
        app.dependency_overrides.clear()
