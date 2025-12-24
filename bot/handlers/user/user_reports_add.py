# bot/handlers/user/user_reports_add.py
import calendar

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from bot.shared_auth import ensure_approved
from db.session import SessionLocal
from db.models import Translator
from datetime import datetime, timedelta
from config.settings import TIMEZONE
from .user_reports_add_helpers import (
    PREDEFINED_HOSPITALS, PREDEFINED_DEPARTMENTS, DIRECT_DEPARTMENTS,
    PREDEFINED_ACTIONS, validate_text_input, save_report_to_db,
    broadcast_report, create_evaluation
)

# استيراد مكتبة التوقيت
from zoneinfo import ZoneInfo  # Python 3.9+ (متوفر في Python 3.12)

(R_DATE, R_DATE_TIME, R_PATIENT, R_HOSPITAL, R_DEPARTMENT, R_DOCTOR,
 R_ACTION, R_RADIOLOGY_TYPE, R_RADIOLOGY_DELIVERY_DATE, R_RADIOLOGY_TRANSLATOR,
 R_RADIOLOGY_CONFIRM, R_COMPLAINT, R_DECISION, R_CASE_STATUS, R_FOLLOWUP_DATE,
 R_FOLLOWUP_TIME, R_FOLLOWUP_REASON, R_TRANSLATOR, R_CONFIRM) = range(19)

def _cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء العملية", callback_data="abort")]])


MONTH_NAMES_AR = {
    1: "يناير",
    2: "فبراير",
    3: "مارس",
    4: "أبريل",
    5: "مايو",
    6: "يونيو",
    7: "يوليو",
    8: "أغسطس",
    9: "سبتمبر",
    10: "أكتوبر",
    11: "نوفمبر",
    12: "ديسمبر",
}

WEEKDAYS_AR = ["س", "أ", "ث", "ر", "خ", "ج", "س"]


def _chunked(seq, size):
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _build_followup_calendar_markup(year: int, month: int):
    """بناء تقويم تاريخ العودة - لا يعرض التواريخ القديمة، فقط التقويم"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []
    
    # تقويم الشهر مع أزرار التنقل
    keyboard.append([
        [
            InlineKeyboardButton("⬅️", callback_data=f"cal_prev:{year}-{month:02d}"),
            InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
            InlineKeyboardButton("➡️", callback_data=f"cal_next:{year}-{month:02d}"),
        ],
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
                            row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"cal_day:{date_str}"))
                        else:
                            row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"cal_day:{date_str}"))
                except:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    keyboard.append(
        [
            InlineKeyboardButton("⏭️ بدون موعد", callback_data="followup:no"),
        ]
    )
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])

    text = f"""📅 **اختيار تاريخ العودة**

{MONTH_NAMES_AR.get(month, str(month))} {year}

اختر التاريخ من التقويم:"""
    return text, InlineKeyboardMarkup(keyboard)


def _build_hour_keyboard():
    """بناء لوحة اختيار الساعات بصيغة 12 ساعة مع تنظيم أفضل"""
    keyboard = []
    
    # أوقات شائعة أولاً (صباحاً)
    common_morning = [
        ("🌅 8:00 صباحاً", "08"),
        ("🌅 9:00 صباحاً", "09"),
        ("🌅 10:00 صباحاً", "10"),
        ("🌅 11:00 صباحاً", "11"),
    ]
    keyboard.append([InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in common_morning])
    
    # الظهر
    keyboard.append([
        InlineKeyboardButton("☀️ 12:00 ظهراً", callback_data="time_hour:12")
    ])
    
    # بعد الظهر
    common_afternoon = [
        ("🌆 1:00 مساءً", "13"),
        ("🌆 2:00 مساءً", "14"),
        ("🌆 3:00 مساءً", "15"),
        ("🌆 4:00 مساءً", "16"),
    ]
    keyboard.append([InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in common_afternoon])
    
    # مساءً
    common_evening = [
        ("🌃 5:00 مساءً", "17"),
        ("🌃 6:00 مساءً", "18"),
        ("🌃 7:00 مساءً", "19"),
        ("🌃 8:00 مساءً", "20"),
    ]
    keyboard.append([InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in common_evening])
    
    # زر "أوقات أخرى"
    keyboard.append([InlineKeyboardButton("🕐 أوقات أخرى", callback_data="time_hour:more")])
    
    keyboard.append([InlineKeyboardButton("⏭️ بدون وقت", callback_data="time_skip")])
    keyboard.append(
        [
            InlineKeyboardButton("🔙 تغيير التاريخ", callback_data="time_change_date"),
            InlineKeyboardButton("❌ إلغاء", callback_data="abort"),
        ]
    )
    return InlineKeyboardMarkup(keyboard)


def _build_minute_keyboard(hour: str):
    """بناء لوحة اختيار الدقائق مع عرض الوقت بصيغة 12 ساعة"""
    minute_options = ["00", "15", "30", "45"]
    keyboard = []
    
    # تحويل الساعة إلى صيغة 12 ساعة للعرض
    hour_int = int(hour)
    if hour_int == 0:
        hour_display = "12"
        period = "صباحاً"
    elif hour_int < 12:
        hour_display = str(hour_int)
        period = "صباحاً"
    elif hour_int == 12:
        hour_display = "12"
        period = "ظهراً"
    else:
        hour_display = str(hour_int - 12)
        period = "مساءً"
    
    for chunk in _chunked(minute_options, 2):
        row = []
        for m in chunk:
            label = f"{hour_display}:{m} {period}"
            row.append(InlineKeyboardButton(label, callback_data=f"time_minute:{hour}:{m}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⏭️ بدون وقت", callback_data="time_skip")])
    keyboard.append(
        [
            InlineKeyboardButton("🔙 تغيير الساعة", callback_data="time_back_hour"),
            InlineKeyboardButton("🔙 تغيير التاريخ", callback_data="time_change_date"),
        ]
    )
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
    return InlineKeyboardMarkup(keyboard)


async def _render_followup_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم موعد العودة - يعمل مع message أو query"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    selected_date = data_tmp.get("followup_date")
    if year is None or month is None:
        if selected_date and hasattr(selected_date, "year"):
            year = selected_date.year
            month = selected_date.month
        else:
            now = datetime.now()
            year = now.year
            month = now.month

    text, markup = _build_followup_calendar_markup(year, month)
    data_tmp["calendar_year"] = year
    data_tmp["calendar_month"] = month
    
    # التحقق إذا كان message أو query
    if hasattr(message_or_query, 'edit_message_text'):
        # query object
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        # message object
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_approved(update, context):
        return ConversationHandler.END
    context.user_data["report_tmp"] = {}
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 استخدام التاريخ الحالي", callback_data="date:now")],
        [InlineKeyboardButton("📝 إدخال تاريخ يدوياً", callback_data="date:manual")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]
    ])
    await update.message.reply_text("""📅 **إضافة تقرير جديد**

اختر طريقة إدخال التاريخ:""", reply_markup=keyboard, parse_mode="Markdown")
    return R_DATE

def format_time_12h(dt: datetime) -> str:
    """تحويل الوقت إلى صيغة 12 ساعة مع التمييز بين صباح/مساء"""
    hour = dt.hour
    minute = dt.minute
    if hour == 0:
        return f"12:{minute:02d} صباحاً"
    elif hour < 12:
        return f"{hour}:{minute:02d} صباحاً"
    elif hour == 12:
        return f"12:{minute:02d} ظهراً"
    else:
        return f"{hour-12}:{minute:02d} مساءً"

async def handle_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "date:now":
        # استخدام توقيت الهند مباشرة (IST = UTC+5:30)
        try:
            tz = ZoneInfo("Asia/Kolkata")  # توقيت الهند مباشرة
            now = datetime.now(tz)
        except Exception as e:
            # في حالة الخطأ، استخدام UTC+5:30 يدوياً
            from datetime import timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(timezone.utc).astimezone(ist)
        
        # حفظ الوقت بتوقيت الهند
        context.user_data["report_tmp"]["report_date"] = now
        
        # عرض التاريخ والوقت بتوقيت الهند
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(now.weekday(), '')
        
        # استخدام format_time_12h لعرض الوقت بصيغة 12 ساعة بتوقيت الهند
        time_str = format_time_12h(now)
        date_str = now.strftime('%Y-%m-%d')
        
        await query.edit_message_text(
            f"""✅ **تم اختيار التاريخ الحالي**

📅 **التاريخ:**
{now.strftime('%d')} {MONTH_NAMES_AR.get(now.month, now.month)} {now.year} ({day_name})

🕐 **الوقت (بتوقيت الهند):**
{time_str}"""
        )
        await query.message.reply_text(
            """👤 **اسم المريض**

يرجى إدخال اسم المريض:""",
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        return R_PATIENT
    elif query.data == "date:manual":
        await query.edit_message_text("""📅 **إدخال التاريخ يدوياً**

يرجى إدخال التاريخ بصيغة (YYYY-MM-DD):
مثال: 2025-10-15""")
        return R_DATE

async def handle_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        dt = datetime.strptime(txt, "%Y-%m-%d")
        context.user_data["report_tmp"]["_pending_date"] = dt
        await update.message.reply_text(
            f"""✅ **تم حفظ التاريخ**

📅 **التاريخ:**
{txt}

🕐 **الوقت**

اختر الساعة:""",
            reply_markup=_build_hour_keyboard(),
            parse_mode="Markdown"
        )
        return R_DATE_TIME
    except ValueError:
        await update.message.reply_text("""⚠️ **صيغة غير صحيحة!**

يرجى استخدام الصيغة: YYYY-MM-DD
مثال: 2025-10-15""", reply_markup=_cancel_kb())
        return R_DATE

async def handle_patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=2, max_length=100)
    if not valid:
        await update.message.reply_text(f"""⚠️ **خطأ: {msg}**

يرجى إدخال اسم المريض:""", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_PATIENT
    context.user_data["report_tmp"]["patient_name"] = text
    await show_hospitals_menu(update.message, context)
    return R_HOSPITAL

# ================================================
# 🏥 نظام المستشفيات والأقسام الجديد - منظم وقوي
# ================================================

def _build_hospitals_keyboard(page=0, search_query=""):
    """بناء لوحة مفاتيح المستشفيات مع بحث"""
    items_per_page = 8
    
    # تصفية المستشفيات إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        filtered_hospitals = [h for h in PREDEFINED_HOSPITALS if search_lower in h.lower()]
        hospitals_list = sorted(filtered_hospitals)
    else:
        hospitals_list = sorted(PREDEFINED_HOSPITALS.copy())
    
    total = len(hospitals_list)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    
    keyboard = []
    
    # عرض المستشفيات في صفوف (2 لكل صف)
    for i in range(start_idx, end_idx, 2):
        row = []
        # المستشفى الأول في الصف
        row.append(InlineKeyboardButton(
            f"🏥 {hospitals_list[i][:25]}..." if len(hospitals_list[i]) > 25 else f"🏥 {hospitals_list[i]}",
            callback_data=f"hospital:{hospitals_list[i]}"
        ))
        # المستشفى الثاني في الصف (إن وجد)
        if i + 1 < end_idx:
            row.append(InlineKeyboardButton(
                f"🏥 {hospitals_list[i+1][:25]}..." if len(hospitals_list[i+1]) > 25 else f"🏥 {hospitals_list[i+1]}",
                callback_data=f"hospital:{hospitals_list[i+1]}"
            ))
        keyboard.append(row)
    
    # أزرار التنقل
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"hosp_page:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"hosp_page:{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
    
    text = f"""🏥 **اختيار المستشفى**

📋 **العدد:** {total} مستشفى"""
    if search_query:
        text += f"""
🔍 **البحث:** {search_query}"""
    text += f"""
📄 **الصفحة:** {page+1} من {total_pages}

اختر المستشفى:"""
    
    return text, InlineKeyboardMarkup(keyboard), search_query

async def show_hospitals_menu(message, context, page=0, search_query=""):
    """عرض قائمة المستشفيات"""
    text, keyboard, search = _build_hospitals_keyboard(page, search_query)
    context.user_data["report_tmp"]["hospitals_search"] = search
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def handle_hospital_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار المستشفى"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("hosp_search"):
        await query.edit_message_text(
            "🔍 **البحث عن المستشفى**

"
            "يرجى إدخال كلمة البحث:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="abort")]]),
            parse_mode="Markdown"
        )
        context.user_data["report_tmp"]["hospitals_search_mode"] = True
        return R_HOSPITAL
    
    choice = query.data.split(":", 1)[1]
    context.user_data["report_tmp"]["hospital_name"] = choice
    context.user_data["report_tmp"].pop("hospitals_search", None)
    context.user_data["report_tmp"].pop("hospitals_search_mode", None)
    
    await query.edit_message_text(
        f"✅ **تم اختيار المستشفى**

"
        f"🏥 **المستشفى:**
"
        f"{choice}"
    )
    await show_departments_menu(query.message, context)
    return R_DEPARTMENT

async def handle_hospital_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات المستشفيات"""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    search = context.user_data.get("report_tmp", {}).get("hospitals_search", "")
    text, keyboard, search = _build_hospitals_keyboard(page, search)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return R_HOSPITAL

async def handle_hospital_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث في المستشفيات"""
    if update.message:
        search_mode = context.user_data.get("report_tmp", {}).get("hospitals_search_mode", False)
        if search_mode:
            search_query = update.message.text.strip()
            context.user_data["report_tmp"]["hospitals_search"] = search_query
            context.user_data["report_tmp"]["hospitals_search_mode"] = False
            text, keyboard, _ = _build_hospitals_keyboard(0, search_query)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return R_HOSPITAL
        else:
            # إذا لم يكن في وضع البحث، تجاهل النص
            return R_HOSPITAL

def _build_departments_keyboard(page=0, search_query=""):
    """بناء لوحة مفاتيح الأقسام مع بحث"""
    items_per_page = 8
    
    # جمع جميع الأقسام
    all_departments = []
    
    # إضافة الأقسام الرئيسية مع فروعها
    for main_dept, subdepts in PREDEFINED_DEPARTMENTS.items():
        all_departments.append(main_dept)  # القسم الرئيسي
        all_departments.extend(subdepts)  # الفروع
    
    # إضافة الأقسام المباشرة
    all_departments.extend(DIRECT_DEPARTMENTS)
    
    # إزالة التكرار
    all_departments = sorted(list(set(all_departments)))
    
    # تصفية الأقسام إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        filtered_depts = []
        for dept in all_departments:
            # البحث في الاسم العربي والإنجليزي
            if search_lower in dept.lower():
                filtered_depts.append(dept)
        all_departments = filtered_depts
    
    total = len(all_departments)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    
    keyboard = []
    
    # عرض الأقسام في صفوف (2 لكل صف)
    for i in range(start_idx, end_idx, 2):
        row = []
        # القسم الأول في الصف
        dept_name_1 = all_departments[i]
        display_1 = f"🏷️ {dept_name_1[:23]}..." if len(dept_name_1) > 23 else f"🏷️ {dept_name_1}"
        row.append(InlineKeyboardButton(display_1, callback_data=f"dept:{dept_name_1}"))
        
        # القسم الثاني في الصف (إن وجد)
        if i + 1 < end_idx:
            dept_name_2 = all_departments[i + 1]
            display_2 = f"🏷️ {dept_name_2[:23]}..." if len(dept_name_2) > 23 else f"🏷️ {dept_name_2}"
            row.append(InlineKeyboardButton(display_2, callback_data=f"dept:{dept_name_2}"))
        
        keyboard.append(row)
    
    # أزرار التنقل
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"dept_page:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"dept_page:{page+1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
    
    text = (
        f"🏷️ **اختيار القسم**

"
        f"📋 **العدد:** {total} قسم"
    )
    if search_query:
        text += f"
🔍 **البحث:** {search_query}"
    text += f"
📄 **الصفحة:** {page+1} من {total_pages}

اختر القسم:"
    
    return text, InlineKeyboardMarkup(keyboard), search_query

async def show_departments_menu(message, context, page=0, search_query=""):
    """عرض قائمة الأقسام"""
    text, keyboard, search = _build_departments_keyboard(page, search_query)
    context.user_data["report_tmp"]["departments_search"] = search
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def handle_department_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار القسم"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("dept_search"):
        await query.edit_message_text(
            "🔍 **البحث عن القسم**

"
            "يرجى إدخال كلمة البحث:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="abort")]]),
            parse_mode="Markdown"
        )
        context.user_data["report_tmp"]["departments_search_mode"] = True
        return R_DEPARTMENT
    
    dept = query.data.split(":", 1)[1]
    context.user_data["report_tmp"]["department_name"] = dept
    context.user_data["report_tmp"].pop("departments_search", None)
    context.user_data["report_tmp"].pop("departments_search_mode", None)
    
    await query.edit_message_text(
        f"✅ **تم اختيار القسم**

"
        f"🏷️ **القسم:**
"
        f"{dept}"
    )
    await show_doctor_input(query.message, context)
    return R_DOCTOR

async def handle_department_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات الأقسام"""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    search = context.user_data.get("report_tmp", {}).get("departments_search", "")
    text, keyboard, search = _build_departments_keyboard(page, search)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return R_DEPARTMENT

async def handle_department_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث في الأقسام"""
    if update.message:
        search_mode = context.user_data.get("report_tmp", {}).get("departments_search_mode", False)
        if search_mode:
            search_query = update.message.text.strip()
            context.user_data["report_tmp"]["departments_search"] = search_query
            context.user_data["report_tmp"]["departments_search_mode"] = False
            text, keyboard, _ = _build_departments_keyboard(0, search_query)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return R_DEPARTMENT
        else:
            # إذا لم يكن في وضع البحث، تجاهل النص
            return R_DEPARTMENT

async def show_doctor_input(message, context):
    await message.reply_text("👨‍⚕️ **اسم الطبيب**

يرجى إدخال اسم الطبيب:", reply_markup=_cancel_kb(), parse_mode="Markdown")

async def handle_doctor_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=2, max_length=100)
    if not valid:
        await update.message.reply_text(f"⚠️ **خطأ: {msg}**

يرجى إدخال اسم الطبيب:", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_DOCTOR
    context.user_data["report_tmp"]["doctor_name"] = text
    await update.message.reply_text(
        f"✅ **تم حفظ اسم الطبيب**

"
        f"👨‍⚕️ **الطبيب:**
"
        f"{text}"
    )
    await show_action_options(update.message, context)
    return R_ACTION

async def show_action_options(message, context, page=0):
    items_per_page = 8
    total = len(PREDEFINED_ACTIONS)
    total_pages = (total + items_per_page - 1) // items_per_page
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    keyboard = []
    for i in range(start_idx, end_idx):
        keyboard.append([InlineKeyboardButton(f"⚕️ {PREDEFINED_ACTIONS[i]}", callback_data=f"action:{PREDEFINED_ACTIONS[i]}")])
    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"action_page:{page-1}"))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"action_page:{page+1}"))
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
    await message.reply_text(f"⚕️ **نوع الإجراء** (صفحة {page+1}/{total_pages})

اختر نوع الإجراء من القائمة:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_action_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    context.user_data["report_tmp"]["medical_action"] = choice
    
    if choice == "أشعة وفحوصات":
        await query.edit_message_text(
            f"✅ **تم اختيار نوع الإجراء**

"
            f"⚕️ **النوع:**
"
            f"{choice}"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📝 ادخل نوع الأشعة والفحوصات", callback_data="radiology:enter")], [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]])
        await query.message.reply_text(
            "🔬 **أشعة وفحوصات**

"
            "اضغط على الزر أدناه:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return R_RADIOLOGY_TYPE
    elif choice == "استشارة أخيرة":
        # استشارة أخيرة: لا شكوى، فقط التشخيص (كقرار الطبيب) + حالة إنهاء
        await query.edit_message_text(
            f"✅ **تم اختيار نوع الإجراء**

"
            f"⚕️ **النوع:**
"
            f"{choice}"
        )
        context.user_data["report_tmp"]["complaint_text"] = ""  # لا شكوى في استشارة أخيرة
        await query.message.reply_text(
            "📝 **التشخيص**

"
            "يرجى إدخال التشخيص:",
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        return R_DECISION  # نذهب مباشرة إلى قرار الطبيب (التشخيص)
    elif choice == "استشارة مع قرار عملية":
        # استشارة مع قرار عملية: شكوى + قرار العملية
        await query.edit_message_text(
            f"✅ **تم اختيار نوع الإجراء**

"
            f"⚕️ **النوع:**
"
            f"{choice}"
        )
        await query.message.reply_text(
            "💬 **شكوى المريض**

"
            "يرجى إدخال شكوى المريض:",
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        return R_COMPLAINT
    else:
        # استشارة جديدة أو أنواع أخرى: شكوى + قرار الطبيب
        await query.edit_message_text(
            f"✅ **تم اختيار نوع الإجراء**

"
            f"⚕️ **النوع:**
"
            f"{choice}"
        )
        await query.message.reply_text(
            "💬 **شكوى المريض**

"
            "يرجى إدخال شكوى المريض:",
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        return R_COMPLAINT

async def handle_action_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    await query.message.delete()
    await show_action_options(query.message, context, page)
    return R_ACTION

async def handle_radiology_enter_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 **نوع الأشعة**

يرجى إدخال نوع الأشعة:", parse_mode="Markdown")
    return R_RADIOLOGY_TYPE

async def handle_radiology_type_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)
    if not valid:
        await update.message.reply_text(f"⚠️ **خطأ: {msg}**", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_RADIOLOGY_TYPE
    context.user_data["report_tmp"]["radiology_type"] = text
    await update.message.reply_text(f"✅ حفظ

📅 تاريخ التسليم (YYYY-MM-DD):", reply_markup=_cancel_kb(), parse_mode="Markdown")
    return R_RADIOLOGY_DELIVERY_DATE

async def handle_radiology_delivery_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        delivery_date = datetime.strptime(text, "%Y-%m-%d")
        context.user_data["report_tmp"]["radiology_delivery_date"] = delivery_date
        await update.message.reply_text(f"✅ تم حفظ التاريخ")
        await ask_radiology_translator_name(update.message, context)
        return R_RADIOLOGY_TRANSLATOR
    except ValueError:
        await update.message.reply_text("⚠️ صيغة غير صحيحة!", reply_markup=_cancel_kb())
        return R_RADIOLOGY_DELIVERY_DATE

async def ask_radiology_translator_name(message, context):
    user_id = message.chat.id
    translator_name = "غير محدد"
    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if translator:
            translator_name = translator.full_name
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ {translator_name}", callback_data="radiology_translator:auto")], [InlineKeyboardButton("✏️ إدخال آخر", callback_data="radiology_translator:manual")], [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]])
    await message.reply_text(f"👤 المترجم: {translator_name}

اختر:", reply_markup=keyboard, parse_mode="Markdown")

async def handle_radiology_translator_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "radiology_translator:auto":
        user_id = query.from_user.id
        with SessionLocal() as s:
            translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
            if translator:
                context.user_data["report_tmp"]["translator_name"] = translator.full_name
            else:
                context.user_data["report_tmp"]["translator_name"] = "غير محدد"
        await show_radiology_summary(query.message, context)
        return R_RADIOLOGY_CONFIRM
    elif query.data == "radiology_translator:manual":
        await query.edit_message_text("👤 أدخل اسم المترجم:", parse_mode="Markdown")
        return R_RADIOLOGY_TRANSLATOR

async def handle_radiology_translator_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=2, max_length=100)
    if not valid:
        await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_RADIOLOGY_TRANSLATOR
    context.user_data["report_tmp"]["translator_name"] = text
    await show_radiology_summary(update.message, context)
    return R_RADIOLOGY_CONFIRM

async def show_radiology_summary(message, context):
    d = context.user_data.get("report_tmp", {})
    summary = f"📋 ملخص

🔬 {d.get('radiology_type')}
📅 {d.get('radiology_delivery_date')}
👤 {d.get('translator_name')}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💾 حفظ", callback_data="radiology:save")], [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]])
    await message.reply_text(summary, reply_markup=keyboard, parse_mode="Markdown")

async def handle_radiology_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "radiology:save":
        await save_radiology_report(query, context)
        return ConversationHandler.END

async def save_radiology_report(query, context):
    from db.models import Report, Patient, Hospital, Department, Doctor
    data_tmp = context.user_data.get("report_tmp", {})
    
    # التحقق من البيانات
    if not data_tmp.get("patient_name"):
        await query.edit_message_text("❌ خطأ: لا يوجد اسم مريض", parse_mode="Markdown")
        return
    
    if not data_tmp.get("hospital_name"):
        await query.edit_message_text("❌ خطأ: لا يوجد مستشفى", parse_mode="Markdown")
        return
    
    session = None
    try:
        session = SessionLocal()
        
        # حفظ المريض
        print(f"🔄 حفظ المريض: {data_tmp.get('patient_name')}")
        patient = session.query(Patient).filter_by(full_name=data_tmp.get("patient_name")).first()
        if not patient:
            patient = Patient(full_name=data_tmp.get("patient_name"))
            session.add(patient)
            session.flush()
        
        # حفظ المستشفى
        print(f"🔄 حفظ المستشفى: {data_tmp.get('hospital_name')}")
        hospital = session.query(Hospital).filter_by(name=data_tmp.get("hospital_name")).first()
        if not hospital:
            hospital = Hospital(name=data_tmp.get("hospital_name"))
            session.add(hospital)
            session.flush()
        
        # حفظ القسم
        department = None
        if data_tmp.get("department_name"):
            print(f"🔄 حفظ القسم: {data_tmp.get('department_name')}")
            department = session.query(Department).filter_by(name=data_tmp["department_name"]).first()
            if not department:
                department = Department(name=data_tmp["department_name"])
                session.add(department)
                session.flush()
        
        # حفظ الطبيب
        doctor = None
        if data_tmp.get("doctor_name"):
            print(f"🔄 حفظ الطبيب: {data_tmp.get('doctor_name')}")
            doctor = session.query(Doctor).filter_by(full_name=data_tmp["doctor_name"]).first()
            if not doctor:
                doctor = Doctor(
                    name=data_tmp["doctor_name"],  # Use same value for name
                    full_name=data_tmp["doctor_name"]
                )
                session.add(doctor)
                session.flush()
        
        # المترجم
        translator = None
        created_by_tg_user_id = None
        if query.from_user:
            translator = session.query(Translator).filter_by(tg_user_id=query.from_user.id).first()
            created_by_tg_user_id = query.from_user.id
            print(f"👤 المترجم: {translator.full_name if translator else 'غير موجود'}")
        
        # إنشاء التقرير
        print("📝 إنشاء تقرير أشعة...")
        new_report = Report(
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id if department else None,
            doctor_id=doctor.id if doctor else None,
            translator_id=translator.id if translator else None,
            created_by_tg_user_id=created_by_tg_user_id,  # المستخدم الذي أنشأ التقرير
            complaint_text="أشعة وفحوصات",
            doctor_decision=f"نوع: {data_tmp.get('radiology_type', 'غير محدد')}",
            medical_action=data_tmp.get("medical_action", ""),
            followup_date=data_tmp.get("radiology_delivery_date"),
            followup_reason="تسليم نتائج",
            report_date=data_tmp.get("report_date") or datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        session.add(new_report)
        session.commit()
        session.refresh(new_report)
        
        print(f"✅ تم حفظ تقرير الأشعة برقم: {new_report.id}")
        
        # بث التقرير
        try:
            from services.broadcast_service import broadcast_new_report
            # تنسيق التاريخ والوقت بصيغة 12 ساعة
            report_date_obj = data_tmp.get('report_date')
            if report_date_obj and hasattr(report_date_obj, 'strftime'):
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                day_name = days_ar.get(report_date_obj.weekday(), '')
                time_str = format_time_12h(report_date_obj)
                report_date_formatted = f"{report_date_obj.strftime('%d')} {MONTH_NAMES_AR.get(report_date_obj.month, report_date_obj.month)} {report_date_obj.year} ({day_name}) - {time_str}"
            else:
                report_date_formatted = str(report_date_obj) if report_date_obj else 'غير محدد'
            
            broadcast_data = {
                'report_date': report_date_formatted,
                'patient_name': data_tmp.get('patient_name', 'غير محدد'),
                'hospital_name': data_tmp.get('hospital_name', 'غير محدد'),
                'department_name': data_tmp.get('department_name', 'غير محدد'),
                'doctor_name': data_tmp.get('doctor_name', 'لم يتم التحديد'),
                'medical_action': data_tmp.get('medical_action', 'غير محدد'),
                'radiology_type': data_tmp.get('radiology_type', 'لا يوجد'),
                'radiology_delivery_date': data_tmp.get('radiology_delivery_date').strftime('%Y-%m-%d') if data_tmp.get('radiology_delivery_date') else 'لا يوجد',
                'complaint_text': 'أشعة وفحوصات',
                'doctor_decision': f"نوع: {data_tmp.get('radiology_type', 'غير محدد')}",
                'followup_date': data_tmp.get('radiology_delivery_date').strftime('%Y-%m-%d') if data_tmp.get('radiology_delivery_date') else 'لا يوجد',
                'followup_reason': 'تسليم نتائج',
                'case_status': 'لا يوجد',
                'translator_name': data_tmp.get('translator_name') or (translator.full_name if translator else "غير محدد")
            }
            # Get context from query
            from telegram.ext import CallbackContext
            await broadcast_new_report(query._bot, broadcast_data)
        except Exception as e:
            print(f"خطأ في بث: {e}")
        
        context.user_data.pop("report_tmp", None)
        await query.edit_message_text(f"✅ تم الحفظ بنجاح!

📋 رقم التقرير: {new_report.id}", parse_mode="Markdown")
        
    except Exception as e:
        if session:
            session.rollback()
        print(f"❌ خطأ في save_radiology_report: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(f"❌ خطأ في الحفظ:
{str(e)}", parse_mode="Markdown")
    finally:
        if session:
            session.close()

async def handle_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)
    if not valid:
        await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_COMPLAINT
    context.user_data["report_tmp"]["complaint_text"] = text
    await update.message.reply_text("✅

📝 قرار الطبيب:", reply_markup=_cancel_kb(), parse_mode="Markdown")
    return R_DECISION

async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)
    if not valid:
        await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_DECISION
    context.user_data["report_tmp"]["doctor_decision"] = text
    
    # إذا كانت استشارة أخيرة، نضيف حالة إنهاء تلقائياً
    medical_action = context.user_data["report_tmp"].get("medical_action", "")
    if medical_action == "استشارة أخيرة":
        context.user_data["report_tmp"]["case_status"] = "استشارة أخيرة - إنهاء الحالة"
        # استشارة أخيرة لا تحتاج موعد عودة - الانتقال مباشرة إلى اسم المترجم
        data_tmp = context.user_data.setdefault("report_tmp", {})
        data_tmp["followup_date"] = None
        data_tmp["followup_date_text"] = None
        data_tmp["followup_time"] = None
        data_tmp["followup_reason"] = None
        data_tmp["followup_is_text"] = False
        data_tmp.pop("_pending_hour", None)
        await update.message.reply_text("✅")
        await ask_translator_name(update.message, context)
        return R_TRANSLATOR
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📋 ماذا تم؟", callback_data="case_status:ask")], [InlineKeyboardButton("⏭️ تخطي", callback_data="case_status:skip")], [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]])
        await update.message.reply_text("✅

اختر:", reply_markup=keyboard, parse_mode="Markdown")
        return R_CASE_STATUS

async def handle_case_status_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "case_status:skip":
        context.user_data["report_tmp"]["case_status"] = None
        await query.edit_message_text("⏭️ تخطي")
        # الانتقال مباشرة إلى التقويم
        data_tmp = context.user_data.setdefault("report_tmp", {})
        data_tmp["followup_is_text"] = False
        data_tmp["followup_date_text"] = None
        data_tmp["followup_time"] = None
        data_tmp["followup_reason"] = None
        data_tmp.pop("_pending_hour", None)
        await _render_followup_calendar(query.message, context)
        return R_FOLLOWUP_DATE
    elif query.data == "case_status:ask":
        await query.edit_message_text("📋 ماذا تم للحالة؟", parse_mode="Markdown")
        return R_CASE_STATUS

async def handle_case_status_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)
    if not valid:
        await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_CASE_STATUS
    context.user_data["report_tmp"]["case_status"] = text
    await update.message.reply_text(f"✅")
    # الانتقال مباشرة إلى التقويم
    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp["followup_is_text"] = False
    data_tmp["followup_date_text"] = None
    data_tmp["followup_time"] = None
    data_tmp["followup_reason"] = None
    data_tmp.pop("_pending_hour", None)
    await _render_followup_calendar(update.message, context)
    return R_FOLLOWUP_DATE

async def handle_followup_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "followup:no":
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_reason"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        await query.edit_message_text("⏭️ لا يوجد")
        await ask_translator_name(query.message, context)
        return R_TRANSLATOR
    elif query.data == "followup:yes":
        data_tmp = context.user_data.setdefault("report_tmp", {})
        data_tmp["followup_is_text"] = False
        data_tmp["followup_date_text"] = None
        data_tmp["followup_time"] = None
        data_tmp["followup_reason"] = None
        data_tmp.pop("_pending_hour", None)
        await _render_followup_calendar(query, context)
        return R_FOLLOWUP_DATE

async def handle_followup_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prefix, ym = query.data.split(":", 1)
    year, month = map(int, ym.split("-"))
    if prefix == "cal_prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    else:
        month += 1
        if month > 12:
            month = 1
            year += 1
    await _render_followup_calendar(query, context, year, month)
    return R_FOLLOWUP_DATE


async def handle_followup_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split(":", 1)[1]
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await query.answer("صيغة غير صالحة", show_alert=True)
        return R_FOLLOWUP_DATE

    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp["followup_date"] = selected_date
    data_tmp["followup_date_text"] = None
    data_tmp["followup_is_text"] = False
    data_tmp["followup_time"] = None
    data_tmp.pop("_pending_hour", None)

    # عرض التاريخ المختار بشكل منسق
    days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
    day_name = days_ar.get(selected_date.weekday(), '')
    date_display = f"📅 {selected_date.strftime('%d')} {MONTH_NAMES_AR.get(selected_date.month, selected_date.month)} {selected_date.year} ({day_name})"
    
    await query.edit_message_text(
        f"✅ **تم اختيار التاريخ**

"
        f"📅 **التاريخ:**
"
        f"{date_display}"
    )
    await query.message.reply_text(
        "🕐 **اختيار الوقت**

"
        "اختر الساعة المناسبة:",
        reply_markup=_build_hour_keyboard(),
        parse_mode="Markdown",
    )
    return R_FOLLOWUP_TIME


async def handle_followup_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                hour_labels.append(f"{h-12}:00 مساءً")
                hour_values.append(f"{h:02d}")
        
        # تقسيم الساعات إلى صفوف (4 ساعات لكل صف)
        for chunk_labels, chunk_values in zip(_chunked(hour_labels, 4), _chunked(hour_values, 4)):
            row = [InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in zip(chunk_labels, chunk_values)]
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("⏭️ بدون وقت", callback_data="time_skip")])
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="time_back_hour"),
            InlineKeyboardButton("❌ إلغاء", callback_data="abort"),
        ])
        
        await query.edit_message_text(
            "🕐 **اختيار الساعة**

اختر الساعة من القائمة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return R_FOLLOWUP_TIME
    
    context.user_data.setdefault("report_tmp", {})["_pending_hour"] = hour
    
    # عرض الساعة بصيغة 12 ساعة
    hour_int = int(hour)
    if hour_int == 0:
        hour_display = "12"
        period = "صباحاً"
    elif hour_int < 12:
        hour_display = str(hour_int)
        period = "صباحاً"
    elif hour_int == 12:
        hour_display = "12"
        period = "ظهراً"
    else:
        hour_display = str(hour_int - 12)
        period = "مساءً"
    
    await query.edit_message_text(
        f"✅ **تم اختيار الساعة**

"
        f"🕐 **الساعة:**
"
        f"{hour_display}:00 {period}

"
        f"🕐 **اختيار الدقائق**

"
        f"اختر الدقائق:",
        reply_markup=_build_minute_keyboard(hour),
        parse_mode="Markdown",
    )
    return R_FOLLOWUP_TIME


async def handle_date_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الساعة عند إدخال التاريخ يدوياً"""
    query = update.callback_query
    await query.answer()
    hour = query.data.split(":", 1)[1]
    context.user_data.setdefault("report_tmp", {})["_pending_date_hour"] = hour
    await query.edit_message_text(
        f"🕐 اختر الدقائق للساعة {hour}:",
        reply_markup=_build_minute_keyboard(hour),
        parse_mode="Markdown",
    )
    return R_DATE_TIME

async def handle_date_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الدقائق عند إدخال التاريخ يدوياً"""
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
        
        # عرض الوقت بصيغة 12 ساعة
        hour_int = int(hour)
        if hour_int == 0:
            time_display = f"12:{minute} صباحاً"
        elif hour_int < 12:
            time_display = f"{hour_int}:{minute} صباحاً"
        elif hour_int == 12:
            time_display = f"12:{minute} ظهراً"
        else:
            time_display = f"{hour_int-12}:{minute} مساءً"
        
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(dt.weekday(), '')
        date_str = f"📅🕐 {dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name}) - {time_display}"
        
        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ والوقت**

"
            f"📅 **التاريخ:**
"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})

"
            f"🕐 **الوقت:**
"
            f"{time_display}"
        )
        await query.message.reply_text(
            "👤 **اسم المريض**

"
            "يرجى إدخال اسم المريض:",
            reply_markup=_cancel_kb(),
            parse_mode="Markdown"
        )
        return R_PATIENT
    
    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return R_DATE_TIME

async def handle_followup_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, hour, minute = query.data.split(":")
    time_value = f"{hour}:{minute}"

    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp["followup_time"] = time_value
    data_tmp.pop("_pending_hour", None)

    # عرض الوقت بصيغة 12 ساعة في الرسالة
    hour_int = int(hour)
    if hour_int == 0:
        time_display = f"12:{minute} صباحاً"
    elif hour_int < 12:
        time_display = f"{hour_int}:{minute} صباحاً"
    elif hour_int == 12:
        time_display = f"12:{minute} ظهراً"
    else:
        time_display = f"{hour_int-12}:{minute} مساءً"

    # عرض التاريخ والوقت معاً بشكل منسق
    data_tmp = context.user_data.setdefault("report_tmp", {})
    followup_date = data_tmp.get("followup_date")
    if followup_date:
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(followup_date.weekday(), '')
        date_display = f"{followup_date.strftime('%d')} {MONTH_NAMES_AR.get(followup_date.month, followup_date.month)} {followup_date.year} ({day_name})"
        full_display = f"📅🕐 {date_display} - {time_display}"
    else:
        full_display = f"🕐 {time_display}"
    
    if followup_date:
        await query.edit_message_text(
            f"✅ **تم اختيار الوقت**

"
            f"📅 **التاريخ:**
"
            f"{date_display}

"
            f"🕐 **الوقت:**
"
            f"{time_display}"
        )
    else:
        await query.edit_message_text(
            f"✅ **تم اختيار الوقت**

"
            f"🕐 **الوقت:**
"
            f"{time_display}"
        )
    await query.message.reply_text(
        "✍️ **سبب العودة**

"
        "يرجى إدخال سبب العودة:",
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    return R_FOLLOWUP_REASON


async def handle_followup_time_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp["followup_time"] = None
    data_tmp.pop("_pending_hour", None)
    # عرض التاريخ فقط بدون وقت
    data_tmp = context.user_data.setdefault("report_tmp", {})
    followup_date = data_tmp.get("followup_date")
    if followup_date:
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(followup_date.weekday(), '')
        date_display = f"📅 {followup_date.strftime('%d')} {MONTH_NAMES_AR.get(followup_date.month, followup_date.month)} {followup_date.year} ({day_name})"
    else:
        date_display = "📅 بدون تحديد وقت"
    
    if followup_date:
        await query.edit_message_text(
            f"✅ **تم الاختيار**

"
            f"📅 **التاريخ:**
"
            f"{date_display}

"
            f"⏭️ **الوقت:**
"
            f"بدون تحديد وقت معين"
        )
    else:
        await query.edit_message_text(
            f"✅ **تم الاختيار**

"
            f"📅 **التاريخ:**
"
            f"بدون تحديد

"
            f"⏭️ **الوقت:**
"
            f"بدون تحديد وقت معين"
        )
    await query.message.reply_text(
        "✍️ **سبب العودة**

"
        "يرجى إدخال سبب العودة:",
        reply_markup=_cancel_kb(),
        parse_mode="Markdown"
    )
    return R_FOLLOWUP_REASON


async def handle_followup_time_change_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp.pop("_pending_hour", None)
    year = data_tmp.get("calendar_year")
    month = data_tmp.get("calendar_month")
    await _render_followup_calendar(query, context, year, month)
    return R_FOLLOWUP_DATE


async def handle_followup_time_back_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع إلى اختيار الساعة"""
    query = update.callback_query
    await query.answer()
    data_tmp = context.user_data.setdefault("report_tmp", {})
    data_tmp.pop("_pending_hour", None)
    
    # عرض التاريخ المختار إذا كان موجوداً
    followup_date = data_tmp.get("followup_date")
    if followup_date:
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(followup_date.weekday(), '')
        date_display = f"{followup_date.strftime('%d')} {MONTH_NAMES_AR.get(followup_date.month, followup_date.month)} {followup_date.year} ({day_name})"
        text = f"📅 **التاريخ المختار:** {date_display}

🕐 **اختيار الساعة**

اختر الساعة المناسبة:"
    else:
        text = "🕐 **اختيار الساعة**

اختر الساعة المناسبة:"
    
    await query.edit_message_text(text, reply_markup=_build_hour_keyboard(), parse_mode="Markdown")
    return R_FOLLOWUP_TIME


async def handle_followup_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data_tmp = context.user_data.setdefault("report_tmp", {})

    if text == "-":
        data_tmp["followup_time"] = None
        data_tmp.pop("_pending_hour", None)
        await update.message.reply_text("⏭️")
        await update.message.reply_text("✍️ سبب العودة:", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_FOLLOWUP_REASON

    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await update.message.reply_text("⚠️ صيغة الوقت يجب أن تكون HH:MM أو '-' للتخطي", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_FOLLOWUP_TIME

    data_tmp["followup_time"] = text
    data_tmp.pop("_pending_hour", None)
    
    # تحويل الوقت إلى صيغة 12 ساعة للعرض
    hour, minute = text.split(':')
    hour_int = int(hour)
    if hour_int == 0:
        time_display = f"12:{minute} صباحاً"
    elif hour_int < 12:
        time_display = f"{hour_int}:{minute} صباحاً"
    elif hour_int == 12:
        time_display = f"12:{minute} ظهراً"
    else:
        time_display = f"{hour_int-12}:{minute} مساءً"
    
    await update.message.reply_text(f"✅ **تم حفظ الوقت**

🕐 **الوقت:**
{time_display}", parse_mode="Markdown")
    await update.message.reply_text("✍️ **سبب العودة**

يرجى إدخال سبب العودة:", reply_markup=_cancel_kb(), parse_mode="Markdown")
    return R_FOLLOWUP_REASON


async def handle_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if context.user_data["report_tmp"].get("followup_is_text"):
        valid, msg = validate_text_input(txt, min_length=3, max_length=200)
        if not valid:
            await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
            return R_FOLLOWUP_DATE
        context.user_data["report_tmp"]["followup_date_text"] = txt
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        await update.message.reply_text(f"✅

✍️ سبب العودة:", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_FOLLOWUP_REASON
    else:
        try:
            fd = datetime.strptime(txt, "%Y-%m-%d")
            data_tmp = context.user_data.setdefault("report_tmp", {})
            data_tmp["followup_date"] = fd
            data_tmp["followup_date_text"] = None
            data_tmp["followup_is_text"] = False
            data_tmp["followup_time"] = None
            data_tmp["calendar_year"] = fd.year
            data_tmp["calendar_month"] = fd.month
            data_tmp.pop("_pending_hour", None)
            await update.message.reply_text(
                f"✅ تم حفظ التاريخ: {txt}

🕐 اختر الساعة:",
                reply_markup=_build_hour_keyboard(),
                parse_mode="Markdown",
            )
            return R_FOLLOWUP_TIME
        except ValueError:
            await update.message.reply_text("⚠️ صيغة غير صحيحة!", reply_markup=_cancel_kb())
            return R_FOLLOWUP_DATE

async def handle_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)
    if not valid:
        await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text
    await update.message.reply_text("✅")
    await ask_translator_name(update.message, context)
    return R_TRANSLATOR

async def ask_translator_name(message, context):
    user_id = message.chat.id
    translator_name = "غير محدد"
    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if translator:
            translator_name = translator.full_name
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ {translator_name}", callback_data="translator:auto")], [InlineKeyboardButton("✏️ آخر", callback_data="translator:manual")], [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]])
    await message.reply_text(f"👤 المترجم: {translator_name}

اختر:", reply_markup=keyboard, parse_mode="Markdown")

async def handle_translator_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "translator:auto":
        user_id = query.from_user.id
        with SessionLocal() as s:
            translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
            if translator:
                context.user_data["report_tmp"]["translator_name"] = translator.full_name
            else:
                context.user_data["report_tmp"]["translator_name"] = "غير محدد"
        await show_report_summary(query.message, context)
        return R_CONFIRM
    elif query.data == "translator:manual":
        await query.edit_message_text("👤 أدخل اسم المترجم:", parse_mode="Markdown")
        return R_TRANSLATOR

async def handle_translator_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=2, max_length=100)
    if not valid:
        await update.message.reply_text(f"⚠️ {msg}", reply_markup=_cancel_kb(), parse_mode="Markdown")
        return R_TRANSLATOR
    context.user_data["report_tmp"]["translator_name"] = text
    await update.message.reply_text(f"✅")
    await show_report_summary(update.message, context)
    return R_CONFIRM

async def show_report_summary(message, context):
    d = context.user_data.get("report_tmp", {})
    report_date_obj = d.get('report_date')
    if report_date_obj and hasattr(report_date_obj, 'strftime'):
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(report_date_obj.weekday(), '')
        time_str = format_time_12h(report_date_obj)
        report_date_str = f"📅🕐 {report_date_obj.strftime('%d')} {MONTH_NAMES_AR.get(report_date_obj.month, report_date_obj.month)} {report_date_obj.year} ({day_name}) - {time_str}"
    else:
        report_date_str = str(report_date_obj) if report_date_obj else 'غير محدد'
    
    medical_action = d.get('medical_action', '')
    summary = f"📋 مراجعة

{report_date_str}
👤 {d.get('patient_name')}
🏥 {d.get('hospital_name')}
🏷️ {d.get('department_name')}
👨‍⚕️ {d.get('doctor_name')}
⚕️ {medical_action}"
    
    # عرض شكوى المريض فقط إذا لم تكن استشارة أخيرة
    if medical_action != "استشارة أخيرة" and d.get('complaint_text'):
        summary += f"
💬 شكوى المريض:
{d.get('complaint_text')}"
    
    # عرض قرار الطبيب فقط إذا كان موجوداً - التحقق من عدم التكرار
    if d.get('doctor_decision'):
        doctor_decision_text = d.get('doctor_decision')
        # إذا كان النص يحتوي بالفعل على "قرار الطبيب:" أو "التشخيص:" نعرضه مباشرة
        if any(keyword in doctor_decision_text for keyword in ['قرار الطبيب:', 'التشخيص:', 'الفحوصات المطلوبة:']):
            summary += f"
📝 {doctor_decision_text}"
        else:
            summary += f"
📝 قرار الطبيب:
{doctor_decision_text}"
    
    if d.get('case_status'):
        summary += f"
📋 {d.get('case_status')}"
    if d.get('followup_date_text'):
        summary += f"
📅 {d.get('followup_date_text')}"
    elif d.get('followup_date'):
        followup_date_obj = d.get('followup_date')
        if hasattr(followup_date_obj, 'strftime'):
            days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
            day_name = days_ar.get(followup_date_obj.weekday(), '')
            followup_date_str = f"{followup_date_obj.strftime('%d')} {MONTH_NAMES_AR.get(followup_date_obj.month, followup_date_obj.month)} {followup_date_obj.year} ({day_name})"
        else:
            followup_date_str = str(followup_date_obj)
        followup_time = d.get('followup_time')
        if followup_time:
            # تحويل الوقت إلى صيغة 12 ساعة
            hour, minute = followup_time.split(':')
            hour_int = int(hour)
            if hour_int == 0:
                time_display = f"12:{minute} صباحاً"
            elif hour_int < 12:
                time_display = f"{hour_int}:{minute} صباحاً"
            elif hour_int == 12:
                time_display = f"12:{minute} ظهراً"
            else:
                time_display = f"{hour_int-12}:{minute} مساءً"
            summary += f"
📅🕐 {followup_date_str} - {time_display}"
        else:
            summary += f"
📅 {followup_date_str}"
    else:
        summary += f"
📅 لا يوجد"
    summary += f"
✍️ {d.get('followup_reason') or 'لا يوجد'}
👤 {d.get('translator_name')}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💾 حفظ", callback_data="save_report")], [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]])
    await message.reply_text(summary, reply_markup=keyboard, parse_mode="Markdown")

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "save_report":
        await save_report(query, context)
        return ConversationHandler.END

async def save_report(query, context):
    data_tmp = context.user_data.get("report_tmp", {})
    try:
        # حفظ في قاعدة البيانات
        result = await save_report_to_db(query, context)
        if not result:
            await query.edit_message_text("❌ فشل الحفظ - تحقق من البيانات", parse_mode="Markdown")
            return
        
        report_id, translator_id, translator_name = result
        
        # الرد الفوري للمستخدم
        await query.edit_message_text(
            f"✅ **تم الحفظ بنجاح!**

"
            f"📋 رقم التقرير: {report_id}
"
            f"👤 المريض: {data_tmp.get('patient_name')}

"
            f"⏳ جاري إرسال التقرير للمستخدمين...",
            parse_mode="Markdown"
        )
        
        # إنشاء التقييم والبث في الخلفية
        import asyncio
        asyncio.create_task(_send_report_background(report_id, translator_id, data_tmp, context.bot))
        
        context.user_data.pop("report_tmp", None)
        
    except Exception as e:
        print(f"❌ خطأ في save_report: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(f"❌ خطأ في الحفظ:
{str(e)}", parse_mode="Markdown")


async def _send_report_background(report_id, translator_id, data_tmp, bot):
    """إرسال التقرير في الخلفية"""
    try:
        # إنشاء التقييم (بدون جلب الكائنات)
        try:
            from services.evaluation_service import evaluation_service
            translator_name = data_tmp.get("translator_name", "غير محدد")
            evaluation_service.create_daily_evaluation_by_id(report_id, translator_name)
        except Exception as e:
            print(f"⚠️ خطأ في التقييم: {e}")
        
        # بث التقرير
        await broadcast_report(bot, data_tmp, None)
        print(f"✅ تم إرسال التقرير {report_id} لجميع المستخدمين")
        
    except Exception as e:
        print(f"❌ خطأ في الإرسال الخلفي: {e}")

async def handle_abort(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("report_tmp", None)
    await query.edit_message_text("❌ تم الإلغاء", parse_mode="Markdown")
    return ConversationHandler.END

async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

def register(app):
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 إضافة تقرير جديد$"), start_report)],
        states={
            R_DATE: [CallbackQueryHandler(handle_date_choice, pattern="^date:"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date_text), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_HOSPITAL: [
                CallbackQueryHandler(handle_hospital_page, pattern="^hosp_page:"),
                CallbackQueryHandler(handle_hospital_selection, pattern="^(hospital:|hosp_search)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_search),
                CallbackQueryHandler(handle_abort, pattern="^abort$"),
                CallbackQueryHandler(handle_noop, pattern="^noop$")
            ],
            R_DEPARTMENT: [
                CallbackQueryHandler(handle_department_page, pattern="^dept_page:"),
                CallbackQueryHandler(handle_department_selection, pattern="^(dept:|dept_search)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
                CallbackQueryHandler(handle_abort, pattern="^abort$"),
                CallbackQueryHandler(handle_noop, pattern="^noop$")
            ],
            R_DOCTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor_text), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_ACTION: [CallbackQueryHandler(handle_action_page, pattern="^action_page:"), CallbackQueryHandler(handle_action_choice, pattern="^action:"), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_RADIOLOGY_TYPE: [CallbackQueryHandler(handle_radiology_enter_button, pattern="^radiology:enter$"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiology_type_text), CallbackQueryHandler(handle_abort, pattern="^abort$")],
            R_RADIOLOGY_DELIVERY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiology_delivery_date), CallbackQueryHandler(handle_abort, pattern="^abort$")],
            R_RADIOLOGY_TRANSLATOR: [CallbackQueryHandler(handle_radiology_translator_choice, pattern="^radiology_translator:"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiology_translator_text), CallbackQueryHandler(handle_abort, pattern="^abort$")],
            R_RADIOLOGY_CONFIRM: [CallbackQueryHandler(handle_radiology_confirm, pattern="^radiology:(save|edit)$"), CallbackQueryHandler(handle_abort, pattern="^abort$")],
            R_COMPLAINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_complaint), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_DECISION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_decision), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_CASE_STATUS: [CallbackQueryHandler(handle_case_status_choice, pattern="^case_status:"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_case_status_text), CallbackQueryHandler(handle_abort, pattern="^abort$")],
            R_DATE_TIME: [
                CallbackQueryHandler(handle_date_time_hour, pattern="^time_hour:"),
                CallbackQueryHandler(handle_date_time_minute, pattern="^time_minute:"),
                CallbackQueryHandler(handle_abort, pattern="^abort$"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
            ],
            R_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_followup_choice, pattern="^followup:"),
                CallbackQueryHandler(handle_followup_calendar_nav, pattern="^cal_(prev|next):"),
                CallbackQueryHandler(handle_followup_calendar_day, pattern="^cal_day:"),
                CallbackQueryHandler(handle_abort, pattern="^abort$"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
            ],
            R_FOLLOWUP_TIME: [
                CallbackQueryHandler(handle_followup_time_hour, pattern="^time_hour:"),
                CallbackQueryHandler(handle_followup_time_minute, pattern="^time_minute:"),
                CallbackQueryHandler(handle_followup_time_skip, pattern="^time_skip$"),
                CallbackQueryHandler(handle_followup_time_back_hour, pattern="^time_back_hour$"),
                CallbackQueryHandler(handle_followup_time_change_date, pattern="^time_change_date$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_time_text),
                CallbackQueryHandler(handle_abort, pattern="^abort$"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
            ],
            R_FOLLOWUP_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_reason), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_TRANSLATOR: [CallbackQueryHandler(handle_translator_choice, pattern="^translator:"), MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")],
            R_CONFIRM: [CallbackQueryHandler(handle_confirm, pattern="^save_report$"), CallbackQueryHandler(handle_abort, pattern="^abort$"), CallbackQueryHandler(handle_noop, pattern="^noop$")]
        },
        fallbacks=[CallbackQueryHandler(handle_abort, pattern="^abort$")],
        name="user_reports_add_conv",
        per_chat=True,
        per_user=True
    )
    app.add_handler(conv)
