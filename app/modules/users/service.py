import datetime

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import CannotModifyOwnRoleError, EmailAlreadyExistsError, UserNotFoundError
from app.core.logging import get_logger
from app.modules.users.models import Role, User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate

logger = get_logger(__name__)


class UserService:
    """Public interface of the users module — auth/workers go through this, never the repository directly."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def register_user(self, data: UserCreate) -> User:
        """Raises EmailAlreadyExistsError if taken. The check below isn't race-proof by
        itself (two concurrent signups can both pass it) — the except clause is the real
        guarantee, translating the DB's unique-index violation into a clean domain error
        instead of an unhandled IntegrityError."""
        existing = await self._repository.get_by_email(data.email)
        if existing is not None:
            raise EmailAlreadyExistsError(f"Email '{data.email}' is already registered")

        user = User(
            email=data.email,
            password_hash=data.password_hash,
            first_name=data.first_name,
            last_name=data.last_name,
            role=Role.USER,
            is_verified=False,
        )
        self._repository.add(user)
        try:
            await self._repository.flush()
        except IntegrityError as exc:
            raise EmailAlreadyExistsError(f"Email '{data.email}' is already registered") from exc
        return user

    async def get_by_id(self, user_id: int) -> User:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User {user_id} not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self._repository.get_by_email(email)

    async def list_users(self, offset: int = 0, limit: int = 50) -> tuple[list[User], int]:
        users = await self._repository.list(offset=offset, limit=limit)
        total = await self._repository.count()
        return users, total

    async def update_user(self, user_id: int, data: UserUpdate) -> User:
        # ponytail: only first_name/last_name are patchable — email/password/role
        # need their own re-auth/re-verification flow, not a generic PATCH.
        user = await self.get_by_id(user_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value)
        return user

    async def update_role(self, user_id: int, new_role: Role, requested_by: int) -> User:
        """requested_by is the acting admin's own id — an admin can't change their own
        role through this endpoint, so a lone admin can't accidentally lock themselves
        out of admin access. (Doesn't protect against demoting the *last* admin via a
        second admin account — that's a further hardening step, not implemented here.)"""
        if user_id == requested_by:
            raise CannotModifyOwnRoleError("You cannot change your own role")
        return await self.set_role(user_id, new_role)

    async def set_role(self, user_id: int, new_role: Role) -> User:
        """No self-check — update_role (HTTP) adds that policy on top of this primitive.
        Used directly by trusted, non-HTTP callers (see app/cli.py) that need to bootstrap
        the first admin, where "requested by another admin" doesn't apply."""
        user = await self.get_by_id(user_id)
        user.role = new_role
        logger.info("role changed: user_id=%s new_role=%s", user_id, new_role.value)
        return user

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_by_id(user_id)
        await self._repository.delete(user)
        logger.info("user deleted: user_id=%s email=%s", user_id, user.email)

    async def set_verification_code(self, user_id: int, code: str, expires_at: datetime.datetime) -> User:
        user = await self.get_by_id(user_id)
        user.verification_code = code
        user.verification_code_expires_at = expires_at
        return user

    async def verify_user(self, user: User) -> User:
        user.is_verified = True
        user.verification_code = None
        user.verification_code_expires_at = None
        return user

    async def delete_unverified_older_than(self, retention: datetime.timedelta) -> int:
        """The actual cleanup logic — the Celery task is just a scheduled caller of this."""
        cutoff = datetime.datetime.now(datetime.timezone.utc) - retention
        return await self._repository.delete_unverified_created_before(cutoff)
