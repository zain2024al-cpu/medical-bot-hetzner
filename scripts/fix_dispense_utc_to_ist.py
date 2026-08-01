# -*- coding: utf-8 -*-
"""تصحيح تواريخ سجلات الصرف القديمة: UTC ← IST (+5:30).

كانت سجلات الصرف تُختَم بـ ``datetime.utcnow()`` بينما يعمل المستخدمون
بتوقيت الهند (UTC+5:30)، فأي عمل بين 00:00 و 05:29 بتوقيت الهند خُزِّن
باسم اليوم السابق واختفى من مسير ذلك اليوم. هذا السكربت يُضيف 5:30 إلى
الأختام القديمة فتعود إلى يومها الصحيح.

⚠️ لا يمسّ السجلات التي اختار المستخدم تاريخها يدوياً من التقويم
(ختمها 00:00:00 بالضبط) — إضافة 5:30 إليها ستُبقيها في اليوم نفسه على أي
حال، لكننا نتركها كما هي احتياطاً لئلا نغيّر اختياراً صريحاً.

الاستخدام:
    venv/bin/python scripts/fix_dispense_utc_to_ist.py                # معاينة
    venv/bin/python scripts/fix_dispense_utc_to_ist.py --apply        # تنفيذ

خذ نسخة احتياطية من قاعدة البيانات قبل --apply.
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import MedicationRecord, SuppliesRecord

SHIFT = timedelta(hours=5, minutes=30)
# الحدّ الفاصل: التصحيح يخصّ السجلات المكتوبة قبل نشر إصلاح التوقيت.
# مرِّر --since YYYY-MM-DD لتقييد النطاق، وإلا فكل السجلات القديمة.


def main() -> None:
    apply = "--apply" in sys.argv
    since = None
    if "--since" in sys.argv:
        from datetime import date, datetime, time
        since = datetime.combine(
            date.fromisoformat(sys.argv[sys.argv.index("--since") + 1]), time.min)

    changed_days = 0
    total = 0

    with SessionLocal() as s:
        for stype, model in (("medication", MedicationRecord), ("supplies", SuppliesRecord)):
            q = s.query(model).filter(model.created_at.isnot(None))
            if since is not None:
                q = q.filter(model.created_at >= since)
            for r in q.order_by(model.created_at).all():
                old = r.created_at
                if old.hour == 0 and old.minute == 0 and old.second == 0:
                    continue                      # تاريخ اختاره المستخدم صراحةً
                new = old + SHIFT
                total += 1
                moved = new.date() != old.date()
                if moved:
                    changed_days += 1
                mark = "  ← ينتقل ليوم آخر" if moved else ""
                print(f"[{stype}#{r.id}] {(r.patient_name or '')[:22]:22s} "
                      f"{old:%d/%m %H:%M} → {new:%d/%m %H:%M}{mark}")
                if apply:
                    r.created_at = new
        if apply:
            s.commit()

    print(f"\nالمجموع: {total} سجل ، منها {changed_days} ينتقل إلى يوم تقويمي آخر")
    if apply:
        print("✅ نُفِّذ وحُفِظ.")
    else:
        print("ℹ️  معاينة فقط — لم يُعدَّل شيء. أعد التشغيل مع --apply للتنفيذ.")


if __name__ == "__main__":
    main()
