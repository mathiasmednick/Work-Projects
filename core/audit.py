"""Helpers for writing audit log entries."""
from core.models import AuditLog


def log_action(user, model_name, object_id, object_repr, action):
    """Record an audit log entry."""
    AuditLog.objects.create(
        user=user,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr[:300],
        action=action,
    )
