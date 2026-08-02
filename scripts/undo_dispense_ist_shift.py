# -*- coding: utf-8 -*-
"""تراجع: يُلغي أثر scripts/fix_dispense_utc_to_ist.py (نظرية توقيت خاطئة).

تبيّن أن اختفاء تاريخ 31/07 من المسير كان خطأ إدخال من المستخدم (اختار
31 أغسطس بدل 31 يوليو من التقويم)، لا مشكلة توقيت UTC/IST. سكربت
`fix_dispense_utc_to_ist.py --apply` كان قد أضاف 5:30 ساعة لختم كل سجلات
الصرف القديمة على افتراض خاطئ. هذا السكربت يعكس ذلك تماماً بطرح 5:30.

يعتمد نفس معيار الاستثناء المستخدم في السكربت الأصلي (تجاهل الأختام
عند 00:00:00 بالضبط — تواريخ اختيرت صراحة من التقويم ولم تُلمَس أصلاً)،
فالنتيجة عكس دقيق للتعديل السابق فقط، بلا مساس بأي سجل آخر.

الاستخدام:
    venv/bin/python scripts/undo_dispense_ist_shift.py                # معاينة
    venv/bin/python scripts/undo_dispense_ist_shift.py --apply        # تنفيذ

خذ نسخة احتياطية من قاعدة البيانات قبل --apply (رغم أن التعديل هنا
عكسي بحت ومضمون الاسترجاع لتلك السجلات فقط).
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import MedicationRecord, SuppliesRecord

SHIFT = timedelta(hours=5, minutes=30)


def main() -> None:
    apply = "--apply" in sys.argv

    changed_days = 0
    total = 0

    with SessionLocal() as s:
        for stype, model in (("medication", MedicationRecord), ("supplies", SuppliesRecord)):
            for r in s.query(model).filter(model.created_at.isnot(None)).order_by(model.created_at).all():
                old = r.created_at
                if old.hour == 0 and old.minute == 0 and old.second == 0:
                    continue                      # تاريخ اختاره المستخدم صراحةً — لم يُلمَس أصلاً
                new = old - SHIFT
                total += 1
                moved = new.date() != old.date()
                if moved:
                    changed_days += 1
                mark = "  ← يرجع ليوم آخر" if moved else ""
                print(f"[{stype}#{r.id}] {(r.patient_name or '')[:22]:22s} "
                      f"{old:%d/%m %H:%M} → {new:%d/%m %H:%M}{mark}")
                if apply:
                    r.created_at = new
        if apply:
            s.commit()

    print(f"\nالمجموع: {total} سجل ، منها {changed_days} يرجع ليوم تقويمي آخر")
    if apply:
        print("✅ نُفِّذ التراجع وحُفِظ.")
    else:
        print("ℹ️  معاينة فقط — لم يُعدَّل شيء. أعد التشغيل مع --apply للتنفيذ.")


if __name__ == "__main__":
    main()
