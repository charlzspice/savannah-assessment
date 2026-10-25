import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only record of who did what to which record. Stores identifiers only, never
    names, contact details or free-text clinical notes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=32)
    object_id = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("AuditLog entries are immutable.")
        super().save(*args, **kwargs)
