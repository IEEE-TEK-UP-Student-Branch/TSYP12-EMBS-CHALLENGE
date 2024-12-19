from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('chat/', views.chat_view, name='chat'),
    path('register/', views.register, name='register'),
    path('onboarding/', views.onboarding, name='onboarding'),
    # Topic pages
    path('topics/<str:topic_slug>/', views.topic_page, name='topic_page'),
    # Chat endpoints
    path('chat/message/', views.chat_message, name='chat_message'),
    # Report endpoints
    path('report/new/', views.report_record, name='report_new'),
    path('report/record/<uuid:report_id>/', views.report_record, name='report_record'),
    path('report/view/<uuid:report_id>/', views.report_view, name='report_view'),
    # API notification endpoints
    path('api/notifications/', views.get_notifications, name='get_notifications'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/', views.notifications_page, name='notifications'),
]
