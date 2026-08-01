# -*- coding: utf-8 -*-
"""تشخيص (قراءة فقط): توزيع تواريخ سجلات الصرف مقابل تواريخ إدخال الفواتير.

الاستخدام:
    venv/bin/python scripts/diag_dispense_range.py 2026-07-25 2026-08-02

يكشف ما إذا كان صرفُ يومٍ ما قد خُزِّن تحت يومٍ آخر (فرق توقيت، أو اختيار
خاطئ في خطوة «📅 اختر التاريخ»)، بمقارنة تاريخ سجل الصرف بتاريخ إنشاء
تقريره المالي وبساعة الحفظ الفعلية. لا يُعدّل أي شيء.
"""
import os
import sys
from collections import defaultdict
from datetime import date, datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import MedicationRecord, SuppliesRecord, PharmacyFinancialRecord


def main() -> None:
    try:
        start = date.fromisoformat(sys.argv[1])
        end = date.fromisoformat(sys.argv[2])
    except (IndexError, ValueError):
        print("الاستخدام: diag_dispense_range.py YYYY-MM-DD YYYY-MM-DD")
        return

    start_dt = datetime.combine(start, time.min)
    end_dt = datetime.combine(end, time.max)

    per_day = defaultdict(list)
    hours = defaultdict(int)

    with SessionLocal() as s:
        for stype, model in (("medication", MedicationRecord), ("supplies", SuppliesRecord)):
            for r in (s.query(model)
                      .filter(model.created_at >= start_dt, model.created_at <= end_dt)
                      .order_by(model.created_at).all()):
                fin = (s.query(PharmacyFinancialRecord)
                       .filter_by(source_type=stype, source_record_id=r.id).first())
                per_day[r.created_at.date()].append((stype, r, fin))
                hours[r.created_at.hour] += 1

        print(f"=== سجلات الصرف من {start} إلى {end} ===\n")
        d = start
        while d <= end:
            items = per_day.get(d, [])
            print(f"{d.strftime('%d/%m/%Y')} ({d.strftime('%A')}): {len(items)} سجل")
            for stype, r, fin in items:
                fin_day = fin.created_at.strftime("%d/%m %H:%M") if fin else "—"
                flag = ""
                if fin and fin.created_at.date() != r.created_at.date():
                    flag = "  ⚠️ الفاتورة أُدخلت في يوم مختلف"
                print(f"    {r.created_at.strftime('%H:%M:%S')} | {stype:10s} | "
                      f"{(r.patient_name or '')[:22]:22s} | جهة={r.dispense_source!r} | "
                      f"فاتورة={fin_day}{flag}")
            d = date.fromordinal(d.toordinal() + 1)

    print("\n=== توزيع ساعة الحفظ (يكشف فرق التوقيت UTC/IST) ===")
    for h in sorted(hours):
        print(f"  الساعة {h:02d}:00 — {hours[h]} سجل  {'← ساعة مبكرة جداً' if h < 3 else ''}")
    if hours:
        print("\nملاحظة: الهند UTC+5:30. لو كانت الساعات مركّزة بين 18:00 و 23:59")
        print("فهذا يعني أن التخزين بتوقيت UTC وأن الصرف المسائي يُنسب لليوم نفسه،")
        print("أما ما بين 18:30 و 23:59 UTC فيقع فعلياً في اليوم التالي بتوقيت الهند.")


if __name__ == "__main__":
    main()
