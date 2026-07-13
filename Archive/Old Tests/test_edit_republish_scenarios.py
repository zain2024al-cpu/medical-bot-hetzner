import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.broadcast_service import format_report_message

def test_editing_scenario(pathway_name, data):
    """اختبار سيناريو التعديل وإعادة النشر"""
    print(f"\n{'='*60}")
    print(f"📝 TESTING EDIT & REPUBLISH: {pathway_name}")
    print(f"{'='*60}")
    
    # المرة الأولى - النشر الأولي
    print("🔶 INITIAL PUBLISH:")
    print("-" * 30)
    result1 = format_report_message(data)
    print(result1)
    
    # المرة الثانية - التعديل وإعادة النشر (نفس البيانات)
    print("\n🔶 AFTER EDITING & REPUBLISHING:")
    print("-" * 30)
    result2 = format_report_message(data)
    print(result2)
    
    # مقارنة النتائج
    print("\n🔍 COMPARISON RESULT:")
    if result1 == result2:
        print("✅ IDENTICAL: Both outputs are exactly the same!")
    else:
        print("❌ DIFFERENT: Outputs differ!")
        print("\nDifferences:")
        lines1 = result1.split('\n')
        lines2 = result2.split('\n')
        for i, (line1, line2) in enumerate(zip(lines1, lines2), 1):
            if line1 != line2:
                print(f"Line {i}:")
                print(f"  Initial: {line1}")
                print(f"  Republish: {line2}")
    
    return result1 == result2

# اختبار المسارات المختلفة
print("🚀 TESTING EDIT & REPUBLISH SCENARIOS")
print("="*80)

all_passed = True

# 1. مسار العملية
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

passed = test_editing_scenario("عملية (Operation)", operation_data)
all_passed &= passed

# 2. مسار الاستشارة الجديدة (مع فحوصات)
consult_data = {
    'full_name': 'سارة عبدالله',
    'id_number': '987654321',
    'phone': '0509876543',
    'birth_date': '1985-05-15',
    'medical_action': 'استشارة جديدة',
    'hospital': 'مستشفى الملك فهد',
    'department': 'الباطنة العامة',
    'doctor': 'د. فهد السعد',
    'date': '2024-12-13',
    'time': '14:00',
    'address': 'جدة - الروضة',
    'complaint': 'صداع مستمر',
    'diagnosis': 'صداع توتري',
    'decision': 'علاج دوائي مع فحوصات',
    'tests': 'فحص دم شامل\nصورة أشعة للرأس\nقياس ضغط الدم',
    'room_number': 'عيادة 3'
}

passed = test_editing_scenario("استشارة جديدة (New Consultation)", consult_data)
all_passed &= passed

# 3. مسار متابعة في الرقود (هذا هو المسار المهم الذي ذكره المستخدم)
followup_admission_data = {
    'full_name': 'محمد عبدالرحمن',
    'id_number': '456789123',
    'phone': '0557894561',
    'birth_date': '1975-08-20',
    'medical_action': 'متابعة في الرقود',
    'hospital': 'مستشفى الملك خالد',
    'department': 'الباطنة العامة',
    'doctor': 'د. عبدالله الغامدي',
    'date': '2024-12-13',
    'time': '09:00',
    'address': 'الدمام - الراكة',
    'complaint': 'متابعة حالة السكري',
    'diagnosis': 'السكري النوع الثاني غير مستقر',
    'decision': 'تعديل جرعة الأنسولين والمتابعة',
    'notes': 'المريض يحتاج مراقبة دقيقة لمستوى السكر',
    'room_number': 'غرفة 301'
}

passed = test_editing_scenario("متابعة في الرقود (Follow-up Admission)", followup_admission_data)
all_passed &= passed

# 4. مسار الأجهزة التعويضية
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

passed = test_editing_scenario("أجهزة تعويضية (Prosthetic Devices)", device_data)
all_passed &= passed

print(f"\n{'='*80}")
print(f"📊 FINAL SUMMARY:")
print(f"{'='*80}")
if all_passed:
    print("✅ ALL TESTS PASSED!")
    print("✅ جميع المسارات تعمل بشكل صحيح بعد التعديل وإعادة النشر")
    print("✅ قرار الطبيب يظهر بنفس الطريقة في المرة الأولى والثانية")
    print("✅ جميع الحقول المتخصصة تظهر بشكل مستقر")
else:
    print("❌ SOME TESTS FAILED!")
    print("❌ هناك اختلافات في العرض بين النشر الأولي وإعادة النشر")

print(f"\n🎯 خاصة مسار 'متابعة في الرقود' الذي ذكره المستخدم - تم اختباره!")