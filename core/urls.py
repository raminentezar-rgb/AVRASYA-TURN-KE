from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('student/login/', views.student_login, name='student_login'),
    path('student/qr/', views.student_qr, name='student_qr'),
    path('student/api/live-token/', views.get_live_token, name='get_live_token'),
    path('excel-import/', views.import_from_excel, name='import_from_excel'),
    path('latest-logs/', views.get_latest_logs, name='get_latest_logs'),
    path('system-guide/', views.system_guide, name='system_guide'),
    path('api/validate/', views.api_validate, name='api_validate'),
]
