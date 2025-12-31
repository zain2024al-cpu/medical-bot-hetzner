# =============================
# date_time_handlers.py
# معالجات التاريخ والوقت
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ChatType
import logging
import calendar
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from .states import (
    STATE_SELECT_DATE, STATE_SELECT_DATE_TIME, STATE_SELECT_PATIENT,
    R_DATE, R_DATE_TIME
)
from .navigation import nav_push
from .utils import (
    MONTH_NAMES_AR, WEEKDAYS_AR, format_time_12h, 
    _build_hour_keyboard, _build_minute_keyboard, _chunked,
    get_step_back_button
)

logger = logging.getLogger(__name__)

# Imports المشتركة
try:
    from bot.shared_auth import ensure_approved
except ImportError:
    ensure_approved = lambda *a, **kw: True


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة تقرير جديد"""
    # تسجيل تفصيلي للمساعدة في التشخيص
    logger.info("=" * 80)
    logger.info("🚀 start_report CALLED")
    logger.info(f"   User ID: {update.effective_user.id if update.effective_user else 'N/A'}")
    logger.info(f"   Chat Type: {update.effective_chat.type if update.effective_chat else 'N/A'}")
    logger.info(f"   Message Text: {update.message.text if update.message and update.message.text else 'N/A'}")
    logger.info("=" * 80)
    
    try:
        # ✅ منع إضافة التقارير من المجموعات - السماح فقط في الدردشة الخاصة
        chat = update.effective_chat
        if chat and chat.type not in [ChatType.PRIVATE]:
            logger.warning(f"⚠️ محاولة إضافة تقرير من {chat.type} - تم رفضها")
            if update.message:
                await update.message.reply_text(
                    "⚠️ **لا يمكن إضافة التقارير من المجموعة!**\n\n"
                    "💡 يرجى استخدام الدردشة الخاصة مع البوت لإضافة التقارير.\n\n"
                    "📋 للبدء، اضغط على /start في الدردشة الخاصة معي.",
                    parse_mode="Markdown"
                )
            return ConversationHandler.END
        
        if not await ensure_approved(update, context):
            return ConversationHandler.END

        # ✅ تهيئة Navigation Stack
        nav_push(context, STATE_SELECT_DATE)
        context.user_data['_conversation_state'] = STATE_SELECT_DATE

        # تهيئة البيانات
        context.user_data["report_tmp"] = {
            "action_type": None
        }
        
        # ✅ تنظيف أي بيانات من التقرير الأولي لضمان عدم التعارض
        context.user_data.pop("initial_case_search", None)
        context.user_data['_current_search_type'] = 'patient'  # تعيين نوع البحث الافتراضي

        # تحديث الـ conversation state
        context.user_data['_conversation_state'] = STATE_SELECT_DATE

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 إدخال التاريخ الحالي", callback_data="date:now")],
            [InlineKeyboardButton("📅 إدخال من التقويم", callback_data="date:calendar")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])

        await update.message.reply_text(
            "📅 **إضافة تقرير جديد**\n\n"
            "اختر طريقة إدخال التاريخ:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        logger.info("start_report completed successfully")
        return STATE_SELECT_DATE
    except Exception as e:
        logger.error(f"Error in start_report: {e}", exc_info=True)
        if update and update.message:
            try:
                await update.message.reply_text("❌ حدث خطأ في بدء العملية، يرجى المحاولة مرة أخرى.")
            except:
                pass
        return ConversationHandler.END


async def render_date_selection(message, context):
    """عرض شاشة اختيار التاريخ - rendering فقط"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 إدخال التاريخ الحالي", callback_data="date:now")],
        [InlineKeyboardButton("📅 إدخال من التقويم", callback_data="date:calendar")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "📅 **إضافة تقرير جديد** (الخطوة 1 من 5)\n\n"
        "اختر طريقة إدخال التاريخ:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


def _build_main_calendar_markup(year: int, month: int):
    """بناء تقويم التاريخ الرئيسي للتقرير"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []

    # تقويم الشهر مع أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"main_cal_prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"main_cal_next:{year}-{month:02d}"),
    ])
    keyboard.append([InlineKeyboardButton(day, callback_data="noop") for day in WEEKDAYS_AR])

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    # عدم عرض التواريخ القديمة - فقط من اليوم فصاعداً
                    if date_obj < today:
                        row.append(InlineKeyboardButton(" ", callback_data="noop"))
                    else:
                        # تمييز اليوم بعلامة خاصة
                        if date_obj == today:
                            row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"main_cal_day:{date_str}"))
                        else:
                            row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"main_cal_day:{date_str}"))
                except Exception:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    keyboard.append([
        get_step_back_button(),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"📅 **اختيار تاريخ التقرير**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)


async def _render_main_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم التاريخ الرئيسي"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month

    text, markup = _build_main_calendar_markup(year, month)
    data_tmp["main_calendar_year"] = year
    data_tmp["main_calendar_month"] = month

    # التحقق إذا كان message أو query
    if hasattr(message_or_query, 'edit_message_text'):
        # query object
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        # message object
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def handle_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التاريخ"""
    from .navigation_helpers import handle_cancel_navigation
    from .patient_handlers import show_patient_selection
    
    query = update.callback_query
    await query.answer()

    # معالجة زر الإلغاء
    if query.data == "nav:cancel":
        return await handle_cancel_navigation(update, context)

    if query.data == "date:now":
        # استخدام توقيت الهند مباشرة (IST = UTC+5:30)
        try:
            tz = ZoneInfo("Asia/Kolkata")  # توقيت الهند مباشرة
            now = datetime.now(tz)
        except Exception as e:
            # في حالة الخطأ، استخدام UTC+5:30 يدوياً
            ist = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(timezone.utc).astimezone(ist)

        # حفظ الوقت بتوقيت الهند
        context.user_data["report_tmp"]["report_date"] = now
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DATE)

        # عرض التاريخ والوقت بتوقيت الهند
        days_ar = {
            0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس',
            4: 'الجمعة', 5: 'السبت', 6: 'الأحد'
        }
        day_name = days_ar.get(now.weekday(), '')

        # استخدام format_time_12h لعرض الوقت بصيغة 12 ساعة بتوقيت الهند
        time_str = format_time_12h(now)

        # ✅ حفظ الـ state في سجل التنقل قبل الانتقال للمريض
        nav_push(context, STATE_SELECT_PATIENT)
        context.user_data['_conversation_state'] = STATE_SELECT_PATIENT

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ الحالي**\n\n"
            f"📅 **التاريخ:**\n"
            f"{now.strftime('%d')} {MONTH_NAMES_AR.get(now.month, now.month)} {now.year} ({day_name})\n\n"
            f"🕐 **الوقت (بتوقيت الهند):**\n"
            f"{time_str}"
        )
        await show_patient_selection(query.message, context)
        return STATE_SELECT_PATIENT

    elif query.data == "date:calendar":
        # عرض التقويم مباشرة
        await query.edit_message_text("📅 جارٍ تحميل التقويم...")
        await _render_main_calendar(query.message, context)
        return STATE_SELECT_DATE


async def handle_main_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم التاريخ الرئيسي"""
    from .navigation_helpers import handle_cancel_navigation
    
    query = update.callback_query
    await query.answer()

    # معالجة زر الإلغاء
    if query.data == "nav:cancel":
        return await handle_cancel_navigation(update, context)

    # query.data format: "main_cal_prev:2025-11" or "main_cal_next:2025-11"
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return R_DATE

    action_part = parts[0]  # "main_cal_prev" or "main_cal_next"
    date_str = parts[1]  # "2025-11"

    # استخراج action من action_part
    if "prev" in action_part:
        action = "prev"
    elif "next" in action_part:
        action = "next"
    else:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return R_DATE

    year, month = map(int, date_str.split("-"))

    if action == "prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif action == "next":
        month += 1
        if month > 12:
            month = 1
            year += 1

    await _render_main_calendar(query, context, year, month)
    return R_DATE


async def handle_main_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ من التقويم الرئيسي"""
    from .navigation_helpers import handle_cancel_navigation
    
    query = update.callback_query
    await query.answer()

    # معالجة زر الإلغاء
    if query.data == "nav:cancel":
        return await handle_cancel_navigation(update, context)

    date_str = query.data.split(":", 1)[1]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        context.user_data["report_tmp"]["_pending_date"] = dt
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DATE)
        
        # لا نحفظ state هنا لأننا ما زلنا في اختيار التاريخ (نحتاج اختيار الوقت أولاً)

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{date_str}\n\n"
            f"🕐 **الوقت**\n\n"
            f"اختر الساعة:",
            reply_markup=_build_hour_keyboard(),
            parse_mode="Markdown"
        )
        return R_DATE_TIME
    except ValueError:
        await query.answer("⚠️ خطأ في التاريخ", show_alert=True)
        return R_DATE


async def handle_date_time_back_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الرجوع لتغيير الساعة"""
    query = update.callback_query
    await query.answer()
    
    # حذف الساعة المختارة مؤقتاً
    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp.pop("_pending_date_hour", None)
    
    # عرض لوحة اختيار الساعات
    keyboard = _build_hour_keyboard()
    await query.edit_message_text(
        "🕐 **اختيار الساعة**\n\nاختر الساعة من القائمة:",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return R_DATE_TIME


async def handle_date_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الساعة عند إدخال التاريخ يدوياً"""
    query = update.callback_query
    await query.answer()
    hour = query.data.split(":", 1)[1]

    # إذا كان "أوقات أخرى"، نعرض جميع الساعات
    if hour == "more":
        keyboard = []
        hour_labels = []
        hour_values = []
        for h in range(24):
            if h == 0:
                hour_labels.append("12:00 صباحاً")
                hour_values.append("00")
            elif h < 12:
                hour_labels.append(f"{h}:00 صباحاً")
                hour_values.append(f"{h:02d}")
            elif h == 12:
                hour_labels.append("12:00 ظهراً")
                hour_values.append("12")
            else:
                hour_labels.append(f"{h - 12}:00 مساءً")
                hour_values.append(f"{h:02d}")

        # تقسيم الساعات إلى صفوف (4 ساعات لكل صف)
        for chunk_labels, chunk_values in zip(
            _chunked(hour_labels, 4), _chunked(hour_values, 4)):
            row = [
                InlineKeyboardButton(
                    label, callback_data=f"time_hour:{val}")
                for label, val in zip(chunk_labels, chunk_values)]
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
        ])

        await query.edit_message_text(
            "🕐 **اختيار الساعة**\n\nاختر الساعة من القائمة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return R_DATE_TIME

    context.user_data.setdefault("report_tmp", {})["_pending_date_hour"] = hour
    await query.edit_message_text(
        f"🕐 اختر الدقائق للساعة {hour}:",
        reply_markup=_build_minute_keyboard(hour),
        parse_mode="Markdown",
    )
    return R_DATE_TIME


async def handle_date_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الدقائق عند إدخال التاريخ يدوياً"""
    from .patient_handlers import show_patient_selection
    
    query = update.callback_query
    await query.answer()
    _, hour, minute = query.data.split(":")
    time_value = f"{hour}:{minute}"

    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_date")
    if pending_date:
        # دمج التاريخ والوقت
        from datetime import time
        dt = datetime.combine(pending_date.date(), time(int(hour), int(minute)))
        data_tmp["report_date"] = dt
        data_tmp.pop("_pending_date", None)
        data_tmp.pop("_pending_date_hour", None)
        data_tmp.setdefault("step_history", []).append(R_DATE)

        # عرض الوقت بصيغة 12 ساعة
        hour_int = int(hour)
        if hour_int == 0:
            time_display = f"12:{minute} صباحاً"
        elif hour_int < 12:
            time_display = f"{hour_int}:{minute} صباحاً"
        elif hour_int == 12:
            time_display = f"12:{minute} ظهراً"
        else:
            time_display = f"{hour_int - 12}:{minute} مساءً"

        days_ar = {
            0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس',
            4: 'الجمعة', 5: 'السبت', 6: 'الأحد'
        }
        day_name = days_ar.get(dt.weekday(), '')

        # ✅ حفظ الـ state في سجل التنقل قبل الانتقال للمريض
        nav_push(context, STATE_SELECT_PATIENT)
        context.user_data['_conversation_state'] = STATE_SELECT_PATIENT

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ والوقت**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})\n\n"
            f"🕐 **الوقت:**\n"
            f"{time_display}",
            parse_mode="Markdown"
        )
        await show_patient_selection(query.message, context)
        return STATE_SELECT_PATIENT

    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return R_DATE_TIME


async def handle_date_time_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي اختيار الوقت"""
    from .patient_handlers import show_patient_selection
    
    query = update.callback_query
    await query.answer()

    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_date")
    if pending_date:
        # استخدام منتصف النهار كوقت افتراضي
        from datetime import time
        dt = datetime.combine(pending_date.date(), time(12, 0))
        data_tmp["report_date"] = dt
        data_tmp.pop("_pending_date", None)
        data_tmp.pop("_pending_date_hour", None)
        data_tmp.setdefault("step_history", []).append(R_DATE)

        days_ar = {
            0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس',
            4: 'الجمعة', 5: 'السبت', 6: 'الأحد'
        }
        day_name = days_ar.get(dt.weekday(), '')

        # ✅ حفظ الـ state في سجل التنقل قبل الانتقال للمريض
        nav_push(context, STATE_SELECT_PATIENT)
        context.user_data['_conversation_state'] = STATE_SELECT_PATIENT

        await query.edit_message_text(
            f"✅ **تم حفظ التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})"
        )
        await show_patient_selection(query.message, context)
        return STATE_SELECT_PATIENT

    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return R_DATE_TIME


async def handle_step_back_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرجوع من شاشة التاريخ إلى القائمة الرئيسية"""
    from .navigation_helpers import handle_cancel_navigation
    
    query = update.callback_query
    if not query:
        return None
    
    await query.answer()
    
    # استخدام handle_cancel_navigation للرجوع إلى القائمة الرئيسية
    return await handle_cancel_navigation(update, context)
