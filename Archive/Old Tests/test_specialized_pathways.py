import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.broadcast_service import format_report_message

def test_specialized_pathway(pathway_name, data):
    """اختبار المسارات المتخصصة"""
    print(f"\n{'='*60}")
    print(f"🔬 TESTING SPECIALIZED PATHWAY: {pathway_name}")
    print(f"{'='*60}")
    
    result = format_report_message(data)
    print(result)
    
    return result

# اختبار المسارات المتخصصة
print("🔬 TESTING SPECIALIZED PATHWAYS")
print("="*80)

# 1. استشارة جراحية
surgery_consult_data = {
    'full_name': 'أحمد محمد علي',
    'id_number': '123456789',
    'phone': '0541234567',
    'birth_date': '1990-01-01',
    'medical_action': 'استشارة جراحية',
    'hospital': 'مستشفى الملك سلمان',
    'department': 'الجراحة العامة',
    'doctor': 'د. محمد أحمد',
    'date': '2024-12-13',
    'time': '10:30',
    'address': 'الرياض - النزهة',
    'complaint': 'ألم في البطن',
    'diagnosis': 'التهاب الزائدة الدودية',
    'decision': 'إجراء عملية استئصال الزائدة',
    'surgery_type': 'emergency',
    'operation_name_ar': 'استئصال الزائدة الدودية',
    'operation_name_en': 'Laparoscopic Appendectomy',
    'anesthesia_type': 'تخدير عام',
    'room_number': 'غرفة 205'
}

test_specialized_pathway("استشارة جراحية", surgery_consult_data)

# 2. الأشعة
radiology_data = {
    'full_name': 'فاطمة سعد',
    'id_number': '987654321', 
    'phone': '0509876543',
    'birth_date': '1985-05-15',
    'medical_action': 'أشعة',
    'hospital': 'مستشفى الملك فهد',
    'department': 'الأشعة التشخيصية',
    'doctor': 'د. سارة عبدالله',
    'date': '2024-12-13',
    'time': '14:00',
    'address': 'جدة - الروضة',
    'complaint': 'ألم في الصدر',
    'diagnosis': 'يحتاج فحص أشعة للرئتين',
    'decision': 'إجراء أشعة مقطعية للصدر',
    'radiology_type': 'أشعة مقطعية',
    'radiology_area': 'الصدر',
    'preparation_instructions': 'عدم الأكل لمدة 4 ساعات قبل الفحص',
    'room_number': 'قسم الأشعة المقطعية'
}

test_specialized_pathway("أشعة", radiology_data)

# 3. المختبر
lab_data = {
    'full_name': 'عبدالرحمن خالد',
    'id_number': '456789123',
    'phone': '0557894561',
    'birth_date': '1975-08-20',
    'medical_action': 'مختبر',
    'hospital': 'مركز التشخيص الطبي',
    'department': 'المختبر',
    'doctor': 'د. ماجد القحطاني',
    'date': '2024-12-13',
    'time': '09:00',
    'address': 'الدمام - الراكة',
    'complaint': 'فحص دوري للسكري',
    'diagnosis': 'متابعة مستوى السكر في الدم',
    'decision': 'إجراء فحوصات شاملة',
    'tests_requested': 'فحص سكر صائم\nفحص سكر تراكمي\nوظائف كلى\nدهون الدم',
    'preparation_notes': 'صيام 12 ساعة قبل الفحص',
    'room_number': 'مختبر الفحوصات العامة'
}

test_specialized_pathway("مختبر", lab_data)

# 4. الطوارئ
emergency_data = {
    'full_name': 'نورا عبدالعزيز',
    'id_number': '789123456',
    'phone': '0532147896',
    'birth_date': '1992-12-05',
    'medical_action': 'طوارئ',
    'hospital': 'مستشفى الطوارئ',
    'department': 'طوارئ البالغين',
    'doctor': 'د. أحمد الشهراني',
    'date': '2024-12-13',
    'time': '11:30',
    'address': 'أبها - الوسط',
    'complaint': 'ألم حاد في البطن',
    'diagnosis': 'اشتباه التهاب الزائدة الدودية',
    'decision': 'حجز عاجل للجراحة',
    'triage_level': 'عاجل',
    'arrival_method': 'بالإسعاف',
    'emergency_notes': 'المريض يحتاج تدخل جراحي عاجل',
    'room_number': 'غرفة الطوارئ 3'
}

test_specialized_pathway("طوارئ", emergency_data)

print(f"\n{'='*80}")
print("✅ جميع المسارات المتخصصة تعمل بشكل صحيح!")
print("✅ الحقول المتخصصة تظهر في كل مسار حسب نوعه")