# -*- coding: utf-8 -*-
"""تشخيص (قراءة فقط): لماذا لا يظهر تاريخ معيّن في مسير الإخلاء؟

الاستخدام:
    venv/bin/python scripts/diag_manifest_date.py 2026-07-31

يفحص كل شروط الاستبعاد الأربعة لكل سجل صرف في ذلك اليوم:
  1) جهة الصرف ليست "الصيدلية"
  2) لا يوجد تقرير مالي مرتبط
  3) الفاتورة محذوفة
  4) نوع المسير (A/B/C) لا يطابق ما طُبع
لا يُعدّل أي شيء في قاعدة البيانات.
"""
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import MedicationRecord, SuppliesRecord, PharmacyFinancialRecord
from services.pharmacy_evacuation_service import _get_evacuation_ledger_rows_sync


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        target = date.fromisoformat(arg) if arg else date.today()
    except ValueError:
        print(f"تاريخ غير صالح: {arg!r} — الصيغة المطلوبة YYYY-MM-DD")
        return

    start_dt = datetime.combine(target, time.min)
    end_dt = datetime.combine(target, time.max)

    print(f"=== تشخيص مسير يوم {target.strftime('%d/%m/%Y')} ===\n")

    with SessionLocal() as s:
        med = (s.query(MedicationRecord)
               .filter(MedicationRecord.created_at >= start_dt,
                       MedicationRecord.created_at <= end_dt).all())
        sup = (s.query(SuppliesRecord)
               .filter(SuppliesRecord.created_at >= start_dt,
                       SuppliesRecord.created_at <= end_dt).all())

        print(f"سجلات الصرف المخزّنة بهذا التاريخ: أدوية={len(med)}  مستلزمات={len(sup)}")
        if not med and not sup:
            print("\n⚠️  لا يوجد أي سجل صرف مخزَّن بهذا التاريخ إطلاقاً.")
            print("    إمّا لم يُدخَل صرف في ذلك اليوم، أو أُدخل بتاريخ مختلف")
            print("    (خطوة «📅 اختر التاريخ» في أول التدفق تحدّد التاريخ المخزَّن).")

        for stype, rows in (("medication", med), ("supplies", sup)):
            for r in rows:
                fin = (s.query(PharmacyFinancialRecord)
                       .filter_by(source_type=stype, source_record_id=r.id).first())
                blockers = []
                notes = []
                if (r.dispense_source or "") != "الصيدلية":
                    blockers.append(f"جهة الصرف = {r.dispense_source!r} وليست «الصيدلية»")
                if fin is None:
                    blockers.append("لا يوجد تقرير مالي مرتبط")
                else:
                    if getattr(fin, "is_deleted", False):
                        blockers.append("الفاتورة محذوفة")
                    notes.append(f"نوع المسير = {fin.manifest_type!r}")
                    notes.append(f"الصافي = {fin.net_amount}")
                mark = "❌ مستبعَد" if blockers else "✅ يظهر"
                detail = " | ".join(blockers + notes) or "بلا ملاحظات"
                print(f"  [{stype}#{r.id}] {r.patient_name} | {r.created_at} | {mark}")
                print(f"        {detail}")

    print("\n--- ما يُرجعه المسير فعلاً ---")
    for mt in (None, "A", "B", "C"):
        n = len(_get_evacuation_ledger_rows_sync(target, target, mt))
        print(f"  نوع المسير {mt or 'الكل'}: {n} سطر")

    print("\n--- الأيام المجاورة (للمقارنة) ---")
    for delta in (-1, 1):
        d = target + timedelta(days=delta)
        n = len(_get_evacuation_ledger_rows_sync(d, d, None))
        print(f"  {d.strftime('%d/%m/%Y')}: {n} سطر")


if __name__ == "__main__":
    main()
