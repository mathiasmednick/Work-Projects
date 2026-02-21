from datetime import date, timedelta
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.db.models import Q, Sum
from django.views.generic import ListView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from core.mixins import user_is_manager, ManagerRequiredMixin, SchedulerOrManagerMixin
from core.models import AuditLog, ProjectWeatherCache, ProjectWeatherLocation
from core.weather_utils import get_daily_precip_prob, get_max_precip_prob_7day, get_risk_level, parse_forecast_days, RISK_UNKNOWN, _project_has_address
from work.models import WorkItem
from time_tracking.models import TimeEntry
from projects.models import Project
from django.utils import timezone as tz


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
    active_work_items_total = overdue.count() + due_this_week.count()

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
        'active_work_items_total': active_work_items_total,
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


class WeatherDashboardView(SchedulerOrManagerMixin, LoginRequiredMixin, View):
    """Weather Risk Monitor dashboard: KPI cards, project list with risk, right-side 7-day detail."""

    def get(self, request):
        projects = list(Project.objects.filter(status=Project.STATUS_ACTIVE).order_by('project_number'))
        cache_by_id = {c.project_id: c for c in ProjectWeatherCache.objects.filter(project_id__in=[p.id for p in projects])}
        project_rows = []
        counts = {'HIGH': 0, 'MODERATE': 0, 'LOW': 0, 'CLEAR': 0, 'UNKNOWN': 0}
        for p in projects:
            cache = cache_by_id.get(p.id)
            forecast_json = cache.forecast_json if cache else None
            risk = RISK_UNKNOWN if not _project_has_address(p) else get_risk_level(forecast_json)
            counts[risk] = counts.get(risk, 0) + 1
            today_precip = get_daily_precip_prob(forecast_json, 0) if forecast_json else None
            today_temp = None
            preview_days = []
            if cache and cache.forecast_json:
                try:
                    data = json.loads(cache.forecast_json)
                    daily = data.get('daily') or {}
                    highs = daily.get('temperature_2m_max') or []
                    if highs:
                        today_temp = highs[0]
                    for i in range(min(7, len(daily.get('time') or []))):
                        preview_days.append(get_daily_precip_prob(forecast_json, i))
                except (json.JSONDecodeError, TypeError):
                    pass
            max_precip_prob = get_max_precip_prob_7day(forecast_json)
            project_rows.append({
                'project': p,
                'cache': cache,
                'risk_level': risk,
                'max_precip_prob': max_precip_prob,
                'has_address': _project_has_address(p),
                'today_precip_prob': today_precip,
                'today_temp': today_temp,
                'preview_days': preview_days,
            })
        selected_project = None
        selected_cache = None
        forecast_days = []
        selected_id = request.GET.get('project')
        selected_max_precip_prob = None
        if selected_id:
            try:
                sid = int(selected_id)
                selected_project = next((p for p in projects if p.id == sid), None)
                selected_cache = cache_by_id.get(selected_project.id) if selected_project else None
                forecast_days = parse_forecast_days(selected_cache.forecast_json) if selected_cache else []
                selected_max_precip_prob = get_max_precip_prob_7day(selected_cache.forecast_json) if selected_cache else None
            except (ValueError, AttributeError):
                pass
        return render(request, 'core/weather_dashboard.html', {
            'project_rows': project_rows,
            'count_high': counts['HIGH'],
            'count_moderate': counts['MODERATE'],
            'count_low': counts['LOW'],
            'count_clear': counts['CLEAR'],
            'count_unknown': counts['UNKNOWN'],
            'selected_project': selected_project,
            'selected_cache': selected_cache,
            'selected_max_precip_prob': selected_max_precip_prob,
            'forecast_days': forecast_days,
        })


class WeatherTableView(SchedulerOrManagerMixin, LoginRequiredMixin, View):
    """Table view of active projects with cached forecast at /weather/table/."""

    def get(self, request):
        projects = list(Project.objects.filter(status=Project.STATUS_ACTIVE).order_by('project_number'))
        cache_by_id = {c.project_id: c for c in ProjectWeatherCache.objects.filter(project_id__in=[p.id for p in projects])}
        project_rows = []
        for p in projects:
            cache = cache_by_id.get(p.id)
            risk = RISK_UNKNOWN if not _project_has_address(p) else get_risk_level(cache.forecast_json if cache else None)
            max_precip_prob = get_max_precip_prob_7day(cache.forecast_json if cache else None)
            project_rows.append({
                'project': p, 'cache': cache, 'risk_level': risk,
                'max_precip_prob': max_precip_prob, 'has_address': _project_has_address(p),
            })
        return render(request, 'core/weather_list.html', {'project_rows': project_rows})


class WeatherProjectDetailView(SchedulerOrManagerMixin, LoginRequiredMixin, View):
    """Per-project weather detail (7-day forecast, risk badge)."""

    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id, status=Project.STATUS_ACTIVE)
        cache = ProjectWeatherCache.objects.filter(project=project).first()
        forecast_json = cache.forecast_json if cache else None
        risk_level = get_risk_level(forecast_json)
        max_precip_prob = get_max_precip_prob_7day(forecast_json)
        forecast_days = parse_forecast_days(forecast_json)
        today_precip = get_daily_precip_prob(forecast_json, 0) if forecast_json else None
        return render(request, 'core/weather_project_detail.html', {
            'project': project,
            'cache': cache,
            'risk_level': risk_level,
            'max_precip_prob': max_precip_prob,
            'has_address': _project_has_address(project),
            'forecast_days': forecast_days,
            'today_precip_prob': today_precip,
        })


def _schedule_email_builder_csp():
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'self';"
    )


class ScheduleEmailBuilderView(SchedulerOrManagerMixin, LoginRequiredMixin, View):
    """Schedule Update Email Builder: GET only. Renders the page; all CSV processing is client-side.
    POST and any other methods return 405. No CSV or schedule data is ever accepted by the server."""

    # Strict local-only: only GET is allowed; no uploads
    http_method_names = ['get']

    def get(self, request):
        response = render(request, 'core/schedule_email_builder.html')
        response['Content-Security-Policy'] = _schedule_email_builder_csp()
        return response


class ScheduleEmailBuilderTestRunnerView(SchedulerOrManagerMixin, LoginRequiredMixin, View):
    """GET-only page that runs JS unit tests for the schedule email builder (engine, question generator)."""

    http_method_names = ['get']

    def get(self, request):
        response = render(request, 'core/schedule_email_builder_test.html')
        response['Content-Security-Policy'] = _schedule_email_builder_csp()
        return response


class WeatherRefreshView(SchedulerOrManagerMixin, LoginRequiredMixin, View):
    """POST: trigger weather cache refresh for a project or all. Redirects back to weather."""

    def post(self, request):
        from django.core.management import call_command
        project_id = request.POST.get('project_id')
        try:
            call_command('refresh_weather', project_id=str(project_id) if project_id else '')
        except Exception as e:
            messages.warning(request, f'Refresh failed: {e}')
        else:
            messages.success(request, 'Weather data refreshed.')
        return redirect('weather')
