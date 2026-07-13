لا#!/usr/bin/env python3
"""
اختبار التنقل الذكي لمسار مراجعة / عودة دورية
للتأكد من أن زر الرجوع يعمل خطوة بخطوة وليس الرجوع المباشر لقائمة نوع الإجراء
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# استيراد States
from bot.states import *
from bot.handlers.user.user_reports_add_new_system import SmartNavigationManager

def test_periodic_followup_navigation():
    """اختبار خريطة التنقل لمسار مراجعة / عودة دورية"""
    print("=" * 80)
    print("🔍 TESTING PERIODIC FOLLOWUP SMART NAVIGATION")
    print("=" * 80)
    
    nav_manager = SmartNavigationManager()
    flow_type = 'periodic_followup'
    
    # تعريف خطوات مسار مراجعة / عودة دورية
    expected_flow = [
        (STATE_SELECT_DATE, None),
        (STATE_SELECT_PATIENT, STATE_SELECT_DATE),
        (STATE_SELECT_HOSPITAL, STATE_SELECT_PATIENT),
        (STATE_SELECT_DEPARTMENT, STATE_SELECT_HOSPITAL),
        (STATE_SELECT_SUBDEPARTMENT, STATE_SELECT_DEPARTMENT),
        (STATE_SELECT_DOCTOR, STATE_SELECT_SUBDEPARTMENT),
        (STATE_SELECT_ACTION_TYPE, STATE_SELECT_DOCTOR),
        (FOLLOWUP_COMPLAINT, STATE_SELECT_DOCTOR),  # ✅ المطلوب: رجوع ذكي للطبيب
        (FOLLOWUP_DIAGNOSIS, FOLLOWUP_COMPLAINT),
        (FOLLOWUP_DECISION, FOLLOWUP_DIAGNOSIS),
        # تخطي FOLLOWUP_ROOM_FLOOR
        (FOLLOWUP_DATE_TIME, FOLLOWUP_DECISION),
        (FOLLOWUP_REASON, FOLLOWUP_DATE_TIME),
        (FOLLOWUP_TRANSLATOR, FOLLOWUP_REASON),
        (FOLLOWUP_CONFIRM, FOLLOWUP_TRANSLATOR),
    ]
    
    print(f"\n📋 Testing {len(expected_flow)} steps in {flow_type} flow:")
    print("-" * 60)
    
    all_passed = True
    
    for i, (current_state, expected_previous) in enumerate(expected_flow, 1):
        actual_previous = nav_manager.get_previous_step(flow_type, current_state)
        
        if actual_previous == expected_previous:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        
        print(f"{i:2d}. {status} {current_state:25} ← {actual_previous}")
        if actual_previous != expected_previous:
            print(f"    Expected: {expected_previous}")
            print(f"    Actual:   {actual_previous}")
    
    print("-" * 60)
    
    # اختبار خاص للحالة المهمة
    print("\n🎯 TESTING CRITICAL CASE:")
    print("-" * 40)
    
    complaint_previous = nav_manager.get_previous_step(flow_type, FOLLOWUP_COMPLAINT)
    if complaint_previous == STATE_SELECT_DOCTOR:
        print("✅ FOLLOWUP_COMPLAINT → STATE_SELECT_DOCTOR (Smart Navigation)")
    else:
        print(f"❌ FOLLOWUP_COMPLAINT → {complaint_previous} (Should be STATE_SELECT_DOCTOR)")
        all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Periodic followup smart navigation is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED! Check the navigation mapping.")
    print("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    test_periodic_followup_navigation()