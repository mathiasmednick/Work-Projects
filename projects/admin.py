from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('project_number', 'name', 'client', 'pm', 'project_manager', 'status')
    list_filter = ('status',)
    search_fields = ('project_number', 'name', 'client', 'pm')
