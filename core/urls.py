from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('activity/', views.ActivityListView.as_view(), name='activity_list'),
    path('search/', views.SearchView.as_view(), name='search'),
]
