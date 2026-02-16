#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اختبار شامل لمحاكاة المشكلة الحقيقية
"""

def test_real_scenario():
    """محاكاة السيناريو الحقيقي للمستخدم"""
    
    print("="*80)
    print("🔍 محاكاة السيناريو الحقيقي")
    print("="*80)
    
    # قيم الحالات
    STATE_SELECT_ACTION_TYPE = 6
    FOLLOWUP_COMPLAINT = 16
    FOLLOWUP_DIAGNOSIS = 17
    FOLLOWUP_DECISION = 18
    FOLLOWUP_DATE_TIME = 20
    FOLLOWUP_REASON = 21
    FOLLOWUP_TRANSLATOR = 22
    
    # الخرائط من الكود الفعلي
    navigation_maps = {
        'followup': {
            FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,
            FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,
            FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,
            # ... باقي الخريطة
        },
        'periodic_followup': {
            FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,    # شكوى ← نوع الإجراء
            FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,          # تشخيص ← شكوى المريض ✅
            FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,           # قرار ← تشخيص
            FOLLOWUP_DATE_TIME: FOLLOWUP_DECISION,           # تاريخ ← قرار (تخطي رقم الغرفة)
            FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,             # سبب ← تاريخ
            FOLLOWUP_TRANSLATOR: FOLLOWUP_REASON,            # مترجم ← سبب
        }
    }
    
    # سيناريو المستخدم: في التشخيص ويريد الرجوع
    user_scenario = {
        'current_state': FOLLOWUP_DIAGNOSIS,  # 17
        'medical_action': 'مراجعة / عودة دورية',
        'current_flow': 'periodic_followup'
    }
    
    print(f"🎯 المستخدم في: FOLLOWUP_DIAGNOSIS ({user_scenario['current_state']})")
    print(f"🎯 نوع الإجراء: {user_scenario['medical_action']}")
    print(f"🎯 المسار الحالي: {user_scenario['current_flow']}")
    
    # منطق تحديد flow_type (مبسط)
    flow_type = user_scenario['current_flow']
    if not flow_type:
        if user_scenario['medical_action'] == "مراجعة / عودة دورية":
            flow_type = "periodic_followup"
        else:
            flow_type = "periodic_followup"  # افتراضي
    
    print(f"\n🔍 flow_type المحدد: {flow_type}")
    
    # الحصول على الخطوة السابقة
    navigation_map = navigation_maps.get(flow_type, {})
    previous_step = navigation_map.get(user_scenario['current_state'])
    
    print(f"\n🔙 التنقل للخلف:")
    print(f"   من: FOLLOWUP_DIAGNOSIS ({user_scenario['current_state']})")
    print(f"   إلى: {previous_step}")
    
    # تحليل النتيجة
    if previous_step == FOLLOWUP_COMPLAINT:
        print(f"   ✅ صحيح! يرجع لشكوى المريض ({FOLLOWUP_COMPLAINT})")
    elif previous_step == STATE_SELECT_ACTION_TYPE:
        print(f"   ❌ خطأ! يرجع لنوع الإجراء ({STATE_SELECT_ACTION_TYPE}) بدلاً من شكوى المريض!")
        print(f"   🔍 هذا يعني أن النظام يستخدم خريطة خاطئة أو flow_type خاطئ")
    else:
        print(f"   ❓ قيمة غير متوقعة: {previous_step}")
    
    # اختبار إضافي للتأكد
    print(f"\n📋 فحص خريطة periodic_followup مباشرة:")
    periodic_map = navigation_maps['periodic_followup']
    direct_result = periodic_map.get(FOLLOWUP_DIAGNOSIS)
    print(f"   periodic_followup[FOLLOWUP_DIAGNOSIS] = {direct_result}")
    print(f"   FOLLOWUP_COMPLAINT = {FOLLOWUP_COMPLAINT}")
    
    if direct_result == FOLLOWUP_COMPLAINT:
        print(f"   ✅ خريطة periodic_followup صحيحة")
        print(f"   🔍 المشكلة إذن في تحديد flow_type أو استخدام خريطة خاطئة")
    
def test_wrong_flow_detection():
    """اختبار احتمالية استخدام خريطة خاطئة"""
    
    print(f"\n" + "="*80)
    print("🔍 اختبار استخدام خريطة خاطئة")
    print("="*80)
    
    STATE_SELECT_ACTION_TYPE = 6
    FOLLOWUP_COMPLAINT = 16
    FOLLOWUP_DIAGNOSIS = 17
    
    # إذا كان النظام يستخدم خريطة 'followup' بدلاً من 'periodic_followup'
    followup_map = {
        FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,
        FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,  # هذا صحيح
    }
    
    periodic_followup_map = {
        FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,
        FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,  # هذا صحيح أيضاً
    }
    
    print("🧪 اختبار النتيجة من كلا الخريطتين:")
    
    followup_result = followup_map.get(FOLLOWUP_DIAGNOSIS)
    periodic_result = periodic_followup_map.get(FOLLOWUP_DIAGNOSIS)
    
    print(f"   followup map: DIAGNOSIS → {followup_result}")
    print(f"   periodic_followup map: DIAGNOSIS → {periodic_result}")
    
    if followup_result == periodic_result == FOLLOWUP_COMPLAINT:
        print("   🤔 كلا الخريطتين تعطي نفس النتيجة!")
        print("   🔍 المشكلة إذن في مكان آخر...")

if __name__ == "__main__":
    test_real_scenario()
    test_wrong_flow_detection()