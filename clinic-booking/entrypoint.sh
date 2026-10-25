#!/bin/sh
set -e

# Migrations run on boot so the free Render tier (no pre-deploy command) still works.
# With >1 instance, move this to a one-off release job to avoid concurrent migrations.
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate --noinput
fi

# Synthetic demo data only (idempotent). Never enable against real patient data.
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo
fi

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 30 \
  --access-logfile -
