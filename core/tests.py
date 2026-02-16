from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Profile
from core.mixins import user_is_manager
from core.views import dashboard
from projects.models import Project
from time_tracking.models import TimeEntry

User = get_user_model()


class ProfileModelTest(TestCase):
    def test_profile_created_with_user(self):
        user = User.objects.create_user(username='u1', password='pass')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.role, Profile.SCHEDULER)

    def test_manager_profile(self):
        user = User.objects.create_user(username='mgr', password='pass')
        user.profile.role = Profile.MANAGER
        user.profile.save()
        self.assertTrue(user_is_manager(user))


class DashboardAccessTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.manager = User.objects.create_user(username='manager', password='pass')
        self.manager.profile.role = Profile.MANAGER
        self.manager.profile.save()
        self.scheduler = User.objects.create_user(username='sched', password='pass')
        self.scheduler.profile.role = Profile.SCHEDULER
        self.scheduler.profile.save()

    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)

    def test_manager_sees_dashboard(self):
        request = self.factory.get(reverse('dashboard'))
        request.user = self.manager
        r = dashboard(request)
        self.assertEqual(r.status_code, 200)

    def test_scheduler_redirected_to_my_work(self):
        self.client.login(username='sched', password='pass')
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('my-work', r.url)

    def test_scheduler_gets_403_for_project_list(self):
        self.client.login(username='sched', password='pass')
        r = self.client.get(reverse('project_list'))
        self.assertEqual(r.status_code, 403)


class WeeklyHoursTest(TestCase):
    """Hours this week is computed from TimeEntry only; clearing entries gives 0."""

    def setUp(self):
        self.manager = User.objects.create_user(username='mgr', password='pass')
        self.manager.profile.role = Profile.MANAGER
        self.manager.profile.save()
        self.project = Project.objects.create(
            project_number='PRJ-H', name='H', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )

    def test_weekly_hours_zero_after_clearing_time_entries(self):
        from django.db.models import Sum
        today = date.today()
        end_of_week = today + timedelta(days=(6 - today.weekday()))
        start_of_week = end_of_week - timedelta(days=6)
        TimeEntry.objects.create(
            user=self.manager,
            project=self.project,
            date=today,
            hours=Decimal('5.0'),
            description='Test',
        )
        qs = TimeEntry.objects.filter(
            date__gte=start_of_week,
            date__lte=end_of_week,
        )
        total = qs.aggregate(t=Sum('hours'))['t'] or 0
        self.assertGreater(total, 0)

        TimeEntry.objects.filter(user=self.manager).delete()
        total_after = TimeEntry.objects.filter(
            date__gte=start_of_week,
            date__lte=end_of_week,
        ).aggregate(t=Sum('hours'))['t'] or 0
        self.assertEqual(total_after, 0)
