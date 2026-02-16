from django.contrib import admin
from .models import TimeEntry


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'work_item', 'date', 'hours', 'description_short')
    list_filter = ('date', 'user')
    search_fields = ('description',)

    @admin.display(description='Description')
    def description_short(self, obj):
        if not obj.description:
            return ''
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description
