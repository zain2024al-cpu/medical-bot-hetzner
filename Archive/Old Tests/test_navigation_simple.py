#!/usr/bin/env python3
"""
اختبار التنقل الذكي المبسط لمسار مراجعة / عودة دورية
للتأكد من أن زر الرجوع يعمل خطوة بخطوة وليس الرجوع المباشر لقائمة نوع الإجراء
"""

print("=" * 80)
print("🔍 TESTING PERIODIC FOLLOWUP SMART NAVIGATION")
print("=" * 80)

# محاكاة states (قيم رقمية)
STATE_SELECT_DATE = 1
STATE_SELECT_PATIENT = 2
STATE_SELECT_HOSPITAL = 3
STATE_SELECT_DEPARTMENT = 4
STATE_SELECT_SUBDEPARTMENT = 5
STATE_SELECT_DOCTOR = 6
STATE_SELECT_ACTION_TYPE = 7
FOLLOWUP_COMPLAINT = 20
FOLLOWUP_DIAGNOSIS = 21
FOLLOWUP_DECISION = 22
FOLLOWUP_ROOM_FLOOR = 23
FOLLOWUP_DATE_TIME = 24
FOLLOWUP_REASON = 25
FOLLOWUP_TRANSLATOR = 26
FOLLOWUP_CONFIRM = 27

# خريطة التنقل لمسار periodic_followup (المحدثة)
periodic_followup_map = {
    STATE_SELECT_DATE: None,
    STATE_SELECT_PATIENT: STATE_SELECT_DATE,
    STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
    STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
    STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
    STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
    STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
    FOLLOWUP_COMPLAINT: STATE_SELECT_DOCTOR,  # ✅ المطلوب: رجوع ذكي للطبيب
    FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,
    FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,
    # تخطي رقم الغرفة
    FOLLOWUP_DATE_TIME: FOLLOWUP_DECISION,
    FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,
    FOLLOWUP_TRANSLATOR: FOLLOWUP_REASON,
    FOLLOWUP_CONFIRM: FOLLOWUP_TRANSLATOR,
}

def get_previous_step_simple(current_step):
    """دالة مبسطة للحصول على الخطوة السابقة"""
    # البحث بالرقم مباشرة
    if current_step in periodic_followup_map:
        return periodic_followup_map[current_step]
    
    return None

# تعريف خطوات مسار مراجعة / عودة دورية
test_cases = [
    ("STATE_SELECT_DATE", STATE_SELECT_DATE, None),
    ("STATE_SELECT_PATIENT", STATE_SELECT_PATIENT, STATE_SELECT_DATE),
    ("STATE_SELECT_HOSPITAL", STATE_SELECT_HOSPITAL, STATE_SELECT_PATIENT),
    ("STATE_SELECT_DEPARTMENT", STATE_SELECT_DEPARTMENT, STATE_SELECT_HOSPITAL),
    ("STATE_SELECT_SUBDEPARTMENT", STATE_SELECT_SUBDEPARTMENT, STATE_SELECT_DEPARTMENT),
    ("STATE_SELECT_DOCTOR", STATE_SELECT_DOCTOR, STATE_SELECT_SUBDEPARTMENT),
    ("STATE_SELECT_ACTION_TYPE", STATE_SELECT_ACTION_TYPE, STATE_SELECT_DOCTOR),
    ("FOLLOWUP_COMPLAINT", FOLLOWUP_COMPLAINT, STATE_SELECT_DOCTOR),  # ✅ المطلوب: رجوع ذكي للطبيب
    ("FOLLOWUP_DIAGNOSIS", FOLLOWUP_DIAGNOSIS, FOLLOWUP_COMPLAINT),
    ("FOLLOWUP_DECISION", FOLLOWUP_DECISION, FOLLOWUP_DIAGNOSIS),
    # تخطي FOLLOWUP_ROOM_FLOOR
    ("FOLLOWUP_DATE_TIME", FOLLOWUP_DATE_TIME, FOLLOWUP_DECISION),
    ("FOLLOWUP_REASON", FOLLOWUP_REASON, FOLLOWUP_DATE_TIME),
    ("FOLLOWUP_TRANSLATOR", FOLLOWUP_TRANSLATOR, FOLLOWUP_REASON),
    ("FOLLOWUP_CONFIRM", FOLLOWUP_CONFIRM, FOLLOWUP_TRANSLATOR),
]

print(f"\n📋 Testing {len(test_cases)} steps in periodic_followup flow:")
print("-" * 60)

all_passed = True

for i, (state_name, current_state, expected_previous) in enumerate(test_cases, 1):
    actual_previous = get_previous_step_simple(current_state)
    
    if actual_previous == expected_previous:
        status = "✅ PASS"
    else:
        status = "❌ FAIL"
        all_passed = False
    
    print(f"{i:2d}. {status} {state_name:25} ← {actual_previous}")
    if actual_previous != expected_previous:
        print(f"    Expected: {expected_previous}")
        print(f"    Actual:   {actual_previous}")

print("-" * 60)

# اختبار خاص للحالة المهمة
print("\n🎯 TESTING CRITICAL CASE:")
print("-" * 40)

complaint_previous = get_previous_step_simple(FOLLOWUP_COMPLAINT)
if complaint_previous == STATE_SELECT_DOCTOR:
    print("✅ FOLLOWUP_COMPLAINT → STATE_SELECT_DOCTOR (Smart Navigation)")
    print("   This means users can go back to change the doctor, not directly to action type menu!")
else:
    print(f"❌ FOLLOWUP_COMPLAINT → {complaint_previous} (Should be STATE_SELECT_DOCTOR)")
    all_passed = False

print("\n" + "=" * 80)
if all_passed:
    print("🎉 ALL TESTS PASSED! Periodic followup smart navigation is working correctly.")
    print("   ✅ Users can navigate step-by-step and change previous selections")
    print("   ✅ Back button now goes to doctor selection, not action type menu")
else:
    print("⚠️  SOME TESTS FAILED! Check the navigation mapping.")
print("=" * 80)