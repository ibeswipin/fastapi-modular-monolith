from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.dependencies import DbSession
from app.core.exceptions import ForbiddenError
from app.core.rate_limit import RateLimiterDep
from app.core.security import SecurityService, TokenType
from app.modules.auth.schemas import VerifyRequest
from app.modules.users.models import Role, User
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

_bearer_scheme = HTTPBearer(description="JWT access token, e.g. 'Bearer <token>'")


def get_security_service() -> SecurityService:
    return SecurityService(settings)


def get_user_service(db: DbSession) -> UserService:
    return UserService(UserRepository(db))


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    security: Annotated[SecurityService, Depends(get_security_service)],
    users: Annotated[UserService, Depends(get_user_service)],
) -> User:
    user_id = security.decode_token(credentials.credentials, TokenType.ACCESS)
    return await users.get_by_id(user_id)


def require_role(role: Role | None = None):
    """Depends(require_role()) = any authenticated user. Depends(require_role(Role.ADMIN)) = admin only."""

    async def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if role is not None and current_user.role != role:
            raise ForbiddenError(f"This action requires the '{role.value}' role")
        return current_user

    return dependency


def rate_limit_verify_by_email(limit: int, window_seconds: int):
    """Per-email, not per-IP: a 6-digit code is guessable, and the attack targets one account."""

    async def dependency(payload: VerifyRequest, limiter: RateLimiterDep) -> None:
        await limiter.check(f"ratelimit:verify:{payload.email}", limit, window_seconds)

    return dependency
