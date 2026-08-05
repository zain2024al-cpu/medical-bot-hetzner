# -*- coding: utf-8 -*-
"""تشخيص (قراءة فقط): لماذا يظهر مسير الإخلاء فارغاً لمستخدم معيّن.

الاستخدام:
    venv/bin/python scripts/diag_manifest_user.py <telegram_user_id> [من] [إلى]
    venv/bin/python scripts/diag_manifest_user.py 123456789 2026-08-01 2026-08-05

المسير يُظهر سجلاً واحداً فقط إذا اجتاز **أربعة** شروط معاً، وفشل أيٍّ منها
يعطي نفس الرسالة «لا توجد بيانات» دون تمييز. هذا السكربت يفحصها واحداً واحداً
ويقول أيّها أسقط البيانات:

  ١. created_by == المستخدم   (عزل: كل مستخدم يرى ما أدخله هو فقط، إلا الأدمن)
  ٢. dispense_source == "الصيدلية"
  ٣. created_at داخل الفترة المطلوبة
  ٤. وجود تقرير مالي مرتبط غير محذوف

لا يُعدّل أي شيء.
"""
import os
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import MedicationRecord, SuppliesRecord, PharmacyFinancialRecord

_PHARMACY_SOURCE = "الصيدلية"


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    uid = int(sys.argv[1])
    end = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date.today()
    start = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else end - timedelta(days=30)
    start_dt, end_dt = datetime.combine(start, time.min), datetime.combine(end, time.max)

    print("=" * 68)
    print(f"تشخيص مسير الإخلاء — المستخدم {uid}   الفترة {start} → {end}")
    print("=" * 68)

    with SessionLocal() as s:
        for label, Model in (("أدوية", MedicationRecord), ("مستلزمات", SuppliesRecord)):
            print(f"\n── {label} ──")

            total = s.query(Model).filter(Model.created_by == uid).count()
            print(f"  ١. سجلات أدخلها هذا المستخدم (أي تاريخ، أي مصدر صرف): {total}")
            if total == 0:
                print("     ⛔ لم يُدخل هذا المستخدم أي سجل إطلاقاً — لا شيء ليُطبع.")
                srcs = (
                    s.query(Model.created_by, Model.dispense_source)
                    .filter(Model.created_at >= start_dt, Model.created_at <= end_dt)
                    .all()
                )
                others = {c for c, _ in srcs if c}
                if others:
                    print(f"     ℹ️ لكن مستخدمين آخرين أدخلوا سجلات في نفس الفترة: {sorted(others)}")
                continue

            pharm = s.query(Model).filter(
                Model.created_by == uid,
                Model.dispense_source == _PHARMACY_SOURCE,
            ).count()
            print(f"  ٢. منها مصدر صرفها «{_PHARMACY_SOURCE}»: {pharm}")
            if pharm == 0:
                found = {
                    r[0] for r in s.query(Model.dispense_source)
                    .filter(Model.created_by == uid).distinct().all()
                }
                print(f"     ⛔ لا سجل بمصدر «{_PHARMACY_SOURCE}». المصادر المستخدَمة: {found}")
                print("        مسير الإخلاء يشمل صرف الصيدلية فقط.")
                continue

            in_range = s.query(Model).filter(
                Model.created_by == uid,
                Model.dispense_source == _PHARMACY_SOURCE,
                Model.created_at >= start_dt,
                Model.created_at <= end_dt,
            ).all()
            print(f"  ٣. منها داخل الفترة: {len(in_range)}")
            if not in_range:
                allp = s.query(Model).filter(
                    Model.created_by == uid,
                    Model.dispense_source == _PHARMACY_SOURCE,
                ).all()
                ds = sorted({r.created_at.date() for r in allp if r.created_at})
                print(f"     ⛔ خارج الفترة. تواريخ سجلاته الفعلية: {ds}")
                continue

            stype = "medication" if Model is MedicationRecord else "supplies"
            ids = [r.id for r in in_range]
            fins = s.query(PharmacyFinancialRecord).filter(
                PharmacyFinancialRecord.source_type == stype,
                PharmacyFinancialRecord.source_record_id.in_(ids),
            ).all()
            live = [f for f in fins if not f.is_deleted]
            deleted = len(fins) - len(live)
            have = {f.source_record_id for f in live}
            print(f"  ٤. منها له تقرير مالي غير محذوف: {len(have)}"
                  + (f"   (ومحذوف: {deleted})" if deleted else ""))

            missing = [r for r in in_range if r.id not in have]
            if missing:
                print(f"     ⛔ {len(missing)} سجل صرف بلا تقرير مالي — يُستبعَد من المسير تماماً:")
                for r in missing[:10]:
                    d = r.created_at.date() if r.created_at else "?"
                    print(f"        • {r.patient_name or '—'}  ({d})")
                print("        الحل: أكمل «💰 التقرير المالي» لهذه السجلات.")

            if have:
                types = {}
                for f in live:
                    t = f.manifest_type or "A"
                    types[t] = types.get(t, 0) + 1
                print(f"  ✅ سيظهر في المسير: {len(have)} سجل   توزيع نوع المسير: {types}")
                print("     (لو طبعت بفلتر نوع مختلف عن هذا، ستظهر الشاشة فارغة)")

        # ما يراه الأدمن لنفس الفترة — للمقارنة
        adm = 0
        for Model in (MedicationRecord, SuppliesRecord):
            adm += s.query(Model).filter(
                Model.dispense_source == _PHARMACY_SOURCE,
                Model.created_at >= start_dt,
                Model.created_at <= end_dt,
            ).count()
        print(f"\n── للمقارنة ──\n  سجلات صيدلية لكل المستخدمين في نفس الفترة: {adm}")
        print("  (الأدمن وحده يراها كلها؛ غير الأدمن يرى ما أدخله هو فقط)")
    print("\n" + "=" * 68)


if __name__ == "__main__":
    main()
