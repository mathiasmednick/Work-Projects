from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from pathlib import Path

from core.models import Profile
from projects.models import Project
from projects.views import ProjectListView

User = get_user_model()


class ProjectModelTest(TestCase):
    def test_create_project(self):
        p = Project.objects.create(
            project_number='PRJ-M1',
            name='Test Project',
            client='Client A',
            pm='Jane Doe',
            status=Project.STATUS_ACTIVE,
        )
        self.assertEqual(str(p), 'Test Project')


class ProjectViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.manager = User.objects.create_user(username='manager', password='pass')
        self.manager.profile.role = Profile.MANAGER
        self.manager.profile.save()
        self.scheduler = User.objects.create_user(username='sched', password='pass')
        self.scheduler.profile.role = Profile.SCHEDULER
        self.scheduler.profile.save()

    def test_project_list_requires_manager(self):
        self.client.login(username='sched', password='pass')
        r = self.client.get(reverse('project_list'))
        self.assertEqual(r.status_code, 403)

    def test_project_list_manager_ok(self):
        request = self.factory.get(reverse('project_list'))
        request.user = self.manager
        r = ProjectListView.as_view()(request)
        self.assertEqual(r.status_code, 200)

    def test_project_create_manager_ok(self):
        self.client.login(username='manager', password='pass')
        r = self.client.post(reverse('project_create'), {
            'project_number': 'PRJ-NEW',
            'name': 'New Proj',
            'client': 'C',
            'pm': 'P',
            'status': Project.STATUS_ACTIVE,
            'notes': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Project.objects.filter(name='New Proj').exists())

    def test_manager_can_delete_project(self):
        p = Project.objects.create(
            project_number='PRJ-DEL', name='To Delete', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )
        self.client.login(username='manager', password='pass')
        r = self.client.post(reverse('project_delete', kwargs={'pk': p.pk}))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('project_list'))
        self.assertFalse(Project.objects.filter(pk=p.pk).exists())

    def test_scheduler_cannot_delete_project(self):
        p = Project.objects.create(
            project_number='PRJ-NODEL', name='No Delete', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )
        self.client.login(username='sched', password='pass')
        r = self.client.get(reverse('project_delete', kwargs={'pk': p.pk}))
        self.assertEqual(r.status_code, 403)
        r2 = self.client.post(reverse('project_delete', kwargs={'pk': p.pk}))
        self.assertEqual(r2.status_code, 403)
        self.assertTrue(Project.objects.filter(pk=p.pk).exists())

    def test_project_detail_template_has_single_pm_row(self):
        template_path = Path(__file__).resolve().parent / 'templates' / 'projects' / 'project_detail.html'
        content = template_path.read_text(encoding='utf-8')
        self.assertIn('<th>PM</th>', content)
        self.assertNotIn('<th>Project manager</th>', content)
