from django.db.models.signals import post_save
from django.dispatch import receiver

from core.audit import log_action
from core.models import AuditLog
from .models import WorkItem


@receiver(post_save, sender=WorkItem)
def log_work_item_create(sender, instance, created, **kwargs):
    """Log audit entry when a WorkItem is created (e.g. from admin or seed). User may be None."""
    if not created:
        return
    user = getattr(instance, '_audit_user', None)
    log_action(user, 'workitem', instance.pk, instance.title, AuditLog.ACTION_CREATE)
