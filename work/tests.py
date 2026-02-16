from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.models import Profile
from projects.models import Project
from work.models import WorkItem
from work.views import MyWorkListView
from time_tracking.models import TimeEntry

User = get_user_model()


class WorkItemModelTest(TestCase):
    def setUp(self):
        self.project = Project.objects.create(
            project_number='PRJ-W1', name='P', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )
        self.user = User.objects.create_user(username='u', password='p')

    def test_create_work_item(self):
        w = WorkItem.objects.create(
            project=self.project,
            title='Task',
            work_type=WorkItem.WORK_TYPE_UPDATE,
            priority=WorkItem.PRIORITY_HIGH,
            assigned_to=self.user,
        )
        self.assertEqual(str(w), 'Task')

    def test_priority_choices_and_old_value_rejected(self):
        from work.forms import WorkItemForm
        values = [value for value, _ in WorkItem.PRIORITY_CHOICES]
        self.assertEqual(values, [WorkItem.PRIORITY_LOW, WorkItem.PRIORITY_MEDIUM, WorkItem.PRIORITY_HIGH])
        form = WorkItemForm(data={
            'project': self.project.pk,
            'title': 'Bad priority',
            'work_type': WorkItem.WORK_TYPE_UPDATE,
            'priority': 'P1',
            'due_date': '',
            'status': WorkItem.STATUS_OPEN,
            'assigned_to': '',
            'requested_by': '',
            'notes': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('priority', form.errors)

    def test_assigned_to_queryset_only_mathias_and_scheduler1(self):
        from work.forms import WorkItemForm
        User.objects.create_user(username='Mathias', password='pass')
        User.objects.create_user(username='scheduler1', password='pass')
        User.objects.create_user(username='random_user', password='pass')
        form = WorkItemForm()
        usernames = list(form.fields['assigned_to'].queryset.values_list('username', flat=True))
        self.assertEqual(usernames, ['Mathias', 'scheduler1'])


class MyWorkViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.project = Project.objects.create(
            project_number='PRJ-W2', name='P', client='C', pm='PM', status=Project.STATUS_ACTIVE
        )
        self.scheduler = User.objects.create_user(username='sched', password='pass')
        self.scheduler.profile.role = Profile.SCHEDULER
        self.scheduler.profile.save()
        self.other = User.objects.create_user(username='other', password='pass')
        self.other.profile.role = Profile.SCHEDULER
        self.other.profile.save()
        self.assigned_item = WorkItem.objects.create(
            project=self.project,
            title='Mine',
            work_type=WorkItem.WORK_TYPE_OTHER,
            task_type_other='X',
            assigned_to=self.scheduler,
        )
        self.unassigned_item = WorkItem.objects.create(
            project=self.project,
            title='Not mine',
            work_type=WorkItem.WORK_TYPE_OTHER,
            task_type_other='X',
            assigned_to=self.other,
        )

    def test_scheduler_sees_only_assigned(self):
        request = self.factory.get(reverse('my_work'))
        request.user = self.scheduler
        r = MyWorkListView.as_view()(request)
        self.assertEqual(r.status_code, 200)
        r.render()
        self.assertIn(b'Mine', r.content)
        self.assertNotIn(b'Not mine', r.content)

    def test_new_task_button_links_to_create(self):
        url = reverse('work_item_create')
        self.assertEqual(url, '/my-work/create/')

    def test_manager_can_create_task_and_redirects_to_dashboard(self):
        manager = User.objects.create_user(username='mgr', password='pass')
        manager.profile.role = Profile.MANAGER
        manager.profile.save()
        self.client.login(username='mgr', password='pass')
        r = self.client.post(reverse('work_item_create'), {
            'project': self.project.pk,
            'title': 'New demo task',
            'work_type': WorkItem.WORK_TYPE_UPDATE,
            'task_type_other': '',
            'priority': WorkItem.PRIORITY_MEDIUM,
            'due_date': '',
            'status': WorkItem.STATUS_OPEN,
            'assigned_to': '',
            'requested_by': '',
            'notes': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('dashboard'))
        self.assertTrue(WorkItem.objects.filter(title='New demo task').exists())

    def test_completing_task_posts_hours_and_creates_time_entry(self):
        """Complete a task via work_item_complete; task is marked done and a TimeEntry is created."""
        self.assigned_item.status = WorkItem.STATUS_OPEN
        self.assigned_item.save()
        self.client.login(username='sched', password='pass')
        url = reverse('work_item_complete', kwargs={'pk': self.assigned_item.pk})
        r = self.client.post(url, {
            'date_worked': '2025-02-14',
            'hours': '2.5',
            'notes': 'Finished the task',
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('my_work'), r.url)
        self.assigned_item.refresh_from_db()
        self.assertEqual(self.assigned_item.status, WorkItem.STATUS_DONE)
        entry = TimeEntry.objects.filter(
            user=self.scheduler,
            work_item=self.assigned_item,
            date='2025-02-14',
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(float(entry.hours), 2.5)
        self.assertEqual(entry.description, 'Finished the task')
