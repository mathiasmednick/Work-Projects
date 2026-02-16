from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def user_is_manager(user):
    """Return True if user has manager role. Users without a profile are treated as non-manager."""
    if not user or not user.is_authenticated:
        return False
    profile = getattr(user, 'profile', None)
    if profile is None:
        return False
    return profile.role == 'manager'


class ManagerRequiredMixin(LoginRequiredMixin):
    """Restrict view to users with manager role. Others get 403."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_is_manager(request.user):
            return HttpResponseForbidden('Manager access required.')
        return super().dispatch(request, *args, **kwargs)


class SchedulerOrManagerMixin(LoginRequiredMixin):
    """Allow schedulers and managers. Redirect others (e.g. no profile) to login or 403."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            return HttpResponseForbidden('No role assigned.')
        if profile.role not in ('manager', 'scheduler'):
            return HttpResponseForbidden('Scheduler or manager access required.')
        return super().dispatch(request, *args, **kwargs)
