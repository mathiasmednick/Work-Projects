from datetime import date, timedelta
from django.db.models import Sum, Q
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy

from core.mixins import ManagerRequiredMixin
from time_tracking.models import TimeEntry
from .models import Project
from .forms import ProjectForm


class ProjectListView(ManagerRequiredMixin, ListView):
    model = Project
    context_object_name = 'projects'
    template_name = 'projects/project_list.html'
    paginate_by = 10

    def get_queryset(self):
        qs = Project.objects.annotate(
            total_hours=Sum('time_entries__hours')
        ).order_by('name')
        if self.request.GET.get('status'):
            qs = qs.filter(status=self.request.GET.get('status'))
        if self.request.GET.get('q', '').strip():
            q = self.request.GET.get('q', '').strip()
            qs = qs.filter(
                Q(project_number__icontains=q) | Q(name__icontains=q) | Q(client__icontains=q) | Q(pm__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        ctx['total_hours_wtd'] = TimeEntry.objects.filter(
            date__gte=start,
            date__lte=end,
        ).aggregate(t=Sum('hours'))['t'] or 0
        ctx['pending_approvals'] = 0  # placeholder
        q = self.request.GET.copy()
        q.pop('page', None)
        ctx['pagination_query'] = q.urlencode()
        return ctx


class ProjectDetailView(ManagerRequiredMixin, DetailView):
    model = Project
    context_object_name = 'project'
    template_name = 'projects/project_detail.html'


class ProjectCreateView(ManagerRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'
    success_url = reverse_lazy('project_list')


class ProjectUpdateView(ManagerRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/project_form.html'
    context_object_name = 'project'

    def get_success_url(self):
        return reverse_lazy('project_detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(ManagerRequiredMixin, DeleteView):
    model = Project
    context_object_name = 'project'
    template_name = 'projects/project_confirm_delete.html'
    success_url = reverse_lazy('project_list')

    def form_valid(self, form):
        messages.success(self.request, 'Project deleted.')
        return super().form_valid(form)
