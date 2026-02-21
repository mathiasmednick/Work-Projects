from django.urls import path, reverse_lazy
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('activity/', views.ActivityListView.as_view(), name='activity_list'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('weather/', views.WeatherDashboardView.as_view(), name='weather'),
    path('weather/list/', RedirectView.as_view(url=reverse_lazy('weather_table'), permanent=False), name='weather_list_redirect'),
    path('weather/table/', views.WeatherTableView.as_view(), name='weather_table'),
    path('weather/project/<int:project_id>/', views.WeatherProjectDetailView.as_view(), name='weather_project_detail'),
    path('weather/refresh/', views.WeatherRefreshView.as_view(), name='weather_refresh'),
    path('schedule-email-builder/', views.ScheduleEmailBuilderView.as_view(), name='schedule_email_builder'),
    path('schedule-email-builder/test/', views.ScheduleEmailBuilderTestRunnerView.as_view(), name='schedule_email_builder_test'),
]
