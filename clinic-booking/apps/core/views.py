from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    """Liveness/readiness probe. Reports the deployed commit so CI can verify a rollout."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:  # noqa: BLE001 - any DB failure means not ready
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "commit": settings.GIT_COMMIT})


def not_found(request, exception=None):
    return JsonResponse(
        {"error": {"code": "not_found", "message": "Resource not found.", "details": {}}},
        status=404,
    )


def server_error(request):
    return JsonResponse(
        {"error": {"code": "server_error", "message": "Internal server error.", "details": {}}},
        status=500,
    )
