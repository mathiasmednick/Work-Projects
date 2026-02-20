from django.urls import path, reverse_lazy
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('activity/', views.ActivityListView.as_view(), name='activity_list'),
    path('search/', views.SearchView.as_view(), name='search'),
    path('whiteboard/', views.WhiteboardListView.as_view(), name='whiteboard'),
    path('whiteboard/<int:board_id>/', views.WhiteboardBoardView.as_view(), name='whiteboard_board'),
    path('whiteboard/<int:board_id>/card/create/', views.WhiteboardCardCreateView.as_view(), name='whiteboard_card_create'),
    path('whiteboard/card/<int:card_id>/move/', views.WhiteboardCardMoveView.as_view(), name='whiteboard_card_move'),
    path('whiteboard/card/<int:card_id>/update/', views.WhiteboardCardUpdateView.as_view(), name='whiteboard_card_update'),
    path('whiteboard/card/<int:card_id>/delete/', views.WhiteboardCardDeleteView.as_view(), name='whiteboard_card_delete'),
    path('whiteboard/<int:board_id>/item/create/', views.WhiteboardItemCreateView.as_view(), name='whiteboard_item_create'),
    path('whiteboard/item/<int:item_id>/update/', views.WhiteboardItemUpdateView.as_view(), name='whiteboard_item_update'),
    path('whiteboard/item/<int:item_id>/delete/', views.WhiteboardItemDeleteView.as_view(), name='whiteboard_item_delete'),
    path('whiteboard/<int:board_id>/link/create/', views.WhiteboardLinkCreateView.as_view(), name='whiteboard_link_create'),
    path('whiteboard/link/<int:link_id>/delete/', views.WhiteboardLinkDeleteView.as_view(), name='whiteboard_link_delete'),
    path('weather/', views.WeatherDashboardView.as_view(), name='weather'),
    path('weather/list/', RedirectView.as_view(url=reverse_lazy('weather_table'), permanent=False), name='weather_list_redirect'),
    path('weather/table/', views.WeatherTableView.as_view(), name='weather_table'),
    path('weather/project/<int:project_id>/', views.WeatherProjectDetailView.as_view(), name='weather_project_detail'),
    path('weather/refresh/', views.WeatherRefreshView.as_view(), name='weather_refresh'),
    path('schedule-email-builder/', views.ScheduleEmailBuilderView.as_view(), name='schedule_email_builder'),
    path('schedule-email-builder/test/', views.ScheduleEmailBuilderTestRunnerView.as_view(), name='schedule_email_builder_test'),
]
