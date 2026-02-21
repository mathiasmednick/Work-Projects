import csv
from datetime import date, timedelta
from io import StringIO
from django.shortcuts import redirect, render
from django.contrib import messages
from django.views import View
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Sum
from django.http import HttpResponse
from django.contrib.auth import get_user_model

from core.mixins import SchedulerOrManagerMixin, user_is_manager
from .models import TimeEntry
from .forms import TimeEntryForm

User = get_user_model()


def week_range(ref_date):
    """Return (start, end) for the week containing ref_date (Mon–Sun)."""
    start = ref_date - timedelta(days=ref_date.weekday())
    end = start + timedelta(days=6)
    return start, end


class TimeEntryListView(SchedulerOrManagerMixin, View):
    """Quick add form + weekly list of time entries. Schedulers see only their own."""
    def get(self, request):
        week_str = request.GET.get('week_start') or request.GET.get('week')  # YYYY-MM-DD (Monday)
        if week_str:
            try:
                ref = date.fromisoformat(week_str)
            except (ValueError, TypeError):
                ref = date.today()
        else:
            ref = date.today()
        start, end = week_range(ref)

        qs = TimeEntry.objects.filter(user=request.user).filter(
            date__gte=start,
            date__lte=end,
        ).select_related('project', 'work_item').order_by('date', 'id')

        initial = {'date': ref}
        project_id = request.GET.get('project')
        work_item_id = request.GET.get('work_item')
        if work_item_id and project_id:
            initial['work_item'] = work_item_id
            initial['project'] = project_id
        elif project_id:
            initial['project'] = project_id
        form = TimeEntryForm(initial=initial)
        if project_id:
            from work.models import WorkItem
            form.fields['work_item'].queryset = WorkItem.objects.filter(project_id=project_id)
        prev_week = start - timedelta(days=7)
        next_week = start + timedelta(days=7)
        week_total_hours = qs.aggregate(t=Sum('hours'))['t'] or 0

        return render(request, 'time_tracking/time_entry_list.html', {
            'form': form,
            'entries': qs,
            'week_start': start,
            'week_end': end,
            'prev_week': prev_week,
            'next_week': next_week,
            'week_total_hours': week_total_hours,
            'today': date.today(),
        })

    def post(self, request):
        form = TimeEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.save()
            messages.success(request, 'Time entry added.')
            return redirect('time_entry_list')
        try:
            from datetime import datetime
            ref = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
        except (ValueError, TypeError):
            ref = date.today()
        start, end = week_range(ref)
        qs = TimeEntry.objects.filter(user=request.user).filter(
            date__gte=start,
            date__lte=end,
        ).select_related('project', 'work_item').order_by('date', 'id')
        week_total_hours = qs.aggregate(t=Sum('hours'))['t'] or 0
        return render(request, 'time_tracking/time_entry_list.html', {
            'form': form,
            'entries': qs,
            'week_start': start,
            'week_end': end,
            'prev_week': start - timedelta(days=7),
            'next_week': start + timedelta(days=7),
            'week_total_hours': week_total_hours,
            'today': date.today(),
        })


class TimeEntryUpdateView(SchedulerOrManagerMixin, UpdateView):
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'time_tracking/time_entry_form.html'
    success_url = reverse_lazy('time_entry_list')
    context_object_name = 'entry'

    def get_queryset(self):
        return TimeEntry.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Time entry updated.')
        return super().form_valid(form)


class TimeEntryDeleteView(SchedulerOrManagerMixin, DeleteView):
    model = TimeEntry
    success_url = reverse_lazy('time_entry_list')
    template_name = 'time_tracking/time_entry_confirm_delete.html'
    context_object_name = 'entry'

    def get_queryset(self):
        return TimeEntry.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Time entry deleted.')
        return super().form_valid(form)


def _timesheet_user(request):
    """User whose timesheet we're viewing: manager can choose via GET user=; scheduler only self."""
    if user_is_manager(request.user):
        user_id = request.GET.get('user')
        if user_id:
            return User.objects.filter(pk=user_id).first() or request.user
    return request.user


class TimesheetSummaryView(SchedulerOrManagerMixin, View):
    """Aggregate time entries by week and project (and task type). Filter by user and date range."""
    def get(self, request):
        target_user = _timesheet_user(request)
        week_str = request.GET.get('week_start') or request.GET.get('week')
        if week_str:
            try:
                ref = date.fromisoformat(week_str)
            except (ValueError, TypeError):
                ref = date.today()
        else:
            ref = date.today()
        start, end = week_range(ref)

        entries = TimeEntry.objects.filter(
            user=target_user,
            date__gte=start,
            date__lte=end,
        ).select_related('project', 'work_item', 'project__project_manager').order_by('date', 'project__project_number')

        # Group by (week_start, project, task_type) -> hours
        from collections import defaultdict
        groups = defaultdict(lambda: {'hours': 0, 'project': None, 'task_type': ''})
        for e in entries:
            key = (e.project_id, e.work_item.get_display_work_type() if e.work_item else '—')
            if groups[key]['project'] is None:
                groups[key]['project'] = e.project
                groups[key]['task_type'] = key[1]
            groups[key]['hours'] += float(e.hours)

        summary = [{'project': v['project'], 'task_type': v['task_type'], 'hours': v['hours']} for v in groups.values()]
        summary.sort(key=lambda x: (x['project'].project_number if x['project'] else '', x['task_type']))

        return render(request, 'time_tracking/timesheet_summary.html', {
            'week_start': start,
            'week_end': end,
            'summary': summary,
            'total_hours': sum(s['hours'] for s in summary),
            'target_user': target_user,
            'is_manager': user_is_manager(request.user),
            'users': User.objects.filter(time_entries__isnull=False).distinct().order_by('username') if user_is_manager(request.user) else [],
            'prev_week': start - timedelta(days=7),
            'next_week': start + timedelta(days=7),
        })


class TimeEntryCSVExportView(SchedulerOrManagerMixin, View):
    """Export time entries as CSV. Scheduler exports self; manager can choose user via GET user=."""
    def get(self, request):
        target_user = _timesheet_user(request)
        if not user_is_manager(request.user) and target_user != request.user:
            return HttpResponse('Forbidden', status=403)
        date_from = request.GET.get('from') or (date.today() - timedelta(days=30)).isoformat()
        date_to = request.GET.get('to') or date.today().isoformat()
        try:
            from_d = date.fromisoformat(date_from)
            to_d = date.fromisoformat(date_to)
        except (ValueError, TypeError):
            from_d = date.today() - timedelta(days=30)
            to_d = date.today()

        entries = TimeEntry.objects.filter(
            user=target_user,
            date__gte=from_d,
            date__lte=to_d,
        ).select_related('project', 'work_item', 'project__project_manager').order_by('date', 'id')

        buf = StringIO()
        w = csv.writer(buf)
        w.writerow([
            'date', 'user', 'project_number', 'project_name', 'project_manager',
            'task_id', 'task_name', 'task_type', 'hours', 'notes',
        ])
        for e in entries:
            pm = e.project.project_manager if e.project else None
            pm_name = (pm.get_full_name() or pm.username) if pm else ''
            task_type = e.work_item.get_display_work_type() if e.work_item else ''
            task_id = e.work_item_id or ''
            task_name = (e.work_item.title if e.work_item else '') or ''
            w.writerow([
                e.date.isoformat(),
                target_user.username,
                e.project.project_number if e.project else '',
                e.project.name if e.project else '',
                pm_name,
                task_id,
                task_name,
                task_type,
                e.hours,
                (e.description or ''),
            ])

        response = HttpResponse(buf.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="time_entries_{target_user.username}_{from_d}_{to_d}.csv"'
        return response
