FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY services/api/pyproject.toml ./services/api/pyproject.toml
COPY services/api/src ./services/api/src
COPY services/api/alembic.ini ./services/api/alembic.ini
COPY services/api/alembic ./services/api/alembic
COPY services/ai/pyproject.toml ./services/ai/pyproject.toml
COPY services/ai/src ./services/ai/src
RUN python -m pip install --upgrade pip && python -m pip install ./services/api ./services/ai psycopg[binary]==3.2.10

USER 65532:65532
EXPOSE 8000
CMD ["uvicorn", "little_orbit_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "192.168.50.6,127.0.0.1"]
