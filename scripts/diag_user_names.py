#!/usr/bin/env python3
"""
تشخيص ازدواج أسماء المستخدمين — قراءة فقط، لا يُعدّل شيئاً.

── لماذا يوجد اسمان لكل شخص أصلاً ──────────────────────────────────────────────
الاسم في هذا النظام يأتي من **ثلاثة** مخازن، لا اثنين:

  1. `users.full_name`      — يُلتقط تلقائياً من بروفايل تيليجرام لحظة /start.
                              خارج سيطرتنا: قد يكون حرفاً واحداً أو لقباً أو
                              رموزاً، ويتغيّر متى غيّره صاحبه في تيليجرام.
  2. `translators.name`     — يكتبه الأدمن يدوياً عند الموافقة على المستخدم.
                              هذا هو **الاسم المعتمَد**: هو ما يظهر في قائمة
                              المترجمين عند إنشاء تقرير، وفي بطاقة التقرير.
  3. ملف نصّي للأسماء       — نسخة احتياطية تُقرأ فقط إن كان جدول الدليل فارغاً.

فوجود اسمين لشخص واحد **ليس خللاً بحدّ ذاته** — إنه تصميم مقصود: الأول يُعرّف
الحساب، والثاني يُعرّف الشخص. شاشة "تفاصيل المستخدم" تعرضهما معاً عمداً حين
يختلفان ليعرف الأدمن لمن يعود الحساب ذو الاسم الفوضوي.

**الخلل الحقيقي** هو أحد هذه فقط، وهذا ما يكشفه السكربت:
  • شخص واحد له **صفّان** في دليل المترجمين (اسم مختصر + اسم كامل مثلاً) —
    حدث فعلاً سابقاً مع "يحيى"/"يحيى أبو حمزة" و"ياسر"/"ياسر ابو عمار".
  • اسم مكرَّر حرفياً في الدليل بمعرّفَين مختلفَين.
  • صف دليل بلا مستخدم مقابل (اسم يظهر في القوائم لكن صاحبه غير مسجَّل).
  • مستخدم معتمَد بلا صف دليل (لن يظهر اسمه عند إنشاء تقرير).

── التشغيل ────────────────────────────────────────────────────────────────────
    venv/bin/python scripts/diag_user_names.py
"""

from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func                  # noqa: E402

from db.session import SessionLocal          # noqa: E402
from db.models import User, TranslatorDirectory, Report  # noqa: E402


def _norm(s) -> str:
    """تطبيع للمقارنة فقط: تُزال المسافات الزائدة وتوحَّد الألف والتاء المربوطة."""
    t = (s or "").strip()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        t = t.replace(a, b)
    return " ".join(t.split())


def main() -> int:
    with SessionLocal() as s:
        users = s.query(User).all()
        dirs = s.query(TranslatorDirectory).all()

    print("=" * 66)
    print("تشخيص أسماء المستخدمين")
    print("=" * 66)
    print(f"users (الحسابات)        : {len(users)}")
    print(f"translators (الدليل)    : {len(dirs)}")

    dir_by_id = {d.translator_id: (d.name or "").strip() for d in dirs}
    user_ids = {u.tg_user_id for u in users if u.tg_user_id}

    # ── 1) اسمان مختلفان لنفس الشخص (طبيعي غالباً — للاطّلاع) ────────────────
    diff = []
    for u in users:
        dn = dir_by_id.get(u.tg_user_id)
        if dn and _norm(dn) != _norm(u.full_name):
            diff.append((u.tg_user_id, (u.full_name or "").strip(), dn))
    print(f"\n① اسمان مختلفان لنفس الشخص: {len(diff)}")
    print("   (طبيعي: الأول من بروفايل تيليجرام، الثاني اعتمده الأدمن)")
    for tg, fn, dn in diff[:15]:
        print(f"     tg={tg}")
        print(f"        تيليجرام : {fn!r}")
        print(f"        المعتمَد  : {dn!r}")

    # ── 2) 🔴 اسم مكرَّر حرفياً في الدليل ──────────────────────────────────────
    c = Counter(_norm(d.name) for d in dirs if (d.name or "").strip())
    dup_exact = {k: v for k, v in c.items() if v > 1}
    print(f"\n② 🔴 اسم مكرَّر في الدليل: {len(dup_exact)}")
    for name, n in dup_exact.items():
        ids = [d.translator_id for d in dirs if _norm(d.name) == name]
        print(f"     {name!r} ×{n}  المعرّفات: {ids}")

    # ── 3) 🔴 اسم مختصر داخل اسم أطول (نفس الشخص بصفّين) ──────────────────────
    names = [(d.translator_id, (d.name or "").strip()) for d in dirs if (d.name or "").strip()]
    contained = []
    for i, (id_a, a) in enumerate(names):
        for id_b, b in names:
            if id_a == id_b or len(_norm(a)) >= len(_norm(b)):
                continue
            if _norm(b).startswith(_norm(a) + " "):
                contained.append((id_a, a, id_b, b))
    print(f"\n③ 🔴 اسم مختصر يبدأ به اسم أطول (اشتباه نفس الشخص): {len(contained)}")
    for id_a, a, id_b, b in contained:
        print(f"     {a!r} (tg={id_a})   ⊂   {b!r} (tg={id_b})")

    # ── 4) 🔴 صف دليل بلا حساب مستخدم ─────────────────────────────────────────
    orphan_dirs = [(d.translator_id, d.name) for d in dirs if d.translator_id not in user_ids]
    print(f"\n④ 🔴 اسم في الدليل بلا حساب مستخدم: {len(orphan_dirs)}")
    for tg, nm in orphan_dirs[:15]:
        print(f"     tg={tg}  {nm!r}")

    # ── 5) 🟡 مستخدم معتمَد بلا صف دليل ───────────────────────────────────────
    missing = [
        (u.tg_user_id, (u.full_name or "").strip())
        for u in users
        if getattr(u, "is_approved", False) and u.tg_user_id and u.tg_user_id not in dir_by_id
    ]
    print(f"\n⑤ 🟡 مستخدم معتمَد بلا اسم في الدليل: {len(missing)}")
    print("   (لن يظهر اسمه في قائمة المترجمين عند إنشاء تقرير)")
    for tg, nm in missing[:15]:
        print(f"     tg={tg}  {nm!r}")

    # ── 6) كل مستخدم معتمَد: الاسم المعروض + آيدي تيليجرام + عدد تقاريره ──────
    # ⚠️ لا يكشف السكربت تكراراً بين اسمين بلغتين مختلفتين تلقائياً (مثال
    # حقيقي: "ادريس" في الدليل مقابل "Edress" الخام لنفس الشخص بآيديين
    # مختلفين) — الأشكال متباعدة نصّياً ولا رابط برمجي بينهما. هذا الجدول
    # هو الأداة البديلة: يعرض كل اسم بجانب آيديه الحقيقي وعدد تقاريره،
    # فيسهل على الأدمن (الذي يعرف الأشخاص فعلياً) اكتشاف الزوج بصرياً
    # وتقرير أيّهما يُبقيه استناداً لعدد التقارير (الأكثر نشاطاً غالباً
    # هو الحساب الصحيح الذي يجب الإبقاء عليه).
    with SessionLocal() as s:
        report_counts = dict(
            s.query(Report.translator_id, func.count(Report.id))
            .group_by(Report.translator_id)
            .all()
        )
    approved = sorted(
        (u for u in users if getattr(u, "is_approved", False) and u.tg_user_id),
        key=lambda u: _norm(dir_by_id.get(u.tg_user_id) or u.full_name or ""),
    )
    print(f"\n⑥ كل المستخدمين المعتمَدين ({len(approved)}) — بالاسم والآيدي وعدد التقارير:")
    print(f"   {'الاسم المعروض':22} {'آيدي تيليجرام':14} {'تقارير':7} {'(الاسم الخام لو اختلف)'}")
    for u in approved:
        dn = dir_by_id.get(u.tg_user_id)
        raw = (u.full_name or "").strip()
        shown = dn or raw
        cnt = report_counts.get(u.tg_user_id, 0)
        note = f"(خام: {raw!r})" if dn and _norm(dn) != _norm(raw) else ""
        print(f"   {shown:22} {u.tg_user_id!s:14} {cnt:<7} {note}")

    problems = len(dup_exact) + len(contained) + len(orphan_dirs)
    print("\n" + "=" * 66)
    if problems == 0 and not missing:
        print("✅ لا ازدواج فعلي — الاسمان المختلفان لنفس الشخص تصميم مقصود.")
    else:
        print(f"⚠️ مشاكل تستحق المعالجة: {problems} 🔴 + {len(missing)} 🟡")
        print("   أرسل هذا المخرَج وسنقرّر أيّها يُدمَج وأيّها يُحذف.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
