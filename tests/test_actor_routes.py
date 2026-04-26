from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.main import app
from app.routers import actors as actors_router_module
from app.services.actor import ActorService


@pytest.mark.asyncio
async def test_actor_routes_support_public_and_admin_endpoints(monkeypatch):
    actor_id = uuid4()
    captured_cache = {}

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_list_actors(self, query=None, skip=0, limit=20):
        captured_cache["query"] = query
        captured_cache["skip"] = skip
        captured_cache["limit"] = limit
        return ([SimpleNamespace(id=actor_id, full_name="Amy Adams", photo_url=None, bio=None)], 1)

    async def fake_create_actor(self, actor_data):
        return SimpleNamespace(id=actor_id, full_name=actor_data.full_name, photo_url=actor_data.photo_url, bio=actor_data.bio)

    async def fake_get_by_id(self, actor_id_param):
        return SimpleNamespace(id=actor_id_param, full_name="Amy Adams", photo_url=None, bio=None)

    async def fake_get_cache(key: str):
        captured_cache["cache_key"] = key
        return None

    async def fake_set_cache(key: str, value: str, expire: int):
        captured_cache["stored_key"] = key
        captured_cache["expire"] = expire
        return True

    monkeypatch.setattr(ActorService, "list_actors", fake_list_actors)
    monkeypatch.setattr(ActorService, "create_actor", fake_create_actor)
    monkeypatch.setattr(ActorService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(actors_router_module, "get_cache", fake_get_cache)
    monkeypatch.setattr(actors_router_module, "set_cache", fake_set_cache)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            list_response = await client.get("/v1/actors/")
            admin_list_response = await client.get("/v1/admin/actors/?q=amy&offset=5&limit=10")
            admin_detail_response = await client.get(f"/v1/admin/actors/{actor_id}")
            create_response = await client.post("/v1/admin/actors/", json={"full_name": "Amy Adams"})

        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["full_name"] == "Amy Adams"
        assert admin_list_response.status_code == 200
        assert admin_list_response.json()["items"][0]["id"] == str(actor_id)
        assert admin_detail_response.status_code == 200
        assert admin_detail_response.json()["id"] == str(actor_id)
        assert create_response.status_code == 201
        assert create_response.json()["id"] == str(actor_id)
        assert captured_cache["query"] == "amy"
        assert captured_cache["skip"] == 5
        assert captured_cache["limit"] == 10
        assert captured_cache["expire"] == actors_router_module.ADMIN_ACTOR_LIST_TTL_SECONDS
    finally:
        app.dependency_overrides.clear()
