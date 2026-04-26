import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.main import app
from app.routers import movie_categories as movie_categories_router_module
from app.services.movie import MovieCategoryService


@pytest.mark.asyncio
async def test_movie_category_routes_support_crud_and_cached_listing(monkeypatch):
    category_id = uuid4()
    captured_cache = {}

    async def fake_get_db():
        yield object()

    async def fake_admin_user():
        return SimpleNamespace(id=uuid4(), role="admin")

    async def fake_list_categories(self, query=None, skip=0, limit=20):
        captured_cache["query"] = query
        captured_cache["skip"] = skip
        captured_cache["limit"] = limit
        return ([SimpleNamespace(id=category_id, name="Drama", slug="drama")], 1)

    async def fake_get_by_id(self, category_id_param):
        return SimpleNamespace(id=category_id_param, name="Drama", slug="drama")

    async def fake_create_category(self, category_data):
        return SimpleNamespace(id=category_id, name=category_data.name, slug="drama")

    async def fake_update_category(self, category_id_param, category_data):
        return SimpleNamespace(id=category_id_param, name="Drama", slug=category_data.slug or "drama")

    async def fake_delete(self, category_id_param):
        return category_id_param == category_id

    async def fake_get_cache(key: str):
        captured_cache["cache_key"] = key
        return None

    async def fake_set_cache(key: str, value: str, expire: int):
        captured_cache["stored_key"] = key
        captured_cache["stored_payload"] = json.loads(value)
        captured_cache["expire"] = expire
        return True

    async def fake_invalidate():
        captured_cache["invalidated"] = True
        return None

    monkeypatch.setattr(MovieCategoryService, "list_categories", fake_list_categories)
    monkeypatch.setattr(MovieCategoryService, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(MovieCategoryService, "create_category", fake_create_category)
    monkeypatch.setattr(MovieCategoryService, "update_category", fake_update_category)
    monkeypatch.setattr(MovieCategoryService, "delete", fake_delete)
    monkeypatch.setattr(movie_categories_router_module, "get_cache", fake_get_cache)
    monkeypatch.setattr(movie_categories_router_module, "set_cache", fake_set_cache)
    monkeypatch.setattr(movie_categories_router_module, "_invalidate_movie_category_cache", fake_invalidate)
    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_current_admin_user] = fake_admin_user

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            list_response = await client.get("/v1/admin/movies/categories/?q=drama&offset=2&limit=5")
            detail_response = await client.get(f"/v1/admin/movies/categories/{category_id}")
            create_response = await client.post("/v1/admin/movies/categories/", json={"name": "Drama"})
            update_response = await client.patch(f"/v1/admin/movies/categories/{category_id}", json={"slug": "drama-updated"})
            delete_response = await client.delete(f"/v1/admin/movies/categories/{category_id}")

        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["slug"] == "drama"
        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == str(category_id)
        assert create_response.status_code == 201
        assert update_response.status_code == 200
        assert update_response.json()["slug"] == "drama-updated"
        assert delete_response.status_code == 204
        assert captured_cache["query"] == "drama"
        assert captured_cache["skip"] == 2
        assert captured_cache["limit"] == 5
        assert captured_cache["expire"] == movie_categories_router_module.ADMIN_MOVIE_CATEGORY_LIST_TTL_SECONDS
        assert captured_cache["invalidated"] is True
    finally:
        app.dependency_overrides.clear()
