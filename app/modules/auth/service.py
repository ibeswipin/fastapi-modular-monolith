import datetime

from app.core.exceptions import (
    AccountLockedError,
    AlreadyVerifiedError,
    InvalidCredentialsError,
    InvalidVerificationCodeError,
    UserNotFoundError,
)
from app.core.logging import get_logger
from app.core.notifications import NotificationService
from app.core.rate_limit import RateLimiter
from app.core.security import SecurityService, TokenType
from app.modules.auth.schemas import TokenResponse
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService

logger = get_logger(__name__)


def _as_aware_utc(value: datetime.datetime | None) -> datetime.datetime | None:
    """SQLite (tests) returns naive datetimes; Postgres returns aware ones. Everything we write is UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value


class AuthService:
    def __init__(
        self,
        user_service: UserService,
        security_service: SecurityService,
        notification_service: NotificationService,
        rate_limiter: RateLimiter,
        verification_code_ttl: datetime.timedelta,
        max_login_failures: int,
        login_lockout: datetime.timedelta,
    ) -> None:
        self._users = user_service
        self._security = security_service
        self._notifications = notification_service
        self._rate_limiter = rate_limiter
        self._verification_code_ttl = verification_code_ttl
        self._max_login_failures = max_login_failures
        self._login_lockout = login_lockout

    async def signup(self, email: str, password: str, first_name: str | None, last_name: str | None) -> User:
        password_hash = self._security.hash_password(password)
        user = await self._users.register_user(
            UserCreate(email=email, password_hash=password_hash, first_name=first_name, last_name=last_name)
        )
        await self._issue_and_send_verification_code(user)
        logger.info("user signed up: email=%s user_id=%s", email, user.id)
        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        lock_key = f"lockout:login:{email}"
        if await self._rate_limiter.is_locked(lock_key):
            logger.warning("login blocked, account locked: email=%s", email)
            raise AccountLockedError("Account temporarily locked due to too many failed login attempts")

        # Same error for "no such user" and "wrong password" — avoids leaking which emails are registered.
        user = await self._users.get_by_email(email)
        if user is None or not self._security.verify_password(password, user.password_hash):
            await self._register_login_failure(email, lock_key)
            logger.warning("login failed: email=%s", email)
            raise InvalidCredentialsError("Invalid email or password")

        await self._rate_limiter.reset(f"login_failures:{email}")
        logger.info("login success: email=%s user_id=%s", email, user.id)
        return self._issue_token_pair(user.id)

    async def _register_login_failure(self, email: str, lock_key: str) -> None:
        window_seconds = int(self._login_lockout.total_seconds())
        failure_count = await self._rate_limiter.increment(f"login_failures:{email}", window_seconds)
        if failure_count >= self._max_login_failures:
            await self._rate_limiter.lock(lock_key, window_seconds)
            await self._rate_limiter.reset(f"login_failures:{email}")
            logger.warning("account locked after %d failed attempts: email=%s", failure_count, email)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        user_id = self._security.decode_token(refresh_token, TokenType.REFRESH)
        user = await self._users.get_by_id(user_id)  # re-fetched so a deleted account can't keep refreshing
        return self._issue_token_pair(user.id)

    async def verify_email(self, email: str, code: str) -> User:
        user = await self._users.get_by_email(email)
        if user is None:
            raise UserNotFoundError(f"No user registered with email '{email}'")
        if user.is_verified:
            raise AlreadyVerifiedError("This account is already verified")

        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = _as_aware_utc(user.verification_code_expires_at)
        code_matches = user.verification_code is not None and user.verification_code == code
        not_expired = expires_at is not None and expires_at > now
        if not (code_matches and not_expired):
            raise InvalidVerificationCodeError("Verification code is invalid or expired")

        verified = await self._users.verify_user(user)
        logger.info("email verified: email=%s user_id=%s", email, user.id)
        return verified

    async def _issue_and_send_verification_code(self, user: User) -> None:
        code = self._security.generate_verification_code()
        expires_at = datetime.datetime.now(datetime.timezone.utc) + self._verification_code_ttl
        await self._users.set_verification_code(user.id, code, expires_at)
        await self._notifications.send_verification_code(user.email, code)

    def _issue_token_pair(self, user_id: int) -> TokenResponse:
        return TokenResponse(
            access_token=self._security.create_access_token(user_id),
            refresh_token=self._security.create_refresh_token(user_id),
        )
