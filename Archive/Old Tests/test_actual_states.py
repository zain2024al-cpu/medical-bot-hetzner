#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
التحقق من القيم الفعلية للحالات
"""

# محاكاة نفس التعريف من states.py
(
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM
) = range(16, 24)

print("="*80)
print("🔢 القيم الفعلية للحالات (من range(16, 24))")
print("="*80)

states = [
    ('FOLLOWUP_COMPLAINT', FOLLOWUP_COMPLAINT),
    ('FOLLOWUP_DIAGNOSIS', FOLLOWUP_DIAGNOSIS),
    ('FOLLOWUP_DECISION', FOLLOWUP_DECISION),
    ('FOLLOWUP_ROOM_FLOOR', FOLLOWUP_ROOM_FLOOR),
    ('FOLLOWUP_DATE_TIME', FOLLOWUP_DATE_TIME),
    ('FOLLOWUP_REASON', FOLLOWUP_REASON),
    ('FOLLOWUP_TRANSLATOR', FOLLOWUP_TRANSLATOR),
    ('FOLLOWUP_CONFIRM', FOLLOWUP_CONFIRM)
]

for name, value in states:
    print(f"{name:20} = {value}")

print("\n🔍 فحص التضارب:")
if FOLLOWUP_ROOM_FLOOR == FOLLOWUP_DATE_TIME:
    print(f"❌ تضارب! FOLLOWUP_ROOM_FLOOR ({FOLLOWUP_ROOM_FLOOR}) == FOLLOWUP_DATE_TIME ({FOLLOWUP_DATE_TIME})")
else:
    print(f"✅ لا توجد تضاربات:")
    print(f"   FOLLOWUP_ROOM_FLOOR = {FOLLOWUP_ROOM_FLOOR}")
    print(f"   FOLLOWUP_DATE_TIME = {FOLLOWUP_DATE_TIME}")

print("\n🎯 اختبار التنقل للخلف من FOLLOWUP_DIAGNOSIS:")

# خريطة التنقل كما في الكود
periodic_followup_map = {
    FOLLOWUP_COMPLAINT: 6,  # STATE_SELECT_ACTION_TYPE
    FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,  # 17 → 16
    FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,   # 18 → 17
    FOLLOWUP_DATE_TIME: FOLLOWUP_DECISION,   # 20 → 18
    FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,     # 21 → 20
    FOLLOWUP_TRANSLATOR: FOLLOWUP_REASON,    # 22 → 21
    FOLLOWUP_CONFIRM: FOLLOWUP_TRANSLATOR,   # 23 → 22
}

current = FOLLOWUP_DIAGNOSIS  # 17
previous = periodic_followup_map.get(current)  # should be 16

print(f"من FOLLOWUP_DIAGNOSIS ({current}) → {previous}")

if previous == FOLLOWUP_COMPLAINT:
    print(f"✅ صحيح! يرجع لشكوى المريض ({FOLLOWUP_COMPLAINT})")
elif previous == 6:  # STATE_SELECT_ACTION_TYPE
    print(f"❌ خطأ! يرجع لنوع الإجراء ({6}) بدلاً من شكوى المريض!")
else:
    print(f"❓ قيمة غير متوقعة: {previous}")