#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اختبار المشكلة الفعلية - لماذا يرجع لنوع الإجراء بدلاً من التنقل خطوة بخطوة
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot', 'handlers', 'user'))

from user_reports_add_new_system import SmartNavigationManager

# Import states
from user_reports_add_new_system.states import (
    STATE_SELECT_ACTION_TYPE, FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM
)

def test_actual_navigation():
    """اختبار التنقل الفعلي لمراجعة العودة الدورية"""
    print("="*80)
    print("🔍 اختبار التنقل الفعلي لمراجعة العودة الدورية")
    print("="*80)
    
    nav_manager = SmartNavigationManager()
    
    # سيناريو: المستخدم في مرحلة التشخيص ويريد الرجوع
    current_state = FOLLOWUP_DIAGNOSIS
    flow_type = "periodic_followup"
    
    print(f"🎯 الحالة الحالية: {current_state} (FOLLOWUP_DIAGNOSIS)")
    print(f"🎯 نوع المسار: {flow_type}")
    print()
    
    # محاكاة user_data مشابهة للواقع
    mock_user_data = {
        'report_tmp': {
            'medical_action': 'مراجعة / عودة دورية',
            'current_flow': 'periodic_followup'
        },
        '_conversation_state': current_state
    }
    
    print("📋 البيانات المحاكية:")
    print(f"   medical_action: {mock_user_data['report_tmp']['medical_action']}")
    print(f"   current_flow: {mock_user_data['report_tmp']['current_flow']}")
    print(f"   _conversation_state: {mock_user_data['_conversation_state']}")
    print()
    
    # اختبار التنقل
    print("🔙 اختبار زر الرجوع:")
    previous_step = nav_manager.get_previous_step(flow_type, current_state)
    
    print(f"   Current: {current_state} → Previous: {previous_step}")
    
    # تحقق من النتيجة المتوقعة
    expected = FOLLOWUP_COMPLAINT
    if previous_step == expected:
        print(f"   ✅ صحيح! يجب أن يرجع إلى {expected} (FOLLOWUP_COMPLAINT)")
    else:
        print(f"   ❌ خطأ! توقعنا {expected} لكن حصلنا على {previous_step}")
    
    print()
    print("🔍 فحص خريطة التنقل المباشرة:")
    
    # فحص الخريطة مباشرة
    flow_map = nav_manager.step_flows.get('periodic_followup', {})
    direct_previous = flow_map.get(current_state)
    
    print(f"   خريطة periodic_followup[{current_state}] = {direct_previous}")
    print(f"   STATE_SELECT_ACTION_TYPE = {STATE_SELECT_ACTION_TYPE}")
    print(f"   FOLLOWUP_COMPLAINT = {FOLLOWUP_COMPLAINT}")
    
    if direct_previous == FOLLOWUP_COMPLAINT:
        print("   ✅ الخريطة صحيحة - التشخيص يرجع لشكوى المريض")
    elif direct_previous == STATE_SELECT_ACTION_TYPE:
        print("   ❌ الخريطة خاطئة - التشخيص يرجع لنوع الإجراء!")
    else:
        print(f"   ❓ قيمة غير متوقعة: {direct_previous}")

def test_all_periodic_steps():
    """اختبار جميع خطوات مراجعة العودة الدورية"""
    print("\n" + "="*80)
    print("📋 اختبار جميع خطوات مراجعة العودة الدورية")
    print("="*80)
    
    nav_manager = SmartNavigationManager()
    flow_map = nav_manager.step_flows.get('periodic_followup', {})
    
    test_cases = [
        (FOLLOWUP_COMPLAINT, "شكوى المريض"),
        (FOLLOWUP_DIAGNOSIS, "التشخيص"),  
        (FOLLOWUP_DECISION, "قرار الطبيب"),
        (FOLLOWUP_DATE_TIME, "تاريخ العودة"),
        (FOLLOWUP_REASON, "سبب العودة"),
        (FOLLOWUP_TRANSLATOR, "اسم المترجم"),
        (FOLLOWUP_CONFIRM, "تأكيد التقرير")
    ]
    
    for current_step, description in test_cases:
        previous_step = flow_map.get(current_step, "NOT FOUND")
        print(f"{description:15} ({current_step:2d}) → {previous_step}")
        
        # تحقق خاص لكل حالة
        if current_step == FOLLOWUP_COMPLAINT:
            expected = STATE_SELECT_ACTION_TYPE
            status = "✅" if previous_step == expected else "❌"
            print(f"   {status} متوقع: {expected} (نوع الإجراء)")
        elif current_step == FOLLOWUP_DIAGNOSIS:
            expected = FOLLOWUP_COMPLAINT
            status = "✅" if previous_step == expected else "❌"
            print(f"   {status} متوقع: {expected} (شكوى المريض)")

if __name__ == "__main__":
    test_actual_navigation()
    test_all_periodic_steps()
    print("\n🔍 إذا رأيت ❌ فهذا يعني أن هناك مشكلة في الخريطة!")