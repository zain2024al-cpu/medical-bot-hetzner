# scripts/audit_schema.py
# 🔎 كشف انحراف القاعدة عن النموذج: أعمدة يعرّفها الموديل ولا تحملها
# القاعدة الفعلية.
#
# ⚠️ **لماذا العمود الناقص أخطر ممّا يبدو**: SQLAlchemy يبني `SELECT`
# بكل أعمدة الموديل. فعمود واحد ناقص لا يُعطّل ميزته وحدها — يُسقِط
# **كل قراءة** لذلك الجدول بـ`no such column`، مهما كانت الميزة. وكثير
# من هذه السقطات مُبتلَع في `except` عام فلا يظهر في السجلّ أصلاً.
#
# ⚠️ **ولا يظهر شيء من هذا محلياً**: القاعدة المحلية تُبنى من الموديل
# بـ`create_all` فتطابقه دائماً. الانحراف حكرٌ على قاعدة عاشت ترقيات —
# أي على الخادم وحده. فهذا السكربت لا معنى له إلا مُشغَّلاً هناك:
#
#   venv/bin/python scripts/audit_schema.py
#
# العلاج لكل عمود يظهر هنا: سطر `_migrate_column` في `db/maintenance.py`
# ثم إعادة تشغيل البوت — الترحيل يعمل عند بدء التشغيل.
#
# (كان هذا السكربت يقرأ `db/models.py` بتعابير نمطية ويُثبِّت مسار قاعدة
# محلياً؛ صار يقرأ النموذج والقاعدة الحقيقيين من نفس مصدر البوت.)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sqlalchemy import text  # noqa: E402

from db.models import Base  # noqa: E402
from db.session import DATABASE_PATH, engine  # noqa: E402

LINE = "─" * 64


def audit() -> tuple[list[str], list[tuple[str, list[str], int]], list[tuple[str, list[str]]]]:
    """(جداول مفقودة، [(جدول، أعمدة ناقصة، صفوفه)]، [(جدول، فهارس ناقصة)])."""
    with engine.connect() as conn:
        tables = {r[0] for r in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}

        missing_tables: list[str] = []
        drift: list[tuple[str, list[str], int]] = []
        ix_drift: list[tuple[str, list[str]]] = []

        for t in Base.metadata.sorted_tables:
            if t.name not in tables:
                missing_tables.append(t.name)
                continue
            real = {r[1] for r in conn.exec_driver_sql(
                f"PRAGMA table_info({t.name})").fetchall()}
            gap = sorted({c.name for c in t.columns} - real)
            if gap:
                # عدد الصفوف بـSQL خام لا بالموديل — قراءة الموديل هي
                # ذاتها ما ينهار هنا.
                n = conn.execute(text(f"SELECT COUNT(*) FROM {t.name}")).scalar() or 0
                drift.append((t.name, gap, n))
            # ⚠️ الفهارس تُفحَص أيضاً: جدولٌ أعمدته تامّة وفهارسه ناقصة
            # يعمل ويبطئ فقط — فلا شيء يكشفه، ويبقى «لا انحراف» طمأنينة
            # كاذبة. حدث فعلاً: `ALTER TABLE RENAME` ينقل فهارس الجدول
            # معه، فيبقى الاسم محجوزاً ولا يُبنى فهرس الجديد.
            # ⚠️ والفحص **لكل جدول** لا بالاسم في القاعدة كلها: الفهرس
            # المنقول يحمل الاسم نفسه معلَّقاً بجدول آخر، فالبحث العام
            # يجده ويُعلن السلامة كذباً.
            own = {r[1] for r in conn.exec_driver_sql(
                f"PRAGMA index_list({t.name})").fetchall()}
            ix_gap = sorted({i.name for i in t.indexes} - own)
            if ix_gap:
                ix_drift.append((t.name, ix_gap))
    return missing_tables, drift, ix_drift


def main() -> int:
    missing_tables, drift, ix_drift = audit()

    print(LINE)
    print("  فحص انحراف القاعدة عن النموذج")
    print(f"  {DATABASE_PATH}")
    print(LINE)

    if missing_tables:
        print(f"\n🚫 جداول في النموذج وغير موجودة في القاعدة ({len(missing_tables)}):")
        for t in missing_tables:
            print(f"   ⊘ {t}")

    if drift:
        print(f"\n💥 جداول تسقط كل قراءة لها ({len(drift)}):\n")
        for t, cols, n in drift:
            print(f"   ⚠️ {t}  —  {n} صفّاً")
            for c in cols:
                print(f"        ينقص: {c}")
        print("\n  العلاج: أضف لكل عمود سطر _migrate_column في db/maintenance.py")
        print("  ثم أعد تشغيل البوت — الترحيل يعمل عند بدء التشغيل.")

    if ix_drift:
        # ليست عطباً يُسقِط شيئاً — بطءٌ صامت في الجداول الكبيرة.
        print(f"\n🐢 فهارس ناقصة (القراءة تعمل وتبطؤ) ({len(ix_drift)}):\n")
        for t, ixs in ix_drift:
            print(f"   ⚠️ {t}")
            for i in ixs:
                print(f"        ينقص الفهرس: {i}")
        print("\n  العلاج: `create_all` يبنيها عند الإقلاع ما لم يكن الاسم")
        print("  محجوزاً بفهرس جدول آخر — راجع scripts/rebuild_user_activity.py")

    if not drift and not ix_drift:
        print("\n✅ لا انحراف: أعمدة النموذج وفهارسه كلها موجودة في القاعدة.")
        return 0

    print(f"\n{LINE}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
