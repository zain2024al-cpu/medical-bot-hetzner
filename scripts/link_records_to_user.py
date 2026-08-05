# -*- coding: utf-8 -*-
"""ربط السجلات المحفوظة باسم شخص معيّن بمعرّف تليجرام الخاص به.

    # ١. اكتشاف فقط (لا يعدّل شيئاً) — ابدأ دائماً بهذا:
    venv/bin/python scripts/link_records_to_user.py --name "مبروك"

    # ٢. معاينة التغيير على جدول محدَّد (لا يعدّل شيئاً):
    venv/bin/python scripts/link_records_to_user.py --name "مبروك" --id 7377506883

    # ٣. التنفيذ الفعلي (بعد أخذ نسخة احتياطية):
    venv/bin/python scripts/link_records_to_user.py --name "مبروك" --id 7377506883 --apply

⚠️ **لا يُعدّل شيئاً بلا `--apply`.** خُذ نسخة احتياطية من قاعدة البيانات قبل
التنفيذ — لا تراجع تلقائياً عن هذه العملية.

⚠️ **`specialist_name` لا يُلمَس إطلاقاً.** في سجلات الرعاية الصحية
(أدوية/مستلزمات/جروح/متابعة) هناك حقلان مختلفان تماماً:
    • `specialist_name` = الطبيب الذي **يخصّه** السجل
    • `created_by`      = المستخدم الذي **أدخل** السجل
نقل الملكية بناءً على `specialist_name` ينسب لشخصٍ سجلاتٍ لم يُدخلها،
ويكسر عزل المسير بدل إصلاحه. الاسم يُطابَق فقط حيث يقابله معرّف مالك صريح.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db import models as M

# (الموديل, عمود الاسم, عمود المعرّف) — أزواج «اسم المالك ↔ معرّف المالك» فقط.
_PAIRS = [
    (M.Report,                 "translator_name",  "translator_id"),
    (M.PendingReport,          "translator_name",  "translator_id"),
    (M.Followup,               "translator_name",  "translator_id"),
    (M.DailyPatient,           "translator_name",  "translator_id"),
    (M.DailyReportTracking,    "translator_name",  "translator_id"),
    (M.TreatmentPlan,          "created_by_name",  "created_by"),
]

# جداول فيها الاسم لكن **بلا** معنى ملكية — تُعرَض للعلم ولا تُعدَّل أبداً.
_NAME_ONLY = [
    (M.MedicationRecord,       "specialist_name"),
    (M.SuppliesRecord,         "specialist_name"),
    (M.WoundRecord,            "specialist_name"),
    (M.MedicalFollowupRecord,  "specialist_name"),
    (M.OtherHealthcareRecord,  "specialist_name"),
]


def _safe(pairs):
    """يتجاهل أي موديل/عمود غير موجود في هذه النسخة من المخطط."""
    out = []
    for entry in pairs:
        model = entry[0]
        cols = {c.name for c in model.__table__.columns}
        if all(c in cols for c in entry[1:]):
            out.append(entry)
    return out


def main() -> None:
    p = argparse.ArgumentParser(add_help=True)
    p.add_argument("--name", required=True, help="جزء من الاسم كما هو مخزَّن (بحث LIKE)")
    p.add_argument("--id", type=int, default=None, help="معرّف تليجرام الهدف")
    p.add_argument("--apply", action="store_true", help="نفِّذ فعلياً (بدونه معاينة فقط)")
    a = p.parse_args()

    like = f"%{a.name}%"
    print("=" * 70)
    print(f"البحث عن اسم يحتوي: {a.name!r}"
          + (f"   ← الهدف: {a.id}" if a.id else "   (اكتشاف فقط)"))
    print("=" * 70)

    total_changed = 0
    with SessionLocal() as s:
        print("\n── جداول قابلة للربط (اسم مالك + معرّف مالك) ──")
        found_any = False
        for model, name_col, id_col in _safe(_PAIRS):
            NC, IC = getattr(model, name_col), getattr(model, id_col)
            rows = s.query(model).filter(NC.isnot(None), NC.like(like)).all()
            if not rows:
                continue
            found_any = True
            names = sorted({getattr(r, name_col) for r in rows})
            by_id = {}
            for r in rows:
                by_id[getattr(r, id_col)] = by_id.get(getattr(r, id_col), 0) + 1
            print(f"\n  {model.__tablename__}  ({len(rows)} صف)")
            print(f"     الأسماء المطابقة : {names}")
            print(f"     المعرّف الحالي    : {by_id}")

            if a.id is None:
                continue
            need = [r for r in rows if getattr(r, id_col) != a.id]
            print(f"     سيتغيّر           : {len(need)} صف"
                  + (" (الباقي مربوط سلفاً)" if len(need) != len(rows) else ""))
            if a.apply and need:
                for r in need:
                    setattr(r, id_col, a.id)
                total_changed += len(need)
            elif need:
                for r in need[:5]:
                    who = getattr(r, "patient_name", None) or f"id={r.id}"
                    print(f"        • {who}   {getattr(r, id_col)} → {a.id}")
                if len(need) > 5:
                    print(f"        … و{len(need) - 5} غيرها")

        if not found_any:
            print("  لا شيء. جرّب جزءاً أقصر من الاسم — قد يكون مخزَّناً بصيغة مختلفة.")

        print("\n── للعلم فقط: الاسم يظهر هنا لكنه ليس مالكاً (لن يُلمَس) ──")
        for model, name_col in _safe(_NAME_ONLY):
            NC = getattr(model, name_col)
            n = s.query(model).filter(NC.isnot(None), NC.like(like)).count()
            if n:
                print(f"  {model.__tablename__}.{name_col}: {n} صف"
                      f"  — الطبيب المعنيّ بالسجل، لا مُدخِله (created_by)")

        if a.apply and total_changed:
            s.commit()
            print(f"\n✅ تم التنفيذ: {total_changed} صف رُبطت بالمعرّف {a.id}")
        elif a.apply:
            print("\n✅ لا شيء يحتاج تغييراً — كله مربوط سلفاً.")
        elif a.id is not None:
            print(f"\n🔎 معاينة فقط — لم يُعدَّل شيء. أضف --apply للتنفيذ.")
    print("=" * 70)


if __name__ == "__main__":
    main()
