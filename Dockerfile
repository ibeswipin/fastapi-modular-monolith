# Single-stage: all deps ship prebuilt wheels, no compiler needed.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

COPY app app
COPY alembic alembic
COPY alembic.ini .

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# No HEALTHCHECK here: this image is reused for app/worker/beat/migrate with
# different commands, and a /health HTTP check is only meaningful for app —
# see the per-service `healthcheck:` overrides in docker-compose.yml instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
