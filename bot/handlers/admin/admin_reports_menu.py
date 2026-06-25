# bot/handlers/admin/admin_reports_menu.py
#
# Entry point for reporting system. Routes to either:
#   📊 Comprehensive Report (all patients in date range)
#   👤 Patient Report (single patient with filters)
#
# Replaces: ReplyKeyboard direct linking to admin_patient_report.py
#
# Dialog flow:
#   "🖨️ طباعة التقارير" button
#       ↓
#   Choose type: [📊 Comprehensive] [👤 Patient]
#       ↓ (branching delegates to appropriate handler)

from __future__ import annotations

import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
MENU_CHOOSE_TYPE = 800

_PFX = "report_menu"  # Note: patterns in universal_fallback are "report_menu:"

# ── Keyboard ──────────────────────────────────────────────────────────────────

def _type_kb() -> InlineKeyboardMarkup:
    """Choose report type."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقرير شامل", callback_data=f"{_PFX}:comp")],
        [InlineKeyboardButton("👤 تقرير مريض", callback_data=f"{_PFX}:patient")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Entry ─────────────────────────────────────────────────────────────────────

async def start_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry from ReplyKeyboard button '🖨️ طباعة التقارير'."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "🖨️ *نظام التقارير الاحترافي*\n\n"
        "اختر نوع التقرير المطلوب:",
        reply_markup=_type_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return MENU_CHOOSE_TYPE


# ── Callback handler ──────────────────────────────────────────────────────────

async def handle_type_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User picked type. Delegate to respective handler."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم إلغاء العملية.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    if data == f"{_PFX}:comp":
        # Delegate to comprehensive report handler
        context.user_data["_report_type"] = "comprehensive"
        from . import admin_comprehensive_report
        # Show period menu - this handler will take over from here
        await admin_comprehensive_report.show_period_menu(update, context)
        # End this conversation, comprehensive_report handler takes over
        return ConversationHandler.END

    if data == f"{_PFX}:patient":
        # Delegate to patient report handler (v2 with patient_selector)
        context.user_data["_report_type"] = "patient"
        from . import admin_patient_report_v2
        # Show patient selector and let patient_report_v2 handler take over
        result = await admin_patient_report_v2.show_patient_selector(update, context)
        # Return the state from patient_report_v2, don't end here
        # (This allows the ConversationHandler there to manage the flow)
        return result

    return MENU_CHOOSE_TYPE


# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel from any state."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register reports menu handler as entry point."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^🖨️ طباعة التقارير$"),
                start_reports_menu,
            ),
        ],
        states={
            MENU_CHOOSE_TYPE: [
                CallbackQueryHandler(handle_type_selection, pattern=rf"^{_PFX}:"),
            ],
            # Note: PR_SHOW_SELECTOR and other states from delegated handlers
            # are NOT defined here - those handlers manage their own states
        },
        fallbacks=[
            CallbackQueryHandler(cancel_reports_menu, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="reports_menu_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=False,  # Don't re-enter once delegated
    )
    app.add_handler(conv)
    logger.info("[reports_menu] ConversationHandler registered  button=🖨️ طباعة التقارير")
