#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')
from services.broadcast_service import format_report_message

# بيانات اختبار لكل مسار
test_cases = {
    'استشارة جديدة': {
        'medical_action': 'استشارة جديدة',
        'patient_name': 'أحمد محمد',
        'hospital_name': 'مستشفى دمشق',
        'department_name': 'الباطنة',
        'doctor_name': 'د. محمد علي',
        'complaint_text': 'ألم في المعدة',
        'diagnosis': 'التهاب المعدة الحاد',
        'decision': 'علاج دوائي والراحة',
        'tests': 'تحليل دم، أشعة البطن',
        'followup_date': '2026-01-20',
        'followup_time': '10:00',
        'followup_reason': 'متابعة الحالة',
        'translator_name': 'مترجم اختبار',
        'is_edit': True
    },
    'متابعة في الرقود': {
        'medical_action': 'متابعة في الرقود',
        'patient_name': 'فاطمة أحمد',
        'hospital_name': 'مستشفى حلب',
        'department_name': 'الجراحة',
        'doctor_name': 'د. سارة كريم',
        'complaint_text': 'ألم بعد العملية',
        'diagnosis': 'التئام جيد للجرح',
        'decision': 'متابعة العلاج والراحة',
        'room_number': 'غرفة 205 - الطابق الثاني',
        'followup_date': '2026-01-25',
        'followup_reason': 'فحص دوري',
        'translator_name': 'مترجم اختبار',
        'is_edit': True
    },
    'استشارة مع قرار عملية': {
        'medical_action': 'استشارة مع قرار عملية',
        'patient_name': 'عبد الله حسن',
        'hospital_name': 'مستشفى اللاذقية',
        'department_name': 'العظمية',
        'doctor_name': 'د. أحمد صالح',
        'diagnosis': 'كسر في عظمة الفخذ',
        'decision': 'ضرورة إجراء عملية جراحية',
        'operation_name_en': 'Femoral Fracture Repair',
        'success_rate': '95%',
        'benefit_rate': '90%',
        'tests': 'أشعة مقطعية، تحليل دم شامل',
        'followup_date': '2026-02-01',
        'followup_reason': 'تحديد موعد العملية',
        'translator_name': 'مترجم اختبار',
        'is_edit': True
    },
    'أشعة وفحوصات': {
        'medical_action': 'أشعة وفحوصات',
        'patient_name': 'زينب عبد الرحمن',
        'hospital_name': 'مستشفى طرطوس',
        'department_name': 'الأشعة',
        'doctor_name': 'د. محمود يوسف',
        'radiology_type': 'أشعة مقطعية للبطن، تحليل دم شامل',
        'radiology_delivery_date': '2026-01-18',
        'translator_name': 'مترجم اختبار',
        'is_edit': True
    },
    'تأجيل موعد': {
        'medical_action': 'تأجيل موعد',
        'patient_name': 'محمد عبد الله',
        'hospital_name': 'مستشفى حمص',
        'department_name': 'القلبية',
        'doctor_name': 'د. لينا محمد',
        'app_reschedule_reason': 'ظروف طارئة للمريض',
        'app_reschedule_return_date': '2026-01-30',
        'app_reschedule_return_reason': 'فحص دوري للقلب',
        'translator_name': 'مترجم اختبار',
        'is_edit': True
    },
    'استشارة أخيرة': {
        'medical_action': 'استشارة أخيرة',
        'patient_name': 'عائشة علي',
        'hospital_name': 'مستشفى السويداء',
        'department_name': 'الأورام',
        'doctor_name': 'د. رامي حسين',
        'diagnosis': 'شفاء تام من المرض',
        'decision': 'انتهاء العلاج وعدم الحاجة لمتابعة',
        'recommendations': 'نظام غذائي صحي ومتابعة سنوية',
        'translator_name': 'مترجم اختبار',
        'is_edit': True
    }
}

def test_all_flows():
    """اختبار جميع المسارات"""
    print("فحص شامل لجميع المسارات بعد التعديل وإعادة النشر:")
    print("=" * 80)
    
    for flow_name, test_data in test_cases.items():
        print(f"\n🔍 اختبار مسار: {flow_name}")
        print("-" * 50)
        
        try:
            # تطبيق format_report_message
            result = format_report_message(test_data)
            
            # فحص وجود العناصر المهمة
            required_elements = {
                'تقرير معدل': '✏️ **تقرير معدل**' in result,
                'اسم المريض': test_data['patient_name'] in result,
                'المستشفى': test_data['hospital_name'] in result,
                'القسم': test_data['department_name'] in result,
                'الطبيب': test_data['doctor_name'] in result,
                'المترجم': test_data['translator_name'] in result,
                'نوع الإجراء': test_data['medical_action'] in result,
            }
            
            # فحص الحقول الخاصة لكل مسار
            if flow_name == 'استشارة جديدة':
                required_elements.update({
                    'الشكوى': test_data['complaint_text'] in result,
                    'التشخيص': test_data['diagnosis'] in result,
                    'قرار الطبيب': test_data['decision'] in result,
                    'الفحوصات': test_data['tests'] in result,
                    'موعد العودة': 'موعد العودة' in result
                })
            elif flow_name == 'متابعة في الرقود':
                required_elements.update({
                    'الشكوى': test_data['complaint_text'] in result,
                    'التشخيص': test_data['diagnosis'] in result,
                    'قرار الطبيب': test_data['decision'] in result,
                    'رقم الغرفة': test_data['room_number'] in result
                })
            elif flow_name == 'استشارة مع قرار عملية':
                required_elements.update({
                    'التشخيص': test_data['diagnosis'] in result,
                    'قرار الطبيب': test_data['decision'] in result,
                    'اسم العملية': test_data['operation_name_en'] in result,
                    'نسبة النجاح': test_data['success_rate'] in result,
                    'نسبة الاستفادة': test_data['benefit_rate'] in result,
                    'الفحوصات': test_data['tests'] in result
                })
            elif flow_name == 'أشعة وفحوصات':
                required_elements.update({
                    'نوع الأشعة': test_data['radiology_type'] in result,
                    'تاريخ التسليم': 'تاريخ التسليم' in result
                })
            elif flow_name == 'تأجيل موعد':
                required_elements.update({
                    'سبب التأجيل': test_data['app_reschedule_reason'] in result,
                    'موعد العودة': 'موعد العودة' in result,
                    'سبب العودة': test_data['app_reschedule_return_reason'] in result
                })
            elif flow_name == 'استشارة أخيرة':
                required_elements.update({
                    'التشخيص': test_data['diagnosis'] in result,
                    'قرار الطبيب': test_data['decision'] in result,
                    'التوصيات': test_data['recommendations'] in result
                })
            
            # عرض النتائج
            missing_elements = []
            for element, found in required_elements.items():
                if found:
                    print(f"✅ {element}: موجود")
                else:
                    print(f"❌ {element}: مفقود")
                    missing_elements.append(element)
            
            if missing_elements:
                print(f"\n⚠️ عناصر مفقودة في مسار {flow_name}: {', '.join(missing_elements)}")
                print(f"\n📄 المحتوى الكامل:")
                print(result[:500] + "..." if len(result) > 500 else result)
            else:
                print(f"\n✅ جميع العناصر موجودة في مسار {flow_name}")
                
        except Exception as e:
            print(f"❌ خطأ في اختبار مسار {flow_name}: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 50)

if __name__ == "__main__":
    test_all_flows()