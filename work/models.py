from django.db import models
from django.conf import settings


class WorkItemQuerySet(models.QuerySet):
    def exclude_deleted(self):
        return self.filter(deleted_at__isnull=True)


class WorkItemManager(models.Manager.from_queryset(WorkItemQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class WorkItem(models.Model):
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]
    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_DONE = 'done'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_DONE, 'Done'),
    ]
    WORK_TYPE_BASELINE = 'baseline_schedule_review'
    WORK_TYPE_UPDATE = 'schedule_update'
    WORK_TYPE_UPDATE_REVIEW = 'schedule_update_review'
    WORK_TYPE_CLAIM = 'claim_analysis'
    WORK_TYPE_OTHER = 'other'
    WORK_TYPE_CHOICES = [
        (WORK_TYPE_BASELINE, 'Baseline schedule review'),
        (WORK_TYPE_UPDATE, 'Schedule update'),
        (WORK_TYPE_UPDATE_REVIEW, 'Schedule update review'),
        (WORK_TYPE_CLAIM, 'Claim analysis'),
        (WORK_TYPE_OTHER, 'Other'),
    ]

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='work_items',
    )
    title = models.CharField(max_length=300)
    work_type = models.CharField(max_length=50, choices=WORK_TYPE_CHOICES, default=WORK_TYPE_UPDATE)
    task_type_other = models.CharField(max_length=200, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    due_date = models.DateField(null=True, blank=True)
    meeting_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_work_items',
    )
    requested_by = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_work_items',
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deleted_work_items',
    )

    objects = WorkItemManager()
    all_objects = models.Manager()

    class Meta:
        db_table = 'work_workitem'
        ordering = ['-due_date', 'priority']

    def __str__(self):
        return self.title

    def get_display_work_type(self):
        if self.work_type == self.WORK_TYPE_OTHER and self.task_type_other:
            return f'Other: {self.task_type_other}'
        return self.get_work_type_display()

    @property
    def days_until_purge(self):
        """Days left before this deleted item is eligible for permanent purge (max 30)."""
        if not self.deleted_at:
            return None
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        if self.deleted_at < cutoff:
            return 0
        delta = timezone.now() - self.deleted_at
        return max(0, 30 - delta.days)
