import asyncio
import datetime
import logging

from app.core.config import settings
from app.core.database import async_session_factory
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.cleanup_unverified_users")
def cleanup_unverified_users() -> int:
    deleted_count = asyncio.run(_cleanup_unverified_users_async())
    logger.info("cleanup_unverified_users: deleted %d unverified account(s)", deleted_count)
    return deleted_count


async def _cleanup_unverified_users_async() -> int:
    retention = datetime.timedelta(days=settings.UNVERIFIED_USER_RETENTION_DAYS)
    async with async_session_factory() as session:
        service = UserService(UserRepository(session))
        deleted_count = await service.delete_unverified_older_than(retention)
        await session.commit()
        return deleted_count
