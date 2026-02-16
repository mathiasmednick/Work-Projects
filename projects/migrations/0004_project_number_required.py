# Make project_number non-null (after 0003 backfill)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_backfill_project_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='project_number',
            field=models.CharField(max_length=50, unique=True),
        ),
    ]
