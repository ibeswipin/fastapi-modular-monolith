import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    """Only place that talks SQLAlchemy for the `users` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list(self, offset: int = 0, limit: int = 50) -> list[User]:
        result = await self._session.execute(select(User).order_by(User.id).offset(offset).limit(limit))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    def add(self, user: User) -> None:
        self._session.add(user)

    async def flush(self) -> None:
        """Populates DB-generated values (id, server_default timestamps) without committing."""
        await self._session.flush()

    async def delete(self, user: User) -> None:
        await self._session.delete(user)

    async def delete_unverified_created_before(self, cutoff: datetime.datetime) -> int:
        result = await self._session.execute(
            delete(User).where(User.is_verified.is_(False), User.created_at < cutoff)
        )
        return result.rowcount or 0
