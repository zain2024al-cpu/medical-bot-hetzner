# ================================================
# services/stats_service.py
# المصدر الوحيد والمركزي لجميع إحصائيات المترجمين
# ================================================
#
# القاعدة: كل ملف في المشروع يحتاج إحصائيات مترجمين
# يستدعي get_monthly_stats() أو get_translator_stats() من هنا فقط.
# لا يُسمح بأي حساب مستقل في أي ملف آخر.
#
# التعريف الرسمي:
#   - إجمالي التقارير: COUNT(*) WHERE status='active' AND translator_id IS NOT NULL
#   - أيام الحضور (attendance_days): COUNT(DISTINCT DATE(created_at)) - الأيام التي رفع فيها تقارير
#   - أيام العمل (work_days): نفس أيام الحضور (كل يوم نُشر فيه تقرير = يوم دوام)
#   - التقارير المتأخرة: ساعة «وقت التقرير» >= 20 (IST)، بالترتيب:
#       ساعة report_date إن وُجد في الحقل وقت (بعد دمج visit_time عند الحفظ)،
#       وإلا ساعة من visit_time (H:MM)، وإلا ساعة created_at بعد التحويل إلى IST
# ================================================

import logging
import re as _re
import sqlite3
from datetime import datetime, date, timedelta
from sqlalchemy import text
from db.session import DATABASE_PATH

logger = logging.getLogger(__name__)


# محارف تزيينية/مخفية شائعة قد تلتصق بأسماء الإجراءات عند اللصق من رسائل تيليجرام
# (خطوط أفقية، علامات RTL/LRM، فراغات صفرية، شرطات طويلة، tatweel، tashkeel)
_DECORATION_CHARS = (
    "\u200b\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
    "\u2066\u2067\u2068\u2069\ufeff"
    "\u0640"  # Arabic tatweel
)
_BOX_DRAWING_RANGE = _re.compile(r"[\u2500-\u257F]+")
_DASH_RANGE = _re.compile(r"[\u2010-\u2015]+")
_TASHKEEL_RANGE = _re.compile(r"[\u064B-\u0652\u0670]+")
_TRAILING_PUNCT = _re.compile(r"[\s\-_.،,:;/\\|•·–—]+$")
_LEADING_PUNCT = _re.compile(r"^[\s\-_.،,:;/\\|•·–—]+")


def normalize_action_name(s) -> str:
    """
    تطبيع اسم الإجراء: إزالة خطوط التزيين/علامات RTL ودمج الفراغات،
    لمنع تكرار مفاتيح مثل «تأجيل موعد» و«تأجيل موعد━».
    """
    if s is None:
        return ""
    t = str(s)
    # إزالة المحارف غير المرئية/التزيينية
    for ch in _DECORATION_CHARS:
        t = t.replace(ch, "")
    # إزالة خطوط الرسم (━ ─ ┃ …) والشرطات الطويلة
    t = _BOX_DRAWING_RANGE.sub(" ", t)
    t = _DASH_RANGE.sub(" ", t)
    # إزالة التشكيل
    t = _TASHKEEL_RANGE.sub("", t)
    # دمج الفراغات
    t = " ".join(t.split())
    # إزالة علامات الترقيم من البداية/النهاية
    t = _LEADING_PUNCT.sub("", t)
    t = _TRAILING_PUNCT.sub("", t)
    return t.strip()

# ساعة 0–23 بالـ IST لاحتساب «بعد 8 مساءً» في SQLite (نفس ترتيب المنطق في Python)
_EFF_HOUR_IST_FOR_LATE_SQL = """(
    CASE
        WHEN r.report_date IS NOT NULL AND (
             CAST(strftime('%H', r.report_date) AS INTEGER) != 0
             OR CAST(strftime('%M', r.report_date) AS INTEGER) != 0
        )
        THEN CAST(strftime('%H', r.report_date) AS INTEGER)
        WHEN r.visit_time IS NOT NULL AND length(trim(r.visit_time)) >= 3
             AND instr(trim(r.visit_time), ':') > 0
        THEN (
            CASE
                WHEN (
                    lower(trim(r.visit_time)) LIKE '%pm%'
                    OR trim(r.visit_time) LIKE '%مساء%'
                )
                AND CAST(substr(trim(r.visit_time), 1, instr(trim(r.visit_time), ':') - 1) AS INTEGER) < 12
                THEN CAST(substr(trim(r.visit_time), 1, instr(trim(r.visit_time), ':') - 1) AS INTEGER) + 12

                WHEN (
                    lower(trim(r.visit_time)) LIKE '%am%'
                    OR trim(r.visit_time) LIKE '%صباح%'
                )
                AND CAST(substr(trim(r.visit_time), 1, instr(trim(r.visit_time), ':') - 1) AS INTEGER) = 12
                THEN 0

                ELSE CAST(substr(trim(r.visit_time), 1, instr(trim(r.visit_time), ':') - 1) AS INTEGER)
            END
        )
        ELSE CAST(strftime('%H', datetime(r.created_at, '+5 hours', '+30 minutes')) AS INTEGER)
    END
)"""


def _effective_ist_hour_for_late(visit_time, report_date, created_at):
    """نسخة Python لنفس منطق _EFF_HOUR_IST_FOR_LATE_SQL (المسار الاحتياطي)."""
    rd = _parse_datetime(report_date)
    if rd and (rd.hour != 0 or rd.minute != 0 or (getattr(rd, "second", 0) or 0) != 0):
        return rd.hour
    vt = (visit_time or "").strip()
    if vt and ":" in vt:
        part = vt.split(":")[0].strip()
        try:
            h = int(part)
            if 0 <= h <= 23:
                vt_lower = vt.lower()
                is_pm = ("مساء" in vt) or ("pm" in vt_lower)
                is_am = ("صباح" in vt) or ("am" in vt_lower)
                if is_pm and h < 12:
                    h += 12
                elif is_am and h == 12:
                    h = 0
                return h
        except ValueError:
            pass
    cd = _parse_datetime(created_at)
    if not cd:
        return 0
    local_hour = cd.hour + 5 + (1 if cd.minute >= 30 else 0)
    if local_hour >= 24:
        local_hour -= 24
    return local_hour


def _parse_datetime(value):
    """تحويل التاريخ النصي/الكائني إلى datetime بشكل آمن."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    s = str(value).strip()
    if not s:
        return None

    for fmt in (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None

# أنواع الإجراءات الطبية الرسمية (13 نوع)
ALL_ACTION_TYPES = [
    "استشارة جديدة", "استشارة مع قرار عملية", "استشارة أخيرة",
    "طوارئ", "متابعة في الرقود", "مراجعة / عودة دورية",
    "عملية", "علاج طبيعي وإعادة تأهيل", "ترقيد",
    "خروج من المستشفى", "أشعة وفحوصات", "تأجيل موعد", "جلسة إشعاعي"
]


def _run_translator_query(session, start_date_str: str, end_date_str: str):
    """
    الاستعلام المركزي الوحيد - يُستدعى داخلياً فقط.
    لا يجب استدعاؤه مباشرة من خارج هذا الملف.

    Returns:
        list[dict] - قائمة بإحصائيات كل مترجم
    """
    try:
        # ═══ الاستعلام الرسمي الوحيد ═══
        # ✅ استخدام TranslatorDirectory كمرجع أساسي لتوحيد الأسماء
        # ✅ تحويل created_at من UTC إلى التوقيت المحلي (UTC+5:30) قبل مقارنة الساعة
        # ✅ استخدام COALESCE(report_date, created_at) لضمان عدم فقدان تقارير بدون report_date
        # ✅ التجميع بالاسم (لتوحيد المترجمين الذين لهم أكثر من translator_id)
        # ✅ WHERE مزدوج: report_date OR created_at بتوقيت IST
        # لأن التقارير القديمة (قبل إصلاح التوقيت) قد تكون report_date بـ UTC
        sql = text(f"""
            SELECT
                MIN(r.translator_id) as translator_id,
                COALESCE(td.name, r.translator_name, 'مترجم #' || r.translator_id) as translator_name,
                COUNT(*) as total_reports,
                COUNT(
                    DISTINCT DATE(
                        CASE
                            WHEN r.created_at IS NOT NULL
                            THEN datetime(r.created_at, '+5 hours', '+30 minutes')
                            ELSE r.report_date
                        END
                    )
                ) as attendance_days,
                SUM(
                    CASE WHEN {_EFF_HOUR_IST_FOR_LATE_SQL} >= 20
                    THEN 1 ELSE 0 END
                ) as late_reports,
                SUM(CASE WHEN r.has_paper_report = 1 THEN 1 ELSE 0 END) as paper_yes,
                SUM(CASE WHEN r.has_paper_report = 0 THEN 1 ELSE 0 END) as paper_no,
                SUM(CASE WHEN r.has_paper_report = 2 THEN 1 ELSE 0 END) as paper_pending
            FROM reports r
            LEFT JOIN translators td ON r.translator_id = td.translator_id
            WHERE (
                (COALESCE(r.report_date, r.created_at) >= :start AND COALESCE(r.report_date, r.created_at) < :end)
                OR (DATE(datetime(r.created_at, '+5 hours', '+30 minutes')) >= :start AND DATE(datetime(r.created_at, '+5 hours', '+30 minutes')) < :end)
            )
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
            GROUP BY COALESCE(td.name, r.translator_name)
            ORDER BY total_reports DESC
        """)

        rows = session.execute(sql, {"start": start_date_str, "end": end_date_str}).fetchall()

        # ═══ LOG: عدد المترجمين والتقارير ═══
        logger.info(f"📊 stats_service: range=[{start_date_str} → {end_date_str}], translators={len(rows)}")
        for row in rows:
            logger.info(f"   ├ tid={row[0]}, name={row[1]}, reports={row[2]}, days={row[3]}, late={row[4]}, paper_yes={row[5]}, paper_no={row[6]}, paper_pending={row[7]}")

        # ═══ شرط التاريخ الموحّد (يلتقط التقارير القديمة المحفوظة بـ UTC أيضاً) ═══
        _DATE_FILTER = """(
            (COALESCE(r.report_date, r.created_at) >= :start AND COALESCE(r.report_date, r.created_at) < :end)
            OR (DATE(datetime(r.created_at, '+5 hours', '+30 minutes')) >= :start AND DATE(datetime(r.created_at, '+5 hours', '+30 minutes')) < :end)
        )"""

        # ═══ LOG: إجمالي التقارير بدون تجميع ═══
        count_sql = text(f"""
            SELECT COUNT(*) FROM reports r
            WHERE {_DATE_FILTER}
            AND r.status = 'active'
        """)
        total_all = session.execute(count_sql, {"start": start_date_str, "end": end_date_str}).scalar()

        count_with_tid = text(f"""
            SELECT COUNT(*) FROM reports r
            WHERE {_DATE_FILTER}
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
        """)
        total_with_tid = session.execute(count_with_tid, {"start": start_date_str, "end": end_date_str}).scalar()

        count_no_tid = text(f"""
            SELECT COUNT(*) FROM reports r
            WHERE {_DATE_FILTER}
            AND r.status = 'active'
            AND r.translator_id IS NULL
        """)
        total_no_tid = session.execute(count_no_tid, {"start": start_date_str, "end": end_date_str}).scalar()

        logger.info(f"📊 stats_service: total_all={total_all}, with_tid={total_with_tid}, without_tid={total_no_tid}")

        # ═══ استعلام تفصيل الإجراءات (مجمّع بالاسم) ═══
        action_sql = text(f"""
            SELECT
                COALESCE(td.name, r.translator_name) as tname,
                COALESCE(r.medical_action, 'أخرى') as action_type,
                COUNT(*) as action_count
            FROM reports r
            LEFT JOIN translators td ON r.translator_id = td.translator_id
            WHERE {_DATE_FILTER}
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
            GROUP BY tname, action_type
        """)

        action_rows = session.execute(action_sql, {"start": start_date_str, "end": end_date_str}).fetchall()

        # تجميع الإجراءات حسب الاسم (مع تطبيع المفاتيح لمنع التكرار بسبب مسافات/خطوط زخرفية)
        action_map = {}
        for row in action_rows:
            tname = row[0]
            action_type = normalize_action_name(row[1]) or "أخرى"
            count = row[2]
            if tname not in action_map:
                action_map[tname] = {}
            action_map[tname][action_type] = action_map[tname].get(action_type, 0) + count

        # بناء النتيجة النهائية
        results = []
        for row in rows:
            tid = row[0]
            name = row[1]
            total = row[2]
            attendance_days = row[3]  # الأيام التي رفع فيها تقارير فعلاً
            late = row[4] or 0
            paper_yes = int(row[5] or 0)
            paper_no = int(row[6] or 0)
            paper_pending = int(row[7] or 0)
            work_days = attendance_days

            # بناء action_breakdown مع ضمان وجود كل الأنواع الـ 13
            # ✅ البحث بالاسم (لتوحيد المترجمين ذوي الأكثر من ID)
            # ✅ توحيد المفاتيح: strip + دمج المسافات المتعددة لمنع تكرار مثل
            #    "تأجيل موعد" و"تأجيل موعد " (نفس النص لكن بفراغ لاحق)
            raw_actions = action_map.get(name, {})
            action_breakdown = {a: 0 for a in ALL_ACTION_TYPES}
            for action_name, count in raw_actions.items():
                action_name_clean = normalize_action_name(action_name)
                if not action_name_clean:
                    continue
                # += بدلاً من = لتجميع أي متغيرات متطابقة بعد التطبيع
                action_breakdown[action_name_clean] = action_breakdown.get(action_name_clean, 0) + count

            results.append({
                "translator_id": tid,
                "translator_name": name,
                "total_reports": total,
                "work_days": work_days,
                "attendance_days": attendance_days,
                "late_reports": late,
                "paper_yes": paper_yes,
                "paper_no": paper_no,
                "paper_pending": paper_pending,
                "action_breakdown": action_breakdown,
                "start_date": start_date_str,
                "end_date": end_date_str,
            })

        return results

    except Exception as e:
        error_text = str(e).lower()
        if "malformed" not in error_text and "disk image" not in error_text:
            raise

        logger.warning("⚠️ stats_service: DB appears malformed, using resilient fallback aggregation.")
        logger.warning(f"⚠️ stats_service fallback reason: {e}")
        return _run_translator_query_resilient(start_date_str, end_date_str)


def _run_translator_query_resilient(start_date_str: str, end_date_str: str):
    """
    Fallback resilient aggregation for partially corrupted SQLite DB.
    Reads reports row-by-row using id to skip unreadable rows.
    """
    start_dt = _parse_datetime(start_date_str)
    end_dt = _parse_datetime(end_date_str)
    if not start_dt or not end_dt:
        return []

    results_map = {}
    unreadable_rows = 0
    users_name_cache = {}

    con = sqlite3.connect(DATABASE_PATH)
    cur = con.cursor()

    # max id may still be readable even with partial corruption
    try:
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM reports")
        max_id = int(cur.fetchone()[0] or 0)
    except Exception:
        con.close()
        return []

    for report_id in range(1, max_id + 1):
        try:
            cur.execute(
                "SELECT translator_id, translator_name, medical_action, report_date, created_at, visit_time, status, has_paper_report "
                "FROM reports WHERE id = ?",
                (report_id,),
            )
            row = cur.fetchone()
        except Exception:
            unreadable_rows += 1
            continue

        if not row:
            continue

        translator_id, translator_name, medical_action, report_date, created_at, visit_time, status, has_paper_report = row
        if translator_id is None:
            continue
        if status and str(status).strip().lower() != "active":
            continue

        report_dt = _parse_datetime(report_date)
        created_dt = _parse_datetime(created_at)

        # ✅ استخدام COALESCE: report_date أولاً، وإذا غاب نستخدم created_at
        if not report_dt:
            report_dt = created_dt
        if not report_dt and not created_dt:
            continue

        in_range = False
        if report_dt and (start_dt <= report_dt < end_dt):
            in_range = True
        if not in_range and created_dt:
            created_local_date = (created_dt + timedelta(hours=5, minutes=30)).date()
            if start_dt.date() <= created_local_date < end_dt.date():
                in_range = True
        if not in_range:
            continue

        tid = int(translator_id)
        if tid not in users_name_cache:
            try:
                # ✅ استخدام TranslatorDirectory بدلاً من users
                cur.execute("SELECT name FROM translators WHERE translator_id = ?", (tid,))
                urow = cur.fetchone()
                users_name_cache[tid] = (urow[0] if urow and urow[0] else None)
            except Exception:
                users_name_cache[tid] = None

        display_name = users_name_cache.get(tid) or translator_name or f"مترجم #{tid}"
        if tid not in results_map:
            results_map[tid] = {
                "translator_id": tid,
                "translator_name": str(display_name),
                "total_reports": 0,
                "attendance_dates": set(),
                "late_reports": 0,
                "paper_yes": 0,
                "paper_no": 0,
                "paper_pending": 0,
                "action_breakdown": {a: 0 for a in ALL_ACTION_TYPES},
            }

        item = results_map[tid]
        item["total_reports"] += 1
        if created_dt:
            item["attendance_dates"].add((created_dt + timedelta(hours=5, minutes=30)).date())
        elif report_dt:
            item["attendance_dates"].add(report_dt.date())
        if _effective_ist_hour_for_late(visit_time, report_date, created_at) >= 20:
            item["late_reports"] += 1
        if has_paper_report == 1:
            item["paper_yes"] += 1
        elif has_paper_report == 0:
            item["paper_no"] += 1
        elif has_paper_report == 2:
            item["paper_pending"] += 1

        action_name = normalize_action_name(medical_action) or "أخرى"
        item["action_breakdown"][action_name] = item["action_breakdown"].get(action_name, 0) + 1

    con.close()

    if unreadable_rows > 0:
        logger.warning(f"⚠️ stats_service fallback skipped unreadable rows: {unreadable_rows}")

    results = []
    for _, item in sorted(results_map.items(), key=lambda kv: kv[1]["total_reports"], reverse=True):
        attendance_days = len(item["attendance_dates"])
        results.append({
            "translator_id": item["translator_id"],
            "translator_name": item["translator_name"],
            "total_reports": item["total_reports"],
            "work_days": attendance_days,
            "attendance_days": attendance_days,
            "late_reports": item["late_reports"],
            "paper_yes": item["paper_yes"],
            "paper_no": item["paper_no"],
            "paper_pending": item["paper_pending"],
            "action_breakdown": item["action_breakdown"],
            "start_date": start_date_str,
            "end_date": end_date_str,
        })

    return results


def get_monthly_stats(session, year: int, month):
    """
    إحصائيات المترجمين لشهر محدد أو سنة كاملة.

    Parameters:
        session: SQLAlchemy session (must be open)
        year: int - السنة
        month: int or "all" - الشهر (1-12) أو "all" لكل السنة

    Returns:
        list[dict] - مرتبة من الأعلى إلى الأقل في عدد التقارير
    """
    if month == "all" or month == 0:
        start_date = f"{year}-01-01"
        end_date = f"{year + 1}-01-01"
    else:
        m = int(month)
        start_date = f"{year}-{m:02d}-01"
        if m == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{m + 1:02d}-01"

    return _run_translator_query(session, start_date, end_date)


def get_translator_stats(session, start_date, end_date):
    """
    إحصائيات المترجمين لفترة زمنية عشوائية.

    Parameters:
        session: SQLAlchemy session (must be open)
        start_date: date or str - بداية الفترة
        end_date: date or str - نهاية الفترة (exclusive)

    Returns:
        list[dict] - نفس الصيغة كـ get_monthly_stats
    """
    if isinstance(start_date, (date, datetime)):
        start_str = start_date.strftime("%Y-%m-%d")
    else:
        start_str = str(start_date)

    if isinstance(end_date, (date, datetime)):
        # نضيف يوم واحد لجعل النهاية exclusive
        if isinstance(end_date, date) and not isinstance(end_date, datetime):
            end_dt = end_date + timedelta(days=1)
        else:
            end_dt = end_date + timedelta(days=1)
        end_str = end_dt.strftime("%Y-%m-%d")
    else:
        end_str = str(end_date)

    return _run_translator_query(session, start_str, end_str)
