# Backfill: move non-standard work_type to 'other' + task_type_other

from django.db import migrations

VALID_WORK_TYPES = {
    'baseline_schedule_review',
    'schedule_update',
    'schedule_update_review',
    'claim_analysis',
    'other',
}


def backfill_work_type(apps, schema_editor):
    WorkItem = apps.get_model('work', 'WorkItem')
    for item in WorkItem.objects.exclude(work_type__in=VALID_WORK_TYPES):
        item.task_type_other = item.work_type or ''
        item.work_type = 'other'
        item.save(update_fields=['work_type', 'task_type_other'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0002_add_task_type_choices_and_other'),
    ]

    operations = [
        migrations.RunPython(backfill_work_type, noop),
    ]
