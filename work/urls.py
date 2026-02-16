from django.urls import path
from . import views

urlpatterns = [
    path('', views.MyWorkListView.as_view(), name='my_work'),
    path('create/', views.WorkItemCreateView.as_view(), name='work_item_create'),
    path('deleted/', views.WorkItemDeletedListView.as_view(), name='work_item_deleted_list'),
    path('<int:pk>/', views.WorkItemDetailView.as_view(), name='work_item_detail'),
    path('<int:pk>/edit/', views.WorkItemUpdateView.as_view(), name='work_item_edit'),
    path('<int:pk>/complete/', views.WorkItemCompleteView.as_view(), name='work_item_complete'),
    path('<int:pk>/delete/', views.WorkItemDeleteView.as_view(), name='work_item_delete'),
    path('<int:pk>/restore/', views.WorkItemRestoreView.as_view(), name='work_item_restore'),
]
