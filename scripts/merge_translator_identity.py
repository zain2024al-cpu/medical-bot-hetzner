# scripts/merge_translator_identity.py
# 🔀 غلاف سطر أوامر على `services/translator_merge_service.py`.
#
# ⚠️ **المنطق ليس هنا**: الدمج نفسه في الخدمة، ويستدعيه أيضاً زر الأدمن
# في البوت (إدارة المترجمين ⇐ «🔁 مترجم غيّر حسابه»). نسختان من العملية
# كانتا ستتباعدان. هذا الملف يعرض ويسأل ويطبع، لا أكثر.
#
# يبقى مفيداً رغم وجود الزر: يعمل والبوت متوقّف، ويطبع تفصيلاً أوسع مما
# تحتمله رسالة تليجرام، ويصلح لحالة لا يصل إليها الأدمن من الشاشة.
#
# الاستعمال على الخادم:
#   venv/bin/python scripts/merge_translator_identity.py 8310133494 8932896483
#   venv/bin/python scripts/merge_translator_identity.py 8310133494 8932896483 --apply

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from services.translator_merge_service import (  # noqa: E402
    merge, preview, resolve_name,
)

LINE = "─" * 64


def print_preview(s: dict) -> int:
    old, new = s["old"], s["new"]
    print(LINE)
    print(f"  معاينة الدمج:  {old}  ←  {new}")
    print(LINE)

    print("\n📇 دليل المترجمين (translators):")
    for label, row, tid in (("القديم", s["dir_old"], old), ("الجديد", s["dir_new"], new)):
        print(f"   {label} {tid}: " + (f"«{row['name']}»" if row else "— لا صفّ —"))

    print("\n👤 حساب المستخدم (users):")
    for label, row, tid in (("القديم", s["user_old"], old), ("الجديد", s["user_new"], new)):
        if row:
            print(f"   {label} {tid}: id={row['id']}  "
                  f"«{row['full_name'] or row['first_name'] or '—'}»  "
                  f"معتمد={row['is_approved']}  نشط={row['is_active']}  مجمَّد={row['is_suspended']}")
        else:
            print(f"   {label} {tid}: — لا صفّ —")

    print("\n🔑 صلاحيات الوحدات (user_module_access):")
    if not s["has_modules"]:
        print("   — الجدول غير موجود في القاعدة —")
    else:
        print(f"   القديم: {', '.join(s['mod_old']) or '—'}")
        print(f"   الجديد: {', '.join(s['mod_new']) or '—'}")
        missing = [m for m in s["mod_old"] if m not in s["mod_new"]]
        if missing:
            print(f"   ↪ ستُنسَخ إلى الجديد: {', '.join(missing)}")

    print("\n📊 الصفوف:")
    for t, (o, n) in s["tables"].items():
        print(f"   {'➡' if o else ' '} {t:26s} القديم={o:<6d} الجديد={n}")
    if s["has_submitted"]:
        print(f"\n   📄 reports.submitted_by_user_id: "
              f"القديم={s['submitted_old']}  الجديد={s['submitted_new']}")

    # ⚠️ الانحراف يُعلَن ولا يُبتلَع: جدول متخطّىً يعني تاريخاً باقياً تحت
    # الآيدي القديم، وإخفاؤه يجعل الدمج يبدو تامّاً وهو ليس كذلك.
    if s["skipped"]:
        print("\n⚠️ جداول متخطّاة (انحراف القاعدة عن النموذج):")
        for t, why in s["skipped"]:
            print(f"   ⊘ {t:26s} {why}")
        print("   ▸ عالِجها بـ scripts/audit_schema.py ثم db/maintenance.py")

    print(f"\n   ▸ إجمالي ما سيُنقَل: {s['total']} صفّاً")
    return s["total"]


def main() -> int:
    ap = argparse.ArgumentParser(description="دمج هويّة مترجم من آيدي قديم إلى جديد")
    ap.add_argument("old_id", type=int)
    ap.add_argument("new_id", type=int)
    ap.add_argument("--name", default=None, help="الاسم النهائي (افتراضياً اسم الصفّ القديم)")
    ap.add_argument("--apply", action="store_true", help="التنفيذ الفعلي (بدونه معاينة فقط)")
    ap.add_argument("--keep-old-user", action="store_true",
                    help="إبقاء حساب الآيدي القديم معتمداً ونشطاً")
    a = ap.parse_args()

    if a.old_id == a.new_id:
        print("❌ الآيديان متطابقان — لا شيء للدمج.")
        return 2

    s = preview(a.old_id, a.new_id)
    total = print_preview(s)

    name = resolve_name(s, a.name)
    if not name:
        print("\n❌ لا اسم في الدليل لأيٍّ من الآيديين — مرّر --name صراحةً.")
        return 2
    print(f"\n🔤 الاسم النهائي بعد الدمج: «{name}»")

    if not a.apply:
        print(f"\n{LINE}\n  معاينة فقط — لم يتغيّر شيء.")
        print(f"  للتنفيذ: أعد الأمر نفسه مضافاً إليه --apply\n{LINE}")
        return 0

    if total == 0 and not s["dir_old"]:
        print("\n✅ لا شيء تحت الآيدي القديم — الدمج غير لازم.")
        return 0

    print(f"\n{LINE}\n  التنفيذ…\n{LINE}")
    try:
        res = merge(a.old_id, a.new_id, name, keep_old_user=a.keep_old_user)
    except Exception as exc:
        print(f"\n❌ فشل الدمج — تراجعت القاعدة كاملةً، ولم يتغيّر شيء.\n   {exc}")
        return 1

    if res["backup"]:
        print(f"💾 نسخة احتياطية: {res['backup']}")
    for t, n in res["moved"].items():
        print(f"   ➡ {t}: {n}")
    for mk in res["granted"]:
        print(f"   🔑 صلاحية منقولة: {mk}")
    if res["dir_deleted"]:
        print(f"   🗑 حُذف صفّ الدليل القديم {a.old_id}")
    if res["user_disabled"]:
        print(f"   🚫 عُطِّل الحساب القديم {a.old_id}")

    print(f"\n{LINE}\n  ✅ تمّ. التحقّق بعد الدمج:\n{LINE}")
    print_preview(preview(a.old_id, a.new_id))
    return 0


if __name__ == "__main__":
    sys.exit(main())
