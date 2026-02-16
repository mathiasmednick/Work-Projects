from django.contrib import admin
from .models import WorkItem


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'work_type', 'task_type_other', 'priority', 'due_date', 'status', 'assigned_to')
    list_filter = ('priority', 'status', 'work_type')
    search_fields = ('title', 'notes')
    date_hierarchy = 'due_date'
