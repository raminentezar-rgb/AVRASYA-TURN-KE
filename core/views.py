from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Student, AccessLog, Teacher, CourseSection, AttendanceSession, AttendanceRecord
import pyotp
import json
import logging
import os
import pandas as pd
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import openpyxl
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth

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
def import_classes_excel(request):
    """View to import Teachers, Courses, and Sections from classes.xlsx"""
    file_path = os.path.join(settings.BASE_DIR, 'classes.xlsx')
    
    if not os.path.exists(file_path):
        messages.error(request, 'Sınıf Excel dosyası (classes.xlsx) bulunamadı. Lütfen ana dizine ekleyin.')
        return redirect('dashboard')

    try:
        from django.contrib.auth.models import User
        df = pd.read_excel(file_path)
        
        teacher_count = 0
        course_count = 0
        section_count = 0
        enrollment_count = 0
        
        for _, row in df.iterrows():
            teacher_tc = str(row.get('Öğretmen TC', '')).strip()
            if not teacher_tc or teacher_tc == 'nan':
                continue

            # 1. Handle Teacher
            first_name = str(row.get('Öğretmen Adı', '')).strip()
            last_name = str(row.get('Öğretmen Soyadı', '')).strip()
            t_dept = str(row.get('Öğretmen Bölüm', '')).strip()
            
            user, created = User.objects.get_or_create(
                username=teacher_tc,
                defaults={'first_name': first_name, 'last_name': last_name}
            )
            if created:
                user.set_password(teacher_tc) # default password is TC
                user.save()
                
            teacher, t_created = Teacher.objects.get_or_create(
                user=user,
                defaults={'department': t_dept}
            )
            if t_created: teacher_count += 1
            
            # 2. Handle Course
            course_code = str(row.get('Ders Kodu', '')).strip()
            course_name = str(row.get('Ders Adı', '')).strip()
            c_dept = str(row.get('Ders Bölüm', '')).strip()
            
            course, c_created = Course.objects.get_or_create(
                code=course_code,
                defaults={'name': course_name, 'department': c_dept}
            )
            if c_created: course_count += 1
            
            # 3. Handle Section
            section_name = str(row.get('Şube', '')).strip()
            section, s_created = CourseSection.objects.get_or_create(
                course=course,
                teacher=teacher,
                name=section_name
            )
            if s_created: section_count += 1
            
            # 4. Handle Enrollment
            student_no = str(row.get('Öğrenci No', '')).strip()
            if student_no and student_no != 'nan':
                try:
                    student = Student.objects.get(student_no=student_no)
                    if student not in section.students.all():
                        section.students.add(student)
                        enrollment_count += 1
                except Student.DoesNotExist:
                    pass # Student must exist first from the other excel
                    
        messages.success(request, f'Başarıyla {teacher_count} öğretmen, {course_count} ders, {section_count} şube ve {enrollment_count} kayıt eklendi.')
        
    except Exception as e:
        messages.error(request, f'Sınıf aktarımı sırasında hata: {str(e)}')
        logger.exception("Class Excel import failed")
        
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
            
            next_url = request.session.pop('next_attendance', None)
            if next_url:
                return redirect(next_url)
                
            return redirect('student_qr')
        except Student.DoesNotExist:
            messages.error(request, "Geçersiz kimlik bilgileri.")
    
    return render(request, 'core/student_login.html')

def student_logout(request):
    """Clears the student session and redirects to the student login page."""
    if request.method == 'POST':
        request.session.flush()
    return redirect('student_login')

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

# --- CLASSROOM ATTENDANCE SYSTEM VIEWS ---

@login_required
def teacher_dashboard(request):
    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(request, "Öğretmen profili bulunamadı. Lütfen yöneticiye başvurun.")
        return redirect('dashboard')
        
    sections = teacher.sections.all()
    context = {'teacher': teacher, 'sections': sections}
    return render(request, 'core/teacher_dashboard.html', context)

@login_required
def start_attendance_session(request, section_id):
    section = get_object_or_404(CourseSection, id=section_id, teacher__user=request.user)
    
    # Optional: Close previous loose active sessions for this section
    AttendanceSession.objects.filter(section=section, is_active=True).update(is_active=False)
    
    session = AttendanceSession.objects.create(section=section)
    return redirect('projector_view', session_id=session.id)

@login_required
def projector_view(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id, section__teacher__user=request.user)
    
    # We will pass the initial token, but it will be refreshed via AJAX
    context = {'session': session}
    return render(request, 'core/projector_view.html', context)

@login_required
def api_projector_token(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id, section__teacher__user=request.user)
    if not session.is_active:
        return JsonResponse({'error': 'Session inactive'}, status=400)
    
    return JsonResponse({
        'token': session.get_totp_token()
    })

@login_required
def api_projector_live(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id, section__teacher__user=request.user)
    records = session.records.all().order_by('-timestamp')
    data = []
    for r in records:
        data.append({
            'student_name': f"{r.student.first_name} {r.student.last_name}",
            'student_no': r.student.student_no,
            'time': r.timestamp.strftime('%H:%M:%S')
        })
    return JsonResponse({'records': data, 'count': records.count()})

def student_scan(request):
    # This URL is hit when student scans QR. e.g. /attendance/scan/?session=12&token=123456
    session_id = request.GET.get('session')
    token = request.GET.get('token')
    
    if not session_id or not token:
        messages.error(request, 'Geçersiz bağlantı.')
        return render(request, 'core/scan_result.html', {'success': False})
        
    student_id = request.session.get('student_id')
    if not student_id:
        # Save next redirect
        request.session['next_attendance'] = request.get_full_path()
        return redirect('student_login')
        
    student = get_object_or_404(Student, id=student_id)
    session = get_object_or_404(AttendanceSession, id=session_id)
    
    # Checks
    if not session.is_active:
        messages.warning(request, 'Bu yoklama oturumu sona ermiş.')
        return render(request, 'core/scan_result.html', {'success': False})
        
    if student not in session.section.students.all():
        messages.error(request, 'Bu derse kayıtlı değilsiniz.')
        return render(request, 'core/scan_result.html', {'success': False})
        
    if not session.verify_totp(token):
        messages.error(request, 'QR kodun süresi dolmuş. Lütfen tahtadaki yeni kodu okutun.')
        return render(request, 'core/scan_result.html', {'success': False})
        
    # Record Checkin
    record, created = AttendanceRecord.objects.get_or_create(session=session, student=student)
    if not created:
        messages.info(request, 'Yoklamanız zaten alınmıştı.')
    else:
        messages.success(request, 'Başarıyla yoklamanız alındı.')
        
    return render(request, 'core/scan_result.html', {'success': True, 'record': record})

def get_unicode_font():
    """Returns a path to a font that supports Turkish characters based on the OS."""
    possible_paths = [
        "C:\\Windows\\Fonts\\arial.ttf", # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", # Linux (PythonAnywhere)
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf", # Linux alternative
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", # Linux alternative
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

@login_required
def close_attendance_session(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id, section__teacher__user=request.user)
    session.is_active = False
    session.save()
    
    present_ids = session.records.values_list('student_id', flat=True)
    enrolled = session.section.students.all()
    absent_count = enrolled.count() - len(present_ids)
    
    context = {
        'session': session,
        'present_count': len(present_ids),
        'absent_count': absent_count,
        'total_count': enrolled.count(),
    }
    return render(request, 'core/attendance_summary.html', context)

@login_required
def export_attendance_report(request, session_id, export_format='excel'):
    session = get_object_or_404(AttendanceSession, id=session_id, section__teacher__user=request.user)
    enrolled_students = session.section.students.all().order_by('first_name')
    present_student_ids = set(session.records.values_list('student_id', flat=True))
    
    data = []
    for s in enrolled_students:
        is_present = s.id in present_student_ids
        record = session.records.filter(student=s).first() if is_present else None
        data.append({
            'Öğrenci No': s.student_no,
            'Ad Soyad': f"{s.first_name} {s.last_name}",
            'Bölüm': s.department,
            'Durum': 'PRESENT' if is_present else 'ABSENT',
            'Giriş Saati': record.timestamp.strftime('%H:%M:%S') if record else '-'
        })
    
    # Translate status for display
    for item in data:
        item['Durum'] = 'VAR' if item['Durum'] == 'PRESENT' else 'YOK'
    
    filename = f"Yoklama_{session.section.course.code}_{session.created_at.strftime('%Y-%m-%d')}"
    
    if export_format == 'excel':
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Yoklama')
            # Basic formatting
            worksheet = writer.sheets['Yoklama']
            for i, col in enumerate(df.columns):
                column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[openpyxl.utils.get_column_letter(i+1)].width = column_len

        response = HttpResponse(output.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
        return response
    
    elif export_format == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Font Configuration
        font_path = get_unicode_font()
        font_name = 'Helvetica' # fallback
        if font_path:
            try:
                pdfmetrics.registerFont(TTFont('TurkishFont', font_path))
                font_name = 'TurkishFont'
                # Create a custom style using the registered font
                styles.add(ParagraphStyle(name='TurkishTitle', parent=styles['Title'], fontName='TurkishFont'))
                styles.add(ParagraphStyle(name='TurkishNormal', parent=styles['Normal'], fontName='TurkishFont'))
            except:
                pass
        
        title_style = styles.get('TurkishTitle', styles['Title'])
        normal_style = styles.get('TurkishNormal', styles['Normal'])
        
        # Add Logo
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'avrasya-logo.png')
        if os.path.exists(logo_path):
            img = Image(logo_path, width=80, height=80)
            img.hAlign = 'CENTER'
            elements.append(img)
            elements.append(Spacer(1, 10))

        # Title and Header Info
        elements.append(Paragraph(f"<b>{session.section.course.name} ({session.section.course.code})</b>", title_style))
        elements.append(Paragraph(f"Yoklama Listesi", title_style))
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph(f"<b>Şube:</b> {session.section.name}", normal_style))
        elements.append(Paragraph(f"<b>Tarih:</b> {session.created_at.strftime('%Y-%m-%d %H:%M')}", normal_style))
        elements.append(Paragraph(f"<b>Öğretmen:</b> {session.section.teacher.user.get_full_name()}", normal_style))
        elements.append(Spacer(1, 24))
        
        # Table Data
        table_data = [['NO', 'ÖĞRENCİ NO', 'AD SOYAD', 'BÖLÜM', 'DURUM', 'GİRİŞ SAATİ']]
        for i, row in enumerate(data, 1):
            table_data.append([
                i, 
                row['Öğrenci No'], 
                row['Ad Soyad'], 
                row['Bölüm'], 
                row['Durum'], 
                row['Giriş Saati']
            ])
            
        t = Table(table_data, colWidths=[30, 80, 150, 150, 70, 60])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            # Highlight absent
            *([('TEXTCOLOR', (4, i), (4, i), colors.red) for i, row in enumerate(data, 1) if row['Durum'] == 'YOK'])
        ]))
        elements.append(t)
        
        response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
        return response
    
    return redirect('teacher_dashboard')

@login_required
def notify_absent_parents(request, session_id):
    session = get_object_or_404(AttendanceSession, id=session_id, section__teacher__user=request.user)
    
    enrolled_students = session.section.students.all()
    present_student_ids = session.records.values_list('student_id', flat=True)
    absent_students = enrolled_students.exclude(id__in=present_student_ids)
    
    notified_count = 0
    for student in absent_students:
        if student.parent_phone:
            # PLACEHOLDER: Integrate your SMS Gateway API here (e.g., Netgsm, MutluSMS)
            # Example logic:
            # send_sms(student.parent_phone, f"Sayın veli, {student.first_name} bugünkü {session.section.course.name} dersine katılmamıştır.")
            print(f"SMS SENT to {student.parent_phone}: {student.first_name} is absent.")
            notified_count += 1
            
    if notified_count > 0:
        messages.success(request, f"{notified_count} veliye bilgilendirme SMS'i gönderildi.")
    else:
        messages.warning(request, "Bildirim gönderilecek veli telefonu bulunamadی.")
        
    return redirect('close_attendance_session', session_id=session_id)

@login_required
def teacher_stats(request):
    teacher = get_object_or_404(Teacher, user=request.user)
    sections = teacher.sections.all()
    
    # Monthly Attendance Trends
    monthly_stats = AttendanceRecord.objects.filter(session__section__teacher=teacher)\
        .annotate(month=TruncMonth('timestamp'))\
        .values('month')\
        .annotate(count=Count('id'))\
        .order_by('month')
        
    # Stats for Chart.js
    chart_labels = [s['month'].strftime('%B %Y') for s in monthly_stats]
    chart_data = [s['count'] for s in monthly_stats]
    
    context = {
        'sections': sections,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'core/teacher_stats.html', context)

    return HttpResponse("Invalid format", status=400)
