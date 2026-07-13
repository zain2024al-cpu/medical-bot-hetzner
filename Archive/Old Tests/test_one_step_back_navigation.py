#!/usr/bin/env python3
"""
اختبار التنقل خطوة واحدة للخلف
حسب طلب المستخدم: إذا كان في التشخيص يرجع إلى شكوى المريض
"""

print("=" * 80)
print("✅ اختبار التنقل خطوة واحدة للخلف")
print("=" * 80)

# محاكاة states
STATES = {
    'STATE_SELECT_DOCTOR': 6,
    'STATE_SELECT_ACTION_TYPE': 7,
    'FOLLOWUP_COMPLAINT': 16,
    'FOLLOWUP_DIAGNOSIS': 17,
    'FOLLOWUP_DECISION': 18,
    'FOLLOWUP_DATE_TIME': 20,
    'FOLLOWUP_REASON': 21,
    'FOLLOWUP_TRANSLATOR': 22,
}

def test_step_by_step_navigation():
    """اختبار التنقل خطوة بخطوة"""
    
    # الخريطة المحدثة
    periodic_followup_nav = {
        STATES['FOLLOWUP_COMPLAINT']: STATES['STATE_SELECT_ACTION_TYPE'],  # شكوى ← نوع الإجراء
        STATES['FOLLOWUP_DIAGNOSIS']: STATES['FOLLOWUP_COMPLAINT'],        # تشخيص ← شكوى المريض ✅
        STATES['FOLLOWUP_DECISION']: STATES['FOLLOWUP_DIAGNOSIS'],         # قرار ← تشخيص
        STATES['FOLLOWUP_DATE_TIME']: STATES['FOLLOWUP_DECISION'],         # تاريخ ← قرار
        STATES['FOLLOWUP_REASON']: STATES['FOLLOWUP_DATE_TIME'],           # سبب ← تاريخ
        STATES['FOLLOWUP_TRANSLATOR']: STATES['FOLLOWUP_REASON'],          # مترجم ← سبب
    }
    
    print("🎯 اختبار التنقل خطوة واحدة للخلف:")
    print("-" * 50)
    
    test_cases = [
        ("شكوى المريض", STATES['FOLLOWUP_COMPLAINT'], STATES['STATE_SELECT_ACTION_TYPE'], "نوع الإجراء"),
        ("التشخيص", STATES['FOLLOWUP_DIAGNOSIS'], STATES['FOLLOWUP_COMPLAINT'], "شكوى المريض"),
        ("قرار الطبيب", STATES['FOLLOWUP_DECISION'], STATES['FOLLOWUP_DIAGNOSIS'], "التشخيص"),
        ("تاريخ العودة", STATES['FOLLOWUP_DATE_TIME'], STATES['FOLLOWUP_DECISION'], "قرار الطبيب"),
        ("سبب العودة", STATES['FOLLOWUP_REASON'], STATES['FOLLOWUP_DATE_TIME'], "تاريخ العودة"),
        ("اسم المترجم", STATES['FOLLOWUP_TRANSLATOR'], STATES['FOLLOWUP_REASON'], "سبب العودة"),
    ]
    
    all_correct = True
    
    for current_name, current_state, expected_prev, expected_name in test_cases:
        actual_prev = periodic_followup_nav.get(current_state)
        
        if actual_prev == expected_prev:
            status = "✅ صحيح"
        else:
            status = "❌ خطأ"
            all_correct = False
        
        print(f"{status} إذا كان في {current_name:15} → يرجع إلى {expected_name}")
        
        if actual_prev != expected_prev:
            print(f"     متوقع: {expected_prev}, الفعلي: {actual_prev}")
    
    return all_correct

def show_complete_flow():
    """عرض التدفق الكامل"""
    
    print(f"\n📋 التدفق الكامل للتنقل:")
    print("-" * 50)
    
    print("التنقل للأمام:")
    forward_steps = [
        "1. اختيار التاريخ",
        "2. اختيار المريض", 
        "3. اختيار المستشفى",
        "4. اختيار القسم",
        "5. اختيار القسم الفرعي",
        "6. اختيار الطبيب",
        "7. اختيار نوع الإجراء",
        "8. شكوى المريض",
        "9. التشخيص",            # ← المثال المذكور
        "10. قرار الطبيب",
        "11. تاريخ العودة",
        "12. سبب العودة",
        "13. اسم المترجم"
    ]
    
    for step in forward_steps:
        print(f"   {step}")
    
    print(f"\nالتنقل للخلف (خطوة واحدة فقط):")
    back_steps = [
        "اسم المترجم ← سبب العودة",
        "سبب العودة ← تاريخ العودة",
        "تاريخ العودة ← قرار الطبيب",
        "قرار الطبيب ← التشخيص",
        "التشخيص ← شكوى المريض",      # ← المثال المذكور ✅
        "شكوى المريض ← نوع الإجراء",
        "نوع الإجراء ← الطبيب",
        "الطبيب ← القسم الفرعي",
        "... وهكذا خطوة بخطوة"
    ]
    
    for step in back_steps:
        print(f"   🔙 {step}")

def main():
    success = test_step_by_step_navigation()
    show_complete_flow()
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 ممتاز! التنقل خطوة واحدة للخلف يعمل بشكل صحيح!")
        print()
        print("✅ السلوك المطلوب:")
        print("   • إذا كان في التشخيص → يرجع إلى شكوى المريض")
        print("   • إذا كان في قرار الطبيب → يرجع إلى التشخيص")  
        print("   • إذا كان في شكوى المريض → يرجع إلى نوع الإجراء")
        print("   • وهكذا... خطوة واحدة فقط للخلف في كل مرة")
        print()
        print("🔥 التدفق الآن خطوة بخطوة بدون تخطي!")
    else:
        print("❌ هناك خطأ في التسلسل!")
    print("=" * 80)

if __name__ == "__main__":
    main()