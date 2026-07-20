import datetime
import enum
import secrets
import uuid

import bcrypt
import jwt

from app.core.config import Settings
from app.core.exceptions import InvalidTokenError

# bcrypt truncates/errors past 72 bytes; also enforced at the API boundary (auth/schemas.py).
_BCRYPT_MAX_PASSWORD_BYTES = 72


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class SecurityService:
    """Password hashing + JWT lifecycle. Only place that imports bcrypt/jwt directly."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def hash_password(self, plain_password: str) -> str:
        password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_PASSWORD_BYTES]
        hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))

    def create_access_token(self, user_id: int) -> str:
        expires_delta = datetime.timedelta(minutes=self._settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return self._create_token(user_id, TokenType.ACCESS, expires_delta)

    def create_refresh_token(self, user_id: int) -> str:
        expires_delta = datetime.timedelta(days=self._settings.REFRESH_TOKEN_EXPIRE_DAYS)
        return self._create_token(user_id, TokenType.REFRESH, expires_delta)

    def decode_token(self, token: str, expected_type: TokenType) -> int:
        """Raises InvalidTokenError on bad signature, expiry, or wrong token type."""
        try:
            payload = jwt.decode(
                token,
                self._settings.SECRET_KEY,
                algorithms=[self._settings.JWT_ALGORITHM],
            )
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("Token is invalid") from exc

        if payload.get("type") != expected_type.value:
            raise InvalidTokenError(f"Expected a {expected_type.value} token")

        try:
            return int(payload["sub"])
        except (KeyError, ValueError) as exc:
            raise InvalidTokenError("Token is missing a valid subject") from exc

    def _create_token(self, user_id: int, token_type: TokenType, expires_delta: datetime.timedelta) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            "sub": str(user_id),
            "type": token_type.value,
            "iat": now,
            "exp": now + expires_delta,
            # ponytail: jti isn't checked against a blacklist, so tokens can't be
            # revoked early. Add a Redis set of revoked jtis (TTL = token lifetime) later.
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(payload, self._settings.SECRET_KEY, algorithm=self._settings.JWT_ALGORITHM)

    @staticmethod
    def generate_verification_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"
