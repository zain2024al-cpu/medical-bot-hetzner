#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اختبار مبسط للمشكلة
"""

def test_states():
    """اختبار قيم الحالات"""
    
    # Constants من states.py
    STATE_SELECT_ACTION_TYPE = 6
    FOLLOWUP_COMPLAINT = 16
    FOLLOWUP_DIAGNOSIS = 17
    FOLLOWUP_DECISION = 18
    FOLLOWUP_DATE_TIME = 19
    FOLLOWUP_REASON = 20
    FOLLOWUP_TRANSLATOR = 21
    FOLLOWUP_CONFIRM = 22
    
    print("="*80)
    print("🔍 قيم الحالات")
    print("="*80)
    print(f"STATE_SELECT_ACTION_TYPE = {STATE_SELECT_ACTION_TYPE}")
    print(f"FOLLOWUP_COMPLAINT = {FOLLOWUP_COMPLAINT}")
    print(f"FOLLOWUP_DIAGNOSIS = {FOLLOWUP_DIAGNOSIS}")
    print(f"FOLLOWUP_DECISION = {FOLLOWUP_DECISION}")
    print()
    
    # خريطة التنقل كما هي في الكود
    periodic_followup_map = {
        FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,        # شكوى ← نوع الإجراء
        FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,              # تشخيص ← شكوى المريض  
        FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,               # قرار ← تشخيص
        FOLLOWUP_DATE_TIME: FOLLOWUP_DECISION,               # تاريخ ← قرار
        FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,                 # سبب ← تاريخ
        FOLLOWUP_TRANSLATOR: FOLLOWUP_REASON,                # مترجم ← سبب
        FOLLOWUP_CONFIRM: FOLLOWUP_TRANSLATOR,
    }
    
    print("🗺️ خريطة التنقل:")
    print("="*80)
    
    test_cases = [
        (FOLLOWUP_COMPLAINT, "شكوى المريض"),
        (FOLLOWUP_DIAGNOSIS, "التشخيص"),  
        (FOLLOWUP_DECISION, "قرار الطبيب"),
        (FOLLOWUP_DATE_TIME, "تاريخ العودة"),
        (FOLLOWUP_REASON, "سبب العودة"),
        (FOLLOWUP_TRANSLATOR, "اسم المترجم")
    ]
    
    for current_step, description in test_cases:
        previous_step = periodic_followup_map.get(current_step, "NOT FOUND")
        print(f"{description:15} ({current_step:2d}) → {previous_step}")
        
        # تحليل خاص
        if current_step == FOLLOWUP_DIAGNOSIS:
            if previous_step == FOLLOWUP_COMPLAINT:
                print("   ✅ صحيح - التشخيص يرجع لشكوى المريض")
            elif previous_step == STATE_SELECT_ACTION_TYPE:
                print("   ❌ خطأ - التشخيص يرجع لنوع الإجراء!")
            else:
                print(f"   ❓ قيمة غير متوقعة: {previous_step}")
    
    print()
    print("🎯 اختبار السؤال الأساسي:")
    print(f"إذا كان المستخدم في التشخيص ({FOLLOWUP_DIAGNOSIS})")
    diagnosis_previous = periodic_followup_map.get(FOLLOWUP_DIAGNOSIS)
    print(f"فسوف يرجع إلى: {diagnosis_previous}")
    
    if diagnosis_previous == FOLLOWUP_COMPLAINT:
        print("✅ هذا صحيح - سيرجع لشكوى المريض")
    elif diagnosis_previous == STATE_SELECT_ACTION_TYPE:
        print("❌ هذا خطأ - سيرجع لنوع الإجراء (المشكلة موجودة!)")

if __name__ == "__main__":
    test_states()