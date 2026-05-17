# =============================
# bot/handlers/user/user_case_summary.py
# 📋 ملخص الحالة — structured operational summary (read-only)
# =============================
#
# Queries use raw SQL (sqlalchemy.text) only — never ORM model objects —
# so the handler is immune to schema gaps between the ORM model and older
# production databases.

import logging

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
from services.case_summary_service import build_full_summary

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────
CS_SELECT_PATIENT = 10
CS_SHOW_SUMMARY   = 11

# ─── Constants ────────────────────────────────────────────
_PER_PAGE_PATIENTS = 10
# Telegram hard limit is 4096; we stay safely under it
_MAX_MSG_LEN = 3800

# ─── All report columns needed by the summary service ─────
# Explicit list — no SELECT * — immune to schema additions.
_REPORT_COLS = """
    report_date, medical_action, complaint_text, doctor_decision,
    case_status, diagnosis, treatment_plan, medications, notes,
    hospital_name, department, doctor_name, room_number,
    followup_date, followup_department, followup_reason,
    followup_time,
    app_reschedule_reason, app_reschedule_return_date,
    app_reschedule_return_reason,
    radiology_type, radiology_delivery_date,
    radiation_therapy_type, radiation_therapy_session_number,
    radiation_therapy_remaining, radiation_therapy_recommendations,
    radiation_therapy_return_date, radiation_therapy_return_reason,
    radiation_therapy_final_notes, radiation_therapy_completed
""".strip()

_REPORT_COL_NAMES = [c.strip() for c in _REPORT_COLS.replace("\n", "").split(",")]


# ─── DB loaders (raw SQL) ─────────────────────────────────

def _load_all_patients() -> list:
    sql = text(
        "SELECT id, full_name FROM patients "
        "WHERE full_name IS NOT NULL AND full_name != '' "
        "ORDER BY full_name"
    )
    with SessionLocal() as s:
        rows = s.execute(sql).fetchall()
    seen: set = set()
    result = []
    for row in rows:
        pid, name = row[0], (row[1] or "").strip()
        if name and name not in seen:
            seen.add(name)
            result.append({"id": pid, "name": name})
    return result


def _load_reports(patient_id: int) -> list:
    """Returns list of plain dicts. Newest first."""
    sql = text(
        f"SELECT {_REPORT_COLS} FROM reports "
        "WHERE patient_id = :pid "
        "  AND (status IS NULL OR status != 'deleted') "
        "ORDER BY report_date DESC"
    )
    with SessionLocal() as s:
        rows = s.execute(sql, {"pid": patient_id}).fetchall()
    return [dict(zip(_REPORT_COL_NAMES, row)) for row in rows]


def _patient_hospital(reports: list) -> str:
    """Return the most recent non-empty hospital name."""
    for r in reports:
        h = (r.get("hospital_name") or "").strip()
        if h and h not in ("", "None", "—"):
            return h
    return ""


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

    # Search button — same inline query mechanism as add-report flow
    rows.append([
        InlineKeyboardButton("📋 عرض الكل", callback_data=f"cs_page:{page}"),
        InlineKeyboardButton("🔍 بحث باسم المريض", switch_inline_query_current_chat=""),
    ])

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


def _summary_keyboard(patient_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 اختيار مريض آخر", callback_data="cs_back_to_list")],
        [InlineKeyboardButton("❌ إنهاء", callback_data="cs_cancel")],
    ])


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
    context.user_data["_current_search_type"] = "patient"

    await update.message.reply_text(
        f"📋 *ملخص الحالة*\n\nاختر مريضاً لعرض ملخصه الطبي ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, 0),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_patient_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    page = int(q.data.split(":")[1])
    patients = context.user_data.get("cs_patients") or _load_all_patients()
    context.user_data["cs_patients"] = patients
    context.user_data["cs_page"] = page
    context.user_data["_current_search_type"] = "patient"

    await q.edit_message_text(
        f"📋 *ملخص الحالة*\n\nاختر مريضاً ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, page),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_patient_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    patient_id = int(q.data.split(":")[1])

    patients = context.user_data.get("cs_patients") or _load_all_patients()
    patient_name = next(
        (p["name"] for p in patients if p["id"] == patient_id),
        f"مريض #{patient_id}",
    )

    try:
        reports = _load_reports(patient_id)
    except Exception as e:
        logger.error(f"cs: load reports failed patient={patient_id}: {e}", exc_info=True)
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

    hospital = _patient_hospital(reports)
    last_date = reports[0].get("report_date")   # newest first

    summary = build_full_summary(
        patient_name=patient_name,
        hospital_name=hospital,
        reports=reports,
        last_date=last_date,
    )

    # Guard against Telegram 4096-char limit
    if len(summary) > _MAX_MSG_LEN:
        summary = summary[:_MAX_MSG_LEN] + "\n\n…"

    context.user_data["cs_patient_id"] = patient_id
    context.user_data["cs_patient_name"] = patient_name

    await q.edit_message_text(
        summary,
        reply_markup=_summary_keyboard(patient_id),
        parse_mode="Markdown",
    )
    return CS_SHOW_SUMMARY


async def handle_back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    patients = context.user_data.get("cs_patients") or _load_all_patients()
    context.user_data["cs_patients"] = patients
    page = context.user_data.get("cs_page", 0)
    context.user_data["_current_search_type"] = "patient"

    await q.edit_message_text(
        f"📋 *ملخص الحالة*\n\nاختر مريضاً ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, page),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    for key in ("cs_patients", "cs_page", "cs_patient_id", "cs_patient_name"):
        context.user_data.pop(key, None)
    await q.edit_message_text("✅ تم إغلاق ملخص الحالة.")
    return ConversationHandler.END


async def handle_inline_patient_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receives the '__PATIENT_SELECTED__:{id}:{name}' message produced by the
    inline query when the user picks a patient from the search results.
    Mirrors the same protocol used in the add-report flow.
    """
    text_msg = update.message.text or ""
    if not text_msg.startswith("__PATIENT_SELECTED__"):
        return CS_SELECT_PATIENT

    try:
        parts = text_msg.split(":", 2)
        patient_id = int(parts[1])
        patient_name = parts[2] if len(parts) > 2 else f"مريض #{patient_id}"
    except Exception:
        await update.message.reply_text("⚠️ لم يتم التعرف على المريض. حاول مرة أخرى.")
        return CS_SELECT_PATIENT

    if patient_id == 0 or patient_name in ("خطأ", "لا يوجد"):
        await update.message.reply_text("⚠️ لم يتم العثور على المريض. حاول مرة أخرى.")
        return CS_SELECT_PATIENT

    # Delete the raw __PATIENT_SELECTED__ message so it doesn't clutter the chat
    try:
        await update.message.delete()
    except Exception:
        pass

    try:
        reports = _load_reports(patient_id)
    except Exception as e:
        logger.error(f"cs inline: load reports failed patient={patient_id}: {e}", exc_info=True)
        await update.message.reply_text("⚠️ خطأ في تحميل التقارير. حاول مرة أخرى.")
        return CS_SELECT_PATIENT

    if not reports:
        await update.message.reply_text(
            f"👤 {patient_name}\n\n⚠️ لا توجد تقارير مسجلة لهذا المريض.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 اختيار مريض آخر", callback_data="cs_back_to_list")],
                [InlineKeyboardButton("❌ إنهاء", callback_data="cs_cancel")],
            ]),
        )
        return CS_SHOW_SUMMARY

    hospital = _patient_hospital(reports)
    last_date = reports[0].get("report_date")

    summary = build_full_summary(
        patient_name=patient_name,
        hospital_name=hospital,
        reports=reports,
        last_date=last_date,
    )
    if len(summary) > _MAX_MSG_LEN:
        summary = summary[:_MAX_MSG_LEN] + "\n\n…"

    context.user_data["cs_patient_id"] = patient_id
    context.user_data["cs_patient_name"] = patient_name

    await update.message.reply_text(
        summary,
        reply_markup=_summary_keyboard(patient_id),
        parse_mode="Markdown",
    )
    return CS_SHOW_SUMMARY


# ─── Register ─────────────────────────────────────────────

def register(app):
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📋 ملخص الحالة$"), start_case_summary),
        ],
        states={
            CS_SELECT_PATIENT: [
                MessageHandler(filters.Regex(r"^__PATIENT_SELECTED__"), handle_inline_patient_selected),
                CallbackQueryHandler(handle_patient_page,      pattern=r"^cs_page:\d+$"),
                CallbackQueryHandler(handle_patient_selection, pattern=r"^cs_patient:\d+$"),
                CallbackQueryHandler(handle_cancel,            pattern=r"^cs_cancel$"),
            ],
            CS_SHOW_SUMMARY: [
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
