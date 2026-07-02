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
    """Calendar view for date selection - month view."""
    from calendar import monthcalendar, day_name

    today = date.today()
    buttons = []

    # Header with month and year
    month_names = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                   "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
    month_label = f"{month_names[today.month - 1]} {today.year}"
    buttons.append([InlineKeyboardButton(f"📅 {month_label}", callback_data=f"{_PFX}:dummy")])

    # Day headers (abbreviated)
    day_headers = ["إ", "ث", "ع", "خ", "ج", "س", "ح"]  # أول حرف من كل يوم
    buttons.append([InlineKeyboardButton(d, callback_data=f"{_PFX}:dummy") for d in day_headers])

    # Calendar days
    cal = monthcalendar(today.year, today.month)
    for week in cal:
        week_buttons = []
        for day_num in week:
            if day_num == 0:
                # Empty cell for days outside current month
                week_buttons.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:dummy"))
            else:
                d = date(today.year, today.month, day_num)
                # Mark today with ⭐
                label = f"⭐{day_num}" if d == today else str(day_num)
                callback = f"{_PFX}:date:{d.year}-{d.month}-{d.day}"
                week_buttons.append(InlineKeyboardButton(label, callback_data=callback))
        buttons.append(week_buttons)

    # Navigation and back buttons
    buttons.append([
        InlineKeyboardButton("⬅️ الشهر السابق", callback_data=f"{_PFX}:prev_month"),
        InlineKeyboardButton("الشهر التالي ➡️", callback_data=f"{_PFX}:next_month")
    ])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:back")])

    return InlineKeyboardMarkup(buttons)


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_upcoming_appointments(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point: show menu.

    ✅ يدعم الاستدعاء من زر نصي (update.message) ومن زر inline
    (update.callback_query) — لإتاحة الدخول من قائمة "🛠️ إدارة النظام"
    الجديدة دون كسر المسار النصي القديم.
    """
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()

    text = "📅 *المواعيد القادمة*\n\nاختر طريقة عرض المواعيد:"

    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            try:
                await query.edit_message_text(text, reply_markup=_menu_kb(), parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await query.message.reply_text(text, reply_markup=_menu_kb(), parse_mode=ParseMode.MARKDOWN)
        elif update.message:
            await update.message.reply_text(text, reply_markup=_menu_kb(), parse_mode=ParseMode.MARKDOWN)
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
    """Fetch and display appointments for a given date.

    ✅ يقرأ من Report.followup_date مباشرة (نفس المصدر المستخدم فعلياً
    وبنجاح في services/followup_reminder.py). النموذجان Followup
    و FollowupTracking فارغان دائماً في قاعدة البيانات الفعلية (لا يوجد
    أي مكان في المشروع يُدرج فيهما بشكل صحيح)، لذا لا يصح الاعتماد
    عليهما لعرض المواعيد — كل مواعيد المتابعة الحقيقية تُحفظ مباشرة على
    حقل followup_date في جدول التقارير عند إنشاء كل تقرير.
    """
    try:
        from db.session import SessionLocal
        from db.models import Report
        from datetime import datetime

        with SessionLocal() as s:
            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())

            appointments = (
                s.query(Report)
                .filter(
                    Report.followup_date >= start_of_day,
                    Report.followup_date <= end_of_day,
                )
                .order_by(Report.followup_date.asc())
                .all()
            )

        # Format date
        day_names = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        day_name = day_names[target_date.weekday()]
        date_label = f"{day_name} - {target_date.day}/{target_date.month}/{target_date.year}"

        if not appointments:
            text = (
                f"📭 *لا توجد مواعيد في* {date_label}\n\n"
                "💡 يمكنك:\n"
                "• اختيار يوم آخر من التقويم\n"
                "• العودة للقائمة الرئيسية"
            )
        else:
            text = f"📅 *المواعيد في* {date_label}\n"
            text += f"━━━━━━━━━━━━━━━━━━━━\n\n"

            for idx, apt in enumerate(appointments, 1):
                # ✅ الوقت: نُفضّل followup_time (نص مُدخل يدوياً) وإلا نأخذه من ساعة followup_date
                if apt.followup_time:
                    time_str = apt.followup_time
                elif apt.followup_date and (apt.followup_date.hour or apt.followup_date.minute):
                    time_str = apt.followup_date.strftime("%H:%M")
                else:
                    time_str = "—"

                patient_name = apt.patient_name or "مريض غير معروف"

                text += f"{idx}. 📌 *{time_str}* - {patient_name}\n"

                if apt.department:
                    text += f"   📋 {apt.department}\n"
                if apt.translator_name:
                    text += f"   👨‍🏫 {apt.translator_name}\n"
                if apt.followup_reason and apt.followup_reason not in ("لا يوجد", ""):
                    text += f"   💬 {apt.followup_reason}\n"

                text += "\n"

            text += f"━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 المجموع: {len(appointments)} موعد"

        try:
            await query.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            try:
                await query.message.reply_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass

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
            # ✅ نقطة دخول إضافية من قائمة "🛠️ إدارة النظام" الجديدة (admin_system_menu.py)
            CallbackQueryHandler(start_upcoming_appointments, pattern=r"^goto:appointments$"),
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
