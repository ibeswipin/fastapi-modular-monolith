from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "users_api",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# ponytail: plain interval schedule is enough for one job; a DB-backed
# scheduler only earns its keep once there are several periodic tasks.
celery_app.conf.beat_schedule = {
    "cleanup-unverified-users": {
        "task": "app.workers.tasks.cleanup_unverified_users",
        "schedule": settings.CLEANUP_SCHEDULE_MINUTES * 60,
    },
}
