from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Users API"
    ENVIRONMENT: str = "development"

    # postgresql+asyncpg://user:password@host:port/db_name
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/users_api"

    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    VERIFICATION_CODE_EXPIRE_MINUTES: int = 15
    UNVERIFIED_USER_RETENTION_DAYS: int = 2

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    CLEANUP_SCHEDULE_MINUTES: int = 60

    # Separate Redis DB index from Celery's broker/backend to keep rate-limit keys isolated.
    REDIS_URL: str = "redis://localhost:6379/2"

    # Account lockout: N failed logins in a row locks the account (any IP) for this many minutes. (for security.purposes)
    MAX_LOGIN_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
