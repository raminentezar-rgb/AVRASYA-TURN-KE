from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('student/login/', views.student_login, name='student_login'),
    path('student/logout/', views.student_logout, name='student_logout'),
    path('student/qr/', views.student_qr, name='student_qr'),
    path('student/api/live-token/', views.get_live_token, name='get_live_token'),
    path('excel-import/', views.import_from_excel, name='import_from_excel'),
    path('import-classes/', views.import_classes_excel, name='import_classes_excel'),
    path('latest-logs/', views.get_latest_logs, name='get_latest_logs'),
    path('system-guide/', views.system_guide, name='system_guide'),
    path('download-student-template/', views.download_student_template, name='download_student_template'),
    path('download-class-template/', views.download_class_template, name='download_class_template'),
    path('api/validate/', views.api_validate, name='api_validate'),
    
    # Class Attendance System URLs
    path('teacher/login/', auth_views.LoginView.as_view(template_name='core/teacher_login.html', redirect_authenticated_user=True), name='teacher_login'),
    path('teacher/logout/', auth_views.LogoutView.as_view(next_page='teacher_login'), name='teacher_logout'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/session/<int:section_id>/start/', views.start_attendance_session, name='start_attendance_session'),
    path('teacher/projector/<int:session_id>/', views.projector_view, name='projector_view'),
    path('teacher/api/projector/<int:session_id>/token/', views.api_projector_token, name='api_projector_token'),
    path('teacher/api/projector/<int:session_id>/live/', views.api_projector_live, name='api_projector_live'),
    path('teacher/session/<int:session_id>/close/', views.close_attendance_session, name='close_attendance_session'),
    path('teacher/session/<int:session_id>/export/<str:export_format>/', views.export_attendance_report, name='export_attendance_report'),
    path('teacher/session/<int:session_id>/notify-parents/', views.notify_absent_parents, name='notify_absent_parents'),
    path('teacher/statistics/', views.teacher_stats, name='teacher_stats'),
    path('attendance/scan/', views.student_scan, name='student_scan'),
]
