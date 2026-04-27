from pydantic import Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.base import BaseSchema


class UserBase(BaseSchema):
    username: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=1000)


class UserSync(UserBase):
    """Данные для синхронизации пользователя без firebase_uid."""
    pass


class UserRegister(UserBase):
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=255)
    confirm_password: str = Field(..., min_length=8, max_length=255)

    @validator("confirm_password")
    def passwords_match(cls, v, values, **kwargs):
        if "password" in values and v != values["password"]:
            raise ValueError("passwords do not match")
        return v


class UserLogin(BaseSchema):
    email: str = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=255)


class UserCreate(UserBase):
    firebase_uid: str = Field(..., max_length=128)


class UserUpdate(UserBase):
    pass


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(UserBase):
    id: UUID
    firebase_uid: Optional[str] = None
    email: Optional[str] = None
    role: str
    created_at: datetime


class RegisterResponse(TokenResponse):
    user: UserResponse
