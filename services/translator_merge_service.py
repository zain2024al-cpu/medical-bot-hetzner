# services/translator_merge_service.py
# 🔀 دمج هويّة مترجم غيّر حسابه في تليجرام — المنطق الوحيد للعملية.
#
# ⚠️ **لماذا خدمة لا شيفرة داخل الشاشة**: العملية تُستدعى من مكانين —
# زر الأدمن في البوت، و`scripts/merge_translator_identity.py` من الخادم.
# تكرارها في الاثنين يعني نسختين تتباعدان، وهو بعينه العطب الذي تكرّر في
# هذا المشروع مراراً. النسخة هنا واحدة، والاثنان غلافان عليها.
#
# ⚠️ **الآيدي مفتاح ربط بلا مفاتيح أجنبية**: لا شيء في القاعدة يمنع بقاء
# صفوف يتيمة تشير إلى آيدي محذوف. فالترتيب مقصود: تُنقَل البيانات أولاً
# ويُحذف صفّ الدليل القديم آخراً، وكل ذلك في معاملة واحدة — الدمج
# الجزئي أسوأ من عدمه، لأنه يقسّم التاريخ بلا أثر ظاهر.

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

_EMPTY = "''"


# ─────────────────────────── قراءة البنية الفعلية ───────────────────────────

def real_columns(conn, table: str) -> set[str]:
    """أعمدة الجدول **كما هي في الملف** لا كما يصفها النموذج."""
    return {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}


def existing_tables(conn) -> set[str]:
    return {r[0] for r in conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}


def plan_tables(conn) -> tuple[list[tuple[str, bool]], list[tuple[str, str]]]:
    """(الجداول المشمولة مع هل تحمل عمود الاسم، المتخطّاة وسببها).

    المرشَّحون يُشتقّون من نموذج القاعدة — فأي جدول جديد يحمل الحقلين يدخل
    الدمج تلقائياً بلا تحديث قائمة مكتوبة. لكن الشمول يُقرَّر من **الملف
    نفسه**: قاعدة الخادم انحرفت عن النموذج فعلياً، والثقة بالنموذج وحده
    تُفجِّر العملية في منتصفها. و`translator_name` اختياري — وجود
    `translator_id` وحده يكفي لنقل الهويّة.

    `translators` خارج القائمة: لا يحمل `translator_name`، ويُعالَج على
    حدة لأن الآيدي فيه مفتاح أساسي.
    """
    from db.models import Base

    have = existing_tables(conn)
    targets, skipped = [], []
    for t in Base.metadata.sorted_tables:
        model_cols = {c.name for c in t.columns}
        if not {"translator_id", "translator_name"} <= model_cols:
            continue
        if t.name not in have:
            skipped.append((t.name, "الجدول غير موجود في القاعدة"))
            continue
        cols = real_columns(conn, t.name)
        if "translator_id" not in cols:
            skipped.append((t.name, "لا عمود translator_id في القاعدة"))
            continue
        targets.append((t.name, "translator_name" in cols))
    return sorted(targets), sorted(skipped)


# ─────────────────────────────── المعاينة ───────────────────────────────

def _scalar(conn, sql, **p):
    from sqlalchemy import text
    return conn.execute(text(sql), p).scalar() or 0


def preview(old: int, new: int) -> dict:
    """كل ما سيتغيّر، بلا تغيير أي شيء."""
    from sqlalchemy import text

    from db.session import engine

    with engine.connect() as conn:
        targets, skipped = plan_tables(conn)
        rows = {}
        for t, _has_name in targets:
            rows[t] = (
                _scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE translator_id = :i", i=old),
                _scalar(conn, f"SELECT COUNT(*) FROM {t} WHERE translator_id = :i", i=new),
            )

        have = existing_tables(conn)
        has_users = "users" in have
        has_modules = "user_module_access" in have
        has_submitted = ("reports" in have
                         and "submitted_by_user_id" in real_columns(conn, "reports"))

        def dir_row(i):
            r = conn.execute(text("SELECT translator_id, name FROM translators "
                                  "WHERE translator_id = :i"), {"i": i}).first()
            return {"translator_id": r[0], "name": r[1]} if r else None

        def user_row(i):
            if not has_users:
                return None
            r = conn.execute(text(
                "SELECT id, full_name, first_name, is_approved, is_active, is_suspended "
                "FROM users WHERE tg_user_id = :i"), {"i": i}).first()
            if not r:
                return None
            return {"id": r[0], "full_name": r[1], "first_name": r[2],
                    "is_approved": r[3], "is_active": r[4], "is_suspended": r[5]}

        def modules(i):
            if not has_modules:
                return []
            return [x[0] for x in conn.execute(text(
                "SELECT module_key FROM user_module_access "
                "WHERE tg_user_id = :i AND is_active = 1"), {"i": i}).fetchall()]

        submitted_old = _scalar(
            conn, "SELECT COUNT(*) FROM reports WHERE submitted_by_user_id = :i",
            i=old) if has_submitted else 0
        submitted_new = _scalar(
            conn, "SELECT COUNT(*) FROM reports WHERE submitted_by_user_id = :i",
            i=new) if has_submitted else 0

        return {
            "old": old, "new": new,
            "targets": targets, "skipped": skipped,
            "has_users": has_users, "has_modules": has_modules,
            "has_submitted": has_submitted,
            "tables": rows,
            "dir_old": dir_row(old), "dir_new": dir_row(new),
            "user_old": user_row(old), "user_new": user_row(new),
            "mod_old": modules(old), "mod_new": modules(new),
            "submitted_old": submitted_old, "submitted_new": submitted_new,
            "total": sum(o for o, _n in rows.values()) + submitted_old,
        }


def resolve_name(p: dict, override: str | None = None) -> str | None:
    """الاسم النهائي: المُمرَّر، وإلا اسم الصفّ القديم، وإلا الجديد."""
    return (override
            or (p["dir_old"] or {}).get("name")
            or (p["dir_new"] or {}).get("name"))


# ─────────────────────────────── التنفيذ ───────────────────────────────

def backup_db() -> str | None:
    """لقطة متّسقة من القاعدة قبل عملية لا تُراجَع.

    ⚠️ بواجهة النسخ في sqlite لا بنسخ الملف: القاعدة تعمل بـWAL، ونسخ
    الملف والبوت يكتب قد يُنتِج لقطة ممزّقة — وهي أسوأ من لا نسخة، لأنها
    تُطمئن كذباً.
    """
    try:
        from db.session import DATABASE_PATH
        dst = f"{DATABASE_PATH}.bak-merge-{datetime.now():%Y%m%d-%H%M%S}"
        src = sqlite3.connect(DATABASE_PATH)
        try:
            out = sqlite3.connect(dst)
            try:
                src.backup(out)
            finally:
                out.close()
        finally:
            src.close()
        return dst
    except Exception as exc:
        logger.error("[merge] تعذّرت النسخة الاحتياطية: %s", exc)
        return None


def _apply(conn, old: int, new: int, name: str, keep_old_user: bool) -> dict:
    """⚠️ تُستدعى **داخل** معاملة صريحة — لا تفتحها ولا تُنهيها بنفسها."""
    from sqlalchemy import text

    now = datetime.utcnow().isoformat(sep=" ")
    targets, _skipped = plan_tables(conn)
    have = existing_tables(conn)
    moved: dict[str, int] = {}

    for t, has_name in targets:
        setter = ("translator_id = :new, translator_name = :name" if has_name
                  else "translator_id = :new")
        p = {"new": new, "old": old}
        if has_name:
            p["name"] = name
        r = conn.execute(text(f"UPDATE {t} SET {setter} WHERE translator_id = :old"), p)
        if r.rowcount:
            moved[t] = r.rowcount

    # توحيد الاسم على الصفوف الموجودة أصلاً تحت الآيدي الجديد، وإلا ظهر
    # المترجم الواحد باسمين في الشاشة الواحدة بعد الدمج.
    for t, has_name in targets:
        if not has_name:
            continue
        conn.execute(text(
            f"UPDATE {t} SET translator_name = :name "
            f"WHERE translator_id = :new AND IFNULL(translator_name, {_EMPTY}) <> :name"),
            {"new": new, "name": name})

    if "reports" in have and "submitted_by_user_id" in real_columns(conn, "reports"):
        r = conn.execute(text("UPDATE reports SET submitted_by_user_id = :new "
                              "WHERE submitted_by_user_id = :old"), {"new": new, "old": old})
        if r.rowcount:
            moved["reports.submitted_by_user_id"] = r.rowcount

    # الصلاحيات: تُنسَخ الناقصة فقط — (tg_user_id, module_key) قيد فريد،
    # ونسخ ما هو موجود يُفشل العملية كلها.
    granted: list[str] = []
    if "user_module_access" in have:
        miss = conn.execute(text(
            "SELECT module_key FROM user_module_access "
            "WHERE tg_user_id = :old AND is_active = 1 AND module_key NOT IN "
            "(SELECT module_key FROM user_module_access WHERE tg_user_id = :new)"),
            {"old": old, "new": new}).fetchall()
        for (mk,) in miss:
            conn.execute(text(
                "INSERT INTO user_module_access (tg_user_id, module_key, granted_at, is_active) "
                "VALUES (:tg, :mk, :at, 1)"), {"tg": new, "mk": mk, "at": now})
            granted.append(mk)
        conn.execute(text("UPDATE user_module_access SET is_active = 0, revoked_at = :at "
                          "WHERE tg_user_id = :old AND is_active = 1"), {"old": old, "at": now})

    # الدليل: صفّ واحد بالآيدي الجديد، ثم يُحذف القديم.
    if conn.execute(text("SELECT 1 FROM translators WHERE translator_id = :i"),
                    {"i": new}).first():
        conn.execute(text("UPDATE translators SET name = :n WHERE translator_id = :i"),
                     {"n": name, "i": new})
    else:
        conn.execute(text("INSERT INTO translators (translator_id, name) VALUES (:i, :n)"),
                     {"i": new, "n": name})
    dir_deleted = bool(conn.execute(
        text("DELETE FROM translators WHERE translator_id = :i"), {"i": old}).rowcount)

    # الحساب القديم يُعطَّل: تركه معتمداً يعني هويّة موازية تستطيع الدخول
    # والكتابة بعد أن نُقل تاريخها كلّه إلى غيرها.
    user_disabled = False
    if not keep_old_user and "users" in have:
        user_disabled = bool(conn.execute(text(
            "UPDATE users SET is_approved = 0, is_active = 0, updated_at = :at "
            "WHERE tg_user_id = :old"), {"old": old, "at": now}).rowcount)

    return {"moved": moved, "granted": granted,
            "dir_deleted": dir_deleted, "user_disabled": user_disabled,
            "total": sum(moved.values())}


def merge(old: int, new: int, name: str, *, keep_old_user: bool = False,
          backup: bool = True) -> dict:
    """ينفّذ الدمج كاملاً أو لا ينفّذ منه شيئاً. يرمي عند الفشل."""
    from db.session import engine

    if old == new:
        raise ValueError("الآيديان متطابقان")

    bak = backup_db() if backup else None
    with engine.connect() as conn:
        # ⚠️ BEGIN صريح: المحرّك يفتح sqlite بـisolation_level=None أي أن
        # كل جملة تُثبَّت وحدها. بلا هذا السطر لا معاملة أصلاً، وانقطاع في
        # المنتصف يترك التاريخ مقسوماً بين آيديين.
        conn.exec_driver_sql("BEGIN")
        try:
            res = _apply(conn, old, new, name, keep_old_user)
        except Exception:
            conn.exec_driver_sql("ROLLBACK")
            logger.exception("[merge] فشل الدمج %s → %s — تراجعت القاعدة", old, new)
            raise
        conn.exec_driver_sql("COMMIT")

    res["backup"] = bak
    logger.info("[merge] %s → %s «%s»: %s صفّاً، صلاحيات %s، حذف الدليل=%s",
                old, new, name, res["total"], res["granted"], res["dir_deleted"])
    return res
