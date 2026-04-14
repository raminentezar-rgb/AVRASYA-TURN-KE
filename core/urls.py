from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('student/login/', views.student_login, name='student_login'),
    path('student/qr/', views.student_qr, name='student_qr'),
    path('student/api/live-token/', views.get_live_token, name='get_live_token'),
    path('excel-import/', views.import_from_excel, name='import_from_excel'),
    path('import-classes/', views.import_classes_excel, name='import_classes_excel'),
    path('latest-logs/', views.get_latest_logs, name='get_latest_logs'),
    path('system-guide/', views.system_guide, name='system_guide'),
    path('api/validate/', views.api_validate, name='api_validate'),
    
    # Class Attendance System URLs
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/session/<int:section_id>/start/', views.start_attendance_session, name='start_attendance_session'),
    path('teacher/projector/<int:session_id>/', views.projector_view, name='projector_view'),
    path('teacher/api/projector/<int:session_id>/token/', views.api_projector_token, name='api_projector_token'),
    path('teacher/api/projector/<int:session_id>/live/', views.api_projector_live, name='api_projector_live'),
    path('attendance/scan/', views.student_scan, name='student_scan'),
]
