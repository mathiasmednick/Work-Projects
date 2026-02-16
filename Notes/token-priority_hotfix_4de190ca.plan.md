---
name: Token-priority hotfix
overview: "Minimal hotfixes: wire New Task/Work Item buttons to a new create view, add profile page and clickable sidebar user, enforce manager-only access and logout, fix hours-from-TimeEntry and seed (Mathias, 0 hours after seed), plus three targeted tests."
todos: []
isProject: false
---

# Token-Priority Hotfix Plan

Minimal diffs only. No refactors. Existing URLs/templates preserved; additive where possible.

---

## 1) Fix "+ New Work Item" and "+ New Task" buttons

**Current state**

- [core/templates/core/dashboard.html](gc_scheduler/core/templates/core/dashboard.html) has `<a href="#" class="btn btn-primary">+ New Work Item</a>`.
- [work/templates/work/my_work.html](gc_scheduler/work/templates/work/my_work.html) has `<a href="#" class="btn btn-primary">+ New Task</a>`.
- No task create view or URL exists; [work/urls.py](gc_scheduler/work/urls.py) has detail/edit/delete/restore/deleted list only. [work/forms.py](gc_scheduler/work/forms.py) and [work/templates/work/workitem_form.html](gc_scheduler/work/templates/work/workitem_form.html) already support create (form has no instance; template uses "New task" and Cancel → my_work when `work_item` is absent).

**Changes**

- **work/views.py**: Add `WorkItemCreateView` (inherit `SchedulerOrManagerMixin`, `CreateView`). Use existing `WorkItemForm`, `template_name='work/workitem_form.html'`, `context_object_name='work_item'` (will be None). In `form_valid`: set `updated_by=request.user`, call `log_action(..., ACTION_CREATE)` (optional, for audit), then `super().form_valid`. Override `get_success_url`: if `user_is_manager(request.user)` return `reverse_lazy('dashboard')`, else `reverse_lazy('my_work')`. Manager must be able to create (and assign); schedulers create (form already has `assigned_to`; no need to restrict for this hotfix).
- **work/urls.py**: Add `path('create/', views.WorkItemCreateView.as_view(), name='work_item_create')` (place before `<int:pk>/` so `create/` is not captured as pk).
- **Templates**:  
  - [core/templates/core/dashboard.html](gc_scheduler/core/templates/core/dashboard.html): Replace `href="#"` with `href="{% url 'work_item_create' %}"`.  
  - [work/templates/work/my_work.html](gc_scheduler/work/templates/work/my_work.html): Replace `href="#"` with `href="{% url 'work_item_create' %}"`.
- **Form errors**: [work/templates/work/workitem_form.html](gc_scheduler/work/templates/work/workitem_form.html) already shows `form.errors` in a `<ul class="messages">` block; ensure it is visible (e.g. use class `error` for list items). No change needed if already present.

**Result**: Both buttons go to `/my-work/create/`. After save, manager → dashboard, scheduler → my work. Invalid form shows errors.

---

## 2) Sidebar profile icon clickable + Profile and Edit Profile pages

**Current state**

- [templates/base.html](gc_scheduler/templates/base.html): `.sidebar-user` is a plain div (lines 51–57); not wrapped in a link.
- No `/profile/` or `/profile/edit/` in [core/urls.py](gc_scheduler/core/urls.py) or root urls.

**Changes**

- **base.html**: Wrap the entire `.sidebar-user` block in `<a href="{% url 'profile' %}">...</a>` so the avatar and name/role are clickable (single link to profile page).
- **core/views.py**: Add two views (both require login; use `LoginRequiredMixin` or equivalent).
  - `ProfileView`: GET only; render template with `request.user` (and `request.user.profile` if needed). Template shows: username, first_name, last_name, email, role (from profile); links: "Edit Profile", "Logout".
  - `ProfileEditView`: FormView or simple GET/POST. Form fields: `first_name`, `last_name`, `email` (User model). Optional: add a separate "Change password" link that goes to Django's `password_change` if you add it to auth urls (optional per spec). POST: update `request.user` fields, save, redirect to profile with message. Use a small custom form (no ModelForm necessary) or `UserChangeForm`-style with only those fields.
- **core/urls.py**: Add `path('profile/', views.ProfileView.as_view(), name='profile')` and `path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit')`.
- **Templates**: Create `core/templates/core/profile.html` (read-only user info + links to Edit Profile and Logout). Create `core/templates/core/profile_edit.html` (form for first_name, last_name, email; submit/cancel).
- **Logout**: In profile template and optionally in profile edit, add link `{% url 'logout' %}` (Django's `django.contrib.auth.urls` provides `logout`). No URL change needed; root already includes `path('accounts/', include('django.contrib.auth.urls'))`.

**Result**: Bottom-left user block is clickable → `/profile/`. Profile page shows info and links to Edit Profile and Logout. Edit profile updates name/email; password change optional.

---

## 3) Auth and role separation

**Current state**

- Dashboard in [core/views.py](gc_scheduler/core/views.py) already redirects non-managers to `my_work` (lines 17–18).
- [projects/views.py](gc_scheduler/projects/views.py): `ProjectListView`, `ProjectCreateView`, etc. use `ManagerRequiredMixin` (403 for non-managers).
- [core/views.py](gc_scheduler/core/views.py): `ActivityListView` uses `ManagerRequiredMixin`.
- [work/views.py](gc_scheduler/work/views.py): `WorkItemDeletedListView` uses `SchedulerOrManagerMixin`; schedulers currently can access `/my-work/deleted/` and see only their own deleted items. Requirement: "scheduler cannot access ... deleted tasks" → treat as manager-only.

**Changes**

- **work/views.py**: Change `WorkItemDeletedListView` to use `ManagerRequiredMixin` instead of `SchedulerOrManagerMixin` so schedulers get 403 (and nav already hides "Recently Deleted" for schedulers).
- **Nav**: [templates/base.html](gc_scheduler/templates/base.html) already hides Overview, Recently Deleted, Projects, Edit History for non-managers via `{% if user|user_role == 'manager' %}`. No change needed.
- **Logout**: Ensure logout works: link to `{% url 'logout' %}` (or `accounts/logout/`) and that `LOGIN_URL` / `LOGOUT_REDIRECT_URL` are set if desired (e.g. redirect to login after logout). Default Django behavior is to redirect to admin or `/`; set `LOGOUT_REDIRECT_URL = '/accounts/login/'` in settings if not already, so "logout then login as scheduler" flow is clear.

**Result**: Scheduler cannot open overview, projects, edit history, or deleted list (403 or redirect). Nav hides those. Logout works and returns to login.

---

## 4) "Hours this week" correctness and fresh-demo behavior

**Current state**

- [core/views.py](gc_scheduler/core/views.py) (lines 35–49): `time_this_week = TimeEntry.objects.filter(date__gte=start_of_week, date__lte=end_of_week)` and `total_hours_week = time_this_week.aggregate(t=Sum('hours'))['t'] or 0`. Hours are already computed only from `TimeEntry`; no task cache. So the logic is correct. The issue is data: if old `TimeEntry` rows exist (e.g. from a previous seed run), hours stay non-zero after "deleting tasks." Tasks and time entries are independent; deleting tasks does not delete time entries.

**Changes**

- **Dashboard**: No change to the hours query (already TimeEntry-only). Optionally ensure week boundaries are consistent (e.g. Mon–Sun); current code uses `end_of_week = today + timedelta(days=(6 - today.weekday()))`, `start_of_week = end_of_week - timedelta(days=6)` (Mon–Sun). Leave as-is unless you find a bug.
- **Seed**: In [core/management/commands/seed_scheduler.py](gc_scheduler/core/management/commands/seed_scheduler.py):
  - After creating/getting the manager and the two schedulers (by username), delete all `TimeEntry` rows for those users so a re-run or fresh run starts with 0 hours. Example: after the three `Profile.objects.get_or_create(...)` blocks, run `TimeEntry.objects.filter(user__in=[manager, s1, s2]).delete()`.
  - Remove (or stop creating) the "Time entries this week" block (the loop that does `TimeEntry.objects.get_or_create(...)` for the demo entries). That way, after `seed_scheduler`, the dashboard shows 0 hours until the user logs time.
- **Optional**: Add a management command `reset_demo_data` that only does `TimeEntry.objects.filter(user__username__in=['Mathias', 'scheduler1', 'scheduler2']).delete()` (and optionally same users' work items if you want a full reset). Per spec you can do "OR update seed_scheduler"; the above (clear in seed + no time entries created) satisfies "fresh runs show 0" without a separate command. If you prefer a dedicated command for "reset demo data" without re-seeding, add it as one small command.

**Result**: Hours this week = sum of `TimeEntry` for the week only. After `seed_scheduler`, dashboard shows 0 hours. "Hours by Project" already uses `time_this_week.values('project__name').annotate(total=Sum('hours'))` (TimeEntry-based); no change.

---

## 5) Seed data: manager display name "Mathias"

**Current state**

- [core/management/commands/seed_scheduler.py](gc_scheduler/core/management/commands/seed_scheduler.py): Manager is `username='manager'`, password `devpass`, email `manager@example.com`.

**Changes**

- In `seed_scheduler`, change manager to use `username='Mathias'` (and keep password `devpass`). Update the `User.objects.get_or_create` for manager to `username='Mathias'` and set `first_name='Mathias'` in defaults (or leave first_name empty; username will show in sidebar if `get_full_name` is blank). Ensure any reference to the manager user later in the command (e.g. `project_manager=manager`, time entry loop) still uses the same variable. Final message: e.g. "Log in as Mathias/devpass or scheduler1/devpass."
- If you clear time entries by user list, use `[manager, s1, s2]` (the variables), not hardcoded usernames, so it works after renaming to Mathias.

**Result**: Manager login is Mathias / devpass. Seed message updated. Fresh seed → 0 hours (from step 4).

---

## 6) Tests (minimal)

- **New task button and create**: In `work/tests.py` (or a single test file): (1) Log in as manager, GET my_work, assert response contains `href` for `work_item_create` (or `/my-work/create/`). (2) POST to `work_item_create` with valid form data (project, title, work_type, etc.); assert redirect to dashboard and `WorkItem.objects.filter(title=...).exists()`.
- **Scheduler 403 on manager overview**: In `core/tests.py` or `projects/tests.py`: Log in as scheduler, GET `reverse('dashboard')`; assert status 302 and redirect to my_work (or 403 if you prefer). Same idea for `reverse('project_list')`: assert 403.
- **Weekly hours 0 after clearing time entries**: In `time_tracking` or `core` tests: Create a user and a `TimeEntry` for this week, assert dashboard or time_this_week aggregate > 0; then `TimeEntry.objects.filter(user=user).delete()` and assert the same aggregate is 0 (or that the dashboard view returns context `total_hours_week == 0` for that user’s scope if you pass a request with that user).

---

## 7) Commands to run (exact)

```bash
# From project root (gc_scheduler)
python manage.py migrate
python manage.py seed_scheduler --no-input
python manage.py runserver
```

Optional: if you add `reset_demo_data`, then:

```bash
python manage.py reset_demo_data
```

No new migrations required for this hotfix unless you add a new model (profile edit does not require new models; User already has first_name, last_name, email).

---

## File checklist (minimal edits)


| Area              | File                                                                                                                                                      | Action                                                                                      |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Buttons           | [core/templates/core/dashboard.html](gc_scheduler/core/templates/core/dashboard.html)                                                                     | Replace `#` with `{% url 'work_item_create' %}`                                             |
| Buttons           | [work/templates/work/my_work.html](gc_scheduler/work/templates/work/my_work.html)                                                                         | Same                                                                                        |
| Create view       | [work/views.py](gc_scheduler/work/views.py)                                                                                                               | Add `WorkItemCreateView`; import `CreateView`, `user_is_manager`                            |
| Create URL        | [work/urls.py](gc_scheduler/work/urls.py)                                                                                                                 | Add `path('create/', ...)` before `<int:pk>/`                                               |
| Sidebar           | [templates/base.html](gc_scheduler/templates/base.html)                                                                                                   | Wrap `.sidebar-user` in `<a href="{% url 'profile' %}">`                                    |
| Profile           | [core/views.py](gc_scheduler/core/views.py)                                                                                                               | Add `ProfileView`, `ProfileEditView`                                                        |
| Profile URLs      | [core/urls.py](gc_scheduler/core/urls.py)                                                                                                                 | Add `profile/`, `profile/edit/`                                                             |
| Profile templates | New: `core/templates/core/profile.html`, `core/templates/core/profile_edit.html`                                                                          | Profile read-only + Edit form                                                               |
| Deleted list      | [work/views.py](gc_scheduler/work/views.py)                                                                                                               | `WorkItemDeletedListView`: use `ManagerRequiredMixin`                                       |
| Logout redirect   | [gc_scheduler/settings.py](gc_scheduler/gc_scheduler/settings.py) (or project settings)                                                                   | Set `LOGOUT_REDIRECT_URL = '/accounts/login/'` if missing                                   |
| Hours/seed        | [core/management/commands/seed_scheduler.py](gc_scheduler/core/management/commands/seed_scheduler.py)                                                     | Manager username `Mathias`; clear TimeEntry for seed users; remove time-entry creation loop |
| Tests             | [work/tests.py](gc_scheduler/work/tests.py), [core/tests.py](gc_scheduler/core/tests.py) or [time_tracking/tests.py](gc_scheduler/time_tracking/tests.py) | Add the three tests above                                                                   |


---

## Optional (only if "easy")

- **Password change**: Add `path('accounts/', include('django.contrib.auth.urls'))` already includes `password_change` if `LOGIN_URL` is set. Add a "Change password" link on profile to `{% url 'password_change' %}` and a simple `password_change_done` redirect in settings. Omit if you want to keep the hotfix minimal.

