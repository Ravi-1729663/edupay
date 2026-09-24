"""Auth + user schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import EmailStr, Field

from app.models.user import Role
from app.schemas.common import ORMBase


class LoginRequest(ORMBase):
    email: EmailStr
    password: str = Field(min_length=1)


class UserRead(ORMBase):
    id: str
    email: str
    full_name: str
    role: Role
    is_active: bool
    student_id: Optional[str] = None


class TokenResponse(ORMBase):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class UserCreate(ORMBase):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: Role
    student_id: Optional[str] = None


class UserUpdate(ORMBase):
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    student_id: Optional[str] = None
