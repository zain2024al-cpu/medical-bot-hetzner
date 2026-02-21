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
#   - التقارير المتأخرة: created_at hour >= 20
# ================================================

import logging
import sqlite3
from datetime import datetime, date, timedelta
from sqlalchemy import text
from db.session import DATABASE_PATH

logger = logging.getLogger(__name__)


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
        sql = text("""
            SELECT
                MIN(r.translator_id) as translator_id,
                COALESCE(td.name, r.translator_name, 'مترجم #' || r.translator_id) as translator_name,
                COUNT(*) as total_reports,
                COUNT(DISTINCT DATE(COALESCE(r.report_date, r.created_at))) as attendance_days,
                SUM(
                    CASE WHEN CAST(strftime('%H', datetime(r.created_at, '+5 hours', '+30 minutes')) AS INTEGER) >= 20
                    THEN 1 ELSE 0 END
                ) as late_reports
            FROM reports r
            LEFT JOIN translators td ON r.translator_id = td.translator_id
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
            GROUP BY COALESCE(td.name, r.translator_name)
            ORDER BY total_reports DESC
        """)

        rows = session.execute(sql, {"start": start_date_str, "end": end_date_str}).fetchall()

        # ═══ LOG: عدد المترجمين والتقارير ═══
        logger.info(f"📊 stats_service: range=[{start_date_str} → {end_date_str}], translators={len(rows)}")
        for row in rows:
            logger.info(f"   ├ tid={row[0]}, name={row[1]}, reports={row[2]}, days={row[3]}, late={row[4]}")

        # ═══ LOG: إجمالي التقارير بدون تجميع ═══
        count_sql = text("""
            SELECT COUNT(*) FROM reports r
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
        """)
        total_all = session.execute(count_sql, {"start": start_date_str, "end": end_date_str}).scalar()

        count_with_tid = text("""
            SELECT COUNT(*) FROM reports r
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
        """)
        total_with_tid = session.execute(count_with_tid, {"start": start_date_str, "end": end_date_str}).scalar()

        count_no_tid = text("""
            SELECT COUNT(*) FROM reports r
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
            AND r.translator_id IS NULL
        """)
        total_no_tid = session.execute(count_no_tid, {"start": start_date_str, "end": end_date_str}).scalar()

        logger.info(f"📊 stats_service: total_all={total_all}, with_tid={total_with_tid}, without_tid={total_no_tid}")

        # ═══ استعلام تفصيل الإجراءات (مجمّع بالاسم) ═══
        action_sql = text("""
            SELECT
                COALESCE(td.name, r.translator_name) as tname,
                COALESCE(r.medical_action, 'أخرى') as action_type,
                COUNT(*) as action_count
            FROM reports r
            LEFT JOIN translators td ON r.translator_id = td.translator_id
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
            GROUP BY tname, action_type
        """)

        action_rows = session.execute(action_sql, {"start": start_date_str, "end": end_date_str}).fetchall()

        # تجميع الإجراءات حسب الاسم
        action_map = {}
        for row in action_rows:
            tname = row[0]
            action_type = row[1] or "أخرى"
            count = row[2]
            if tname not in action_map:
                action_map[tname] = {}
            action_map[tname][action_type] = count

        # ═══ استعلام التقارير المكررة (نفس الاسم + نفس المريض + نفس اليوم) ═══
        dup_sql = text("""
            SELECT COALESCE(td.name, r.translator_name) as tname,
                   COUNT(*) - COUNT(DISTINCT r.patient_name || '|' || DATE(COALESCE(r.report_date, r.created_at))) as duplicates
            FROM reports r
            LEFT JOIN translators td ON r.translator_id = td.translator_id
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
            GROUP BY tname
        """)
        dup_rows = session.execute(dup_sql, {"start": start_date_str, "end": end_date_str}).fetchall()
        dup_map = {row[0]: max(row[1], 0) for row in dup_rows}

        # ═══ متوسط ساعة الإرسال لكل مترجم بالاسم (بتوقيت IST) ═══
        avg_hour_sql = text("""
            SELECT COALESCE(td.name, r.translator_name) as tname,
                   AVG(CAST(strftime('%H', datetime(r.created_at, '+5 hours', '+30 minutes')) AS REAL)
                       + CAST(strftime('%M', datetime(r.created_at, '+5 hours', '+30 minutes')) AS REAL) / 60.0
                   ) as avg_hour
            FROM reports r
            LEFT JOIN translators td ON r.translator_id = td.translator_id
            WHERE COALESCE(r.report_date, r.created_at) >= :start
            AND COALESCE(r.report_date, r.created_at) < :end
            AND r.status = 'active'
            AND r.translator_id IS NOT NULL
            GROUP BY tname
        """)
        avg_hour_rows = session.execute(avg_hour_sql, {"start": start_date_str, "end": end_date_str}).fetchall()
        avg_hour_map = {row[0]: round(row[1], 1) if row[1] is not None else None for row in avg_hour_rows}

        # بناء النتيجة النهائية
        results = []
        for row in rows:
            tid = row[0]
            name = row[1]
            total = row[2]
            attendance_days = row[3]  # الأيام التي رفع فيها تقارير فعلاً
            late = row[4] or 0
            work_days = attendance_days

            # بناء action_breakdown مع ضمان وجود كل الأنواع الـ 13
            # ✅ البحث بالاسم (لتوحيد المترجمين ذوي الأكثر من ID)
            raw_actions = action_map.get(name, {})
            action_breakdown = {a: 0 for a in ALL_ACTION_TYPES}
            for action_name, count in raw_actions.items():
                action_name_clean = (action_name or "").strip()
                if action_name_clean in action_breakdown:
                    action_breakdown[action_name_clean] = count
                elif action_name_clean:
                    action_breakdown[action_name_clean] = count

            results.append({
                "translator_id": tid,
                "translator_name": name,
                "total_reports": total,
                "work_days": work_days,
                "attendance_days": attendance_days,
                "late_reports": late,
                "duplicate_reports": dup_map.get(name, 0),
                "avg_hour": avg_hour_map.get(name),
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
                "SELECT translator_id, translator_name, medical_action, report_date, created_at, status "
                "FROM reports WHERE id = ?",
                (report_id,),
            )
            row = cur.fetchone()
        except Exception:
            unreadable_rows += 1
            continue

        if not row:
            continue

        translator_id, translator_name, medical_action, report_date, created_at, status = row
        if translator_id is None:
            continue
        if status and str(status).strip().lower() != "active":
            continue

        report_dt = _parse_datetime(report_date)
        created_dt = _parse_datetime(created_at)

        # ✅ استخدام COALESCE: report_date أولاً، وإذا غاب نستخدم created_at
        if not report_dt:
            report_dt = created_dt
        if not report_dt:
            continue

        if not (start_dt <= report_dt < end_dt):
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
                "action_breakdown": {a: 0 for a in ALL_ACTION_TYPES},
            }

        item = results_map[tid]
        item["total_reports"] += 1
        item["attendance_dates"].add(report_dt.date())
        # ✅ تحويل created_at من UTC إلى التوقيت المحلي (UTC+5:30) قبل المقارنة
        if created_dt:
            local_hour = created_dt.hour + 5 + (1 if created_dt.minute >= 30 else 0)
            if local_hour >= 24:
                local_hour -= 24
            if local_hour >= 20:
                item["late_reports"] += 1

        action_name = (medical_action or "أخرى").strip() if medical_action else "أخرى"
        if action_name in item["action_breakdown"]:
            item["action_breakdown"][action_name] += 1
        else:
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
