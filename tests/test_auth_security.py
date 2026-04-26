from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.database import get_db
from app.core.security import get_current_user, verify_password
from app.main import app
from app.routers.bookings import BookingService
from app.schemas import UserRegister, UserSync
from app.schemas.booking import BookingStatus
from app.services.user import UserService


class FakeUserRepository:
    def __init__(self):
        self.users_by_email = {}
        self.users_by_firebase_uid = {}
        self.created_payload = None
        self.updated_payloads = {}

    async def get_by_email(self, email: str):
        return self.users_by_email.get(email.strip().lower())

    async def get_by_firebase_uid(self, firebase_uid: str):
        return self.users_by_firebase_uid.get(firebase_uid)

    async def create(self, data: dict):
        user = SimpleNamespace(id=uuid4(), **data)
        if user.email:
            self.users_by_email[user.email] = user
        if user.firebase_uid:
            self.users_by_firebase_uid[user.firebase_uid] = user
        self.created_payload = data
        return user

    async def update(self, user_id, data: dict):
        user = None
        for candidate in self.users_by_email.values():
            if candidate.id == user_id:
                user = candidate
                break
        if user is None:
            for candidate in self.users_by_firebase_uid.values():
                if candidate.id == user_id:
                    user = candidate
                    break
        if user is None:
            raise AssertionError("User not found in fake repository")

        for key, value in data.items():
            setattr(user, key, value)
        if getattr(user, "email", None):
            self.users_by_email[user.email] = user
        if getattr(user, "firebase_uid", None):
            self.users_by_firebase_uid[user.firebase_uid] = user
        self.updated_payloads[user_id] = data
        return user

    async def get_by_id(self, user_id):
        for candidate in self.users_by_email.values():
            if candidate.id == user_id:
                return candidate
        for candidate in self.users_by_firebase_uid.values():
            if candidate.id == user_id:
                return candidate
        return None


def build_user_service(repository: FakeUserRepository) -> UserService:
    service = object.__new__(UserService)
    service.repository = repository
    return service


@pytest.mark.asyncio
async def test_create_user_normalizes_email_and_hashes_password():
    repository = FakeUserRepository()
    service = build_user_service(repository)

    result = await service.create_user(
        UserRegister(
            email="  TestUser@Example.com ",
            password="super-secret-pass",
            username="tester",
        )
    )

    assert result["user"].email == "testuser@example.com"
    assert repository.created_payload["password_hash"] != "super-secret-pass"
    assert verify_password("super-secret-pass", repository.created_payload["password_hash"])


@pytest.mark.asyncio
async def test_sync_links_existing_user_only_with_verified_email():
    repository = FakeUserRepository()
    existing_user = SimpleNamespace(
        id=uuid4(),
        email="user@example.com",
        firebase_uid=None,
        username="before",
        avatar_url=None,
        role="user",
    )
    repository.users_by_email[existing_user.email] = existing_user
    service = build_user_service(repository)

    result = await service.get_or_create_user(
        firebase_uid="firebase-123",
        user_data=UserSync(username="after"),
        firebase_email="User@Example.com",
        email_verified=True,
    )

    assert result["created"] is False
    assert result["user"].firebase_uid == "firebase-123"
    assert result["user"].username == "after"

    with pytest.raises(ValueError, match="Verified email is required"):
        await service.get_or_create_user(
            firebase_uid="firebase-456",
            user_data=UserSync(username="blocked"),
            firebase_email="user@example.com",
            email_verified=False,
        )


@pytest.mark.asyncio
async def test_protected_routes_require_authentication():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        bookings_response = await client.get("/public/bookings/me")
        assert bookings_response.status_code == 401

        admin_response = await client.post(
            "/v1admin/movies/",
            json={"name": "Test movie"},
        )
        assert admin_response.status_code == 401

        admin_category_response = await client.post(
            "/v1admin/movies/categories",
            json={"name": "Drama"},
        )
        assert admin_category_response.status_code == 401


@pytest.mark.asyncio
async def test_booking_reference_is_hidden_from_other_users(monkeypatch):
    owner_id = uuid4()
    requester_id = uuid4()
    booking_id = uuid4()
    event_id = uuid4()

    async def fake_get_db():
        yield object()

    async def fake_get_booking_by_reference(self, booking_reference: str):
        return SimpleNamespace(
            id=booking_id,
            event_id=event_id,
            user_id=owner_id,
            seats_count=2,
            total_price=500.0,
            status=BookingStatus.CONFIRMED,
            booking_reference=booking_reference,
            created_at=datetime.utcnow(),
            updated_at=None,
        )

    monkeypatch.setattr(BookingService, "get_booking_by_reference", fake_get_booking_by_reference)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=requester_id, role="user")
    app.dependency_overrides[get_db] = fake_get_db

    try:
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            response = await client.get("/public/bookings/ABC12345")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
