from django.contrib import admin

from .models import Student, AccessLog, Teacher, Course, CourseSection, AttendanceSession, AttendanceRecord

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_no', 'first_name', 'last_name', 'department')
    search_fields = ('student_no', 'first_name', 'last_name', 'tc_no')

@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('student', 'status', 'timestamp')
    list_filter = ('status', 'timestamp')

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'department')
    search_fields = ('user__first_name', 'user__last_name', 'department')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'department')
    search_fields = ('code', 'name')
    list_filter = ('department',)

@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ('course', 'name', 'teacher')
    search_fields = ('course__name', 'teacher__user__first_name', 'name')
    filter_horizontal = ('students',)

@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ('section', 'created_at', 'is_active')
    list_filter = ('is_active', 'created_at')

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('session', 'student', 'timestamp', 'status')
    list_filter = ('timestamp', 'status')
