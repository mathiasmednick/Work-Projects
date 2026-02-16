from django.db import models
from django.conf import settings


class Profile(models.Model):
    MANAGER = 'manager'
    SCHEDULER = 'scheduler'
    ROLE_CHOICES = [
        (MANAGER, 'Manager'),
        (SCHEDULER, 'Scheduler'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=SCHEDULER)

    class Meta:
        db_table = 'core_profile'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class AuditLog(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_RESTORE = 'restore'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
        (ACTION_RESTORE, 'Restore'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
    )
    model_name = models.CharField(max_length=50)  # e.g. 'workitem', 'project'
    object_id = models.PositiveIntegerField()
    object_repr = models.CharField(max_length=300)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_auditlog'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_action_display()} {self.model_name}#{self.object_id} by {self.user_id} at {self.timestamp}"
