# bot/handlers/admin/admin_comprehensive_report.py
#
# Comprehensive PDF report handler — all cases in a date range.
#
# Dialog flow:
#   📊 Comprehensive Report selected
#       ↓
#   Choose period: [Today] [Week] [Month] [3mo] [Year] [Custom]
#       ↓
#   Generate PDF and send
#
# Callback prefix: cr:
# States: CR_PERIOD → END
#
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler,
)

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
CR_PERIOD = 801

_PFX = "cr"  # callback prefix


# ── Keyboard ──────────────────────────────────────────────────────────────────

def _period_kb() -> InlineKeyboardMarkup:
    """Period selection for comprehensive report."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕐 اليوم", callback_data=f"{_PFX}:today")],
        [InlineKeyboardButton("📅 هذا الأسبوع", callback_data=f"{_PFX}:week")],
        [InlineKeyboardButton("📅 هذا الشهر", callback_data=f"{_PFX}:month")],
        [InlineKeyboardButton("📅 آخر 3 أشهر", callback_data=f"{_PFX}:3m")],
        [InlineKeyboardButton("📅 السنة كاملة", callback_data=f"{_PFX}:year")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{_PFX}:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Show period menu ──────────────────────────────────────────────────────────

async def show_period_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Show period selection menu."""
    try:
        await update.callback_query.edit_message_text(
            "📊 *التقرير الشامل*\n\n"
            "📅 اختر الفترة الزمنية:",
            reply_markup=_period_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        # Fallback: send as new message if edit fails
        await update.callback_query.message.reply_text(
            "📊 *التقرير الشامل*\n\n"
            "📅 اختر الفترة الزمنية:",
            reply_markup=_period_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    return CR_PERIOD


# ── Handle period selection ───────────────────────────────────────────────────

async def handle_period(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User selected a period. Generate and send report."""
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

    if data == f"{_PFX}:back":
        # Re-show menu from parent (admin_reports_menu)
        from . import admin_reports_menu
        return await admin_reports_menu.start_reports_menu(update, context)

    # Extract period code
    period_code = data.replace(f"{_PFX}:", "")
    start, end, period_label = _resolve_period(period_code)

    if not start or not end:
        return CR_PERIOD

    # Generate report
    await query.edit_message_text("⏳ جارٍ إعداد التقرير...", parse_mode=ParseMode.MARKDOWN)

    try:
        from services.reports_repository import get_reports, compute_stats
        from services.comprehensive_report_pdf import build_comprehensive_pdf

        # Fetch all reports in period
        reports = await get_reports(start, end)

        if not reports:
            await query.edit_message_text(
                f"⚠️ لا توجد حالات في الفترة:\n{period_label}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return CR_PERIOD

        # Compute stats
        stats = compute_stats(reports)

        # Build PDF
        pdf_buf = build_comprehensive_pdf(reports, stats, period_label)

        # Send PDF
        filename = f"Comprehensive_{start}_{end}.pdf"
        caption = (
            f"📊 *التقرير الشامل*\n"
            f"📅 {period_label}\n"
            f"📋 {stats['total']} حالة | {stats['unique_patients']} مريض | "
            f"{stats['unique_hospitals']} مستشفى"
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
            f"[comprehensive_report] PDF sent  period={period_code}"
            f"  cases={stats['total']}  patients={stats['unique_patients']}"
        )

    except Exception as exc:
        logger.exception("[comprehensive_report] PDF generation failed")
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


# ── Period resolution ─────────────────────────────────────────────────────────

def _resolve_period(code: str) -> tuple[date, date, str]:
    """Resolve period code to (start, end, label)."""
    today = date.today()

    if code == "today":
        return today, today, f"اليوم {today.strftime('%d/%m/%Y')}"

    if code == "week":
        start = today - timedelta(days=today.weekday())
        end = today
        return start, end, f"هذا الأسبوع ({start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')})"

    if code == "month":
        start = today.replace(day=1)
        end = today
        return start, end, f"هذا الشهر {today.strftime('%m/%Y')}"

    if code == "3m":
        start = today - timedelta(days=90)
        end = today
        return start, end, f"آخر 3 أشهر ({start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')})"

    if code == "year":
        start = today.replace(month=1, day=1)
        end = today
        return start, end, f"السنة {today.year}"

    return None, None, ""


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register comprehensive report handler (as fallback, not primary entry)."""
    # NOTE: This handler is delegated to by admin_reports_menu,
    #       NOT registered as a primary ConversationHandler entry point.
    #       We only add this fallback handler for period callbacks.
    app.add_handler(
        CallbackQueryHandler(handle_period, pattern=rf"^{_PFX}:(today|week|month|3m|year|back|cancel)$"),
    )
    logger.info("[comprehensive_report] Callback handlers registered  prefix=cr:")
