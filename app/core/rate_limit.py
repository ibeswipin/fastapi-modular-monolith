from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Request

from app.core.config import settings
from app.core.exceptions import RateLimitExceededError

_redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


class RateLimiter:
    """Fixed-window counter in Redis. INCR is atomic, so exactly one caller
    ever observes count == 1 and sets the TTL — no Lua script needed.

    ponytail: a crash between INCR and EXPIRE could leave a key without a
    TTL (rare — same connection, two sequential calls). A Lua script would
    close that gap; not worth it for a login/signup/verify rate limit.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def increment(self, key: str, window_seconds: int) -> int:
        count = await self._client.incr(key)
        if count == 1:
            await self._client.expire(key, window_seconds)
        return count

    async def check(self, key: str, limit: int, window_seconds: int) -> None:
        count = await self.increment(key, window_seconds)
        if count > limit:
            raise RateLimitExceededError("Too many requests, try again later")

    async def reset(self, key: str) -> None:
        await self._client.delete(key)

    async def lock(self, key: str, duration_seconds: int) -> None:
        await self._client.set(key, "1", ex=duration_seconds)

    async def is_locked(self, key: str) -> bool:
        return bool(await self._client.exists(key))


def get_rate_limiter() -> RateLimiter:
    return RateLimiter(_redis_client)


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def rate_limit_by_ip(action: str, limit: int, window_seconds: int):
    """E.g. Depends(rate_limit_by_ip("login", limit=5, window_seconds=60))."""

    async def dependency(request: Request, limiter: RateLimiterDep) -> None:
        client_host = request.client.host if request.client else "unknown"
        await limiter.check(f"ratelimit:{action}:{client_host}", limit, window_seconds)

    return dependency
