from pydantic import BaseModel, EmailStr, Field

_MAX_PASSWORD_LENGTH = 72  # bcrypt ignores bytes beyond 72


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=_MAX_PASSWORD_LENGTH)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=_MAX_PASSWORD_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
