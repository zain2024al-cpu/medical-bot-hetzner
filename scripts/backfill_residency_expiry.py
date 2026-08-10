"""
تعبئة `expiry_date` للملفات المُنشأة تلقائياً من الواصلين وهي فارغة.

── السبب ──────────────────────────────────────────────────────────────────────
`create_profiles_from_arrival_batch` كانت تنسخ **انتهاء الإقامة** وحده. والواصل
الجديد غالباً بلا إقامة بعد (يتخطّى الحقل)، فيُنشأ ملفه بـ`expiry_date` فارغ
ويظهر في البوت بـ«📅 تاريخ الانتهاء: —» و«⏳ الأيام المتبقية: —» — بينما
**انتهاء التأشيرة** مُدخَل فعلاً وهو ما يحكم مدة بقائه.

أُصلح المصدر (صار يرجع إلى التأشيرة عند غياب الإقامة)، لكن الإصلاح لا يمسّ
الصفوف المُنشأة قبله — وهذا السكربت لها.

⚠️ لا يمسّ إلا الصفوف التي `expiry_date` فيها **فارغ** ومصدرها `arrivals`
ولها سجل واصل مرتبط بتأشيرة صالحة. أي صف له تاريخ بالفعل لا يُلمس إطلاقاً،
فلا خطر على بيانات صحيحة.

── التشغيل ────────────────────────────────────────────────────────────────────
    venv/bin/python scripts/backfill_residency_expiry.py           # فحص
    venv/bin/python scripts/backfill_residency_expiry.py --apply   # تنفيذ
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal                                     # noqa: E402
from db.models import (                                                 # noqa: E402
    ResidencyProfile, ResidencyCompanion, ArrivalPatient, ArrivalCompanion,
)
from modules.residency.profiles.models import _to_iso_date              # noqa: E402


def main() -> int:
    apply = "--apply" in sys.argv

    fixes: list[tuple] = []       # (kind, id, name, new_date)
    unfixable: list[tuple] = []   # (kind, id, name, reason)

    with SessionLocal() as s:
        profiles = (
            s.query(ResidencyProfile)
            .filter((ResidencyProfile.expiry_date == "")
                    | (ResidencyProfile.expiry_date.is_(None)))
            .all()
        )
        for p in profiles:
            ap = (s.query(ArrivalPatient)
                  .filter(ArrivalPatient.id == p.arrival_patient_id).first()
                  if p.arrival_patient_id else None)
            if ap is None:
                unfixable.append(("مريض", p.id, p.name or "—", "لا سجل واصل مرتبط"))
                continue
            new = _to_iso_date(ap.residence_expiry) or _to_iso_date(ap.visa_expiry)
            if not new:
                unfixable.append(("مريض", p.id, p.name or "—", "لا إقامة ولا تأشيرة"))
                continue
            fixes.append(("مريض", p.id, p.name or "—", new))

        companions = (
            s.query(ResidencyCompanion)
            .filter((ResidencyCompanion.expiry_date == "")
                    | (ResidencyCompanion.expiry_date.is_(None)))
            .all()
        )
        for c in companions:
            ac = (s.query(ArrivalCompanion)
                  .filter(ArrivalCompanion.id == c.arrival_companion_id).first()
                  if c.arrival_companion_id else None)
            if ac is None:
                unfixable.append(("مرافق", c.id, c.name or "—", "لا سجل واصل مرتبط"))
                continue
            new = _to_iso_date(ac.residence_expiry) or _to_iso_date(ac.visa_expiry)
            if not new:
                unfixable.append(("مرافق", c.id, c.name or "—", "لا إقامة ولا تأشيرة"))
                continue
            fixes.append(("مرافق", c.id, c.name or "—", new))

    print("=" * 68)
    print("ملفات إقامة بلا تاريخ انتهاء")
    print("=" * 68)

    print(f"\n✅ قابلة للتعبئة: {len(fixes)}")
    for kind, rid, name, new in fixes:
        print(f"     {kind} #{rid}  {name}  ⇒  {new}")

    print(f"\n⚠️ غير قابلة — تحتاج إدخالاً يدوياً: {len(unfixable)}")
    for kind, rid, name, why in unfixable:
        print(f"     {kind} #{rid}  {name}  ({why})")
    if unfixable:
        print("\n   استخدم زر «📅 تعديل تاريخ الانتهاء» في ملف المريض داخل البوت.")

    if not apply:
        print("\n" + "=" * 68)
        print("وضع الفحص — لم يُغيَّر شيء.")
        print(f"التنفيذ سيملأ {len(fixes)} صفاً ولن يمسّ أي صف له تاريخ بالفعل.")
        print("أعد التشغيل مع --apply للتنفيذ.")
        print("=" * 68)
        return 0

    if not fixes:
        print("\nلا شيء لتنفيذه.")
        return 0

    with SessionLocal() as s:
        for kind, rid, _name, new in fixes:
            model = ResidencyProfile if kind == "مريض" else ResidencyCompanion
            row = s.query(model).filter(model.id == rid).first()
            if row is not None and not (row.expiry_date or ""):
                row.expiry_date = new
        s.commit()

    print("\n" + "=" * 68)
    print(f"✅ عُبِّئ {len(fixes)} صفاً.")
    print(f"لم يُمَسّ: {len(unfixable)} يحتاج إدخالاً يدوياً.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
