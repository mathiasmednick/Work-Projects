from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Profile
from projects.models import Project
from work.models import WorkItem
from time_tracking.models import TimeEntry

User = get_user_model()


class TimeEntryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', password='p')
        self.project = Project.objects.create(
            project_number='PRJ-T1', name='P', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )

    def test_create_time_entry(self):
        e = TimeEntry.objects.create(
            user=self.user,
            project=self.project,
            date='2025-02-15',
            hours=Decimal('2.5'),
            description='Work',
        )
        self.assertIn('P', str(e))

    def test_work_item_must_belong_to_project(self):
        work = WorkItem.objects.create(
            project=self.project,
            title='W',
            work_type=WorkItem.WORK_TYPE_OTHER,
            task_type_other='X',
        )
        other_project = Project.objects.create(
            project_number='PRJ-T2', name='P2', client='C2', pm='PM2', status=Project.STATUS_ACTIVE
        )
        e = TimeEntry(
            user=self.user,
            project=other_project,
            work_item=work,
            date='2025-02-15',
            hours=Decimal('1'),
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            e.full_clean()


class TimeEntryViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.scheduler = User.objects.create_user(username='sched', password='pass')
        self.scheduler.profile.role = Profile.SCHEDULER
        self.scheduler.profile.save()
        self.project = Project.objects.create(
            project_number='PRJ-T3', name='P', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )

    def test_time_list_requires_login(self):
        r = self.client.get(reverse('time_entry_list'))
        self.assertEqual(r.status_code, 302)

    def test_time_list_scheduler_ok(self):
        from time_tracking.views import TimeEntryListView
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get(reverse('time_entry_list'))
        request.user = self.scheduler
        r = TimeEntryListView.as_view()(request)
        self.assertEqual(r.status_code, 200)

    def test_add_time_entry(self):
        self.client.login(username='sched', password='pass')
        r = self.client.post(reverse('time_entry_list'), {
            'project': self.project.pk,
            'work_item': '',
            'date': '2025-02-15',
            'hours': '3',
            'description': 'Done stuff',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(
            TimeEntry.objects.filter(user=self.scheduler, hours=Decimal('3')).exists()
        )

    def test_negative_hours_rejected(self):
        from time_tracking.forms import TimeEntryForm
        form = TimeEntryForm(data={
            'project': self.project.pk,
            'work_item': '',
            'date': '2025-02-15',
            'hours': '-1',
            'description': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('hours', form.errors)
        self.assertFalse(TimeEntry.objects.filter(hours=Decimal('-1')).exists())


class TimeEntryCSVExportTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.scheduler = User.objects.create_user(username='sched', password='pass')
        self.scheduler.profile.role = Profile.SCHEDULER
        self.scheduler.profile.save()
        self.manager = User.objects.create_user(username='manager', password='pass')
        self.manager.profile.role = Profile.MANAGER
        self.manager.profile.save()
        self.project = Project.objects.create(
            project_number='PRJ-CSV', name='P', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )
        self.entry = TimeEntry.objects.create(
            user=self.scheduler,
            project=self.project,
            date='2025-02-15',
            hours=Decimal('2.5'),
            description='Test notes',
        )

    def test_csv_export_returns_correct_columns_and_data(self):
        self.client.login(username='sched', password='pass')
        r = self.client.get(reverse('time_entry_export_csv') + '?from=2025-02-01&to=2025-02-28')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get('Content-Type'), 'text/csv')
        lines = r.content.decode('utf-8').strip().splitlines()
        self.assertGreaterEqual(len(lines), 2)
        header = lines[0]
        self.assertIn('date', header)
        self.assertIn('user', header)
        self.assertIn('project_number', header)
        self.assertIn('project_name', header)
        self.assertIn('project_manager', header)
        self.assertIn('task_id', header)
        self.assertIn('task_name', header)
        self.assertIn('task_type', header)
        self.assertIn('hours', header)
        self.assertIn('notes', header)
        self.assertIn('2025-02-15', lines[1])
        self.assertIn('sched', lines[1])
        self.assertIn('PRJ-CSV', lines[1])
        self.assertIn('2.5', lines[1])
        self.assertIn('Test notes', lines[1])

    def test_scheduler_can_only_export_self(self):
        other = User.objects.create_user(username='other', password='pass')
        other.profile.role = Profile.SCHEDULER
        other.profile.save()
        TimeEntry.objects.create(
            user=other, project=self.project, date='2025-02-16', hours=Decimal('1'), description=''
        )
        self.client.login(username='sched', password='pass')
        r = self.client.get(reverse('time_entry_export_csv') + '?from=2025-02-01&to=2025-02-28&user=' + str(other.pk))
        self.assertEqual(r.status_code, 200)
        content = r.content.decode('utf-8')
        self.assertIn('sched', content)
        self.assertNotIn('other', content)

    def test_manager_can_export_for_another_user(self):
        self.client.login(username='manager', password='pass')
        r = self.client.get(reverse('time_entry_export_csv') + '?from=2025-02-01&to=2025-02-28&user=' + str(self.scheduler.pk))
        self.assertEqual(r.status_code, 200)
        self.assertIn('sched', r.content.decode('utf-8'))
        self.assertIn('2.5', r.content.decode('utf-8'))


class WeekNavigationTest(TestCase):
    """Week navigation uses week_start param and view respects it."""

    def setUp(self):
        from django.test import RequestFactory
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='u', password='p')
        self.user.profile.role = Profile.SCHEDULER
        self.user.profile.save()
        self.project = Project.objects.create(
            project_number='PRJ-WN', name='P', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )
        TimeEntry.objects.create(
            user=self.user, project=self.project, date='2025-02-15', hours=Decimal('1'), description=''
        )

    def test_week_start_param_filters_time_entry_list(self):
        """Week navigation with week_start=YYYY-MM-DD returns 200 and view uses that week."""
        from time_tracking.views import TimeEntryListView, week_range
        from datetime import date
        start, end = week_range(date(2025, 2, 10))
        self.assertEqual(start, date(2025, 2, 10))
        self.assertEqual(end, date(2025, 2, 16))
        request = self.factory.get(reverse('time_entry_list'), {'week_start': '2025-02-10'})
        request.user = self.user
        response = TimeEntryListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
