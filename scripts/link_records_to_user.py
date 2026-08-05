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

from sqlalchemy import text

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
    """
    يُبقي الجداول الموجودة فعلاً **في قاعدة البيانات** بكل الأعمدة المطلوبة.

    ⚠️ الفحص على القاعدة الحيّة لا على الموديل عمداً: الموديل يعرّف أعمدة قد
    لا تكون موجودة في قاعدة قديمة لم تُرحَّل (مثال واقعي:
    `daily_patients.translator_id` معرَّف في models.py وغير موجود في قاعدة
    السيرفر). الفحص على `__table__.columns` يمرّ بنجاح ثم ينهار الاستعلام
    بـ`no such column`، ولا يظهر ذلك محلياً إطلاقاً لأن القاعدة المحلية
    تُبنى من الموديل فتكون مطابقة له دائماً.
    """
    from sqlalchemy import inspect as sa_inspect
    from db.session import engine

    insp = sa_inspect(engine)
    try:
        tables = set(insp.get_table_names())
    except Exception:
        tables = set()

    out = []
    for entry in pairs:
        model = entry[0]
        table = model.__tablename__
        if table not in tables:
            continue
        try:
            db_cols = {c["name"] for c in insp.get_columns(table)}
        except Exception:
            continue
        missing = [c for c in entry[1:] if c not in db_cols]
        if missing:
            print(f"  ⏭️ تخطّي {table}: أعمدة غير موجودة في القاعدة {missing}")
            continue
        out.append((*entry, db_cols))
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
        for model, name_col, id_col, db_cols in _safe(_PAIRS):
            NC, IC = getattr(model, name_col), getattr(model, id_col)

            # ⚠️ تُنتقى الأعمدة صراحةً بدل s.query(model): استعلام الموديل
            # الكامل يختار **كل** أعمدته، فيكفي عمود واحد معرَّف في models.py
            # وغائب عن قاعدة قديمة ليُسقط الاستعلام كله بـ`no such column` —
            # حتى لو كانت الأعمدة التي نحتاجها فعلاً موجودة. الانتقاء يجعل
            # السكربت محصَّناً ضد أي انحراف في بقية الأعمدة.
            label_col = getattr(model, "patient_name", None) if "patient_name" in db_cols else None
            sel = [model.id, NC, IC] + ([label_col] if label_col is not None else [])
            rows = s.query(*sel).filter(NC.isnot(None), NC.like(like)).all()
            if not rows:
                continue
            found_any = True
            names = sorted({r[1] for r in rows})
            by_id = {}
            for r in rows:
                by_id[r[2]] = by_id.get(r[2], 0) + 1
            print(f"\n  {model.__tablename__}  ({len(rows)} صف)")
            print(f"     الأسماء المطابقة : {names}")
            print(f"     المعرّف الحالي    : {by_id}")

            if a.id is None:
                continue
            need = [r for r in rows if r[2] != a.id]
            print(f"     سيتغيّر           : {len(need)} صف"
                  + (" (الباقي مربوط سلفاً)" if len(need) != len(rows) else ""))
            if a.apply and need:
                # ⚠️ SQL صريح لا Query.update(): الأخير يضيف تلقائياً أعمدة
                # onupdate المعرَّفة في الموديل (مثل updated_at)، فينهار على
                # قاعدة تنقصها. أسماء الجدول والأعمدة من ثوابت هذا الملف لا
                # من مدخلات المستخدم، والقيم مربوطة كمعاملات.
                #
                # `IS NULL` مذكورة صراحةً: `!= :tgt` وحدها لا تطابق NULL في
                # SQL، فكانت الصفوف بلا مالك — وهي جوهر المشكلة — ستُترك.
                res = s.execute(text(
                    f"UPDATE {model.__tablename__} SET {id_col} = :tgt "
                    f"WHERE {name_col} LIKE :like "
                    f"  AND ({id_col} IS NULL OR {id_col} != :tgt)"
                ), {"tgt": a.id, "like": like})
                total_changed += res.rowcount or 0
            elif need:
                for r in need[:5]:
                    who = (r[3] if label_col is not None else None) or f"id={r[0]}"
                    print(f"        • {who}   {r[2]} → {a.id}")
                if len(need) > 5:
                    print(f"        … و{len(need) - 5} غيرها")

        if not found_any:
            print("  لا شيء. جرّب جزءاً أقصر من الاسم — قد يكون مخزَّناً بصيغة مختلفة.")

        print("\n── للعلم فقط: الاسم يظهر هنا لكنه ليس مالكاً (لن يُلمَس) ──")
        for model, name_col, _cols in _safe(_NAME_ONLY):
            NC = getattr(model, name_col)
            # model.id لا s.query(model) — نفس سبب الانتقاء أعلاه
            n = s.query(model.id).filter(NC.isnot(None), NC.like(like)).count()
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
