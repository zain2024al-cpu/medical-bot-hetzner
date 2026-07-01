# bot/handlers/admin/admin_upcoming_appointments.py
#
# نظام عرض المواعيد القادمة
# يسمح بـ:
# 1. اختيار يوم من التقويم
# 2. عرض مواعيد غدا مباشرة

from __future__ import annotations

import logging
from datetime import date, timedelta, datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler,
    filters
)

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

# ── States ─────────────────────────────────────────────────────────────────────
(
    SHOW_MENU,
    SELECT_DATE,
) = range(2)

_PFX = "apt"  # appointments prefix


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """Menu for selecting date source."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اختيار من التقويم", callback_data=f"{_PFX}:calendar")],
        [InlineKeyboardButton("📆 مواعيد غدا", callback_data=f"{_PFX}:tomorrow")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


def _calendar_kb() -> InlineKeyboardMarkup:
    """7-day calendar for date selection."""
    today = date.today()
    buttons = []

    # Header: Current week
    buttons.append([InlineKeyboardButton("📅 اختر يوماً", callback_data=f"{_PFX}:dummy")])

    # 7 days starting from today
    for i in range(7):
        d = today + timedelta(days=i)
        day_name = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"][d.weekday()]
        label = f"{day_name}\n{d.day}/{d.month}"
        callback = f"{_PFX}:date:{d.year}-{d.month}-{d.day}"
        buttons.append([InlineKeyboardButton(label, callback_data=callback)])

    # Back button
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{_PFX}:back")])

    return InlineKeyboardMarkup(buttons)


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_upcoming_appointments(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point: show menu."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()

    try:
        await update.message.reply_text(
            "📅 *المواعيد القادمة*\n\n"
            "اختر طريقة عرض المواعيد:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[upcoming_apt] Failed to show menu: {exc}")

    return SHOW_MENU


async def handle_menu_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle menu selection."""
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

    if data == f"{_PFX}:calendar":
        # Show calendar
        try:
            await query.edit_message_text(
                "📅 *اختر اليوم*",
                reply_markup=_calendar_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return SELECT_DATE

    if data == f"{_PFX}:tomorrow":
        # Show tomorrow's appointments
        tomorrow = date.today() + timedelta(days=1)
        await _show_appointments(query, tomorrow)
        return ConversationHandler.END

    return SHOW_MENU


async def handle_date_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle calendar date selection."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:back":
        # Back to menu
        try:
            await query.edit_message_text(
                "📅 *المواعيد القادمة*\n\n"
                "اختر طريقة عرض المواعيد:",
                reply_markup=_menu_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return SHOW_MENU

    if data.startswith(f"{_PFX}:date:"):
        # Parse selected date
        try:
            date_str = data.split(":", 2)[2]
            year, month, day = map(int, date_str.split("-"))
            selected_date = date(year, month, day)
            await _show_appointments(query, selected_date)
        except Exception as exc:
            logger.error(f"[upcoming_apt] Failed to parse date: {exc}")
            try:
                await query.edit_message_text("❌ خطأ في معالجة التاريخ.")
            except Exception:
                pass

        return ConversationHandler.END

    return SELECT_DATE


async def _show_appointments(query, target_date: date) -> None:
    """Fetch and display appointments for a given date."""
    try:
        from db.session import SessionLocal
        from db.models import Schedule

        with SessionLocal() as s:
            # Query appointments for the target date
            appointments = (
                s.query(Schedule)
                .filter(
                    Schedule.appointment_date == target_date,
                    Schedule.patient_id.isnot(None),
                )
                .order_by(Schedule.appointment_time.asc())
                .all()
            )

        # Format date
        day_name = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"][
            target_date.weekday()
        ]
        date_label = f"{day_name} - {target_date.day}/{target_date.month}/{target_date.year}"

        if not appointments:
            text = f"📭 *لا توجد مواعيد في* {date_label}"
        else:
            text = f"📅 *المواعيد في* {date_label}\n\n"
            for apt in appointments:
                time_str = apt.appointment_time.strftime("%H:%M") if apt.appointment_time else "—"
                patient_name = apt.patient_name or "مريض غير معروف"
                status = "✅" if apt.is_completed else "⏳"

                text += f"{status} *{time_str}* - {patient_name}\n"

                if apt.department:
                    text += f"   📋 القسم: {apt.department}\n"
                if apt.notes:
                    text += f"   📝 ملاحظات: {apt.notes}\n"

                text += "\n"

        try:
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
            )

    except Exception as exc:
        logger.error(f"[upcoming_apt] Failed to show appointments: {exc}")
        try:
            await query.edit_message_text("❌ خطأ في جلب المواعيد.")
        except Exception:
            pass


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel handler."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register upcoming appointments handler."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^📅 المواعيد القادمة$"),
                start_upcoming_appointments,
            ),
        ],
        states={
            SHOW_MENU: [
                CallbackQueryHandler(handle_menu_choice, pattern=rf"^{_PFX}:"),
            ],
            SELECT_DATE: [
                CallbackQueryHandler(handle_date_selection, pattern=rf"^{_PFX}:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="upcoming_appointments_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(conv)
    logger.info("[upcoming_appointments] ConversationHandler registered")
