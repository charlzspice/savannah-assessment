import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key-not-for-production-use-0123456789")

from .settings import *  # noqa: E402, F403

DEBUG = False
SECRET_KEY = "test-only-secret-key-not-for-production-use-0123456789"  # noqa: S105  # nosec B105
ALLOWED_HOSTS = ["testserver", "localhost"]
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {k: "100000/min" for k in ("anon", "user", "booking", "auth")},
}

MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405
