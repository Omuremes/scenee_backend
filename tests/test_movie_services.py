from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas import MovieCategoryCreate, MovieCreate, MovieUpdate
from app.services.movie import MovieCategoryRepository, MovieCategoryService, MovieService


class FakeMovieCategoryRepository:
    def __init__(self):
        self.created_payload = None

    async def get_by_name(self, name: str):
        return None

    async def get_by_slug(self, slug: str):
        return None

    async def create(self, data: dict):
        self.created_payload = data
        return SimpleNamespace(id=uuid4(), **data)


class FakeMovieRepository:
    def __init__(self):
        self.db = object()
        self.update_called = False
        self.created_payload = None

    async def get_with_details(self, movie_id):
        return SimpleNamespace(id=movie_id, name="Existing movie")

    async def update(self, movie_id, data):
        self.update_called = True
        return SimpleNamespace(id=movie_id, **data)

    async def create(self, data):
        self.created_payload = data
        return SimpleNamespace(id=uuid4(), **data)


@pytest.mark.asyncio
async def test_movie_category_service_generates_slug_from_name():
    repository = FakeMovieCategoryRepository()
    service = object.__new__(MovieCategoryService)
    service.repository = repository

    category = await service.create_category(MovieCategoryCreate(name="  Sci Fi & Fantasy  "))

    assert category.name == "Sci Fi & Fantasy"
    assert category.slug == "sci-fi-fantasy"
    assert repository.created_payload == {"name": "Sci Fi & Fantasy", "slug": "sci-fi-fantasy"}


@pytest.mark.asyncio
async def test_movie_service_empty_update_returns_current_resource():
    repository = FakeMovieRepository()
    service = object.__new__(MovieService)
    service.repository = repository

    movie_id = uuid4()
    movie = await service.update_movie(movie_id, MovieUpdate())

    assert movie.id == movie_id
    assert repository.update_called is False


@pytest.mark.asyncio
async def test_movie_service_create_requires_existing_category(monkeypatch):
    repository = FakeMovieRepository()
    service = object.__new__(MovieService)
    service.repository = repository

    async def fake_get_by_id(self, category_id):
        return None

    monkeypatch.setattr(MovieCategoryRepository, "get_by_id", fake_get_by_id)

    with pytest.raises(ValueError, match="Movie category not found"):
        await service.create_movie(
            MovieCreate(
                name="New movie",
                description="Description",
                is_series=False,
                category_id=uuid4(),
            )
        )

    assert repository.created_payload is None
