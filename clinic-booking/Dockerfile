FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Collect static assets (Swagger UI) at build time; the key is a throwaway used only for this step.
RUN DJANGO_SECRET_KEY=build-only-not-used-at-runtime python manage.py collectstatic --noinput \
    && chmod +x entrypoint.sh

# Run as an unprivileged user (numeric uid: no passwd entry needed).
USER 10001
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
