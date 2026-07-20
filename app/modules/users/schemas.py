import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.users.models import Role


class UserCreate(BaseModel):
    """UserService.register_user() input — the users module's public "create" contract."""

    email: EmailStr
    password_hash: str = Field(..., description="Already-hashed password")
    first_name: str | None = None
    last_name: str | None = None


class UserRead(BaseModel):
    """Public representation of a user — safe to return from any endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    first_name: str | None
    last_name: str | None
    role: Role
    is_verified: bool
    created_at: datetime.datetime


class UserUpdate(BaseModel):
    """PATCH /users/{id} payload. Excludes email/password/role — those need their own re-auth flow."""

    first_name: str | None = None
    last_name: str | None = None
