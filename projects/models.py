from django.conf import settings
from django.db import models


class Project(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_ON_HOLD = 'on_hold'
    STATUS_COMPLETE = 'complete'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ON_HOLD, 'On Hold'),
        (STATUS_COMPLETE, 'Complete'),
    ]

    project_number = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=50, default='US', blank=True)
    client = models.CharField(max_length=200)
    pm = models.CharField(max_length=200)
    project_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_projects',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'projects_project'
        ordering = ['project_number']

    def __str__(self):
        return self.name
