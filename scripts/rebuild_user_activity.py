# scripts/rebuild_user_activity.py
# 🧱 إعادة بناء جدول `user_activity` المولود من تعريف آخر.
#
# ⚠️ **لماذا لا يكفي `_migrate_column` هنا**: الجدول على الخادم ينقصه
# `id` — **المفتاح الأساسي نفسه**، وsqlite لا يضيفه بـ`ALTER TABLE`.
# فالعلاج إعادة بناء لا إضافة عمود.
#
# **السبب**: `services/user_tracker.py` (حُذف) كان يعرّف `UserActivity`
# ثانياً بنفس اسم الجدول وبأعمدة مختلفة تماماً — `user_id` مفتاحاً
# أساسياً، وحقول تجميع لا سجلّ أحداث. ونسخته أنشأت الجدول على الخادم.
#
# ⚠️ **الفهارس تنتقل مع الجدول عند `RENAME`**: يبقى
# `ix_user_activity_user_id` قائماً باسمه لكنه معلَّق بالجدول المنقول،
# فيرفض sqlite إنشاء فهرس النموذج بنفس الاسم. تُسقَط الفهارس المتصادمة
# قبل البناء — إسقاطها لا يضرّ الأرشيف، هو نسخة لا يُستعلَم عنها.
#
# ⚠️ **ويُستأنف من حيث توقّف**: الخطوات مستقلّة ومتحقَّق منها، فإعادة
# التشغيل بعد فشل في المنتصف تُكمِل ولا تعيد من الصفر ولا تُفسد شيئاً.
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

WANT_COLS = [c.name for c in UserActivity.__table__.columns]
WANT_INDEXES = sorted(i.name for i in UserActivity.__table__.indexes)


def _names(conn, kind: str) -> set[str]:
    return {r[0] for r in conn.exec_driver_sql(
        f"SELECT name FROM sqlite_master WHERE type = '{kind}'").fetchall()}


def _cols(conn, table: str) -> list[str]:
    return [r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()]


def _own_indexes(conn, table: str) -> set[str]:
    """فهارس هذا الجدول وحده.

    ⚠️ لا بالاسم في القاعدة كلها: الفهرس المنقول مع `RENAME` يحمل الاسم
    نفسه معلَّقاً بالأرشيف، فالبحث العام يجده ويُعلن السلامة كذباً.
    """
    return {r[1] for r in conn.exec_driver_sql(f"PRAGMA index_list({table})").fetchall()}


def state(conn) -> dict:
    tables = _names(conn, "table")
    all_index_names = _names(conn, "index")
    own = _own_indexes(conn, TABLE) if TABLE in tables else set()
    s = {
        "has_table": TABLE in tables,
        "has_legacy": LEGACY in tables,
        "cols": _cols(conn, TABLE) if TABLE in tables else [],
        "rows": 0,
        "legacy_rows": 0,
        "missing_indexes": [i for i in WANT_INDEXES if i not in own],
        # الاسم محجوز في القاعدة لكنه ليس فهرس هذا الجدول ⇒ متصادم
        "stale_indexes": [i for i in WANT_INDEXES
                          if i in all_index_names and i not in own],
    }
    if s["has_table"]:
        s["rows"] = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar() or 0
    if s["has_legacy"]:
        s["legacy_rows"] = conn.execute(text(f"SELECT COUNT(*) FROM {LEGACY}")).scalar() or 0
    s["table_ok"] = s["has_table"] and not (set(WANT_COLS) - set(s["cols"]))
    s["done"] = s["table_ok"] and not s["missing_indexes"]
    return s


def plan(s: dict) -> list[str]:
    """الخطوات الناقصة فقط — ما تمّ منها لا يُعاد."""
    steps = []
    if not s["table_ok"] and s["has_table"]:
        steps.append("rename")
    # الفهرس المتصادم قائم باسمه لكنه معلَّق بالجدول المنقول
    if s["stale_indexes"]:
        steps.append("drop_indexes")
    if not s["table_ok"]:
        steps.append("create")
    if s["missing_indexes"]:
        steps.append("index")
    return steps


def main() -> int:
    ap = argparse.ArgumentParser(description="إعادة بناء جدول user_activity")
    ap.add_argument("--apply", action="store_true", help="التنفيذ الفعلي (بدونه معاينة فقط)")
    a = ap.parse_args()

    with engine.connect() as conn:
        s = state(conn)

        print(LINE)
        print(f"  إعادة بناء {TABLE}")
        print(LINE)
        print(f"\n  الأعمدة في القاعدة : {', '.join(s['cols']) or '— لا جدول —'}")
        print(f"  الأعمدة في النموذج : {', '.join(WANT_COLS)}")
        print(f"  الصفوف الحالية     : {s['rows']}")
        if s["has_legacy"]:
            print(f"  الأرشيف {LEGACY}: {s['legacy_rows']} صفّاً")
        if s["missing_indexes"]:
            print(f"  فهارس ناقصة       : {', '.join(s['missing_indexes'])}")

        if s["done"]:
            print("\n✅ الجدول مطابق للنموذج بأعمدته وفهارسه — لا عمل مطلوب.")
            return 0

        steps = plan(s)
        if "rename" in steps and s["has_legacy"]:
            print(f"\n❌ يلزم نقل `{TABLE}` بينما `{LEGACY}` موجود مسبقاً.")
            print("   احذف الأرشيف يدوياً أو أعد تسميته أولاً.")
            return 2

        labels = {
            "rename": f"نقل الجدول القديم كما هو إلى `{LEGACY}` ({s['rows']} صفّاً)",
            "drop_indexes": f"إسقاط الفهارس المتصادمة: {', '.join(s['stale_indexes'])}",
            "create": "بناء الجدول الجديد مطابقاً للنموذج",
            "index": f"بناء الفهارس: {', '.join(s['missing_indexes'])}",
        }
        print("\n  الخطوات الناقصة:")
        for st in steps:
            print(f"   ▸ {labels[st]}")

        if not a.apply:
            print(f"\n{LINE}\n  معاينة فقط — لم يتغيّر شيء.")
            print(f"  للتنفيذ: أعد الأمر مضافاً إليه --apply\n{LINE}")
            return 0

        print(f"\n{LINE}\n  التنفيذ…\n{LINE}")

        if "rename" in steps:
            conn.exec_driver_sql(f"ALTER TABLE {TABLE} RENAME TO {LEGACY}")
            print(f"   📦 نُقل القديم إلى {LEGACY} ({s['rows']} صفّاً محفوظة)")

        # ⚠️ التصادم يُحسَب **بعد** النقل لا قبله: قبله الفهرس ملكُ الجدول
        # الأصلي فلا يبدو متصادماً، وبالنقل ينتقل معه فيصير الاسم محجوزاً.
        # حسابه من الحالة القديمة يعني تخطّي الإسقاط ثم السقوط عند البناء.
        colliding = [i for i in WANT_INDEXES
                     if i in _names(conn, "index") and i not in _own_indexes(conn, TABLE)] \
            if TABLE in _names(conn, "table") else \
            [i for i in WANT_INDEXES if i in _names(conn, "index")]
        if colliding:
            for ix in colliding:
                conn.exec_driver_sql(f"DROP INDEX IF EXISTS {ix}")
                print(f"   🧹 أُسقط الفهرس المتصادم {ix}")

    # ⚠️ `create_all` يبني الجدول **وفهارسه معاً**، لكنه يتخطّاه كلياً إن
    # كان قائماً — فلا يُكمِل فهارس جدول موجود. لذا تُبنى الفهارس الناقصة
    # صراحةً بعده، وإلا بقيت ناقصة في حالة الاستئناف بالضبط.
    Base.metadata.create_all(bind=engine, tables=[UserActivity.__table__])
    with engine.connect() as conn:
        own = _own_indexes(conn, TABLE)
        for ix in UserActivity.__table__.indexes:
            if ix.name in own:
                continue
            ix.create(bind=conn, checkfirst=True)
            conn.commit()
            print(f"   🧱 بُني الفهرس {ix.name}")
    print("   🧱 الجدول وفهارسه جاهزة")

    with engine.connect() as conn:
        after = state(conn)
    print(f"\n  الأعمدة الآن: {', '.join(after['cols'])}")
    print(f"\n{LINE}")
    if not after["done"]:
        miss = set(WANT_COLS) - set(after["cols"])
        print(f"  ❌ ما زال ناقصاً — أعمدة: {sorted(miss) or '—'}  "
              f"فهارس: {after['missing_indexes'] or '—'}")
        return 1
    print("  ✅ الجدول مطابق للنموذج بأعمدته وفهارسه.")
    if after["has_legacy"]:
        print(f"  📦 الصفوف القديمة محفوظة في {LEGACY} ({after['legacy_rows']} صفّاً).")
    print(LINE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
