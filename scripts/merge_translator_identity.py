# scripts/merge_translator_identity.py
# 🔀 دمج هويّة مترجم غيّر حسابه في تليجرام: كل ما كان تحت آيديه القديم
# ينتقل إلى الجديد، فيبقى تاريخه واحداً ويختفي اسمه المكرر.
#
# ⚠️ **لماذا سكربت لا زر في البوت**: هذه جراحة بيانات تمسّ عدة جداول
# دفعةً واحدة ولا تُراجَع بعد وقوعها. تُشغَّل بالمعاينة أولاً، وتُنفَّذ
# مرة واحدة بنسخة احتياطية قبلها.
#
# ⚠️ **الآيدي مفتاح ربط بلا مفاتيح أجنبية**: لا شيء في القاعدة يمنع بقاء
# صفوف يتيمة تشير إلى آيدي محذوف. فالترتيب مقصود: تُنقَل البيانات أولاً
# ويُحذف صفّ الدليل القديم آخراً، وكل ذلك في معاملة واحدة — الدمج
# الجزئي أسوأ من عدمه، لأنه يقسّم التاريخ بلا أثر ظاهر.
#
# الاستعمال على الخادم:
#   venv/bin/python scripts/merge_translator_identity.py 8310133494 8932896483
#   venv/bin/python scripts/merge_translator_identity.py 8310133494 8932896483 --apply

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sqlalchemy import text  # noqa: E402

from db.models import Base  # noqa: E402
from db.session import DATABASE_PATH, engine  # noqa: E402

LINE = "─" * 64
_EMPTY = "''"


def data_tables() -> list[str]:
    """الجداول التي تحمل هويّة المترجم في بياناتها.

    تُشتقّ من نموذج القاعدة لا من قائمة مكتوبة يدوياً: أي جدول جديد يحمل
    الحقلين يدخل الدمج تلقائياً، فلا يبقى تاريخ خارج النقل لأن أحداً نسي
    تحديث قائمة في سكربت. `translators` نفسه خارج القائمة — لا يحمل
    `translator_name`، ويُعالَج على حدة لأن الآيدي فيه مفتاح أساسي.
    """
    out = []
    for t in Base.metadata.sorted_tables:
        cols = {c.name for c in t.columns}
        if {"translator_id", "translator_name"} <= cols:
            out.append(t.name)
    return sorted(out)


def _scalar(conn, sql, **p):
    return conn.execute(text(sql), p).scalar() or 0


def survey(conn, old: int, new: int) -> dict:
    rows = {}
    for t in data_tables():
        rows[t] = (
            _scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE translator_id = :i", i=old),
            _scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE translator_id = :i", i=new),
        )

    def dir_row(i):
        r = conn.execute(text("SELECT translator_id, name FROM translators "
                              "WHERE translator_id = :i"), {"i": i}).first()
        return {"translator_id": r[0], "name": r[1]} if r else None

    def user_row(i):
        r = conn.execute(text(
            "SELECT id, full_name, first_name, is_approved, is_active, is_suspended "
            "FROM users WHERE tg_user_id = :i"), {"i": i}).first()
        if not r:
            return None
        return {"id": r[0], "full_name": r[1], "first_name": r[2],
                "is_approved": r[3], "is_active": r[4], "is_suspended": r[5]}

    def modules(i):
        return [x[0] for x in conn.execute(text(
            "SELECT module_key FROM user_module_access "
            "WHERE tg_user_id = :i AND is_active = 1"), {"i": i}).fetchall()]

    return {
        "tables": rows,
        "dir_old": dir_row(old), "dir_new": dir_row(new),
        "user_old": user_row(old), "user_new": user_row(new),
        "mod_old": modules(old), "mod_new": modules(new),
        "submitted_old": _scalar(
            conn, "SELECT COUNT(*) FROM reports WHERE submitted_by_user_id = :i", i=old),
        "submitted_new": _scalar(
            conn, "SELECT COUNT(*) FROM reports WHERE submitted_by_user_id = :i", i=new),
    }


def print_survey(s: dict, old: int, new: int) -> int:
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
    print(f"   القديم: {', '.join(s['mod_old']) or '—'}")
    print(f"   الجديد: {', '.join(s['mod_new']) or '—'}")
    missing = [m for m in s["mod_old"] if m not in s["mod_new"]]
    if missing:
        print(f"   ↪ ستُنسَخ إلى الجديد: {', '.join(missing)}")

    print("\n📊 الصفوف:")
    total = 0
    for t, (o, n) in s["tables"].items():
        total += o
        print(f"   {'➡' if o else ' '} {t:26s} القديم={o:<6d} الجديد={n}")
    print(f"\n   📄 reports.submitted_by_user_id: "
          f"القديم={s['submitted_old']}  الجديد={s['submitted_new']}")
    total += s["submitted_old"]
    print(f"\n   ▸ إجمالي ما سيُنقَل: {total} صفّاً")
    return total


def backup_db() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = f"{DATABASE_PATH}.bak-merge-{stamp}"
    shutil.copy2(DATABASE_PATH, dst)
    return dst


def apply_merge(conn, old: int, new: int, name: str, keep_old_user: bool) -> None:
    """⚠️ تُستدعى **داخل** معاملة صريحة — لا تفتحها ولا تُنهيها بنفسها."""
    now = datetime.utcnow().isoformat(sep=" ")

    for t in data_tables():
        r = conn.execute(text(
            f"UPDATE {t} SET translator_id = :new, translator_name = :name "
            f"WHERE translator_id = :old"), {"new": new, "old": old, "name": name})
        if r.rowcount:
            print(f"   ➡ {t}: {r.rowcount}")

    # توحيد الاسم على الصفوف الموجودة أصلاً تحت الآيدي الجديد، وإلا ظهر
    # المترجم الواحد باسمين في الشاشة الواحدة بعد الدمج.
    for t in data_tables():
        conn.execute(text(
            f"UPDATE {t} SET translator_name = :name "
            f"WHERE translator_id = :new AND IFNULL(translator_name, {_EMPTY}) <> :name"),
            {"new": new, "name": name})

    r = conn.execute(text("UPDATE reports SET submitted_by_user_id = :new "
                          "WHERE submitted_by_user_id = :old"), {"new": new, "old": old})
    if r.rowcount:
        print(f"   ➡ reports.submitted_by_user_id: {r.rowcount}")

    # الصلاحيات: تُنسَخ الناقصة فقط — (tg_user_id, module_key) قيد فريد،
    # ونسخ ما هو موجود يُفشل العملية كلها.
    miss = conn.execute(text(
        "SELECT module_key FROM user_module_access "
        "WHERE tg_user_id = :old AND is_active = 1 AND module_key NOT IN "
        "(SELECT module_key FROM user_module_access WHERE tg_user_id = :new)"),
        {"old": old, "new": new}).fetchall()
    for (mk,) in miss:
        conn.execute(text(
            "INSERT INTO user_module_access (tg_user_id, module_key, granted_at, is_active) "
            "VALUES (:tg, :mk, :at, 1)"), {"tg": new, "mk": mk, "at": now})
        print(f"   🔑 صلاحية منقولة: {mk}")
    conn.execute(text("UPDATE user_module_access SET is_active = 0, revoked_at = :at "
                      "WHERE tg_user_id = :old AND is_active = 1"), {"old": old, "at": now})

    # الدليل: صفّ واحد بالآيدي الجديد، ثم يُحذف القديم.
    if conn.execute(text("SELECT 1 FROM translators WHERE translator_id = :i"),
                    {"i": new}).first():
        conn.execute(text("UPDATE translators SET name = :n WHERE translator_id = :i"),
                     {"n": name, "i": new})
        print(f"   📇 حُدِّث صفّ الدليل {new} إلى «{name}»")
    else:
        conn.execute(text("INSERT INTO translators (translator_id, name) VALUES (:i, :n)"),
                     {"i": new, "n": name})
        print(f"   📇 أُنشئ صفّ الدليل {new} باسم «{name}»")
    if conn.execute(text("DELETE FROM translators WHERE translator_id = :i"),
                    {"i": old}).rowcount:
        print(f"   🗑 حُذف صفّ الدليل القديم {old}")

    # الحساب القديم يُعطَّل: تركه معتمداً يعني هويّة موازية تستطيع الدخول
    # والكتابة بعد أن نُقل تاريخها كلّه إلى غيرها.
    if not keep_old_user:
        if conn.execute(text(
                "UPDATE users SET is_approved = 0, is_active = 0, updated_at = :at "
                "WHERE tg_user_id = :old"), {"old": old, "at": now}).rowcount:
            print(f"   🚫 عُطِّل الحساب القديم {old}")


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

    with engine.connect() as conn:
        s = survey(conn, a.old_id, a.new_id)
        total = print_survey(s, a.old_id, a.new_id)

        name = a.name or (s["dir_old"] or {}).get("name") or (s["dir_new"] or {}).get("name")
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

        print(f"\n💾 نسخة احتياطية: {backup_db()}")
        print(f"\n{LINE}\n  التنفيذ…\n{LINE}")
        # ⚠️ BEGIN صريح: المحرّك يفتح sqlite بـisolation_level=None أي أن
        # كل جملة تُثبَّت وحدها. بلا هذا السطر لا معاملة أصلاً، وانقطاع في
        # المنتصف يترك التاريخ مقسوماً بين آيديين.
        conn.exec_driver_sql("BEGIN")
        try:
            apply_merge(conn, a.old_id, a.new_id, name, a.keep_old_user)
        except Exception:
            conn.exec_driver_sql("ROLLBACK")
            print("\n❌ فشل الدمج — تراجعت القاعدة كاملةً، ولم يتغيّر شيء.")
            raise
        conn.exec_driver_sql("COMMIT")

        print(f"\n{LINE}\n  ✅ تمّ. التحقّق بعد الدمج:\n{LINE}")
        print_survey(survey(conn, a.old_id, a.new_id), a.old_id, a.new_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
