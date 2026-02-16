from django.urls import path
from . import views

urlpatterns = [
    path('', views.TimeEntryListView.as_view(), name='time_entry_list'),
    path('summary/', views.TimesheetSummaryView.as_view(), name='timesheet_summary'),
    path('export-csv/', views.TimeEntryCSVExportView.as_view(), name='time_entry_export_csv'),
    path('<int:pk>/edit/', views.TimeEntryUpdateView.as_view(), name='time_entry_edit'),
    path('<int:pk>/delete/', views.TimeEntryDeleteView.as_view(), name='time_entry_delete'),
]
