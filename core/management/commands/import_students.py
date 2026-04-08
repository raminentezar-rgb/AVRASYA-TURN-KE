import pandas as pd
from django.core.management.base import BaseCommand
from core.models import Student
import os

class Command(BaseCommand):
    help = 'Import students from an Excel file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the Excel file')

    def handle(self, *args, **options):
        file_path = options['file_path']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File "{file_path}" does not exist.'))
            return

        try:
            df = pd.read_excel(file_path)
            
            # Remove duplicate student numbers and TC numbers from the file itself
            df = df.drop_duplicates(subset=['Öğrenci No_1'])
            df = df.drop_duplicates(subset=['T.C.Kimlik No_1'])
            
            # Mapping based on the user's excel structure
            # ['T.C.Kimlik No_1', 'Öğrenci No_1', 'Adı_1', 'Soyadı_1', 'Fakülte_1', 'Bölüm_1']
            
            count = 0
            for _, row in df.iterrows():
                tc_no = str(row.get('T.C.Kimlik No_1', '')).strip()
                student_no = str(row.get('Öğrenci No_1', '')).strip()
                
                if not tc_no or not student_no:
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
            
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} new students.'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error importing students: {str(e)}'))
