from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas import EventReviewCreate, EventReviewUpdate, ReviewCreate, SerialReviewCreate, SerialReviewUpdate
from app.services.review import EventReviewService, ReviewService
from app.services.serial_review import SerialReviewService


class FakeReviewRepository:
    def __init__(self):
        self.created_payload = None
        self.updated_payload = None
        self.review = None

    async def get_by_movie_and_user(self, movie_id, user_id):
        return self.review

    async def create(self, data):
        self.created_payload = data
        return SimpleNamespace(id=uuid4(), movie_id=data["movie_id"], user_id=data["user_id"])

    async def update_movie_rating(self, movie_id):
        return None

    async def get_with_user(self, review_id):
        return SimpleNamespace(
            id=review_id,
            movie_id=uuid4(),
            user_id=uuid4(),
            rating=8.5,
            text="ok",
            user=SimpleNamespace(id=uuid4(), username="user", avatar_url=None),
        )


class FakeMovieExistsRepository:
    def __init__(self, exists=True):
        self._exists = exists

    async def exists(self, item_id):
        return self._exists


class FakeEventReviewRepository:
    def __init__(self):
        self.review = None

    async def get_by_event_and_user(self, event_id, user_id):
        return None

    async def create(self, data):
        return SimpleNamespace(id=uuid4(), event_id=data["event_id"], user_id=data["user_id"])

    async def update_event_rating(self, event_id):
        return None

    async def get_by_id(self, review_id):
        return self.review

    async def get_with_user(self, review_id):
        return SimpleNamespace(
            id=review_id,
            event_id=uuid4(),
            user_id=uuid4(),
            rating=9.0,
            text=None,
            user=SimpleNamespace(id=uuid4(), username="user", avatar_url="https://cdn/avatar.png"),
        )

    async def update(self, review_id, data):
        return self.review

    async def get_event_reviews(self, event_id, skip, limit):
        return []


class FakeEventExistsRepository:
    def __init__(self, exists=True, event_type="cinema"):
        self._exists = exists
        self._event_type = event_type

    async def exists(self, item_id):
        return self._exists

    async def get_by_id(self, item_id):
        if not self._exists:
            return None
        return SimpleNamespace(id=item_id, type=self._event_type)


class FakeSerialReviewRepository:
    def __init__(self):
        self.review = None
        self.created_payload = None
        self.updated_payload = None
        self.rating_updates = 0

    async def get_by_id(self, review_id):
        if self.review and self.review.id == review_id:
            return self.review
        return None

    async def get_by_serial_and_user(self, serial_id, user_id):
        return self.review

    async def create(self, data):
        self.created_payload = data
        return SimpleNamespace(id=uuid4(), serial_id=data["serial_id"], user_id=data["user_id"])

    async def update(self, review_id, data):
        self.updated_payload = data
        return self.review

    async def get_with_user(self, review_id):
        return SimpleNamespace(
            id=review_id,
            serial_id=uuid4(),
            user_id=uuid4(),
            rating=4.0,
            text="great",
            user=SimpleNamespace(id=uuid4(), username="user", avatar_url="https://cdn/avatar.png"),
        )

    async def update_serial_rating(self, serial_id):
        self.rating_updates += 1

    async def delete(self, review_id):
        return True

    async def get_serial_reviews(self, serial_id, skip, limit):
        return [
            SimpleNamespace(
                id=uuid4(),
                serial_id=serial_id,
                user_id=uuid4(),
                rating=3.5,
                text="Nice",
                created_at="2026-05-04T12:00:00",
                user=SimpleNamespace(id=uuid4(), username="fan", avatar_url=None),
            )
        ]


class FakeSerialExistsRepository:
    def __init__(self, exists=True):
        self._exists = exists

    async def get_by_id(self, item_id):
        if not self._exists:
            return None
        return SimpleNamespace(id=item_id)


@pytest.mark.asyncio
async def test_create_movie_review_rejects_duplicate_review():
    service = object.__new__(ReviewService)
    repository = FakeReviewRepository()
    repository.review = SimpleNamespace(id=uuid4())
    service.repository = repository
    service.movie_repository = FakeMovieExistsRepository(exists=True)

    with pytest.raises(ValueError, match="already reviewed this movie"):
        await service.create_review(
            uuid4(),
            ReviewCreate(movie_id=uuid4(), rating=8.5, text="Nice"),
        )

    assert repository.created_payload is None


@pytest.mark.asyncio
async def test_create_event_review_requires_existing_event():
    service = object.__new__(EventReviewService)
    service.repository = FakeEventReviewRepository()
    service.event_repository = FakeEventExistsRepository(exists=False)

    with pytest.raises(ValueError, match="Event not found"):
        await service.create_event_review(
            uuid4(),
            EventReviewCreate(event_id=uuid4(), rating=9.0, text="Great"),
        )


@pytest.mark.asyncio
async def test_create_event_review_requires_cinema_event():
    service = object.__new__(EventReviewService)
    service.repository = FakeEventReviewRepository()
    service.event_repository = FakeEventExistsRepository(exists=True, event_type="concerts")

    with pytest.raises(ValueError, match="only available for cinema"):
        await service.create_event_review(
            uuid4(),
            EventReviewCreate(event_id=uuid4(), rating=9.0, text="Great"),
        )


@pytest.mark.asyncio
async def test_get_event_reviews_requires_cinema_event():
    service = object.__new__(EventReviewService)
    service.repository = FakeEventReviewRepository()
    service.event_repository = FakeEventExistsRepository(exists=True, event_type="kids")

    with pytest.raises(ValueError, match="only available for cinema"):
        await service.get_event_reviews(uuid4())


@pytest.mark.asyncio
async def test_create_serial_review_upserts_and_recomputes_rating():
    service = object.__new__(SerialReviewService)
    repository = FakeSerialReviewRepository()
    service.repository = repository
    service.serial_repository = FakeSerialExistsRepository(exists=True)

    review = await service.create_or_update_serial_review(
        uuid4(),
        SerialReviewCreate(serial_id=uuid4(), rating=4.0, text="  Great series  "),
    )

    assert repository.created_payload["text"] == "Great series"
    assert repository.rating_updates == 1
    assert review.user.username == "user"


@pytest.mark.asyncio
async def test_update_serial_review_requires_owner_and_refreshes_rating():
    service = object.__new__(SerialReviewService)
    repository = FakeSerialReviewRepository()
    review_id = uuid4()
    owner_id = uuid4()
    repository.review = SimpleNamespace(id=review_id, serial_id=uuid4(), user_id=owner_id)
    service.repository = repository
    service.serial_repository = FakeSerialExistsRepository(exists=True)

    review = await service.update_serial_review(
        review_id,
        owner_id,
        SerialReviewUpdate(rating=5.0, text="  Updated  "),
    )

    assert repository.updated_payload == {"rating": 5.0, "text": "Updated"}
    assert repository.rating_updates == 1
    assert review.user.username == "user"


@pytest.mark.asyncio
async def test_delete_serial_review_requires_owner():
    service = object.__new__(SerialReviewService)
    repository = FakeSerialReviewRepository()
    serial_id = uuid4()
    owner_id = uuid4()
    repository.review = SimpleNamespace(id=uuid4(), serial_id=serial_id, user_id=owner_id)
    service.repository = repository
    service.serial_repository = FakeSerialExistsRepository(exists=True)

    success = await service.delete_serial_review(repository.review.id, owner_id)

    assert success is True
    assert repository.rating_updates == 1


@pytest.mark.asyncio
async def test_get_serial_reviews_requires_existing_serial():
    service = object.__new__(SerialReviewService)
    service.repository = FakeSerialReviewRepository()
    service.serial_repository = FakeSerialExistsRepository(exists=False)

    with pytest.raises(ValueError, match="Serial not found"):
        await service.get_serial_reviews(uuid4())


@pytest.mark.asyncio
async def test_update_event_review_empty_payload_returns_current_review():
    service = object.__new__(EventReviewService)
    repository = FakeEventReviewRepository()
    owner_id = uuid4()
    review_id = uuid4()
    repository.review = SimpleNamespace(id=review_id, user_id=owner_id, event_id=uuid4())
    service.repository = repository
    service.event_repository = FakeEventExistsRepository(exists=True)

    review = await service.update_event_review(review_id, owner_id, EventReviewUpdate())

    assert review.id == review_id
    assert review.user.avatar_url == "https://cdn/avatar.png"
