import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.broadcast_service import format_report_message

# 1. مسار العملية
print("=" * 60)
print("🔍 TESTING OPERATION PATHWAY (عملية)")
print("=" * 60)

operation_data = {
    'full_name': 'أحمد محمد علي',
    'id_number': '123456789',
    'phone': '0541234567',
    'birth_date': '1990-01-01',
    'medical_action': 'عملية',
    'hospital': 'مستشفى الملك سلمان',
    'department': 'الجراحة العامة',
    'doctor': 'د. محمد أحمد',
    'date': '2024-12-13',
    'time': '10:30',
    'address': 'الرياض - النزهة',
    'complaint': 'ألم في البطن',
    'diagnosis': 'التهاب الزائدة الدودية',
    'decision': 'إجراء عملية استئصال الزائدة',
    'operation_details': 'عملية استئصال الزائدة الدودية بالمنظار',
    'operation_name_en': 'Laparoscopic Appendectomy',
    'notes': 'العملية ستكون تحت التخدير العام',
    'room_number': 'غرفة 205'
}

result = format_report_message(operation_data)
print(result)
print("\n" + "=" * 80)

# 2. مسار الرقود
print("=" * 60)
print("🔍 TESTING ADMISSION PATHWAY (ترقيد)")
print("=" * 60)

admission_data = {
    'full_name': 'فاطمة سعد',
    'id_number': '987654321',
    'phone': '0509876543',
    'birth_date': '1985-05-15',
    'medical_action': 'ترقيد',
    'hospital': 'مستشفى الملك فهد',
    'department': 'الباطنة العامة',
    'doctor': 'د. سارة عبدالله',
    'date': '2024-12-13',
    'time': '14:00',
    'address': 'جدة - الروضة',
    'complaint': 'حمى وضعف عام',
    'diagnosis': 'التهاب رئوي حاد',
    'decision': 'يحتاج رقود للمتابعة والعلاج',
    'admission_reason': 'التهاب رئوي يحتاج مضادات حيوية بالوريد',
    'notes': 'المريض يحتاج مراقبة مستمرة',
    'room_number': 'غرفة 301'
}

result = format_report_message(admission_data)
print(result)
print("\n" + "=" * 80)

# 3. مسار العلاج الطبيعي
print("=" * 60)
print("🔍 TESTING PHYSICAL THERAPY PATHWAY (علاج طبيعي)")
print("=" * 60)

therapy_data = {
    'full_name': 'عبدالرحمن خالد',
    'id_number': '456789123',
    'phone': '0557894561',
    'birth_date': '1975-08-20',
    'medical_action': 'علاج طبيعي',
    'hospital': 'مركز التأهيل الطبي',
    'department': 'العلاج الطبيعي',
    'doctor': 'د. ماجد القحطاني',
    'date': '2024-12-13',
    'time': '09:00',
    'address': 'الدمام - الراكة',
    'complaint': 'آلام في الظهر بعد العملية',
    'diagnosis': 'تيبس في العضلات بعد الجراحة',
    'decision': 'جلسات علاج طبيعي لمدة شهر',
    'therapy_details': 'تمارين تقوية للعضلات والتمدد، علاج بالحرارة والتبريد',
    'notes': '3 جلسات في الأسبوع',
    'room_number': 'قاعة العلاج الطبيعي'
}

result = format_report_message(therapy_data)
print(result)
print("\n" + "=" * 80)

# 4. مسار الأجهزة التعويضية  
print("=" * 60)
print("🔍 TESTING PROSTHETIC DEVICES PATHWAY (أجهزة تعويضية)")
print("=" * 60)

device_data = {
    'full_name': 'نورا عبدالعزيز',
    'id_number': '789123456',
    'phone': '0532147896',
    'birth_date': '1992-12-05',
    'medical_action': 'أجهزة تعويضية',
    'hospital': 'مركز الأطراف الصناعية',
    'department': 'الأجهزة التعويضية',
    'doctor': 'د. أحمد الشهراني',
    'date': '2024-12-13',
    'time': '11:30',
    'address': 'أبها - الوسط',
    'complaint': 'بتر في الساق اليسرى',
    'diagnosis': 'يحتاج طرف صناعي للساق اليسرى',
    'decision': 'تركيب طرف صناعي مع التدريب',
    'device_details': 'طرف صناعي للساق اليسرى بتقنية متقدمة مع مفصل ذكي',
    'notes': 'سيحتاج فترة تدريب لمدة أسبوعين',
    'room_number': 'ورشة التركيب'
}

result = format_report_message(device_data)
print(result)
print("\n" + "=" * 80)

# 5. مسار خروج من المستشفى (بعد رقود)
print("=" * 60)
print("🔍 TESTING DISCHARGE AFTER ADMISSION (خروج بعد رقود)")
print("=" * 60)

discharge_admission_data = {
    'full_name': 'محمد عبدالله السعد',
    'id_number': '321654987',
    'phone': '0501237894',
    'birth_date': '1980-03-10',
    'medical_action': 'خروج من المستشفى',
    'hospital': 'مستشفى الملك عبدالعزيز',
    'department': 'القلبية',
    'doctor': 'د. علي الغامدي',
    'date': '2024-12-13',
    'time': '16:00',
    'address': 'الطائف - السلامة',
    'complaint': 'ألم في الصدر',
    'diagnosis': 'ذبحة صدرية',
    'decision': 'تحسن الحالة، يمكن الخروج مع المتابعة',
    'discharge_type': 'admission',
    'admission_summary': 'تم علاج المريض بالأدوية والمراقبة لمدة 3 أيام، تحسنت حالته بشكل ملحوظ',
    'notes': 'مراجعة العيادة خلال أسبوع',
    'room_number': 'غرفة 410'
}

result = format_report_message(discharge_admission_data)
print(result)
print("\n" + "=" * 80)

# 6. مسار خروج من المستشفى (بعد عملية)
print("=" * 60)
print("🔍 TESTING DISCHARGE AFTER OPERATION (خروج بعد عملية)")
print("=" * 60)

discharge_operation_data = {
    'full_name': 'خديجة أحمد الزهراني',
    'id_number': '654987321',
    'phone': '0512589631',
    'birth_date': '1988-07-25',
    'medical_action': 'خروج من المستشفى',
    'hospital': 'مستشفى الملك خالد',
    'department': 'جراحة العظام',
    'doctor': 'د. سعد البقمي',
    'date': '2024-12-13',
    'time': '13:00',
    'address': 'خميس مشيط - المنهل',
    'complaint': 'كسر في الذراع اليمنى',
    'diagnosis': 'كسر في عظم العضد',
    'decision': 'تمت العملية بنجاح، يمكن الخروج',
    'operation_details': 'تثبيت الكسر بألواح ومسامير معدنية',
    'operation_name_en': 'Open Reduction Internal Fixation (ORIF)',
    'notes': 'عدم تحريك الذراع لمدة 6 أسابيع',
    'room_number': 'غرفة 520'
}

result = format_report_message(discharge_operation_data)
print(result)
print("\n" + "=" * 80)

print("✅ جميع المسارات العامة تم فحصها!")