# scripts/rebuild_user_activity.py
# 🧱 إعادة بناء جدول `user_activity` المولود من تعريف آخر.
#
# ⚠️ **لماذا لا يكفي `_migrate_column` هنا وحده**: الجدول على الخادم ينقصه
# `id` — **المفتاح الأساسي نفسه**، وsqlite لا يضيف مفتاحاً أساسياً
# بـ`ALTER TABLE`. فالعلاج إعادة بناء لا إضافة.
#
# **السبب**: `services/user_tracker.py` (حُذف) كان يعرّف `UserActivity`
# ثانياً بنفس اسم الجدول وبأعمدة مختلفة تماماً — `user_id` مفتاحاً
# أساسياً، وحقول تجميع (عدد التقارير، آخر نشاط) لا سجلّ أحداث. ونسخته
# هي التي أنشأت الجدول على الخادم بـ`__table__.create`.
#
# ⚠️ **لا يُحذف شيء**: الصفوف القديمة تنتقل إلى `user_activity_legacy`
# كما هي. معناها يختلف عن الجدول الجديد (تجميع مقابل أحداث) فلا تُحوَّل
# آلياً — تحويلها اختراعُ بيانات لا ترحيلها.
#
#   venv/bin/python scripts/rebuild_user_activity.py
#   venv/bin/python scripts/rebuild_user_activity.py --apply

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sqlalchemy import text  # noqa: E402

from db.models import Base, UserActivity  # noqa: E402
from db.session import engine  # noqa: E402

LINE = "─" * 64
TABLE = "user_activity"
LEGACY = "user_activity_legacy"


def state(conn) -> dict:
    tables = {r[0] for r in conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    out = {"exists": TABLE in tables, "legacy_exists": LEGACY in tables,
           "cols": [], "rows": 0}
    if out["exists"]:
        out["cols"] = [r[1] for r in conn.exec_driver_sql(
            f"PRAGMA table_info({TABLE})").fetchall()]
        out["rows"] = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar() or 0
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="إعادة بناء جدول user_activity")
    ap.add_argument("--apply", action="store_true", help="التنفيذ الفعلي (بدونه معاينة فقط)")
    a = ap.parse_args()

    want = [c.name for c in UserActivity.__table__.columns]

    with engine.connect() as conn:
        s = state(conn)

        print(LINE)
        print(f"  إعادة بناء {TABLE}")
        print(LINE)
        print(f"\n  الأعمدة في القاعدة : {', '.join(s['cols']) or '— لا جدول —'}")
        print(f"  الأعمدة في النموذج : {', '.join(want)}")
        print(f"  الصفوف الحالية     : {s['rows']}")

        if not s["exists"]:
            print("\n✅ الجدول غير موجود — `create_all` سيبنيه صحيحاً عند التشغيل.")
            return 0

        if not (set(want) - set(s["cols"])):
            print("\n✅ الجدول مطابق للنموذج — لا حاجة لإعادة بناء.")
            return 0

        if s["legacy_exists"]:
            print(f"\n❌ `{LEGACY}` موجود مسبقاً — أُعيد البناء من قبل.")
            print("   احذفه يدوياً أولاً إن كنت تريد إعادة العملية.")
            return 2

        print(f"\n  ▸ سيُنقَل الجدول كما هو إلى `{LEGACY}` ({s['rows']} صفّاً)")
        print("  ▸ ثم يُبنى جدول جديد مطابق للنموذج (فارغ)")

        if not a.apply:
            print(f"\n{LINE}\n  معاينة فقط — لم يتغيّر شيء.")
            print(f"  للتنفيذ: أعد الأمر مضافاً إليه --apply\n{LINE}")
            return 0

        print(f"\n{LINE}\n  التنفيذ…\n{LINE}")
        # ⚠️ BEGIN صريح: المحرّك يفتح sqlite بـisolation_level=None، فبلا
        # هذا السطر تُثبَّت كل جملة وحدها — وانقطاع بين النقل والبناء يترك
        # القاعدة بلا جدول `user_activity` إطلاقاً.
        conn.exec_driver_sql("BEGIN")
        try:
            conn.exec_driver_sql(f"ALTER TABLE {TABLE} RENAME TO {LEGACY}")
        except Exception:
            conn.exec_driver_sql("ROLLBACK")
            print("❌ فشل النقل — لم يتغيّر شيء.")
            raise
        conn.exec_driver_sql("COMMIT")
        print(f"   📦 نُقل القديم إلى {LEGACY} ({s['rows']} صفّاً محفوظة)")

    # البناء بعد إغلاق المعاملة: `create_all` يدير اتصاله ومعاملته بنفسه.
    Base.metadata.create_all(bind=engine, tables=[UserActivity.__table__])

    with engine.connect() as conn:
        after = state(conn)
    print(f"   🧱 بُني الجديد: {', '.join(after['cols'])}")
    missing = set(want) - set(after["cols"])
    print(f"\n{LINE}")
    if missing:
        print(f"  ❌ ما زال ينقص: {', '.join(sorted(missing))}")
        return 1
    print("  ✅ الجدول مطابق للنموذج الآن.")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
