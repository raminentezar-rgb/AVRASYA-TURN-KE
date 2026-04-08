from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.contrib import messages
from .models import Student, AccessLog
import pyotp
import json
import logging
import os
import pandas as pd
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

# Setup logging
logger = logging.getLogger(__name__)

def dashboard(request):
    # Only staff (admins) can see the dashboard
    if not request.user.is_authenticated or not request.user.is_staff:
        # If logged in as student, redirect to QR code
        if 'student_id' in request.session:
            return redirect('student_qr')
        # Otherwise, redirect to login
        return redirect('student_login')
        
    total_students = Student.objects.count()
    total_entries_today = AccessLog.objects.filter(timestamp__date=timezone.now().date(), status='allowed').count()
    recent_logs = AccessLog.objects.order_by('-timestamp')[:10]
    
    context = {
        'total_students': total_students,
        'today_entries': total_entries_today,
        'recent_logs': recent_logs,
    }
    return render(request, 'core/dashboard.html', context)

@staff_member_required
def import_from_excel(request):
    """View to trigger student import from example.xlsx"""
    file_path = os.path.join(settings.BASE_DIR, 'example.xlsx')
    
    if not os.path.exists(file_path):
        messages.error(request, 'Excel dosyası (example.xlsx) bulunamadی.')
        return redirect('dashboard')

    try:
        df = pd.read_excel(file_path)
        
        # Consistent mapping with the management command
        df = df.drop_duplicates(subset=['Öğrenci No_1'])
        df = df.drop_duplicates(subset=['T.C.Kimlik No_1'])
        
        count = 0
        for _, row in df.iterrows():
            tc_no = str(row.get('T.C.Kimlik No_1', '')).strip()
            student_no = str(row.get('Öğrenci No_1', '')).strip()
            
            if not tc_no or not student_no or tc_no == 'nan' or student_no == 'nan':
                continue

            student, created = Student.objects.update_or_create(
                tc_no=tc_no,
                defaults={
                    'student_no': student_no,
                    'first_name': str(row.get('Adı_1', '')).strip(),
                    'last_name': str(row.get('Soyadı_1', '')).strip(),
                    'faculty': str(row.get('Fakülte_1', '')).strip(),
                    'department': str(row.get('Bölüm_1', '')).strip(),
                }
            )
            if created:
                count += 1
        
        messages.success(request, f'Başarıyla {count} yeni öğrenci içe aktarıldı.')
        logger.info(f"Excel import triggered by {request.user.username}: {count} new students added.")
        
    except Exception as e:
        messages.error(request, f'Veri aktarımı sırasında hata: {str(e)}')
        logger.exception("Excel import failed via web dashboard")
        
    return redirect('dashboard')

@staff_member_required
def get_latest_logs(request):
    """Endpoint for the dashboard to fetch recent allowed entries."""
    # Get logs from the last 2 minutes
    since = timezone.now() - timezone.timedelta(minutes=2)
    logs = AccessLog.objects.filter(
        timestamp__gte=since, 
        status='allowed'
    ).order_by('-timestamp')[:5]
    
    data = []
    for log in logs:
        data.append({
            'id': log.id,
            'student_name': f"{log.student.first_name} {log.student.last_name}",
            'student_no': log.student.student_no,
            'department': log.student.department,
            'timestamp': log.timestamp.strftime('%H:%M:%S'),
        })
    
    return JsonResponse({'logs': data})

@staff_member_required
def system_guide(request):
    """View to display the technical hardware integration guide."""
    return render(request, 'core/system_guide.html')

def student_login(request):
    if request.method == 'POST':
        tc = request.POST.get('tc_no')
        student_no = request.POST.get('student_no')
        try:
            student = Student.objects.get(tc_no=tc, student_no=student_no)
            request.session['student_id'] = student.id
            return redirect('student_qr')
        except Student.DoesNotExist:
            messages.error(request, "Geçersiz kimlik bilgileri.")
    
    return render(request, 'core/student_login.html')

def student_qr(request):
    student_id = request.session.get('student_id')
    if not student_id:
        return redirect('student_login')
    
    student = get_object_or_404(Student, id=student_id)
    
    context = {
        'student': student,
    }
    return render(request, 'core/student_qr.html', context)

def get_live_token(request):
    """Endpoint to get current TOTP and expiry for the frontend to refresh."""
    student_id = request.session.get('student_id')
    if not student_id:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    student = Student.objects.get(id=student_id)
    totp = pyotp.TOTP(student.secret_key, interval=20)
    
    # Calculate seconds remaining in current 20s window
    time_remaining = 20 - (timezone.now().timestamp() % 20)
    
    return JsonResponse({
        'token': totp.now(),
        'student_no': student.student_no,
        'expires_in': int(time_remaining)
    })

@csrf_exempt
def api_validate(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'denied', 'message': 'Only POST allowed'}, status=405)
    
    # Verify API Key from headers
    api_key_header = request.headers.get('X-API-KEY')
    expected_api_key = os.environ.get('TURNSTILE_API_KEY')
    
    if not expected_api_key or api_key_header != expected_api_key:
        logger.warning(f"Unauthorized API access attempt from IP: {request.META.get('REMOTE_ADDR')}")
        return JsonResponse({'status': 'denied', 'message': 'Invalid API Key'}, status=403)
    
    try:
        data = json.loads(request.body)
        scan_content = data.get('qr_content', '') # Expected format "student_no:token"
        
        if ':' not in scan_content:
            logger.error(f"Invalid QR content format received: {scan_content}")
            return JsonResponse({'status': 'denied', 'message': 'Invalid format'}, status=400)
        
        student_no, token = scan_content.split(':')
        student = Student.objects.get(student_no=student_no)
        
        if student.verify_totp(token):
            AccessLog.objects.create(student=student, status='allowed')
            logger.info(f"Access ALLOWED for Student: {student.student_no} ({student.first_name} {student.last_name})")
            return JsonResponse({
                'status': 'allowed',
                'name': f"{student.first_name} {student.last_name}",
                'department': student.department
            })
        else:
            AccessLog.objects.create(student=student, status='denied')
            logger.info(f"Access DENIED (Invalid Token) for Student: {student.student_no}")
            return JsonResponse({'status': 'denied', 'message': 'Token expired or invalid'})
            
    except Student.DoesNotExist:
        logger.warning(f"Access DENIED (Student Not Found): {student_no}")
        return JsonResponse({'status': 'denied', 'message': 'Student not found'})
    except Exception as e:
        logger.exception("Unexpected error during API validation")
        return JsonResponse({'status': 'denied', 'message': str(e)}, status=500)
