# =============================
# bot/handlers/user/user_case_summary.py
# 📋 ملخص الحالة — عرض تاريخ المريض الطبي (قراءة فقط)
# =============================

import logging
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
from db.models import Report, Patient

logger = logging.getLogger(__name__)

# ─── States ───────────────────────────────────────────────
CS_SELECT_PATIENT = 10
CS_SHOW_SUMMARY   = 11

# ─── Constants ────────────────────────────────────────────
_PER_PAGE_PATIENTS = 10   # أسماء المرضى في كل صفحة
_PER_PAGE_REPORTS  = 5    # تقارير في كل صفحة
_MAX_TEXT_LEN      = 3800 # حد آمن لرسالة تيليغرام

# ─── Medical action icons ──────────────────────────────────
_ACTION_ICONS = {
    "استشارة جديدة":       "🩺",
    "مراجعة":              "🔄",
    "طوارئ":               "🚨",
    "ترقيد":               "🛏️",
    "أشعة":                "🔬",
    "علاج إشعاعي":         "☢️",
    "تأجيل موعد":          "📅",
    "فحص مخبري":           "🧪",
}


def _action_icon(action) -> str:
    if not action:
        return "📄"
    for key, icon in _ACTION_ICONS.items():
        if key in action:
            return icon
    return "📄"


def _trunc(text, limit: int) -> str:
    if not text:
        return "—"
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _format_date(dt) -> str:
    if not dt:
        return "—"
    try:
        return f"{dt.day}/{dt.month}/{dt.year}"
    except Exception:
        return str(dt)[:10]


def _build_report_entry(report) -> str:
    """يبني نص سطر موحد لكل تقرير."""
    icon = _action_icon(report.medical_action)
    date = _format_date(report.report_date)
    action = report.medical_action or "—"
    complaint = _trunc(report.complaint_text, 60)
    decision = _trunc(report.doctor_decision, 60)
    hospital = report.hospital_name or "—"
    doctor = report.doctor_name or "—"

    lines = [
        f"────────────────────",
        f"{icon} [{date}]  {action}",
        f"📌 الشكوى: {complaint}",
        f"🩺 قرار الطبيب: {decision}",
        f"🏥 {hospital}  |  👨‍⚕️ {doctor}",
    ]
    return "\n".join(lines)


# ─── Patient list helpers ──────────────────────────────────

def _load_all_patients() -> list:
    """Returns sorted list of {id, full_name} dicts."""
    with SessionLocal() as s:
        patients = (
            s.query(Patient)
            .filter(Patient.full_name.isnot(None), Patient.full_name != "")
            .order_by(Patient.full_name)
            .all()
        )
        return [{"id": p.id, "name": p.full_name.strip()} for p in patients if p.full_name and p.full_name.strip()]


def _patient_list_keyboard(patients: list[dict], page: int) -> InlineKeyboardMarkup:
    total = len(patients)
    total_pages = max(1, (total + _PER_PAGE_PATIENTS - 1) // _PER_PAGE_PATIENTS)
    page = max(0, min(page, total_pages - 1))
    start = page * _PER_PAGE_PATIENTS
    page_items = patients[start: start + _PER_PAGE_PATIENTS]

    rows = []
    # Two-column layout for short names, single for long
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

    # Pagination row
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


# ─── Summary pagination helpers ────────────────────────────

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


def _load_reports(patient_id: int) -> list:
    """Loads reports for patient, newest first."""
    with SessionLocal() as s:
        reports = (
            s.query(Report)
            .filter(Report.patient_id == patient_id, Report.status != "deleted")
            .order_by(Report.report_date.desc())
            .all()
        )
        # Detach from session by converting to plain objects
        return list(reports)


def _build_summary_page(patient_name: str, reports: list, page: int) -> str:
    total = len(reports)
    total_pages = max(1, (total + _PER_PAGE_REPORTS - 1) // _PER_PAGE_REPORTS)
    page = max(0, min(page, total_pages - 1))
    start = page * _PER_PAGE_REPORTS
    page_reports = reports[start: start + _PER_PAGE_REPORTS]

    lines = [
        f"📋 **ملخص الحالة**",
        f"👤 المريض: {patient_name}",
        f"📊 عدد التقارير: {total}  |  الصفحة {page+1}/{total_pages}",
        "",
    ]
    for r in page_reports:
        lines.append(_build_report_entry(r))
    lines.append("────────────────────")
    return "\n".join(lines)


# ─── Handlers ─────────────────────────────────────────────

async def start_case_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_approved(update, context):
        return ConversationHandler.END

    patients = _load_all_patients()
    if not patients:
        await update.message.reply_text("⚠️ لا يوجد مرضى مسجلون في النظام.")
        return ConversationHandler.END

    context.user_data["cs_patients"] = patients
    context.user_data["cs_page"] = 0

    await update.message.reply_text(
        f"📋 **ملخص الحالة**\n\n"
        f"اختر مريضاً لعرض سجله الطبي ({len(patients)} مريض):",
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
        f"📋 **ملخص الحالة**\n\naختر مريضاً ({len(patients)} مريض):",
        reply_markup=_patient_list_keyboard(patients, page),
        parse_mode="Markdown",
    )
    return CS_SELECT_PATIENT


async def handle_patient_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    patient_id = int(q.data.split(":")[1])

    # Find name from snapshot
    patients = context.user_data.get("cs_patients") or _load_all_patients()
    patient_name = next((p["name"] for p in patients if p["id"] == patient_id), f"مريض #{patient_id}")

    reports = _load_reports(patient_id)
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
    context.user_data["cs_reports"] = [r.id for r in reports]  # store IDs only

    total_pages = max(1, (len(reports) + _PER_PAGE_REPORTS - 1) // _PER_PAGE_REPORTS)
    text = _build_summary_page(patient_name, reports, 0)

    await q.edit_message_text(
        text,
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
    reports = _load_reports(patient_id)
    total_pages = max(1, (len(reports) + _PER_PAGE_REPORTS - 1) // _PER_PAGE_REPORTS)

    text = _build_summary_page(patient_name, reports, page)
    await q.edit_message_text(
        text,
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
        f"📋 **ملخص الحالة**\n\naختر مريضاً ({len(patients)} مريض):",
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
                CallbackQueryHandler(handle_report_page,   pattern=r"^cs_rep:\d+:\d+$"),
                CallbackQueryHandler(handle_back_to_list,  pattern=r"^cs_back_to_list$"),
                CallbackQueryHandler(handle_cancel,        pattern=r"^cs_cancel$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_cancel, pattern=r"^cs_cancel$"),
        ],
        name="case_summary_conv",
        persistent=False,
    )
    app.add_handler(conv)
