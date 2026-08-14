# -*- coding: utf-8 -*-
"""
حذف كامل لكل الأسماء المضافة عبر زر "🤝 مريض جديد مع مرافقين" — بلا
استثناء، بغض النظر عن حالتها (سواء استُخدمت في الوصول أو لا).

يحذف لكل اسم مطابق:
  • صفّ Patient نفسه (المريض الرئيسي patient_type="companion_parent"
    والمرافقون patient_type="companion").
  • كل ResidencyProfile مرتبط بالاسم (source="companion_flow" الذي
    يُنشأ فور الإضافة، وأيضاً أي source="arrivals" بنفس الاسم إن كان
    الاسم قد أُكمل لاحقاً عبر "🛬 الوصول") + كل ResidencyCompanion و
    ResidencyUpdate التابعة له.
  • كل ArrivalPatient/ArrivalCompanion بنفس الاسم (سجلات الوصول
    المرتبطة إن وُجدت).

⚠️ أمان:
  • الوضع الافتراضي **معاينة فقط** (لا يحذف شيئاً). للتنفيذ الفعلي
    أضف --apply.
  • المطابقة بالاسم الحرفي الكامل (بعد إزالة المسافات الزائدة) — لا
    تُطابق أسماء المرضى العاديين (patient_type=None) إطلاقاً.
  • حذف نهائي بلا نسخة احتياطية (بطلب صريح من المستخدم) — تأكد قبل
    --apply.

الاستخدام على الخادم:
    python scripts/delete_companion_flow_names.py            # معاينة
    python scripts/delete_companion_flow_names.py --apply    # تنفيذ
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    apply_changes = "--apply" in sys.argv

    from db.session import SessionLocal
    from db.models import (
        Patient, ResidencyProfile, ResidencyCompanion, ResidencyUpdate,
        ArrivalPatient, ArrivalCompanion,
    )

    with SessionLocal() as s:
        patients = (
            s.query(Patient)
            .filter(Patient.patient_type.in_(["companion_parent", "companion"]))
            .all()
        )

        if not patients:
            print("لا توجد أسماء مضافة عبر \"🤝 مريض جديد مع مرافقين\" — لا شيء للحذف.")
            return 0

        names = sorted({(p.full_name or "").strip() for p in patients if (p.full_name or "").strip()})
        patient_ids = [p.id for p in patients]

        profiles = (
            s.query(ResidencyProfile)
            .filter(ResidencyProfile.name.in_(names))
            .all()
        )
        profile_ids = [pr.id for pr in profiles]

        companions_by_profile = (
            s.query(ResidencyCompanion)
            .filter(ResidencyCompanion.profile_id.in_(profile_ids))
            .all() if profile_ids else []
        )
        updates_by_profile = (
            s.query(ResidencyUpdate)
            .filter(ResidencyUpdate.profile_id.in_(profile_ids))
            .all() if profile_ids else []
        )

        arrival_patients = (
            s.query(ArrivalPatient)
            .filter(ArrivalPatient.name.in_(names))
            .all()
        )
        arrival_patient_ids = [ap.id for ap in arrival_patients]
        arrival_companions_by_patient = (
            s.query(ArrivalCompanion)
            .filter(ArrivalCompanion.patient_id.in_(arrival_patient_ids))
            .all() if arrival_patient_ids else []
        )
        arrival_companions_by_name = (
            s.query(ArrivalCompanion)
            .filter(ArrivalCompanion.name.in_(names))
            .all()
        )
        # دمج بلا تكرار (بحسب id)
        arrival_companions = {
            ac.id: ac for ac in (arrival_companions_by_patient + arrival_companions_by_name)
        }.values()

        print("=" * 70)
        print(f"أسماء المرضى/المرافقين المطابقة ({len(patients)}):")
        for p in patients:
            kind = "مريض رئيسي" if p.patient_type == "companion_parent" else "مرافق"
            print(f"  • {p.full_name!r}  (id={p.id}, {kind})")
        print()
        print(f"ملفات إقامة مرتبطة (ResidencyProfile): {len(profiles)}")
        for pr in profiles:
            print(f"  • {pr.name!r}  (id={pr.id}, source={pr.source!r}, status={pr.status!r})")
        print(f"  ↳ مرافقو الإقامة (ResidencyCompanion) التابعون لها: {len(companions_by_profile)}")
        print(f"  ↳ سجلات تتبّع (ResidencyUpdate) التابعة لها: {len(updates_by_profile)}")
        print()
        print(f"سجلات وصول مرتبطة (ArrivalPatient): {len(arrival_patients)}")
        for ap in arrival_patients:
            print(f"  • {ap.name!r}  (id={ap.id})")
        print(f"  ↳ مرافقو الوصول (ArrivalCompanion) المرتبطون: {len(arrival_companions)}")
        print("=" * 70)

        if not apply_changes:
            print("🔍 معاينة فقط — لم يُحذف شيء.")
            print("   للتنفيذ: python scripts/delete_companion_flow_names.py --apply")
            return 0

        for u in updates_by_profile:
            s.delete(u)
        for rc in companions_by_profile:
            s.delete(rc)
        for pr in profiles:
            s.delete(pr)
        for ac in arrival_companions:
            s.delete(ac)
        for ap in arrival_patients:
            s.delete(ap)
        for p in patients:
            s.delete(p)

        s.commit()

        print(
            f"🗑️ تم حذف {len(patients)} اسم مريض/مرافق، "
            f"{len(profiles)} ملف إقامة (+{len(companions_by_profile)} مرافق إقامة، "
            f"+{len(updates_by_profile)} سجل تتبّع)، "
            f"{len(arrival_patients)} سجل وصول (+{len(arrival_companions)} مرافق وصول)."
        )
        print("   أعد تشغيل البوت: pm2 restart all")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
