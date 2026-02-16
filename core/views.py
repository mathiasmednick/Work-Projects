from datetime import date, timedelta
from django.shortcuts import redirect, render
from django.db.models import Q, Sum
from django.views.generic import ListView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from core.mixins import user_is_manager, ManagerRequiredMixin, SchedulerOrManagerMixin
from core.models import AuditLog
from work.models import WorkItem
from time_tracking.models import TimeEntry
from projects.models import Project


def _week_range(ref_date):
    """Return (start, end) for the week containing ref_date (Mon–Sun)."""
    start = ref_date - timedelta(days=ref_date.weekday())
    return start, start + timedelta(days=6)


def dashboard(request):
    """Manager dashboard: overdue work, due this week, hours by project/user this week."""
    if not request.user.is_authenticated:
        return redirect('login')
    if not user_is_manager(request.user):
        return redirect('my_work')

    today = date.today()
    week_start_str = request.GET.get('week_start')
    if week_start_str:
        try:
            ref = date.fromisoformat(week_start_str)
        except (ValueError, TypeError):
            ref = today
    else:
        ref = today
    start_of_week, end_of_week = _week_range(ref)
    prev_week = start_of_week - timedelta(days=7)
    next_week = start_of_week + timedelta(days=7)

    overdue = WorkItem.objects.filter(
        due_date__lt=today,
        status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
    ).select_related('project', 'assigned_to').order_by('due_date')

    due_this_week = WorkItem.objects.filter(
        due_date__gte=today,
        due_date__lte=end_of_week,
        status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
    ).select_related('project', 'assigned_to').order_by('due_date')

    time_this_week = TimeEntry.objects.filter(
        date__gte=start_of_week,
        date__lte=end_of_week,
    )
    hours_by_project = (
        time_this_week.values('project__name')
        .annotate(total=Sum('hours'))
        .order_by('-total')
    )
    hours_by_user = (
        time_this_week.values('user__username')
        .annotate(total=Sum('hours'))
        .order_by('-total')
    )
    total_hours_week = time_this_week.aggregate(t=Sum('hours'))['t'] or 0
    open_tasks_count = WorkItem.objects.filter(
        status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
    ).count()
    overdue_count = WorkItem.objects.filter(
        due_date__lt=today,
        status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
    ).count()
    completed_this_week = WorkItem.objects.filter(
        status=WorkItem.STATUS_DONE,
        updated_at__date__gte=start_of_week,
        updated_at__date__lte=end_of_week,
    ).count()
    active_projects_count = Project.objects.filter(status=Project.STATUS_ACTIVE).count()
    active_work_items = list(overdue[:5]) + list(due_this_week[:5])

    return render(request, 'core/dashboard.html', {
        'overdue': overdue,
        'due_this_week': due_this_week,
        'hours_by_project': hours_by_project,
        'hours_by_user': hours_by_user,
        'week_start': start_of_week,
        'week_end': end_of_week,
        'prev_week': prev_week,
        'next_week': next_week,
        'total_hours_week': total_hours_week,
        'open_tasks_count': open_tasks_count,
        'overdue_count': overdue_count,
        'completed_this_week': completed_this_week,
        'active_projects_count': active_projects_count,
        'active_work_items': active_work_items,
        'today': today,
    })


class ActivityListView(ManagerRequiredMixin, ListView):
    """Edit history: recent create/update/delete/restore actions. Manager-only."""
    model = AuditLog
    context_object_name = 'audit_logs'
    template_name = 'core/activity_list.html'
    paginate_by = 25
    ordering = ['-timestamp']

    def get_queryset(self):
        return AuditLog.objects.select_related('user').order_by('-timestamp')


class SearchView(SchedulerOrManagerMixin, View):
    """Global search: projects by number/name, tasks by title or id. GET q=."""
    template_name = 'core/search_results.html'

    def get(self, request):
        q = (request.GET.get('q') or '').strip()
        projects = []
        tasks = []
        if q:
            is_mgr = user_is_manager(request.user)
            projects = list(Project.objects.filter(
                Q(project_number__icontains=q) | Q(name__icontains=q)
            ).order_by('project_number')[:15])
            task_qs = WorkItem.objects.select_related('project').filter(
                Q(title__icontains=q) | (Q(pk=int(q)) if q.isdigit() else Q(pk=-1))
            )
            if not is_mgr:
                task_qs = task_qs.filter(assigned_to=request.user)
            tasks = list(task_qs.order_by('-due_date')[:15])
        return render(request, 'core/search_results.html', {
            'query': q,
            'projects': projects,
            'tasks': tasks,
        })


class ProfileView(LoginRequiredMixin, View):
    """Profile page: user info and links to Edit Profile, Logout."""

    def get(self, request):
        return render(request, 'core/profile.html', {'user': request.user})


class ProfileEditView(LoginRequiredMixin, View):
    """Edit profile: first_name, last_name, email."""

    def get(self, request):
        return render(request, 'core/profile_edit.html', {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
        })

    def post(self, request):
        request.user.first_name = request.POST.get('first_name', '').strip()
        request.user.last_name = request.POST.get('last_name', '').strip()
        request.user.email = request.POST.get('email', '').strip()
        request.user.save()
        messages.success(request, 'Profile updated.')
        return redirect('profile')
