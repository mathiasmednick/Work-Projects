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
        addr_defaults = {
            'address_line1': '123 Main St',
            'city': 'Anytown',
            'state': 'CA',
            'zip_code': '90001',
            'country': 'US',
        }
        p1, _ = Project.objects.get_or_create(
            project_number='PRJ-001',
            defaults={
                'name': 'Building A',
                'client': 'Acme Corp',
                'pm': 'Jane Doe',
                'project_manager': manager,
                'status': Project.STATUS_ACTIVE,
                'notes': 'Main site.',
                **addr_defaults,
            },
        )
        if not p1.project_manager_id:
            p1.project_manager = manager
            p1.save(update_fields=['project_manager'])
        if not (p1.address_line1 or p1.city):
            for k, v in addr_defaults.items():
                setattr(p1, k, v)
            p1.save(update_fields=list(addr_defaults))
        p2, _ = Project.objects.get_or_create(
            project_number='PRJ-002',
            defaults={
                'name': 'Building B',
                'client': 'Beta Inc',
                'pm': 'John Smith',
                'project_manager': manager,
                'status': Project.STATUS_ACTIVE,
                'notes': '',
                **addr_defaults,
            },
        )
        if not p2.project_manager_id:
            p2.project_manager = manager
            p2.save(update_fields=['project_manager'])
        if not (p2.address_line1 or p2.city):
            for k, v in addr_defaults.items():
                setattr(p2, k, v)
            p2.save(update_fields=list(addr_defaults))
        p3, _ = Project.objects.get_or_create(
            project_number='PRJ-003',
            defaults={
                'name': 'Retrofit C',
                'client': 'Gamma LLC',
                'pm': 'Jane Doe',
                'status': Project.STATUS_ON_HOLD,
                'notes': 'On hold until Q2.',
                **addr_defaults,
            },
        )
        if not (p3.address_line1 or p3.city):
            for k, v in addr_defaults.items():
                setattr(p3, k, v)
            p3.save(update_fields=list(addr_defaults))
        self.stdout.write('Projects: Building A, B, Retrofit C')

        # Work items (mix of overdue, due this week, assigned); set _audit_user so signal logs with manager
        def get_or_create_work_item(project, title, **defaults):
            w = WorkItem.objects.filter(project=project, title=title).first()
            if w:
                return w
            w = WorkItem(project=project, title=title, **defaults)
            w._audit_user = manager
            w.save()
            return w

        get_or_create_work_item(
            p1, 'Schedule foundation pour',
            work_type=WorkItem.WORK_TYPE_BASELINE,
            priority=WorkItem.PRIORITY_HIGH,
            due_date=today - timedelta(days=3),
            status=WorkItem.STATUS_OPEN,
            assigned_to=s1,
            requested_by='Superintendent',
            notes='',
        )
        get_or_create_work_item(
            p1, 'Coordinate MEP rough-in',
            work_type=WorkItem.WORK_TYPE_UPDATE,
            priority=WorkItem.PRIORITY_HIGH,
            due_date=today + timedelta(days=2),
            status=WorkItem.STATUS_IN_PROGRESS,
            assigned_to=s1,
            requested_by='PM',
            notes='',
        )
        get_or_create_work_item(
            p2, 'Update 3-week lookahead',
            work_type=WorkItem.WORK_TYPE_UPDATE_REVIEW,
            priority=WorkItem.PRIORITY_MEDIUM,
            due_date=end_of_week,
            status=WorkItem.STATUS_OPEN,
            assigned_to=s2,
            requested_by='Manager',
            notes='',
        )
        get_or_create_work_item(
            p1, 'Submittal log review',
            work_type=WorkItem.WORK_TYPE_OTHER,
            task_type_other='Admin',
            priority=WorkItem.PRIORITY_LOW,
            due_date=today + timedelta(days=5),
            status=WorkItem.STATUS_OPEN,
            assigned_to=s2,
            requested_by='',
            notes='',
        )
        get_or_create_work_item(
            p2, 'Overdue item for demo',
            work_type=WorkItem.WORK_TYPE_OTHER,
            task_type_other='Demo',
            priority=WorkItem.PRIORITY_HIGH,
            due_date=today - timedelta(days=10),
            status=WorkItem.STATUS_OPEN,
            assigned_to=s1,
            requested_by='',
            notes='Shows in overdue list.',
        )
        self.stdout.write('Work items: 5 created or already exist.')

        self.stdout.write(self.style.SUCCESS('Seed complete. Log in as Mathias/devpass or scheduler1/devpass.'))
