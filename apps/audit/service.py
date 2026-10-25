from .models import AuditLog


def record(actor, action: str, object_type: str, object_id, **metadata) -> None:
    """Write an audit entry. Callers must pass identifiers/enums only - no PII or free text."""
    AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        object_type=object_type,
        object_id=str(object_id),
        metadata=metadata,
    )
