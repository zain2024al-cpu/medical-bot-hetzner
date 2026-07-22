# bot/handlers/admin/admin_patient_report_v2.py
#
# Patient Report Handler — uses shared patient_selector (no manual search).
#
# Dialog flow:
#   👤 Patient Report selected
#       ↓
#   Show patient_selector (with search, filtering, pagination)
#       ↓
#   User picks patient
#       ↓
#   Select departments (all / multi-select — options scoped to this patient's own reports)
#       ↓
#   Select procedure types (all / multi-select — scoped to patient + selected departments)
#       ↓
#   Select period (last month / 3mo / year / custom date range via calendar)
#       ↓
#   Generate PDF
#
# Callback prefix: pr2:
# Pattern: use result_router for patient_selector completion

from __future__ import annotations

import asyncio
import logging
from calendar import monthrange
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

from bot.shared_auth import is_admin
from shared.selectors.patient_selector import selector as patient_selector
from shared.selectors import result_router
from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

# ── Route keys ─────────────────────────────────────────────────────────────────
_RKEY_PATIENT = "admin.patient_report.patient"

# ── States ─────────────────────────────────────────────────────────────────────
(
    PR_SHOW_SELECTOR,
    PR_DEPTS,
    PR_ACTIONS,
    PR_PERIOD,
) = range(4)

_PFX = "pr2"

_MONTH_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس",    4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو",   8: "أغسطس",
    9: "سبتمبر",10: "أكتوبر",11: "نوفمبر", 12: "ديسمبر",
}


# ── Keyboards: entry screens (unchanged) ────────────────────────────────────────

def _depts_kb(patient_id: int, patient_name: str) -> InlineKeyboardMarkup:
    """Departments selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ كل الأقسام",
         callback_data=f"{_PFX}:depts:all:{patient_id}")],
        [InlineKeyboardButton("📋 اختيار محدد",
         callback_data=f"{_PFX}:depts:select:{patient_id}")],
        [InlineKeyboardButton("⬅️ اختيار مريض آخر",
         callback_data=f"{_PFX}:back_patient")],
        [InlineKeyboardButton("❌ إلغاء",
         callback_data=f"{_PFX}:cancel")],
    ])


def _actions_kb(patient_id: int) -> InlineKeyboardMarkup:
    """Procedure types selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ كل الإجراءات",
         callback_data=f"{_PFX}:actions:all:{patient_id}")],
        [InlineKeyboardButton("📋 اختيار محدد",
         callback_data=f"{_PFX}:actions:select:{patient_id}")],
        [InlineKeyboardButton("⬅️ اختيار أقسام آخر",
         callback_data=f"{_PFX}:back_depts:{patient_id}")],
        [InlineKeyboardButton("❌ إلغاء",
         callback_data=f"{_PFX}:cancel")],
    ])


def _period_kb(patient_id: int) -> InlineKeyboardMarkup:
    """Period selection keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 آخر شهر",
         callback_data=f"{_PFX}:period:{patient_id}:1m")],
        [InlineKeyboardButton("📅 آخر 3 أشهر",
         callback_data=f"{_PFX}:period:{patient_id}:3m")],
        [InlineKeyboardButton("📅 السنة الحالية",
         callback_data=f"{_PFX}:period:{patient_id}:year")],
        [InlineKeyboardButton("📅 من → إلى (Custom)",
         callback_data=f"{_PFX}:period:{patient_id}:custom")],
        [InlineKeyboardButton("⬅️ اختيار إجراءات أخرى",
         callback_data=f"{_PFX}:back_actions:{patient_id}")],
        [InlineKeyboardButton("❌ إلغاء",
         callback_data=f"{_PFX}:cancel")],
    ])


# ── Generic multi-select keyboard (مُعاد استخدام نفس فكرة admin_comprehensive_report) ─

def _multi_select_kb(
    options: list[dict], selected: set[str], cb: str, patient_id: int, page: int,
) -> InlineKeyboardMarkup:
    per_page = 8
    total_pages = max(1, (len(options) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = options[page * per_page: (page + 1) * per_page]

    buttons = []
    for local_idx, opt in enumerate(page_items):
        global_idx = page * per_page + local_idx
        checked = "✅" if opt["name"] in selected else "◻️"
        label = f"{checked} {opt['name']} ({opt['count']})"
        if len(label) > 60:
            label = label[:57] + "…"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"{_PFX}:{cb}:toggle:{patient_id}:{global_idx}",
        )])

    nav = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{_PFX}:{cb}:page:{patient_id}:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data=f"{_PFX}:noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{_PFX}:{cb}:page:{patient_id}:{page + 1}"))
    if nav:
        buttons.append(nav)

    n = len(selected)
    done_label = f"✅ متابعة ({n} محدد)" if n else "✅ متابعة (لا شيء محدد = الكل)"
    buttons.append([InlineKeyboardButton(done_label, callback_data=f"{_PFX}:{cb}:done:{patient_id}")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Entry: Show patient selector ──────────────────────────────────────────────

async def show_patient_selector(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Entry point when user chooses 👤 تقرير مريض.
    Returns PR_SHOW_SELECTOR to signal ConversationHandler is now active.
    """
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    # Initialize context for patient report flow
    context.user_data["_report_type"] = "patient"
    context.user_data["_patient_id"] = None
    context.user_data["_patient_name"] = None
    context.user_data["_pr_depts"] = None
    context.user_data["_pr_actions"] = None
    context.user_data["_pr_dept_options"] = []
    context.user_data["_pr_selected_depts"] = set()
    context.user_data["_pr_action_options"] = []
    context.user_data["_pr_selected_actions"] = set()
    context.user_data["_pr_cal_start"] = None

    # Open patient selector
    # Note: result_router will call _on_patient_selected when done
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)

    # Tell ConversationHandler we're now in PR_SHOW_SELECTOR state
    # and waiting for patient_selector to complete
    return PR_SHOW_SELECTOR


# ── Patient selected callback ─────────────────────────────────────────────────

async def _on_patient_selected(
    result, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Called by result_router when patient_selector completes.
    result: PatientSelectionResult

    This callback is NOT a ConversationHandler state handler.
    It only handles the result and updates the message.
    The ConversationHandler remains inactive until a callback
    with pattern pr2:* is received.
    """
    if result.cancelled:
        # User pressed back/cancel in patient_selector
        try:
            await update.callback_query.edit_message_text(
                "✅ تم الإلغاء.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        # Clear context for clean state
        context.user_data.clear()
        return

    # Patient selected
    patient_id = result.id
    patient_name = result.name

    context.user_data["_patient_id"] = patient_id
    context.user_data["_patient_name"] = patient_name

    # Show departments selection
    query = update.callback_query
    try:
        await query.edit_message_text(
            f"👤 *{patient_name}*\n\n"
            f"📋 اختر الأقسام:",
            reply_markup=_depts_kb(patient_id, patient_name),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        try:
            await query.message.reply_text(
                f"👤 *{patient_name}*\n\n"
                f"📋 اختر الأقسام:",
                reply_markup=_depts_kb(patient_id, patient_name),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    # Set state for ConversationHandler to enter PR_DEPTS
    context._conversation_state = PR_DEPTS


# ── Departments: multi-select screens ───────────────────────────────────────────

async def _show_depts_multiselect(query, context: ContextTypes.DEFAULT_TYPE, patient_id: int, page: int = 0) -> None:
    options = context.user_data.get("_pr_dept_options") or []
    if not options:
        from services.reports_repository import get_patient_departments
        options = await get_patient_departments(patient_id)
        context.user_data["_pr_dept_options"] = options

    if not options:
        # ✅ لا توجد أقسام لهذا المريض إطلاقاً — نتخطى الشاشة تلقائياً
        context.user_data["_pr_depts"] = None
        try:
            await query.edit_message_text(
                f"👤 *{context.user_data.get('_patient_name', '')}*\n\n📋 اختر الإجراءات:",
                reply_markup=_actions_kb(patient_id), parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return

    selected = context.user_data.get("_pr_selected_depts", set())
    try:
        await query.edit_message_text(
            f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
            f"📋 اختر الأقسام المطلوبة (يظهر عدد التقارير بجانب كل قسم):",
            reply_markup=_multi_select_kb(options, selected, "depts", patient_id, page),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[patient_report_v2] depts multiselect render failed: {exc}")


# ── Actions: multi-select screens ────────────────────────────────────────────────

async def _show_actions_multiselect(query, context: ContextTypes.DEFAULT_TYPE, patient_id: int, page: int = 0) -> None:
    options = context.user_data.get("_pr_action_options") or []
    if not options:
        from services.reports_repository import get_patient_actions
        depts = context.user_data.get("_pr_depts")  # None = all
        options = await get_patient_actions(patient_id, depts=depts)
        context.user_data["_pr_action_options"] = options

    if not options:
        context.user_data["_pr_actions"] = None
        try:
            await query.edit_message_text(
                f"👤 *{context.user_data.get('_patient_name', '')}*\n\n📅 اختر الفترة الزمنية:",
                reply_markup=_period_kb(patient_id), parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return

    selected = context.user_data.get("_pr_selected_actions", set())
    try:
        await query.edit_message_text(
            f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
            f"📋 اختر أنواع الإجراءات (يظهر عدد التقارير بجانب كل نوع):",
            reply_markup=_multi_select_kb(options, selected, "actions", patient_id, page),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[patient_report_v2] actions multiselect render failed: {exc}")


# ── Custom date-range calendar (نفس فكرة admin_comprehensive_report، بادئة pr2:) ──

def _calendar_kb(year: int, month: int, step: str, patient_id: int) -> InlineKeyboardMarkup:
    from calendar import monthcalendar

    today = date.today()
    buttons = []

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    nav_row = [
        InlineKeyboardButton("◀️", callback_data=f"{_PFX}:cal:{step}:{patient_id}:navmonth:{prev_year}-{prev_month}"),
        InlineKeyboardButton(f"{_MONTH_AR[month]} {year}", callback_data=f"{_PFX}:noop"),
    ]
    if (year, month) < (today.year, today.month):
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"{_PFX}:cal:{step}:{patient_id}:navmonth:{next_year}-{next_month}"))
    buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(d, callback_data=f"{_PFX}:noop") for d in ["إ", "ث", "ع", "خ", "ج", "س", "ح"]])

    for week in monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:noop"))
                continue
            d = date(year, month, day_num)
            if d > today:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:noop"))
            else:
                label = f"⭐{day_num}" if d == today else str(day_num)
                row.append(InlineKeyboardButton(
                    label, callback_data=f"{_PFX}:cal:{step}:{patient_id}:select:{d.isoformat()}",
                ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("⬅️ رجوع لاختيار الفترة", callback_data=f"{_PFX}:back_actions:{patient_id}")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _show_calendar(
    query, context: ContextTypes.DEFAULT_TYPE, step: str, patient_id: int,
    year: int | None = None, month: int | None = None,
) -> None:
    today = date.today()
    year = year or today.year
    month = month or today.month
    label = "تاريخ البداية" if step == "start" else "تاريخ النهاية"
    patient_name = context.user_data.get("_patient_name", "")
    try:
        await query.edit_message_text(
            f"👤 *{patient_name}*\n\n📆 فترة مخصصة — اختر {label}:",
            reply_markup=_calendar_kb(year, month, step, patient_id),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[patient_report_v2] calendar render failed: {exc}")


# ── Callback handlers ─────────────────────────────────────────────────────────

@require_admin
async def handle_departments(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User selected departments (all or specific)."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    if data.startswith(f"{_PFX}:back_patient"):
        # Re-open patient selector
        context.user_data["_patient_id"] = None
        context.user_data["_patient_name"] = None
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)
        return PR_SHOW_SELECTOR

    parts = data.split(":")
    # pr2:depts:{action}:{patient_id}[:extra]
    if len(parts) >= 4:
        action = parts[2]

        if action in ("toggle", "page", "done"):
            patient_id = int(parts[3])
            if action == "toggle":
                idx = int(parts[4])
                options = context.user_data.get("_pr_dept_options") or []
                if 0 <= idx < len(options):
                    name = options[idx]["name"]
                    sel = context.user_data.setdefault("_pr_selected_depts", set())
                    sel.symmetric_difference_update({name})
                await _show_depts_multiselect(query, context, patient_id)
            elif action == "page":
                page = int(parts[4])
                await _show_depts_multiselect(query, context, patient_id, page=page)
            elif action == "done":
                sel = context.user_data.get("_pr_selected_depts") or set()
                context.user_data["_pr_depts"] = list(sel) if sel else None
                context.user_data["_pr_action_options"] = []  # reset — scope changed
                context.user_data["_pr_selected_actions"] = set()
                await _show_actions_multiselect(query, context, patient_id)
            return PR_ACTIONS if action == "done" else PR_DEPTS

        # action == "all" or "select"
        patient_id = int(parts[3])

        if action == "all":
            context.user_data["_pr_depts"] = None  # None = all departments
            try:
                await query.edit_message_text(
                    f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
                    f"📋 اختر الإجراءات:",
                    reply_markup=_actions_kb(patient_id),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass
            return PR_ACTIONS

        # action == "select" → افتح شاشة الاختيار المتعدد الفعلية
        context.user_data["_pr_selected_depts"] = set()
        context.user_data["_pr_dept_options"] = []
        await _show_depts_multiselect(query, context, patient_id)
        return PR_DEPTS

    return PR_DEPTS


@require_admin
async def handle_actions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User selected procedure types (all or specific)."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    if data.startswith(f"{_PFX}:back_depts"):
        patient_id = int(data.split(":")[-1])
        try:
            await query.edit_message_text(
                f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
                f"📋 اختر الأقسام:",
                reply_markup=_depts_kb(patient_id, context.user_data.get("_patient_name", "")),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return PR_DEPTS

    parts = data.split(":")
    if len(parts) >= 4:
        action = parts[2]

        if action in ("toggle", "page", "done"):
            patient_id = int(parts[3])
            if action == "toggle":
                idx = int(parts[4])
                options = context.user_data.get("_pr_action_options") or []
                if 0 <= idx < len(options):
                    name = options[idx]["name"]
                    sel = context.user_data.setdefault("_pr_selected_actions", set())
                    sel.symmetric_difference_update({name})
                await _show_actions_multiselect(query, context, patient_id)
            elif action == "page":
                page = int(parts[4])
                await _show_actions_multiselect(query, context, patient_id, page=page)
            elif action == "done":
                sel = context.user_data.get("_pr_selected_actions") or set()
                context.user_data["_pr_actions"] = list(sel) if sel else None
                try:
                    await query.edit_message_text(
                        f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
                        f"📅 اختر الفترة الزمنية:",
                        reply_markup=_period_kb(patient_id), parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception:
                    pass
                return PR_PERIOD
            return PR_ACTIONS

        action_val = action  # "all" or "select"
        patient_id = int(parts[3])

        if action_val == "all":
            context.user_data["_pr_actions"] = None  # None = all actions
            try:
                await query.edit_message_text(
                    f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
                    f"📅 اختر الفترة الزمنية:",
                    reply_markup=_period_kb(patient_id),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass
            return PR_PERIOD

        # action_val == "select" → افتح شاشة الاختيار المتعدد الفعلية
        context.user_data["_pr_selected_actions"] = set()
        context.user_data["_pr_action_options"] = []
        await _show_actions_multiselect(query, context, patient_id)
        return PR_ACTIONS

    return PR_ACTIONS


async def _finalize_and_generate(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    query, patient_id: int, period_start: date, period_end: date, period_label: str,
) -> int:
    """Fetch reports for the resolved period + filters, build PDF, and send it."""
    await query.edit_message_text("⏳ جارٍ إعداد التقرير...")

    try:
        from services.reports_repository import get_reports
        from services.healthcare_records_repository import get_healthcare_records_for_patient
        from services.patient_report_pdf import build_patient_pdf

        depts = context.user_data.get("_pr_depts")
        actions = context.user_data.get("_pr_actions")

        reports = await get_reports(
            start=period_start,
            end=period_end,
            patient_id=patient_id,
            depts=depts,
            actions=actions,
        )

        # ✅ سجلات وحدة الرعاية الصحية (منفصلة تماماً عن تقارير المترجم) —
        # نفس فترة التقرير المختارة أعلاه، تُضاف كقسم إضافي في نفس ملف الـ PDF.
        healthcare_records = await get_healthcare_records_for_patient(
            patient_id=patient_id, start=period_start, end=period_end,
        )

        patient_name = context.user_data.get("_patient_name", "")

        # ✅ لا نتوقف إلا إذا كان كلا المصدرين فارغين — مريض قد لا يملك أي
        # تقرير مترجم لكن له سجلات رعاية صحية (أو العكس)، وكلاهما يستحق تقريراً.
        if not reports and not healthcare_records:
            await query.edit_message_text(
                f"⚠️ لا توجد تقارير أو سجلات رعاية صحية للمريض *{patient_name}* في هذه الفترة/المعايير.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return PR_PERIOD

        from db.session import SessionLocal
        from db.models import Patient

        with SessionLocal() as s:
            patient_obj = s.query(Patient).filter_by(id=patient_id).first()
            patient_data = {
                "id": patient_id,
                "name": patient_name,
                "file_number": getattr(patient_obj, "file_number", "") if patient_obj else "",
                "nationality": getattr(patient_obj, "nationality", "") if patient_obj else "",
                "disease": getattr(patient_obj, "disease", "") if patient_obj else "",
            }

        # ✅ بناء PDF عمل CPU متزامن (matplotlib + reportlab) — ينقل لخيط منفصل
        # حتى لا يُجمِّد حلقة أحداث البوت الوحيدة لكل المستخدمين أثناء البناء.
        pdf_buf = await asyncio.to_thread(
            build_patient_pdf, patient_data, reports, depts, period_label,
            healthcare_records=healthcare_records,
            period_start=period_start, period_end=period_end,
        )

        filename = f"Patient_{patient_id}_{period_start}_{period_end}.pdf"
        caption = (
            f"👤 *تقرير المريض*\n"
            f"📝 {patient_name}\n"
            f"📅 {period_label}\n"
            f"📋 {len(reports)} تقرير"
        )
        if healthcare_records:
            caption += f"\n🏥 {len(healthcare_records)} سجل رعاية صحية"

        try:
            await query.delete_message()
        except Exception:
            pass

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buf,
            filename=filename,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )

        logger.info(
            f"[patient_report_v2] PDF sent  patient_id={patient_id}  "
            f"period={period_label}  reports={len(reports)}"
        )

    except Exception:
        logger.exception("[patient_report_v2] PDF generation failed")
        try:
            await query.edit_message_text(
                "❌ حدث خطأ أثناء إعداد التقرير.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    finally:
        context.user_data.clear()

    return ConversationHandler.END


@require_admin
async def handle_period(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User selected time period."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    if data == f"{_PFX}:noop":
        return PR_PERIOD

    if data.startswith(f"{_PFX}:back_actions"):
        patient_id = int(data.split(":")[-1])
        try:
            await query.edit_message_text(
                f"👤 *{context.user_data.get('_patient_name', '')}*\n\n"
                f"📋 اختر الإجراءات:",
                reply_markup=_actions_kb(patient_id),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return PR_ACTIONS

    # ── Custom date-range calendar callbacks: pr2:cal:{step}:{patient_id}:{sub}[:extra] ─
    if data.startswith(f"{_PFX}:cal:"):
        parts = data.split(":")
        step = parts[2]
        patient_id = int(parts[3])
        sub = parts[4]

        if sub == "navmonth":
            y_str, m_str = parts[5].split("-")
            await _show_calendar(query, context, step=step, patient_id=patient_id, year=int(y_str), month=int(m_str))
        elif sub == "select":
            selected = date.fromisoformat(parts[5])
            if step == "start":
                context.user_data["_pr_cal_start"] = selected
                await _show_calendar(query, context, step="end", patient_id=patient_id, year=selected.year, month=selected.month)
            else:
                start_d = context.user_data.get("_pr_cal_start") or selected
                end_d = selected
                if end_d < start_d:
                    start_d, end_d = end_d, start_d
                end_d = min(end_d, date.today())
                period_label = f"{start_d.strftime('%d/%m/%Y')} إلى {end_d.strftime('%d/%m/%Y')}"
                return await _finalize_and_generate(update, context, query, patient_id, start_d, end_d, period_label)
        return PR_PERIOD

    # Parse period: pr2:period:{patient_id}:{period_code}
    parts = data.split(":")
    if len(parts) >= 4:
        patient_id = int(parts[2])
        period_code = parts[3]  # "1m" | "3m" | "year" | "custom"
    else:
        patient_id = context.user_data.get("_patient_id")
        period_code = "1m"

    if period_code == "custom":
        context.user_data["_pr_cal_start"] = None
        await _show_calendar(query, context, step="start", patient_id=patient_id)
        return PR_PERIOD

    today = date.today()
    if period_code == "1m":
        period_start = today - timedelta(days=30)
        period_label = "آخر شهر"
    elif period_code == "3m":
        period_start = today - timedelta(days=90)
        period_label = "آخر 3 أشهر"
    elif period_code == "year":
        period_start = today.replace(month=1, day=1)
        period_label = f"السنة {today.year}"
    else:
        period_start = date(1900, 1, 1)
        period_label = "كل الفترة"

    return await _finalize_and_generate(update, context, query, patient_id, period_start, today, period_label)


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """
    Register patient report v2 as regular CallbackQueryHandlers (no ConversationHandler).

    This avoids conflicts with admin_reports_menu's ConversationHandler.
    State is managed through context.user_data instead.
    """

    # Register patient_selector completion callback
    result_router.register(_RKEY_PATIENT, _on_patient_selected)

    # Register all pr2:* callbacks as simple handlers (group 0, low priority)
    # This allows them to be called from anywhere, including from within
    # another ConversationHandler.
    #
    # ✅ ملاحظة إصلاح: الأنماط الأصلية كانت تُسجَّل بادئة واحدة فقط لكل معالج
    # (^pr2:depts:, ^pr2:actions:, ^pr2:period:) بينما كل دالة تحتوي فعلياً
    # على كود لمعالجة زر "رجوع" بـcallback_data مختلف (pr2:back_patient،
    # pr2:back_depts:*، pr2:back_actions:*) لا يطابق نمط تسجيلها — أي أن
    # أزرار "⬅️" الثلاثة كانت معطَّلة تماماً منذ إنشاء الملف. تم توسيع كل
    # نمط هنا ليغطي كل الحالات التي تعالجها الدالة فعلياً.
    app.add_handler(
        CallbackQueryHandler(
            handle_departments,
            pattern=rf"^{_PFX}:(depts:|back_patient)",
        ),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_actions,
            pattern=rf"^{_PFX}:(actions:|back_depts:)",
        ),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(
            handle_period,
            pattern=rf"^{_PFX}:(period:|cal:|back_actions:|noop$)",
        ),
        group=0,
    )

    logger.info("[patient_report_v2] CallbackQueryHandlers registered (no ConversationHandler)")
