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

    def test_scheduler_can_view_whiteboard(self):
        from core.views import WhiteboardListView
        request = self.factory.get(reverse('whiteboard'))
        request.user = self.scheduler
        r = WhiteboardListView.as_view()(request)
        self.assertEqual(r.status_code, 200)

    def test_scheduler_gets_403_for_whiteboard_post(self):
        from core.models import Board
        board = Board.objects.create(name='Test Board')
        self.client.login(username='sched', password='pass')
        r = self.client.post(reverse('whiteboard_item_create', kwargs={'board_id': board.pk}), {'type': 'NOTE', 'x': 0, 'y': 0})
        self.assertEqual(r.status_code, 403)

    def test_scheduler_can_access_weather(self):
        from core.views import WeatherDashboardView
        request = self.factory.get(reverse('weather'))
        request.user = self.scheduler
        r = WeatherDashboardView.as_view()(request)
        self.assertEqual(r.status_code, 200)

    def test_scheduler_can_access_weather_project_detail(self):
        from core.views import WeatherProjectDetailView
        proj = Project.objects.create(
            project_number='PRJ-W', name='Weather Proj', client='C', pm='P', status=Project.STATUS_ACTIVE
        )
        request = self.factory.get(reverse('weather_project_detail', kwargs={'project_id': proj.pk}))
        request.user = self.scheduler
        r = WeatherProjectDetailView.as_view()(request, project_id=proj.pk)
        self.assertEqual(r.status_code, 200)

    def test_weather_dashboard_includes_risk_labels(self):
        request = self.factory.get(reverse('weather'))
        request.user = self.manager
        from core.views import WeatherDashboardView
        r = WeatherDashboardView.as_view()(request)
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('High Risk Projects', content)
        self.assertIn('Moderate Risk Projects', content)
        self.assertIn('Clear Projects', content)

    def test_weather_el_segundo_forecast(self):
        """Local test: El Segundo CA project gets forecast with precip_prob 0-100 and non-UNKNOWN risk."""
        from core.models import ProjectWeatherCache
        from core.weather_utils import get_forecast_for_project, get_risk_level, get_daily_precip_prob
        import json
        proj = Project.objects.create(
            project_number='PRJ-ELSEG',
            name='El Segundo Test',
            client='C',
            pm='P',
            status=Project.STATUS_ACTIVE,
            city='El Segundo',
            state='CA',
        )
        try:
            result = get_forecast_for_project(proj, force_refresh=True)
        except Exception:
            self.skipTest('Network or Open-Meteo unavailable')
        if result is None:
            self.skipTest('Open-Meteo returned no forecast (e.g. rate limit or network)')
        self.assertIsNotNone(result, 'get_forecast_for_project should return forecast for El Segundo, CA')
        cache = ProjectWeatherCache.objects.filter(project=proj).first()
        self.assertIsNotNone(cache)
        self.assertTrue(cache.forecast_json)
        data = json.loads(cache.forecast_json)
        daily = data.get('daily') or {}
        times = daily.get('time') or []
        self.assertGreater(len(times), 0, 'Forecast should have daily data')
        for i in range(min(7, len(times))):
            prob = get_daily_precip_prob(cache.forecast_json, i)
            self.assertIsNotNone(prob, f'Day {i} should have precip prob')
            self.assertIsInstance(prob, int)
            self.assertGreaterEqual(prob, 0)
            self.assertLessEqual(prob, 100)
        risk = get_risk_level(cache.forecast_json)
        self.assertNotEqual(risk, 'UNKNOWN', 'Risk should be HIGH/MODERATE/LOW/CLEAR when forecast exists')


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


class ScheduleEmailBuilderTest(TestCase):
    """Schedule Update Email Builder is local-only: GET renders page; POST is rejected."""

    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.scheduler = User.objects.create_user(username='sched', password='pass')
        self.scheduler.profile.role = Profile.SCHEDULER
        self.scheduler.profile.save()

    def test_page_loads_for_logged_in_scheduler(self):
        from core.views import ScheduleEmailBuilderView
        self.client.login(username='sched', password='pass')
        request = self.factory.get(reverse('schedule_email_builder'))
        request.user = self.scheduler
        r = ScheduleEmailBuilderView.as_view()(request)
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        self.assertIn('Schedule Update Email Builder', content)
        self.assertIn('Your CSV is processed locally', content)
        self.assertIn('schedule_email_builder.js', content)

    def test_post_returns_405_method_not_allowed(self):
        self.client.login(username='sched', password='pass')
        r = self.client.post(reverse('schedule_email_builder'), {})
        self.assertEqual(r.status_code, 405)

    def test_no_remote_scripts_in_template(self):
        """Builder page must not load scripts from CDN (local-only)."""
        from core.views import ScheduleEmailBuilderView
        self.client.login(username='sched', password='pass')
        request = self.factory.get(reverse('schedule_email_builder'))
        request.user = self.scheduler
        r = ScheduleEmailBuilderView.as_view()(request)
        content = r.content.decode()
        self.assertIn('static', content)
        self.assertNotIn('cdnjs.cloudflare.com', content)
        self.assertNotIn('cdn.jsdelivr', content)
        self.assertNotIn('unpkg.com', content)
