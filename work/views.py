from datetime import date, timedelta
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.utils import timezone
from django.contrib import messages
from django.views.generic import ListView, DetailView, UpdateView, DeleteView, CreateView, View
from django.urls import reverse_lazy
from core.mixins import SchedulerOrManagerMixin, ManagerRequiredMixin, user_is_manager
from core.audit import log_action
from core.models import AuditLog
from time_tracking.models import TimeEntry
from .models import WorkItem
from .forms import WorkItemForm, CompleteTaskTimeForm

DELETED_RETENTION_DAYS = 30


SORT_FIELDS = {
    'project_number': 'project__project_number',
    'project_name': 'project__name',
    'pm': 'project__project_manager__username',
    'assigned_to': 'assigned_to__username',
    'created': 'created_at',
    'due_date': 'due_date',
    'meeting_at': 'meeting_at',
    'status': 'status',
    'work_type': 'work_type',
}


class MyWorkListView(SchedulerOrManagerMixin, ListView):
    """Assigned work items for the current user, with optional filters and sort."""
    model = WorkItem
    context_object_name = 'work_items'
    template_name = 'work/my_work.html'
    paginate_by = 10

    def _base_queryset(self):
        if getattr(self.request.user, 'profile', None) and self.request.user.profile.role == 'manager':
            return WorkItem.objects.all().select_related('project', 'assigned_to', 'project__project_manager')
        return WorkItem.objects.filter(assigned_to=self.request.user).select_related('project')

    def get_queryset(self):
        from django.contrib.auth import get_user_model
        from projects.models import Project
        GET = self.request.GET
        qs = self._base_queryset()
        today = date.today()

        # Tab filters
        if GET.get('overdue') == '1':
            qs = qs.filter(due_date__lt=today, status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS))
        if GET.get('due_soon') == '1':
            end = today + timedelta(days=7)
            qs = qs.filter(
                due_date__gte=today,
                due_date__lte=end,
                status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
            )
        if GET.get('status'):
            qs = qs.filter(status=GET.get('status'))
        if GET.get('meeting_today') == '1':
            qs = qs.filter(meeting_at__date=today)

        # Advanced filters
        if GET.get('project'):
            qs = qs.filter(project_id=GET.get('project'))
        if GET.get('project_manager'):
            qs = qs.filter(project__project_manager_id=GET.get('project_manager'))
        if GET.get('assigned_to'):
            qs = qs.filter(assigned_to_id=GET.get('assigned_to'))
        if GET.get('work_type'):
            qs = qs.filter(work_type=GET.get('work_type'))
        try:
            if GET.get('created_after'):
                qs = qs.filter(created_at__date__gte=date.fromisoformat(GET.get('created_after')))
            if GET.get('created_before'):
                qs = qs.filter(created_at__date__lte=date.fromisoformat(GET.get('created_before')))
        except (ValueError, TypeError):
            pass
        try:
            if GET.get('due_after'):
                qs = qs.filter(due_date__gte=GET.get('due_after'))
            if GET.get('due_before'):
                qs = qs.filter(due_date__lte=GET.get('due_before'))
        except (ValueError, TypeError):
            pass
        search = (GET.get('q') or '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(project__name__icontains=search)
                | Q(project__project_number__icontains=search)
            )

        # Sort (when meeting today, default to meeting time order)
        sort = GET.get('sort') or ('meeting_at' if GET.get('meeting_today') == '1' else 'due_date')
        order = (GET.get('order') or ('asc' if GET.get('meeting_today') == '1' else 'desc')).lower()
        if sort == 'meeting_at':
            if order == 'asc':
                qs = qs.order_by(F('meeting_at').asc(nulls_last=True), 'priority')
            else:
                qs = qs.order_by(F('meeting_at').desc(nulls_last=True), 'priority')
        elif sort in SORT_FIELDS:
            order_by = SORT_FIELDS[sort]
            if order == 'asc':
                qs = qs.order_by(order_by, 'priority')
            else:
                qs = qs.order_by(f'-{order_by}', 'priority')
        else:
            qs = qs.order_by('-due_date', 'priority')

        return qs

    def get_context_data(self, **kwargs):
        from django.contrib.auth import get_user_model
        from projects.models import Project
        User = get_user_model()
        ctx = super().get_context_data(**kwargs)
        GET = self.request.GET
        ctx['filter_overdue'] = GET.get('overdue') == '1'
        ctx['filter_due_soon'] = GET.get('due_soon') == '1'
        ctx['filter_meeting_today'] = GET.get('meeting_today') == '1'
        ctx['filter_status'] = GET.get('status', '')
        ctx['is_manager'] = getattr(getattr(self.request.user, 'profile', None), 'role', None) == 'manager'
        today = date.today()
        end_soon = today + timedelta(days=7)
        base = self._base_queryset()
        ctx['overdue_count'] = base.filter(due_date__lt=today, status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS)).count()
        ctx['due_soon_count'] = base.filter(
            due_date__gte=today,
            due_date__lte=end_soon,
            status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
        ).count()
        ctx['meeting_today_count'] = base.filter(meeting_at__date=today).count()
        ctx['in_progress_count'] = base.filter(status=WorkItem.STATUS_IN_PROGRESS).count()
        ctx['done_count'] = base.filter(status=WorkItem.STATUS_DONE).count()
        ctx['today'] = today
        # Filter options for template
        ctx['filter_project'] = GET.get('project', '')
        ctx['filter_project_manager'] = GET.get('project_manager', '')
        ctx['filter_assigned_to'] = GET.get('assigned_to', '')
        ctx['filter_work_type'] = GET.get('work_type', '')
        ctx['filter_created_after'] = GET.get('created_after', '')
        ctx['filter_created_before'] = GET.get('created_before', '')
        ctx['filter_due_after'] = GET.get('due_after', '')
        ctx['filter_due_before'] = GET.get('due_before', '')
        ctx['filter_q'] = GET.get('q', '')
        ctx['sort'] = GET.get('sort', 'due_date')
        ctx['order'] = GET.get('order', 'desc')
        ctx['projects'] = Project.objects.all().order_by('project_number')
        ctx['project_managers'] = User.objects.filter(managed_projects__isnull=False).distinct().order_by('username')
        ctx['assignees'] = User.objects.filter(username__in=['Mathias', 'scheduler1']).order_by('username')
        ctx['work_type_choices'] = WorkItem.WORK_TYPE_CHOICES
        ctx['sort_options'] = SORT_FIELDS
        # My Priorities: overdue, due soon, or high priority
        base = self._base_queryset()
        today = date.today()
        end_soon = today + timedelta(days=7)
        from django.db.models import Q
        ctx['my_priorities'] = base.filter(
            Q(due_date__lt=today, status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS))
            | Q(due_date__gte=today, due_date__lte=end_soon, status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS))
            | Q(priority=WorkItem.PRIORITY_HIGH, status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS))
        ).distinct().order_by('due_date', 'priority')[:10]
        q = GET.copy()
        q.pop('page', None)
        ctx['pagination_query'] = q.urlencode()
        return ctx


def _work_item_queryset(request):
    """Queryset for task detail/edit/delete: manager sees all non-deleted, scheduler sees only assigned."""
    if getattr(request.user, 'profile', None) and request.user.profile.role == 'manager':
        return WorkItem.objects.all().select_related('project', 'assigned_to', 'updated_by')
    return WorkItem.objects.filter(assigned_to=request.user).select_related('project', 'assigned_to', 'updated_by')


class WorkItemCreateView(SchedulerOrManagerMixin, CreateView):
    model = WorkItem
    form_class = WorkItemForm
    template_name = 'work/workitem_form.html'
    context_object_name = 'work_item'

    def get_success_url(self):
        return reverse_lazy('dashboard') if user_is_manager(self.request.user) else reverse_lazy('my_work')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.instance._audit_user = self.request.user
        messages.success(self.request, 'Task created.')
        response = super().form_valid(form)
        if form.cleaned_data.get('status') == WorkItem.STATUS_DONE:
            return redirect('work_item_complete', pk=self.object.pk)
        return response


class WorkItemDetailView(SchedulerOrManagerMixin, DetailView):
    model = WorkItem
    context_object_name = 'work_item'
    template_name = 'work/workitem_detail.html'

    def get_queryset(self):
        return _work_item_queryset(self.request)


class WorkItemUpdateView(SchedulerOrManagerMixin, UpdateView):
    model = WorkItem
    form_class = WorkItemForm
    context_object_name = 'work_item'
    template_name = 'work/workitem_form.html'

    def get_queryset(self):
        return _work_item_queryset(self.request)

    def get_success_url(self):
        return reverse_lazy('work_item_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, 'Task updated.')
        response = super().form_valid(form)
        log_action(
            self.request.user,
            'workitem',
            self.object.pk,
            self.object.title,
            AuditLog.ACTION_UPDATE,
        )
        if form.cleaned_data.get('status') == WorkItem.STATUS_DONE:
            return redirect('work_item_complete', pk=self.object.pk)
        return response


class WorkItemDeleteView(SchedulerOrManagerMixin, DeleteView):
    model = WorkItem
    context_object_name = 'work_item'
    template_name = 'work/workitem_confirm_delete.html'

    def get_queryset(self):
        return _work_item_queryset(self.request)

    def get_success_url(self):
        return reverse_lazy('my_work')

    def form_valid(self, form):
        self.object.deleted_at = timezone.now()
        self.object.deleted_by = self.request.user
        self.object.save(update_fields=['deleted_at', 'deleted_by'])
        log_action(
            self.request.user,
            'workitem',
            self.object.pk,
            self.object.title,
            AuditLog.ACTION_DELETE,
        )
        messages.success(self.request, 'Task deleted. You can restore it from Recently Deleted within 30 days.')
        return redirect(self.get_success_url())


def _deleted_queryset(request):
    """Deleted items within retention window. Manager: all; scheduler: only own deleted."""
    cutoff = timezone.now() - timedelta(days=DELETED_RETENTION_DAYS)
    qs = WorkItem.all_objects.filter(
        deleted_at__isnull=False,
        deleted_at__gte=cutoff,
    ).select_related('project', 'assigned_to', 'deleted_by').order_by('-deleted_at')
    if getattr(request.user, 'profile', None) and request.user.profile.role == 'manager':
        return qs
    return qs.filter(deleted_by=request.user)


class WorkItemDeletedListView(ManagerRequiredMixin, ListView):
    """Recently deleted tasks (within 30 days). Manager-only."""
    model = WorkItem
    context_object_name = 'deleted_items'
    template_name = 'work/deleted_list.html'
    paginate_by = 20

    def get_queryset(self):
        return _deleted_queryset(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['retention_days'] = DELETED_RETENTION_DAYS
        ctx['is_manager'] = getattr(getattr(self.request.user, 'profile', None), 'role', None) == 'manager'
        return ctx


class WorkItemCompleteView(SchedulerOrManagerMixin, View):
    """Complete a task and log time: server-rendered form (date, hours, notes). Scheduler: assigned only; Manager: any."""
    def get(self, request, pk):
        work_item = get_object_or_404(_work_item_queryset(request), pk=pk)
        if work_item.status == WorkItem.STATUS_DONE:
            messages.info(request, 'Task already completed. Log time for this completion below.')
        form = CompleteTaskTimeForm(initial={'date_worked': date.today()})
        return render(request, 'work/workitem_complete_confirm.html', {'work_item': work_item, 'form': form})

    def post(self, request, pk):
        work_item = get_object_or_404(_work_item_queryset(request), pk=pk)
        form = CompleteTaskTimeForm(request.POST)
        if not form.is_valid():
            return render(request, 'work/workitem_complete_confirm.html', {'work_item': work_item, 'form': form})
        work_item.status = WorkItem.STATUS_DONE
        work_item.updated_by = request.user
        work_item.save(update_fields=['status', 'updated_by'])
        log_action(request.user, 'workitem', work_item.pk, work_item.title, AuditLog.ACTION_UPDATE)
        TimeEntry.objects.create(
            user=request.user,
            project=work_item.project,
            work_item=work_item,
            date=form.cleaned_data['date_worked'],
            hours=form.cleaned_data['hours'],
            description=form.cleaned_data.get('notes') or '',
        )
        messages.success(request, 'Task completed and time logged.')
        return redirect('my_work')


def work_recommend(request):
    """Scheduler recommendation: top open/in-progress items by due date and priority."""
    if not request.user.is_authenticated:
        return JsonResponse({'recommendations': []}, status=200)
    qs = WorkItem.objects.filter(
        assigned_to=request.user,
        status__in=(WorkItem.STATUS_OPEN, WorkItem.STATUS_IN_PROGRESS),
    ).order_by(F('due_date').asc(nulls_last=True), 'priority')[:10]
    recommendations = [
        {
            'title': item.title,
            'due_date': str(item.due_date) if item.due_date else '',
            'priority': item.get_priority_display(),
        }
        for item in qs
    ]
    return JsonResponse({'recommendations': recommendations})


class WorkItemRestoreView(SchedulerOrManagerMixin, View):
    """Restore a soft-deleted task. Only within 30 days; permission same as delete."""
    def post(self, request, pk):
        cutoff = timezone.now() - timedelta(days=DELETED_RETENTION_DAYS)
        qs = WorkItem.all_objects.filter(
            pk=pk,
            deleted_at__isnull=False,
            deleted_at__gte=cutoff,
        )
        if getattr(request.user, 'profile', None) and request.user.profile.role == 'manager':
            item = get_object_or_404(qs)
        else:
            item = get_object_or_404(qs, assigned_to=request.user)
        item.deleted_at = None
        item.deleted_by = None
        item.save(update_fields=['deleted_at', 'deleted_by'])
        log_action(request.user, 'workitem', item.pk, item.title, AuditLog.ACTION_RESTORE)
        messages.success(request, f'Task "{item.title}" restored.')
        return redirect('work_item_detail', pk=item.pk)
