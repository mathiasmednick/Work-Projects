from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class TimeEntry(models.Model):
    WORK_CODE_SCHEDULE_UPDATE = 'schedule_update'
    WORK_CODE_BASELINE_UPDATE = 'baseline_update'
    WORK_CODE_SCHEDULE_ANALYSIS = 'schedule_analysis'
    WORK_CODE_CHOICES = [
        (WORK_CODE_SCHEDULE_UPDATE, 'Schedule update'),
        (WORK_CODE_BASELINE_UPDATE, 'Baseline update'),
        (WORK_CODE_SCHEDULE_ANALYSIS, 'Schedule analysis'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries',
    )
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='time_entries',
    )
    work_item = models.ForeignKey(
        'work.WorkItem',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='time_entries',
    )
    work_code = models.CharField(max_length=50, choices=WORK_CODE_CHOICES, blank=True)
    date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'time_tracking_timeentry'
        ordering = ['-date', '-id']
        verbose_name_plural = 'Time entries'

    def __str__(self):
        return f"{self.user.username} - {self.project.name} - {self.date}: {self.hours}h"

    def clean(self):
        super().clean()
        if self.work_item_id and self.project_id and self.work_item.project_id != self.project_id:
            raise ValidationError(
                {'work_item': 'Work item must belong to the selected project.'}
            )
        if self.hours is not None and self.hours < 0:
            raise ValidationError({'hours': 'Hours cannot be negative.'})