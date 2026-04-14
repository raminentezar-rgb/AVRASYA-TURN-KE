from django.db import models
from django.contrib.auth.models import User
import pyotp
import uuid

class Student(models.Model):
    tc_no = models.CharField(max_length=11, unique=True, verbose_name="T.C. Kimlik No")
    student_no = models.CharField(max_length=20, unique=True, verbose_name="Öğrenci No")
    first_name = models.CharField(max_length=100, verbose_name="Adı")
    last_name = models.CharField(max_length=100, verbose_name="Soyadı")
    faculty = models.CharField(max_length=255, verbose_name="Fakülte")
    department = models.CharField(max_length=255, verbose_name="Bölüm")
    
    # Secret key for TOTP generation
    secret_key = models.CharField(max_length=32, default=pyotp.random_base32, verbose_name="TOTP Secret")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Öğrenci"
        verbose_name_plural = "Öğrenciler"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_no})"

    def verify_totp(self, token):
        """Verifies if the provided token is valid for the current 20-second window."""
        totp = pyotp.TOTP(self.secret_key, interval=20)
        return totp.verify(token)

    def get_totp_token(self):
        """Generates the current TOTP token."""
        totp = pyotp.TOTP(self.secret_key, interval=20)
        return totp.now()

class AccessLog(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="access_logs")
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('allowed', 'Allowed'), ('denied', 'Denied')])
    device_id = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = "Giriش Logu"
        verbose_name_plural = "Giriش Logları"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    department = models.CharField(max_length=255, verbose_name="Bölüm")
    
    class Meta:
        verbose_name = "Öğretmen"
        verbose_name_plural = "Öğretmenler"
        
    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return full_name if full_name else self.user.username

class Course(models.Model):
    name = models.CharField(max_length=255, verbose_name="Ders Adı")
    code = models.CharField(max_length=50, unique=True, verbose_name="Ders Kodu")
    department = models.CharField(max_length=255, verbose_name="Bölüm")

    class Meta:
        verbose_name = "Ders"
        verbose_name_plural = "Dersler"

    def __str__(self):
        return f"{self.code} - {self.name}"

class CourseSection(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sections", verbose_name="Ders")
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="sections", verbose_name="Öğretmen")
    students = models.ManyToManyField(Student, related_name='enrolled_sections', blank=True, verbose_name="Öğrenciler")
    name = models.CharField(max_length=100, verbose_name="Şube Adı") # e.g., "Grup A"

    class Meta:
        verbose_name = "Ders Şubesi"
        verbose_name_plural = "Ders Şubeleri"

    def __str__(self):
        return f"{self.course.name} - {self.name} ({self.teacher.user.get_full_name()})"

class AttendanceSession(models.Model):
    section = models.ForeignKey(CourseSection, on_delete=models.CASCADE, related_name='attendance_sessions', verbose_name="Ders Şubesi")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name="Aktif mi?")
    secret_key = models.CharField(max_length=32, default=pyotp.random_base32)

    class Meta:
        verbose_name = "Yoklama Oturumu"
        verbose_name_plural = "Yoklama Oturumları"

    def __str__(self):
        return f"{self.section.course.name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
        
    def get_totp_token(self):
        """Generates dynamic token for the projector."""
        totp = pyotp.TOTP(self.secret_key, interval=15)
        return totp.now()

    def verify_totp(self, token):
        """Verifies if the submitted token matches the current window."""
        totp = pyotp.TOTP(self.secret_key, interval=15)
        # allow a bit of lag via valid_window if needed, but 15s is standard
        return totp.verify(token, valid_window=1)

class AttendanceRecord(models.Model):
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='present')

    class Meta:
        unique_together = ('session', 'student')
        verbose_name = "Yoklama Kaydı"
        verbose_name_plural = "Yoklama Kayıtları"

    def __str__(self):
        return f"{self.student.first_name} {self.student.last_name} - {self.session.created_at.strftime('%Y-%m-%d')}"
