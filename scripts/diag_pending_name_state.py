# -*- coding: utf-8 -*-
"""
تشخيص للاسم الذي يظهر معلَّقاً في "🛬 الوصول" و"📋 الملفات المعلّقة"
(الإقامة) في آنٍ واحد — يعرض كل صفوف Patient/ResidencyProfile/
ResidencyCompanion المطابقة للاسم، بلا أي تعديل (قراءة فقط بالكامل).

الاستخدام على الخادم:
    python scripts/diag_pending_name_state.py "اسم المريض هنا"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    if len(sys.argv) < 2:
        print("الاستخدام: python scripts/diag_pending_name_state.py \"اسم المريض\"")
        return 1
    name = sys.argv[1].strip()

    from db.session import SessionLocal
    from db.models import Patient, ResidencyProfile, ResidencyCompanion

    with SessionLocal() as s:
        print("=" * 70)
        print(f"البحث عن: {name!r}")
        print("=" * 70)

        patients = s.query(Patient).filter(Patient.full_name == name).all()
        print(f"\nصفوف Patient مطابقة تماماً ({len(patients)}):")
        for p in patients:
            print(
                f"  id={p.id}  patient_type={p.patient_type!r}  "
                f"pending_arrival={p.pending_arrival!r}  "
                f"companion_of_id={p.companion_of_id!r}  "
                f"created_at={p.created_at}"
            )

        profiles = s.query(ResidencyProfile).filter(ResidencyProfile.name == name).all()
        print(f"\nصفوف ResidencyProfile مطابقة تماماً ({len(profiles)}):")
        for pr in profiles:
            print(
                f"  id={pr.id}  source={pr.source!r}  status={pr.status!r}  "
                f"arrival_patient_id={pr.arrival_patient_id!r}  "
                f"created_by={pr.created_by!r}  created_at={pr.created_at}"
            )
            comps = s.query(ResidencyCompanion).filter(ResidencyCompanion.profile_id == pr.id).all()
            for c in comps:
                print(f"    └ companion id={c.id}  name={c.name!r}  status={c.status!r}")

        still_pending = any(p.pending_arrival for p in patients)

        print("\n" + "=" * 70)
        if still_pending and profiles:
            print("⚠️ تعارض حقيقي: الاسم لا يزال pending_arrival=True (معلّق في الوصول)")
            print("   بينما يوجد له ملف إقامة بالفعل — هذا هو الخلل المُبلَّغ عنه.")
            print("   انظر created_at/source أعلاه لتحديد متى وكيف أُنشئ الملف:")
            print("   • source='companion_flow' ⇒ صفّ قديم من قبل الإصلاح (٣٣) — احذفه يدوياً.")
            print("   • source='arrivals' ⇒ تم تأكيد الوصول فعلياً لكن pending_arrival لم يُمسح (خلل مختلف).")
            print("   • source='manual' ⇒ أُضيف يدوياً من شاشة الإقامة مباشرة (طريق منفصل تماماً).")
        elif patients and profiles and not still_pending:
            print("✅ حالة طبيعية: تم تأكيد الوصول فعلياً (pending_arrival=False)،")
            print("   فوجود الاسم في الطرفين متوقَّع وصحيح — لا خلل هنا.")
        elif patients and not profiles:
            print("✅ الحالة سليمة: الاسم معلّق في الوصول فقط، بلا أي ملف إقامة.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
