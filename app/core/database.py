from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared declarative base — Alembic autogenerate needs one metadata object across modules."""


engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

# expire_on_commit=False avoids implicit post-commit refreshes (MissingGreenlet footgun in async SQLAlchemy).
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Request-scoped session: commit on success, rollback on error. One request = one transaction."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
