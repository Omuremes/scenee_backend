from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.repositories import UserRepository
from app.schemas import UserBase, UserRegister, UserUpdate
from app.services.base import BaseService


class UserService(BaseService[UserRepository]):
    def __init__(self, db: AsyncSession):
        repository = UserRepository(db)
        super().__init__(repository)

    @staticmethod
    def _normalize_email(email: Optional[str]) -> Optional[str]:
        if email is None:
            return None
        normalized_email = email.strip().lower()
        return normalized_email or None

    async def create_user(self, user_data: UserRegister) -> dict:
        normalized_email = self._normalize_email(user_data.email)
        if not normalized_email:
            raise ValueError("Email is required")

        existing_user = await self.repository.get_by_email(normalized_email)
        if existing_user:
            raise ValueError("User with this email already exists")

        create_data = {
            "email": normalized_email,
            "password_hash": hash_password(user_data.password),
            "username": user_data.username,
            "avatar_url": user_data.avatar_url,
            "role": "user",
            "firebase_uid": None,
        }
        new_user = await self.repository.create(create_data)
        return {"user": new_user}

    async def authenticate_user(self, email: str, password: str):
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return None

        user = await self.repository.get_by_email(normalized_email)
        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def get_user_by_email(self, email: str):
        normalized_email = self._normalize_email(email)
        if not normalized_email:
            return None
        return await self.repository.get_by_email(normalized_email)

    async def get_or_create_user(
        self,
        firebase_uid: str,
        user_data: Optional[UserBase] = None,
        firebase_email: Optional[str] = None,
        email_verified: bool = False,
    ) -> dict:
        normalized_email = self._normalize_email(firebase_email)
        profile_updates = user_data.model_dump(exclude_unset=True) if user_data else {}
        user = await self.repository.get_by_firebase_uid(firebase_uid)

        if user:
            update_data = dict(profile_updates)
            if normalized_email and email_verified and user.email != normalized_email:
                existing_email_user = await self.repository.get_by_email(normalized_email)
                if existing_email_user and existing_email_user.id != user.id:
                    raise ValueError("Email is already linked to another account")
                update_data["email"] = normalized_email

            if update_data:
                user = await self.repository.update(user.id, update_data)
            return {"user": user, "created": False}

        create_data = {"firebase_uid": firebase_uid, "role": "user"}
        if normalized_email:
            existing_user = await self.repository.get_by_email(normalized_email)
            if existing_user:
                if existing_user.firebase_uid and existing_user.firebase_uid != firebase_uid:
                    raise ValueError("Email is already linked to another account")
                if not email_verified:
                    raise ValueError("Verified email is required to link this account")

                update_data = {"firebase_uid": firebase_uid, **profile_updates}
                if not existing_user.email:
                    update_data["email"] = normalized_email
                linked_user = await self.repository.update(existing_user.id, update_data)
                return {"user": linked_user, "created": False}

            if email_verified:
                create_data["email"] = normalized_email

        if profile_updates:
            create_data.update(profile_updates)

        new_user = await self.repository.create(create_data)
        return {"user": new_user, "created": True}

    async def get_user_by_id(self, user_id: UUID):
        return await self.repository.get_by_id(user_id)

    async def update_user(self, user_id: UUID, user_data: UserUpdate) -> Optional[dict]:
        update_data = user_data.model_dump(exclude_unset=True)
        if not update_data:
            return None
        return await self.repository.update(user_id, update_data)
