#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')
from services.broadcast_service import format_report_message

# اختبار المسارات العامة (التي تستخدم _build_general_fields)
general_flows_test = {
    'طوارئ': {
        'medical_action': 'طوارئ',
        'patient_name': 'أحمد محمد',
        'hospital_name': 'مستشفى دمشق',
        'department_name': 'الطوارئ',
        'doctor_name': 'د. محمد علي',
        'complaint_text': 'ألم شديد في الصدر',
        'diagnosis': 'احتشاء عضلة القلب المحتمل',
        'decision': 'نقل فوري لوحدة العناية المشددة',
        'case_status': 'تم إجراء تخطيط قلب والتحاليل اللازمة',
        'room_number': 'ICU - غرفة 3',
        'followup_date': '2026-01-16',
        'followup_time': '09:00',
        'followup_reason': 'متابعة حالة القلب',
        'translator_name': 'مترجم طوارئ',
        'is_edit': True
    },
    'ترقيد': {
        'medical_action': 'ترقيد',
        'patient_name': 'فاطمة أحمد',
        'hospital_name': 'مستشفى حلب',
        'department_name': 'الباطنة',
        'doctor_name': 'د. سارة كريم',
        'admission_reason': 'ضرورة المراقبة الطبية المستمرة',
        'room_number': 'غرفة 102 - الطابق الأول',
        'notes': 'مريض يحتاج راحة تامة',
        'followup_date': '2026-01-18',
        'followup_reason': 'تقييم الحالة العامة',
        'translator_name': 'مترجم ترقيد',
        'is_edit': True
    },
    'عملية': {
        'medical_action': 'عملية',
        'patient_name': 'محمد عبد الله',
        'hospital_name': 'مستشفى حمص',
        'department_name': 'الجراحة',
        'doctor_name': 'د. أحمد يوسف',
        'operation_details': 'استئصال الزائدة الدودية',
        'operation_name_en': 'Appendectomy',
        'notes': 'عملية ناجحة بدون مضاعفات',
        'followup_date': '2026-01-20',
        'followup_time': '11:00',
        'followup_reason': 'إزالة الغرز ومتابعة الشفاء',
        'translator_name': 'مترجم عملية',
        'is_edit': True
    },
    'علاج طبيعي': {
        'medical_action': 'علاج طبيعي',
        'patient_name': 'عائشة علي',
        'hospital_name': 'مستشفى اللاذقية',
        'department_name': 'العلاج الطبيعي',
        'doctor_name': 'د. رامي حسين',
        'therapy_details': 'تمارين لتقوية عضلات الساق بعد الكسر',
        'followup_date': '2026-01-22',
        'followup_time': '14:00',
        'followup_reason': 'جلسة علاج طبيعي متابعة',
        'translator_name': 'مترجم علاج طبيعي',
        'is_edit': True
    },
    'أجهزة تعويضية': {
        'medical_action': 'أجهزة تعويضية',
        'patient_name': 'يوسف محمود',
        'hospital_name': 'مستشفى درعا',
        'department_name': 'الأطراف الصناعية',
        'doctor_name': 'د. نورا سليم',
        'device_details': 'طرف صناعي للساق اليسرى، نوع متقدم مع مفصل الركبة',
        'followup_date': '2026-01-25',
        'followup_time': '10:30',
        'followup_reason': 'فحص الطرف الصناعي وضبطه',
        'translator_name': 'مترجم أجهزة',
        'is_edit': True
    },
    'خروج من المستشفى': {
        'medical_action': 'خروج من المستشفى',
        'patient_name': 'ليلى حسن',
        'hospital_name': 'مستشفى السويداء',
        'department_name': 'الجراحة',
        'doctor_name': 'د. عبد الرحمن مصطفى',
        'discharge_type': 'admission',
        'admission_summary': 'تم الشفاء التام من عملية استئصال المرارة، المريض بحالة جيدة',
        'followup_date': '2026-01-30',
        'followup_reason': 'متابعة ما بعد العملية',
        'translator_name': 'مترجم خروج',
        'is_edit': True
    }
}

def test_general_flows():
    """اختبار المسارات العامة"""
    print("فحص المسارات العامة (التي تستخدم _build_general_fields):")
    print("=" * 80)
    
    for flow_name, test_data in general_flows_test.items():
        print(f"\n🔍 اختبار مسار: {flow_name}")
        print("-" * 50)
        
        try:
            result = format_report_message(test_data)
            print("✅ تم إنشاء التقرير بنجاح")
            
            # التحقق من العناصر الأساسية
            basic_checks = {
                'تقرير معدل': '✏️ **تقرير معدل**' in result,
                'اسم المريض': test_data['patient_name'] in result,
                'نوع الإجراء': test_data['medical_action'] in result,
                'المترجم': test_data['translator_name'] in result,
            }
            
            for check, passed in basic_checks.items():
                status = "✅" if passed else "❌"
                print(f"{status} {check}")
            
            # عرض أول 300 حرف للتحقق السريع
            print(f"\n📄 بداية المحتوى:")
            print(result[:300] + "..." if len(result) > 300 else result)
                
        except Exception as e:
            print(f"❌ خطأ في مسار {flow_name}: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 50)

if __name__ == "__main__":
    test_general_flows()