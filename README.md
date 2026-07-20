# Users API

A modular-monolith user management service: registration, JWT auth (access +
refresh), email verification, role-based access control, and automatic
cleanup of unverified accounts.

## Architecture

```
app/
  main.py            FastAPI app: mounts routers, registers exception handlers
  core/               Shared infrastructure — no business logic
    config.py         Settings (env vars), single source of truth for config
    database.py        Async SQLAlchemy engine/session, get_db dependency
    security.py         SecurityService: bcrypt hashing, JWT issue/verify
    notifications.py    NotificationService interface + console dev impl
    rate_limit.py         Redis-backed RateLimiter: fixed-window limits + account lockout
    pagination.py          Generic Page[T] envelope + PaginationParams, reused by any list endpoint
    exceptions.py             Domain exceptions (AppError hierarchy)
    dependencies.py             App-wide FastAPI dependencies (DbSession)
  modules/
    users/              Owns the `users` table and everything about a user
      models.py           ORM model (User, Role)
      schemas.py          Pydantic schemas (UserCreate/UserRead/UserUpdate)
      repository.py        UserRepository — the only file with SQLAlchemy queries
      service.py             UserService — business logic, public module interface
      router.py                GET /me, GET /users, GET/PATCH/DELETE /users/{id}, PATCH /users/{id}/role
    auth/               Authentication and email verification
      schemas.py          Request/response bodies for /auth/*
      service.py            AuthService — orchestrates UserService + SecurityService
      dependencies.py         get_current_user, require_role(...)
      router.py                  POST /auth/signup|login|refresh|verify
  workers/
    celery_app.py       Celery app instance + beat schedule
    tasks.py               Thin wrapper calling UserService.delete_unverified_older_than
```

**Layering, per module:** `router` (HTTP only) → `service` (business logic,
plain constructor-injected classes) → `repository` (SQLAlchemy, ORM only).
Services never see `Request`/`Response`; routers never see `select()`.
Pydantic schemas are separate from ORM models, so a `User` row (with its
`password_hash`) can never leak into an API response by accident.

**Module boundary:** the `auth` module reaches user data only through
`UserService`/`UserRepository` (the `users` module's public interface) —
never through the `User` ORM model or raw SQL of its own. The reverse
direction (the `users` router depending on `auth`'s `get_current_user` /
`require_role` for access control) is the normal shape of a protected API
and isn't a boundary violation.

## Requirements

- Python 3.12+
- PostgreSQL 16+ (for local, non-Docker development)
- Redis (for Celery)
- Docker + Docker Compose (for the containerized path)

## Running locally (without Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements/base.txt

cp .env.example .env                  # adjust DATABASE_URL / SECRET_KEY as needed

# Postgres and Redis must be running and reachable at the URLs in .env.
alembic upgrade head                  # create the `users` table

uvicorn app.main:app --reload         # http://localhost:8000/docs
```

In a second terminal, to run the account-cleanup worker:

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info   # scheduler, separate process
```

Verification codes are printed to the `uvicorn` console in development —
there's no real email provider wired up (see `app/core/notifications.py`).

## Running with Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres, Redis, a one-shot `migrate` service (runs `alembic
upgrade head` then exits), the API (`http://localhost:8000/docs`), a Celery
worker, and Celery beat. `app`/`worker`/`beat` all wait for `migrate` to
finish successfully before starting.

## Creating an admin

`PATCH /users/{id}/role` requires an existing admin, so the first one has to
be created out-of-band:

```bash
python -m app.cli admin@example.com --first-name Jane           # local
docker compose exec app python -m app.cli admin@example.com     # Docker
```

Prompts for a password if `--password` isn't given. If the email is already
registered, promotes that account to admin instead of creating a new one.

## API overview

| Method | Path             | Access          | Description                          |
|--------|------------------|-----------------|---------------------------------------|
| POST   | /auth/signup     | public          | Register a new (unverified) account   |
| POST   | /auth/login      | public          | Exchange credentials for a token pair |
| POST   | /auth/refresh    | public          | Exchange a refresh token for a new pair |
| POST   | /auth/verify     | public          | Confirm a verification code           |
| GET    | /me              | authenticated   | Current user's profile                |
| GET    | /users           | admin           | List users, paginated (`?page=&page_size=`) |
| GET    | /users/{id}      | admin           | Get a user by id                      |
| PATCH  | /users/{id}      | self or admin   | Update first/last name                |
| PATCH  | /users/{id}/role | admin           | Change a user's role (not your own)   |
| DELETE | /users/{id}      | admin           | Delete a user                         |

Full interactive docs (Swagger UI) at `/docs` once the app is running.

## Known simplifications

These are called out inline in the code as `ponytail:` comments too — listed
here for visibility:

- **No token revocation.** JWTs carry a `jti` claim but nothing checks it
  against a blacklist, so logout can't invalidate an outstanding access/
  refresh token before it expires naturally. A real implementation would
  keep a Redis set of revoked `jti`s with a TTL matching the token's
  remaining lifetime.
- **No production notification backend.** `NotificationService` has one
  implementation (console print). A real email/SMS provider would be a
  second class behind the same interface.
- **`role: native_enum=False`** stores role as a plain `VARCHAR`, not a
  native Postgres `ENUM` type — trades a little DB-level strictness for
  migrations that don't need `ALTER TYPE ... ADD VALUE`.