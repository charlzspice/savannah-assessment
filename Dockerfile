# --- build stage: compile mysqlclient into a wheel (needs a compiler + client headers) ---
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# --- runtime stage: only the shared client library, no compiler ---
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels \
    pip install --no-index --find-links=/wheels -r requirements.txt

COPY . .
# Collect static assets (Swagger UI) at build time; the key is a throwaway used only for this step.
RUN DJANGO_SECRET_KEY=build-only-not-used-at-runtime python manage.py collectstatic --noinput \
    && chmod +x entrypoint.sh

# Run as an unprivileged user (numeric uid: no passwd entry needed).
USER 10001
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
