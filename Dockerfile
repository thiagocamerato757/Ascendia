# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv for fast, reproducible dependency installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

WORKDIR /app

# Install runtime dependencies first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application code.
COPY . .

# Collectstatic and migrate run at container start (they need runtime env),
# see docker-compose.yml. Serve the ASGI app with gunicorn + uvicorn worker.
EXPOSE 8000
CMD ["gunicorn", "core.asgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]
