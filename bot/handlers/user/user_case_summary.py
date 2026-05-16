# =============================
# bot/handlers/user/user_case_summary.py
# 📋 ملخص الحالة — عرض تاريخ المريض الطبي (قراءة فقط)
# =============================
#
# Uses raw SQL (text()) instead of ORM model queries so it is immune to
# schema mismatches between the ORM model and older production databases.
# Only the columns actually displayed are requested — no SELECT *.

import logging
from datetime import datetime

from sqlalchemy import text
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from bot.shared_auth import ensure_approved
from db.session import SessionLocal

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────
CS_SELECT_PATIENT = 10
CS_SHOW_SUMMARY   = 11

# ─── Constants ────────────────────────────────────────────
_PER_PAGE_PATIENTS = 10
_PER_PAGE_REPORTS  = 5

# ─── Medical action icons ──────────────────────────────────
_ACTION_ICONS = {
    "استشارة جديدة": "🩺",
    "مراجعة":        "🔄",
    "طوارئ":         "🚨",
    "ترقيد":         "🛏️",
    "أشعة":          "🔬",
    "علاج إشعاعي":   "☢️",
    "تأجيل موعد":    "📅",
    "فحص مخبري":     "🧪",
}


def _action_icon(action) -> str:
    if not action:
        return "📄"
    for key, icon in _ACTION_ICONS.items():
        if key in action:
            return icon
    return "📄"


def _trunc(text_val, limit: int) -> str:
    if not text_val:
        return "—"
    t = str(text_val).strip()
    return t if len(t) <= limit else t[:limit] + "…"


def _format_date(val) -> str:
    if not val:
        return "—"
    if isinstance(val, datetime):
        return f"{val.day}/{val.month}/{val.year}"
    # SQLite sometimes returns strings like "2025-03-14 10:30:00"
    try:
        s = str(val)[:10]       # "YYYY-MM-DD"
        parts = s.split("-")
        return f"{int(parts[2])}/{int(parts[1])}/{parts[0]}"
    except Exception:
        return str(val)[:10]


# ─── Raw SQL helpers ───────────────────────────────────────

def _load_all_patients() -> list:
    """Returns sorted list of {id, name} dicts via raw SQL."""
    sql = text(
        "SELECT id, full_name FROM patients "
        "WHERE full_name IS NOT NULL AND full_name != '' "
        "ORDER BY full_name"
    )
    with SessionLocal() as s:
        rows = s.execute(sql).fetchall()
    result = []
    seen = set()
    for row in rows:
        pid, name = row[0], (row[1] or "").strip()
        if name and name not in seen:
            seen.add(name)
            result.append({"id": pid, "name": name})
    return result


def _load_reports(patient_id: int) -> list:
    """
    Returns list of plain dicts with only the fields we display.
    Raw SQL — immune to ORM column mapping errors on older schemas.
    """
    sql = text(
        "SELECT report_date, medical_action, complaint_text, "
        "       doctor_decision, hospital_name, doctor_name "
        "FROM reports "
        "WHERE patient_id = :pid AND (status IS NULL OR status != 'deleted') "
        "ORDER BY report_date DESC"
    )
    with SessionLocal() as s:
        rows = s.execute(sql, {"pid": patient_id}).fetchall()
    return [
        {
            "report_date":    row[0],
            "medical_action": row[1],
            "complaint_text": row[2],
            "doctor_decision":row[3],
            "hospital_name":  row[4],
            "doctor_name":    row[5],
        }
        for row in rows
    ]


# ─── Formatting ────────────────────────────────────────────

def _build_report_entry(r: dict) -> str:
    icon      = _action_icon(r["medical_action"])
    date      = _format_date(r["report_date"])
    action    = r["medical_action"] or "—"
    complaint = _trunc(r["complaint_text"], 60)
    decision  = _trunc(r["doctor_decision"], 60)
    hospital  = r["hospital_name"] or "—"
    doctor    = r["doctor_name"] or "—"
    return (
        "────────────────────\n"
        f"{icon} [{date}]  {action}\n"
        f"📌 الشكوى: {complaint}\n"
        f"🩺 قرار الطبيب: {decision}\n"
        f"🏥 {hospital}  |  👨‍⚕️ {doctor}"
    )


def _build_summary_page(patient_name: str, reports: list, page: int) -> str:
    total = len(reports)
    total_pages = max(1, (total + _PER_PAGE_REPORTS - 1) // _PER_PAGE_REPORTS)
    page = max(0, min(page, total_pages - 1))
    start = page * _PER_PAGE_REPORTS
    page_reports = reports[start: start + _PER_PAGE_REPORTS]

    lines = [
        "📋 **ملخص الحالة**",
        f"👤 المريض: {patient_name}",
        f"📊 عدد التقارير: {total}  |  الصفحة {page+1}/{total_pages}",
        "",
    ]
    for r in page_reports:
        lines.append(_build_report_entry(r))
    lines.append("────────────────────")
    return "\n".join(lines)


# ─── Keyboards ────────────────────────────────────────────

def _patient_list_keyboard(patients: list, page: int) -> InlineKeyboardMarkup:
    total = len(patients)
    total_pages = max(1, (total + _PER_PAGE_PATIENTS - 1) // _PER_PAGE_PATIENTS)
    page = max(0, min(page, total_pages - 1))
    start = page * _PER_PAGE_PATIENTS
    page_items = patients[start: start + _PER_PAGE_PATIENTS]

    rows = []
    pending = None
    for item in page_items:
        btn = InlineKeyboardButton(
            f"👤 {item['name']}",
            callback_data=f"cs_patient:{item['id']}",
        )
        if len(item["name"]) > 20:
            if pending:
                rows.append([pending])
                pending = None
            rows.append([btn])
        else:
            if pending is None:
                pending = btn
            else:
                rows.append([pending, btn])
                pending = None
    if pending:
        rows.append([pending])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"cs_page:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="cs_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"cs_page:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data="cs_cancel")])
    return InlineKeyboardMarkup(rows)


def _summary_keyboard(patient_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"cs_rep:{patient_id}:{page-1}"))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="cs_noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"cs_rep:{patient_id}:{page+1}"))

    rows = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔙 اختيار مريض آخر", callback_data="cs_back_to_list")])
    rows.append([InlineKeyboardButton("❌ إنهاء", callback_data="cs_cancel")])
    return InlineKeyboardMarkup(rows)


# ─── Handlers ─────────────────────────────────────────────

async def start_case_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_approved(update, context):
        return ConversationHandler.END

    try:
        patients = _load_all_patients()
    except Exception as e:
        logger.error(f"cs: load patients failed: {e}", exc_info=True)
        await update.message.reply_text("⚠️ خطأ في تحميل قائمة المرضى. حاول مرة أخرى.")
        return ConversationHandler.END

    if not patients:
        await update.message.reply_text("⚠️ لا يوجد مرضى مسجلون في النظام.")
        return ConversationHandler.END

    context.user_data["cs_patients"] = patients
    context.user_data["cs_page"] = 0

    await update.message.reply_text(
        f"📋 **ملخص الحالة**\n\nاختر مريضاً لعرض سجله الطبي ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, 0),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_patient_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    page = int(q.data.split(":")[1])
    patients = context.user_data.get("cs_patients")
    if not patients:
        patients = _load_all_patients()
        context.user_data["cs_patients"] = patients

    context.user_data["cs_page"] = page
    await q.edit_message_text(
        f"📋 **ملخص الحالة**\n\nاختر مريضاً ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, page),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_patient_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    patient_id = int(q.data.split(":")[1])

    patients = context.user_data.get("cs_patients") or _load_all_patients()
    patient_name = next((p["name"] for p in patients if p["id"] == patient_id), f"مريض #{patient_id}")

    try:
        reports = _load_reports(patient_id)
    except Exception as e:
        logger.error(f"cs: load reports failed for patient {patient_id}: {e}", exc_info=True)
        await q.edit_message_text(
            "⚠️ خطأ في تحميل التقارير. حاول مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="cs_back_to_list")],
                [InlineKeyboardButton("❌ إنهاء", callback_data="cs_cancel")],
            ]),
        )
        return CS_SHOW_SUMMARY

    if not reports:
        await q.edit_message_text(
            f"👤 {patient_name}\n\n⚠️ لا توجد تقارير مسجلة لهذا المريض.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 اختيار مريض آخر", callback_data="cs_back_to_list")],
                [InlineKeyboardButton("❌ إنهاء", callback_data="cs_cancel")],
            ]),
        )
        return CS_SHOW_SUMMARY

    context.user_data["cs_patient_id"] = patient_id
    context.user_data["cs_patient_name"] = patient_name
    context.user_data["cs_reports"] = reports

    total_pages = max(1, (len(reports) + _PER_PAGE_REPORTS - 1) // _PER_PAGE_REPORTS)
    text_msg = _build_summary_page(patient_name, reports, 0)

    await q.edit_message_text(
        text_msg,
        reply_markup=_summary_keyboard(patient_id, 0, total_pages),
        parse_mode="Markdown",
    )
    return CS_SHOW_SUMMARY


async def handle_report_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, patient_id_str, page_str = q.data.split(":")
    patient_id = int(patient_id_str)
    page = int(page_str)

    patient_name = context.user_data.get("cs_patient_name", f"مريض #{patient_id}")
    reports = context.user_data.get("cs_reports")
    if not reports:
        reports = _load_reports(patient_id)
        context.user_data["cs_reports"] = reports

    total_pages = max(1, (len(reports) + _PER_PAGE_REPORTS - 1) // _PER_PAGE_REPORTS)
    text_msg = _build_summary_page(patient_name, reports, page)

    await q.edit_message_text(
        text_msg,
        reply_markup=_summary_keyboard(patient_id, page, total_pages),
        parse_mode="Markdown",
    )
    return CS_SHOW_SUMMARY


async def handle_back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    patients = context.user_data.get("cs_patients")
    if not patients:
        patients = _load_all_patients()
        context.user_data["cs_patients"] = patients

    page = context.user_data.get("cs_page", 0)
    await q.edit_message_text(
        f"📋 **ملخص الحالة**\n\nاختر مريضاً ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, page),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    for key in ("cs_patients", "cs_page", "cs_patient_id", "cs_patient_name", "cs_reports"):
        context.user_data.pop(key, None)
    await q.edit_message_text("✅ تم إغلاق ملخص الحالة.")
    return ConversationHandler.END


# ─── Register ─────────────────────────────────────────────

def register(app):
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📋 ملخص الحالة$"), start_case_summary),
        ],
        states={
            CS_SELECT_PATIENT: [
                CallbackQueryHandler(handle_patient_page,      pattern=r"^cs_page:\d+$"),
                CallbackQueryHandler(handle_patient_selection, pattern=r"^cs_patient:\d+$"),
                CallbackQueryHandler(handle_cancel,            pattern=r"^cs_cancel$"),
            ],
            CS_SHOW_SUMMARY: [
                CallbackQueryHandler(handle_report_page,  pattern=r"^cs_rep:\d+:\d+$"),
                CallbackQueryHandler(handle_back_to_list, pattern=r"^cs_back_to_list$"),
                CallbackQueryHandler(handle_cancel,       pattern=r"^cs_cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_cancel, pattern=r"^cs_cancel$"),
        ],
        name="case_summary_conv",
        persistent=False,
    )
    app.add_handler(conv)
