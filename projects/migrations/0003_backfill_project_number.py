# Data migration: backfill project_number for existing projects

from django.db import migrations


def backfill_project_number(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')
    for p in Project.objects.filter(project_number__isnull=True):
        p.project_number = f'PRJ-{p.pk}'
        p.save(update_fields=['project_number'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_add_project_number_and_pm'),
    ]

    operations = [
        migrations.RunPython(backfill_project_number, noop),
    ]
