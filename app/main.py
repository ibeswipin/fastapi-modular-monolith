from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    AccountLockedError,
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitExceededError,
    UnauthorizedError,
)
from app.modules import router as modules_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="User registration, JWT authentication, email verification, and role-based user management.",
    version="1.0.0",
)

app.include_router(modules_router)


def _domain_error_handler(status_code: int, headers: dict[str, str] | None = None):
    async def handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)}, headers=headers)

    return handler


# Registered on the 4 base exception classes — Starlette walks the MRO, so
# e.g. EmailAlreadyExistsError resolves to the ConflictError handler below.
app.add_exception_handler(NotFoundError, _domain_error_handler(status.HTTP_404_NOT_FOUND))
app.add_exception_handler(ConflictError, _domain_error_handler(status.HTTP_409_CONFLICT))
app.add_exception_handler(UnauthorizedError,_domain_error_handler(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"}),)
app.add_exception_handler(ForbiddenError, _domain_error_handler(status.HTTP_403_FORBIDDEN))
app.add_exception_handler(RateLimitExceededError, _domain_error_handler(status.HTTP_429_TOO_MANY_REQUESTS))
app.add_exception_handler(AccountLockedError, _domain_error_handler(status.HTTP_423_LOCKED))


@app.get("/health", tags=["health"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
