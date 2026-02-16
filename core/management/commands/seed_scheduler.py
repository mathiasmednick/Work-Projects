"""
Seed dev data: 1 manager, 2 schedulers, 2-3 projects, work items, time entries for current week.
Usage: python manage.py seed_scheduler
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Profile
from projects.models import Project
from work.models import WorkItem
from time_tracking.models import TimeEntry

User = get_user_model()


class Command(BaseCommand):
    help = 'Create sample users (manager + schedulers), projects, work items, and time entries.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for confirmation if data already exists.',
        )

    def handle(self, *args, **options):
        if User.objects.exists() and not options['no_input']:
            if input('Users already exist. Continue and add more data? [y/N]: ') != 'y':
                self.stdout.write('Aborted.')
                return

        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # Users and profiles
        manager, _ = User.objects.get_or_create(
            username='Mathias',
            defaults={'email': 'mathias@example.com', 'first_name': 'Mathias', 'is_staff': True},
        )
        manager.set_password('devpass')
        manager.save()
        prof, _ = Profile.objects.get_or_create(user=manager, defaults={'role': Profile.MANAGER})
        if prof.role != Profile.MANAGER:
            prof.role = Profile.MANAGER
            prof.save()
        self.stdout.write(f'Manager: {manager.username} / devpass')

        s1, _ = User.objects.get_or_create(
            username='scheduler1',
            defaults={'email': 's1@example.com'},
        )
        s1.set_password('devpass')
        s1.save()
        Profile.objects.get_or_create(user=s1, defaults={'role': Profile.SCHEDULER})

        s2, _ = User.objects.get_or_create(
            username='scheduler2',
            defaults={'email': 's2@example.com'},
        )
        s2.set_password('devpass')
        s2.save()
        Profile.objects.get_or_create(user=s2, defaults={'role': Profile.SCHEDULER})

        self.stdout.write('Schedulers: scheduler1, scheduler2 / devpass')

        # Clear time entries for seed users so dashboard shows 0 hours until time is logged
        TimeEntry.objects.filter(user__in=[manager, s1, s2]).delete()

        # Projects
        p1, _ = Project.objects.get_or_create(
            project_number='PRJ-001',
            defaults={
                'name': 'Building A',
                'client': 'Acme Corp',
                'pm': 'Jane Doe',
                'project_manager': manager,
                'status': Project.STATUS_ACTIVE,
                'notes': 'Main site.',
            },
        )
        if not p1.project_manager_id:
            p1.project_manager = manager
            p1.save(update_fields=['project_manager'])
        p2, _ = Project.objects.get_or_create(
            project_number='PRJ-002',
            defaults={
                'name': 'Building B',
                'client': 'Beta Inc',
                'pm': 'John Smith',
                'project_manager': manager,
                'status': Project.STATUS_ACTIVE,
                'notes': '',
            },
        )
        if not p2.project_manager_id:
            p2.project_manager = manager
            p2.save(update_fields=['project_manager'])
        p3, _ = Project.objects.get_or_create(
            project_number='PRJ-003',
            defaults={
                'name': 'Retrofit C',
                'client': 'Gamma LLC',
                'pm': 'Jane Doe',
                'status': Project.STATUS_ON_HOLD,
                'notes': 'On hold until Q2.',
            },
        )
        self.stdout.write('Projects: Building A, B, Retrofit C')

        # Work items (mix of overdue, due this week, assigned)
        WorkItem.objects.get_or_create(
            project=p1,
            title='Schedule foundation pour',
            defaults={
                'work_type': WorkItem.WORK_TYPE_BASELINE,
                'priority': WorkItem.PRIORITY_HIGH,
                'due_date': today - timedelta(days=3),
                'status': WorkItem.STATUS_OPEN,
                'assigned_to': s1,
                'requested_by': 'Superintendent',
                'notes': '',
            },
        )
        WorkItem.objects.get_or_create(
            project=p1,
            title='Coordinate MEP rough-in',
            defaults={
                'work_type': WorkItem.WORK_TYPE_UPDATE,
                'priority': WorkItem.PRIORITY_HIGH,
                'due_date': today + timedelta(days=2),
                'status': WorkItem.STATUS_IN_PROGRESS,
                'assigned_to': s1,
                'requested_by': 'PM',
                'notes': '',
            },
        )
        WorkItem.objects.get_or_create(
            project=p2,
            title='Update 3-week lookahead',
            defaults={
                'work_type': WorkItem.WORK_TYPE_UPDATE_REVIEW,
                'priority': WorkItem.PRIORITY_MEDIUM,
                'due_date': end_of_week,
                'status': WorkItem.STATUS_OPEN,
                'assigned_to': s2,
                'requested_by': 'Manager',
                'notes': '',
            },
        )
        WorkItem.objects.get_or_create(
            project=p1,
            title='Submittal log review',
            defaults={
                'work_type': WorkItem.WORK_TYPE_OTHER,
                'task_type_other': 'Admin',
                'priority': WorkItem.PRIORITY_LOW,
                'due_date': today + timedelta(days=5),
                'status': WorkItem.STATUS_OPEN,
                'assigned_to': s2,
                'requested_by': '',
                'notes': '',
            },
        )
        WorkItem.objects.get_or_create(
            project=p2,
            title='Overdue item for demo',
            defaults={
                'work_type': WorkItem.WORK_TYPE_OTHER,
                'task_type_other': 'Demo',
                'priority': WorkItem.PRIORITY_HIGH,
                'due_date': today - timedelta(days=10),
                'status': WorkItem.STATUS_OPEN,
                'assigned_to': s1,
                'requested_by': '',
                'notes': 'Shows in overdue list.',
            },
        )
        self.stdout.write('Work items: 5 created or already exist.')

        self.stdout.write(self.style.SUCCESS('Seed complete. Log in as Mathias/devpass or scheduler1/devpass.'))
