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
#   Select departments (all / single / multi-select)
#       ↓
#   Select procedure types (all / single / multi-select)
#       ↓
#   Select period (last month / 3mo / year / custom date range)
#       ↓
#   Generate PDF
#
# Callback prefix: pr2:
# Pattern: use result_router for patient_selector completion

from __future__ import annotations

import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from bot.shared_auth import is_admin
from shared.selectors.patient_selector import selector as patient_selector
from shared.selectors import result_router

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


# ── Keyboards ──────────────────────────────────────────────────────────────────

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


# ── Entry: Show patient selector ──────────────────────────────────────────────

async def show_patient_selector(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Open patient_selector when user chooses 👤 تقرير مريض."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    # Store report type in context
    context.user_data["_report_type"] = "patient"
    context.user_data["_patient_id"] = None
    context.user_data["_patient_name"] = None
    context.user_data["_pr_depts"] = None
    context.user_data["_pr_actions"] = None

    # Open patient selector
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)

    return PR_SHOW_SELECTOR


# ── Patient selected callback ─────────────────────────────────────────────────

async def _on_patient_selected(
    result, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Called by result_router when patient_selector completes.
    result: PatientSelectionResult
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
        await query.message.reply_text(
            f"👤 *{patient_name}*\n\n"
            f"📋 اختر الأقسام:",
            reply_markup=_depts_kb(patient_id, patient_name),
            parse_mode=ParseMode.MARKDOWN,
        )

    # Continue conversation in PR_DEPTS state
    context.user_data["_state"] = "depts"


# ── Callback handlers ─────────────────────────────────────────────────────────

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

    # Parse department choice
    parts = data.split(":")
    if len(parts) >= 3:
        action = parts[1]  # "all" or "select"
        patient_id = int(parts[2])

        if action == "all":
            context.user_data["_pr_depts"] = None  # None = all departments
        else:
            # TODO: implement multi-select UI for departments
            # For now, default to "all"
            context.user_data["_pr_depts"] = None

        # Show actions selection
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

    return PR_DEPTS


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

    # Parse action choice
    parts = data.split(":")
    if len(parts) >= 3:
        action = parts[1]  # "all" or "select"
        patient_id = int(parts[2]) if len(parts) > 2 else context.user_data.get("_patient_id")

        if data.startswith(f"{_PFX}:back_depts"):
            # Go back to departments
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

        if action == "all":
            context.user_data["_pr_actions"] = None  # None = all actions
        else:
            # TODO: implement multi-select UI for actions
            # For now, default to "all"
            context.user_data["_pr_actions"] = None

        # Show period selection
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

    return PR_ACTIONS


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

    # Parse period
    parts = data.split(":")
    if len(parts) >= 4:
        patient_id = int(parts[2])
        period_code = parts[3]  # "1m" | "3m" | "year" | "custom"

        if data.startswith(f"{_PFX}:back_actions"):
            # Go back to actions
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

        # Resolve period
        await query.edit_message_text("⏳ جارٍ إعداد التقرير...")

        try:
            from services.reports_repository import get_reports
            from services.patient_report_pdf import build_patient_pdf

            # Compute date range
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

            depts = context.user_data.get("_pr_depts")
            actions = context.user_data.get("_pr_actions")

            reports = await get_reports(
                start=period_start,
                end=today,
                patient_id=patient_id,
                depts=depts,
                actions=actions,
            )

            patient_name = context.user_data.get("_patient_name", "")

            if not reports:
                await query.edit_message_text(
                    f"⚠️ لا توجد تقارير للمريض *{patient_name}* في هذه الفترة.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return PR_PERIOD

            # Build PDF
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

            pdf_buf = build_patient_pdf(patient_data, reports, depts, period_label)

            # Send PDF
            filename = f"Patient_{patient_id}_{period_code}.pdf"
            caption = (
                f"👤 *تقرير المريض*\n"
                f"📝 {patient_name}\n"
                f"📅 {period_label}\n"
                f"📋 {len(reports)} تقرير"
            )

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
                f"period={period_code}  reports={len(reports)}"
            )

        except Exception as exc:
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

    return PR_PERIOD


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register patient report v2 handler with patient_selector integration."""

    # Register patient_selector completion callback
    result_router.register(_RKEY_PATIENT, _on_patient_selected)

    # Patient_selector.register_handler() should be called in handlers_registry
    # before this handler is registered.

    logger.info("[patient_report_v2] Registered with patient_selector integration")
