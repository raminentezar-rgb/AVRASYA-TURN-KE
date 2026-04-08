from django.db import models
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
