from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.main import app
from app.services.actor import ActorService


@pytest.mark.asyncio
async def test_actor_routes_support_public_list_and_admin_create(monkeypatch):
    actor_id = uuid4()

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_list_actors(self, query=None, skip=0, limit=20):
        return ([SimpleNamespace(id=actor_id, full_name="Amy Adams", photo_url=None, bio=None)], 1)

    async def fake_create_actor(self, actor_data):
        return SimpleNamespace(id=actor_id, full_name=actor_data.full_name, photo_url=actor_data.photo_url, bio=actor_data.bio)

    monkeypatch.setattr(ActorService, "list_actors", fake_list_actors)
    monkeypatch.setattr(ActorService, "create_actor", fake_create_actor)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            list_response = await client.get("/v1/actors/")
            create_response = await client.post("/v1/admin/actors/", json={"full_name": "Amy Adams"})

        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["full_name"] == "Amy Adams"
        assert create_response.status_code == 201
        assert create_response.json()["id"] == str(actor_id)
    finally:
        app.dependency_overrides.clear()
