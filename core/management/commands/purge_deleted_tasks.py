"""
Permanently delete WorkItem rows that were soft-deleted more than 30 days ago.
Usage: python manage.py purge_deleted_tasks
"""
from django.utils import timezone
from django.core.management.base import BaseCommand
from datetime import timedelta

from work.models import WorkItem


class Command(BaseCommand):
    help = 'Permanently delete tasks that have been in Recently Deleted for more than 30 days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report how many would be deleted, do not delete.',
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30)
        qs = WorkItem.all_objects.filter(
            deleted_at__isnull=False,
            deleted_at__lt=cutoff,
        )
        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No tasks to purge.'))
            return
        if options['dry_run']:
            self.stdout.write(f'Would permanently delete {count} task(s). Run without --dry-run to purge.')
            return
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f'Permanently deleted {count} task(s).'))
