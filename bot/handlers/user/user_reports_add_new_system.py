def debug_state_monitor(state_name):
    def decorator(func):
        async def wrapper(update, context, *args, **kwargs):
            import sys
            import traceback
            import logging
            logger = logging.getLogger(__name__)
            try:
                print("\n" + "=" * 80)
                print(f"DEBUG_STATE_MONITOR: Entering field: {state_name}")
                print(f"DEBUG_STATE_MONITOR: Update ID = {update.update_id if update else 'N/A'}")
                print(f"DEBUG_STATE_MONITOR: User ID = {update.effective_user.id if update and update.effective_user else 'N/A'}")
                if context and context.user_data:
                    current_state = context.user_data.get('_conversation_state', 'NOT SET')
                    print(f"DEBUG_STATE_MONITOR: Current state = {current_state}")
                    print(f"DEBUG_STATE_MONITOR: Expected state = {state_name}")
                sys.stdout.flush()
                
                logger.info(f"DEBUG_STATE_MONITOR: Entering field: {state_name}")
                logger.info(f"DEBUG_STATE_MONITOR: Current state = {context.user_data.get('_conversation_state', 'NOT SET') if context and context.user_data else 'NOT SET'}")
                
                result = await func(update, context, *args, **kwargs)
                
                print(f"DEBUG_STATE_MONITOR: Exiting field: {state_name}")
                print(f"DEBUG_STATE_MONITOR: Result: {result}")
                print(f"DEBUG_STATE_MONITOR: Result type: {type(result)}")
                print("=" * 80)
                sys.stdout.flush()
                
                logger.info(f"DEBUG_STATE_MONITOR: Exiting field: {state_name}, Result: {result}")
                
                return result
            except Exception as e:
                print("\n" + "=" * 80)
                print(f"ERROR in field: {state_name}")
                print(f"ERROR: Exception: {type(e).__name__}: {e}")
                print("=" * 80)
                traceback.print_exc()
                print("=" * 80)
                sys.stdout.flush()
                logger.error(f"DEBUG_STATE_MONITOR: ERROR in field {state_name}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator

# =============================
# bot/handlers/user/user_reports_add_new_system.py
# 🎨 نظام إضافة التقارير الطبية المتقدم - النظام الكامل
# نظام ذكي مع مسارات مخصصة لكل نوع إجراء
# 10 مسارات - تاريخ ووقت مدمج - أزرار تفاعلية في كل خطوة
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, filters
from telegram.constants import ChatType
import logging

# إعداد logger لهذا الملف
logger = logging.getLogger(__name__)

try:
    from bot.shared_auth import ensure_approved
except ImportError:
    ensure_approved = lambda *a, **kw: True
try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None
try:
    from db.models import Translator, Report, Patient, Hospital, Department, Doctor
except ImportError:
    Translator = Report = Patient = Hospital = Department = Doctor = None
try:
    from config.settings import TIMEZONE
except ImportError:
    TIMEZONE = 'Asia/Riyadh'
from datetime import datetime, timedelta
import calendar
import hashlib
from .user_reports_add_helpers import (
    PREDEFINED_HOSPITALS, PREDEFINED_DEPARTMENTS, DIRECT_DEPARTMENTS,
    PREDEFINED_ACTIONS, validate_text_input, validate_english_only, save_report_to_db,
    broadcast_report, create_evaluation
)
from services.error_monitoring import error_monitor
from services.doctors_smart_search import search_doctors

# استيراد مكتبة التوقيت
from zoneinfo import ZoneInfo  # Python 3.9+ (متوفر في Python 3.12)

# =============================
# تعريف جميع الـ States للمرحلة 1 - State Machine واضحة (FSM)
# كل state له وظيفة محددة ومنفصلة
# =============================

# State Machine لإضافة التقارير الطبية
(
    STATE_SELECT_DATE,           # اختيار التاريخ
    STATE_SELECT_DATE_TIME,      # اختيار التاريخ والوقت
    STATE_SELECT_PATIENT,        # اختيار اسم المريض
    STATE_SELECT_HOSPITAL,       # اختيار المستشفى
    STATE_SELECT_DEPARTMENT,     # اختيار القسم الرئيسي
    STATE_SELECT_SUBDEPARTMENT,  # اختيار القسم الفرعي
    STATE_SELECT_DOCTOR,         # اختيار اسم الطبيب
    STATE_SELECT_ACTION_TYPE,    # اختيار نوع الإجراء
) = range(8)

# =============================
# إصلاح مشكلة conversation handler - callback fallback
# =============================


async def handle_hospital_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج اختيار المستشفى"""
    query = update.callback_query
    await query.answer()

    # استخراج اسم المستشفى
    hospital_name = query.data.replace("select_hospital:", "")

    # حفظ اسم المستشفى
    context.user_data['selected_hospital'] = hospital_name

    # الانتقال للخطوة التالية (اختيار القسم)
    await query.edit_message_text(
        f"✅ تم اختيار المستشفى: {hospital_name}\n\n"
        "الآن يرجى اختيار القسم الطبي:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏥 الطوارئ", callback_data="dept:emergency")],
            [InlineKeyboardButton("🫀 القلب", callback_data="dept:cardiology")],
            [InlineKeyboardButton("🧠 الأعصاب", callback_data="dept:neurology")],
            [InlineKeyboardButton("🫁 الجهاز التنفسي", callback_data="dept:pulmonary")],
            [InlineKeyboardButton("⬅️ رجوع للمستشفيات", callback_data="nav:back")]
        ])
    )

    return STATE_SELECT_DEPARTMENT

# =============================
# معالجات إضافية للبحث عن المستشفيات
# =============================

async def handle_hospital_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج صفحات المستشفيات"""
    query = update.callback_query

    try:
        await query.answer()

        # استخراج رقم الصفحة
        callback_data = query.data
        if ':' in callback_data:
            page_num = int(callback_data.split(':')[1])
        else:
            page_num = 0

        # إعادة عرض قائمة المستشفيات مع الصفحة المطلوبة
        return await show_hospital_search_results(update, context, page_num)

    except Exception as e:
        logger.error(f"خطأ في handle_hospital_page: {e}")
        await query.answer("❌ حدث خطأ")
        return STATE_SELECT_HOSPITAL

async def show_hospital_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0) -> int:
    """عرض نتائج البحث عن المستشفيات"""
    query = update.callback_query

    # قائمة المستشفيات (يمكن استبدالها بقاعدة البيانات)
    hospitals = [
        "مستشفى الملك فيصل", "مستشفى الملك خالد", "مستشفى الملك عبدالعزيز",
        "مستشفى الثورة", "مستشفى السبعين", "مستشفى الجراحي",
        "مستشفى الأطفال", "مستشفى النساء والولادة", "مستشفى الصدر",
        "مستشفى العيون", "مستشفى الأسنان", "مستشفى الطوارئ"
    ]

    # تقسيم لصفحات (5 مستشفيات لكل صفحة)
    items_per_page = 5
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page

    current_hospitals = hospitals[start_idx:end_idx]

    # إنشاء الأزرار
    keyboard = []
    for hospital in current_hospitals:
        keyboard.append([InlineKeyboardButton(
            f"🏥 {hospital}",
            callback_data=f"select_hospital:{hospital}"
        )])

    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"hosp_page:{page-1}"))

    if end_idx < len(hospitals):
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"hosp_page:{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # زر الإلغاء
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])

    markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(
            f"🏥 اختر المستشفى (الصفحة {page + 1}):\n\n" +
            f"📊 المجموع: {len(hospitals)} مستشفى",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في تحديث الرسالة: {e}")
        # إذا فشل التحديث، أرسل رسالة جديدة
        await query.message.reply_text(
            f"🏥 اختر المستشفى (الصفحة {page + 1}):\n\n" +
            f"📊 المجموع: {len(hospitals)} مستشفى",
            reply_markup=markup
        )

    return STATE_SELECT_HOSPITAL

# تعيين الأسماء القديمة للتوافق المؤقت (سيتم إزالتها تدريجياً)
R_DATE = STATE_SELECT_DATE
R_DATE_TIME = STATE_SELECT_DATE_TIME
R_PATIENT = STATE_SELECT_PATIENT
R_HOSPITAL = STATE_SELECT_HOSPITAL
R_DEPARTMENT = STATE_SELECT_DEPARTMENT
R_SUBDEPARTMENT = STATE_SELECT_SUBDEPARTMENT
R_DOCTOR = STATE_SELECT_DOCTOR
R_ACTION_TYPE = STATE_SELECT_ACTION_TYPE

# =============================
# State History Stack Manager
# إدارة تاريخ التنقل بين الـ states
# =============================

class StateHistoryManager:
    """مدير تاريخ الـ states لضمان التنقل الصحيح خطوة بخطوة"""

    def __init__(self):
        self._history = []

    def push_state(self, state):
        """إضافة state جديد إلى التاريخ - منع التكرار"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"📝 push_state: Called with state {state}, current history={self._history}")
        if state is not None and (not self._history or self._history[-1] != state):
            self._history.append(state)
            logger.info(f"📝 push_state: ✅ Added state {state}, new history={self._history}")
        else:
            logger.info(f"📝 push_state: ⚠️ State {state} already exists or None, history={self._history}")

    def pop_state(self):
        """إزالة وإرجاع آخر state"""
        if self._history:
            return self._history.pop()
        return None

    def peek_state(self):
        """رؤية آخر state بدون إزالته"""
        if self._history:
            return self._history[-1]
        return None

    def get_previous_state(self):
        """الحصول على الـ state السابق"""
        if len(self._history) >= 2:
            return self._history[-2]
        return None

    def clear_history(self):
        """تنظيف التاريخ"""
        self._history.clear()

    def get_history(self):
        """الحصول على التاريخ الكامل"""
        return self._history.copy()

    def set_history(self, history):
        """تحديث التاريخ"""
        if isinstance(history, list):
            self._history = history.copy()

    @staticmethod
    def get_state_manager(context):
        """الحصول على state manager من context"""
        report_tmp = context.user_data.get("report_tmp", {})
        if "state_manager" not in report_tmp:
            report_tmp["state_manager"] = StateHistoryManager()
        return report_tmp["state_manager"]

    @staticmethod
    def transition_to_state(context, new_state):
        """دالة مساعدة للانتقال إلى state جديد مع حفظه في التاريخ"""
        state_manager = StateHistoryManager.get_state_manager(context)
        state_manager.push_state(new_state)
        context.user_data['_conversation_state'] = new_state

# =============================
# State Data Managers - فصل البيانات
# =============================

class PatientDataManager:
    """مدير بيانات المرضى - منفصل تماماً عن الأطباء"""

    @staticmethod
    def clear_patient_data(context):
        """تنظيف بيانات المريض عند الرجوع"""
        report_tmp = context.user_data.get("report_tmp", {})
        patient_keys = ["patient_name", "patient_id", "patient_search_query"]
        for key in patient_keys:
            report_tmp.pop(key, None)

    @staticmethod
    def get_patient_data(context):
        """الحصول على بيانات المريض"""
        report_tmp = context.user_data.get("report_tmp", {})
        return {
            "patient_name": report_tmp.get("patient_name"),
            "patient_id": report_tmp.get("patient_id"),
        }

class DoctorDataManager:
    """مدير بيانات الأطباء - منفصل تماماً عن المرضى"""

    @staticmethod
    def clear_doctor_data(context):
        """تنظيف بيانات الطبيب عند الرجوع"""
        report_tmp = context.user_data.get("report_tmp", {})
        doctor_keys = ["doctor_name", "doctor_id", "doctor_manual_mode", "doctor_search_query"]
        for key in doctor_keys:
            report_tmp.pop(key, None)

    @staticmethod
    def get_doctor_data(context):
        """الحصول على بيانات الطبيب"""
        report_tmp = context.user_data.get("report_tmp", {})
        return {
            "doctor_name": report_tmp.get("doctor_name"),
            "doctor_id": report_tmp.get("doctor_id"),
            "manual_mode": report_tmp.get("doctor_manual_mode", False),
        }

class DepartmentDataManager:
    """مدير بيانات الأقسام - منفصل تماماً عن المرضى والأطباء"""

    @staticmethod
    def clear_department_data(context, full_clear=False):
        """تنظيف بيانات القسم عند الرجوع

        Args:
            full_clear: إذا True، ينظف جميع بيانات القسم (للرجوع إلى شاشة الأقسام)
                       إذا False، ينظف فقط بيانات الاختيار الحالي (للرجوع إلى شاشة الطبيب)
        """
        report_tmp = context.user_data.get("report_tmp", {})

        if full_clear:
            # تنظيف كامل للرجوع إلى شاشة الأقسام
            department_keys = ["department_name", "departments_search", "main_department", "subdepartments_list"]
            for key in department_keys:
                report_tmp.pop(key, None)
        else:
            # تنظيف جزئي للرجوع إلى شاشة الطبيب (الاحتفاظ بالمستشفى والقسم الأساسي)
            partial_keys = ["departments_search", "main_department", "subdepartments_list"]
            for key in partial_keys:
                report_tmp.pop(key, None)
            # الاحتفاظ بـ department_name و hospital_name للبحث عن الأطباء

    @staticmethod
    def get_department_data(context):
        """الحصول على بيانات القسم"""
        report_tmp = context.user_data.get("report_tmp", {})
        return {
            "department_name": report_tmp.get("department_name"),
            "main_department": report_tmp.get("main_department"),
        }

# مسار 1: استشارة جديدة (7-15) - تاريخ ووقت منفصلان
(
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DECISION,
    NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_TIME,
    NEW_CONSULT_FOLLOWUP_REASON, NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM
) = range(7, 15)

# مسار 2: مراجعة/عودة دورية (16-23) - مدمج بالفعل ✓ (تم تصحيح التداخل)
(
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM
) = range(16, 24)

# مسار 3: طوارئ (24-33) - مدمج بالفعل ✓ (تم تصحيح التداخل)
(
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION,
    EMERGENCY_STATUS, EMERGENCY_ADMISSION_TYPE, EMERGENCY_ROOM_NUMBER,
    EMERGENCY_DATE_TIME, EMERGENCY_REASON,
    EMERGENCY_TRANSLATOR, EMERGENCY_CONFIRM
) = range(24, 34)

# مسار 4: ترقيد (34-40) - سيصبح مدمج (تم تصحيح التداخل)
(
    ADMISSION_REASON, ADMISSION_ROOM, ADMISSION_NOTES,
    ADMISSION_FOLLOWUP_DATE, ADMISSION_FOLLOWUP_REASON,
    ADMISSION_TRANSLATOR, ADMISSION_CONFIRM
) = range(34, 41)

# مسار 5: استشارة مع قرار عملية (41-50) - سيصبح مدمج (تم تصحيح التداخل)
(
    SURGERY_CONSULT_DIAGNOSIS, SURGERY_CONSULT_DECISION, SURGERY_CONSULT_NAME_EN,
    SURGERY_CONSULT_SUCCESS_RATE, SURGERY_CONSULT_BENEFIT_RATE, SURGERY_CONSULT_TESTS, SURGERY_CONSULT_FOLLOWUP_DATE,
    SURGERY_CONSULT_FOLLOWUP_REASON,
    SURGERY_CONSULT_TRANSLATOR, SURGERY_CONSULT_CONFIRM
) = range(41, 51)

# مسار 6: عملية (51-57) - سيصبح مدمج (تم تصحيح التداخل)
(
    OPERATION_DETAILS_AR, OPERATION_NAME_EN, OPERATION_NOTES,
    OPERATION_FOLLOWUP_DATE, OPERATION_FOLLOWUP_REASON,
    OPERATION_TRANSLATOR, OPERATION_CONFIRM
) = range(51, 58)

# مسار 7: استشارة أخيرة (58-62) (تم تصحيح التداخل)
(
    FINAL_CONSULT_DIAGNOSIS, FINAL_CONSULT_DECISION, FINAL_CONSULT_RECOMMENDATIONS,
    FINAL_CONSULT_TRANSLATOR, FINAL_CONSULT_CONFIRM
) = range(58, 63)

# مسار 8: خروج من المستشفى (63-70) - سيصبح مدمج (تم تصحيح التداخل)
(
    DISCHARGE_TYPE, DISCHARGE_ADMISSION_SUMMARY, DISCHARGE_OPERATION_DETAILS,
    DISCHARGE_OPERATION_NAME_EN, DISCHARGE_FOLLOWUP_DATE, DISCHARGE_FOLLOWUP_REASON,
    DISCHARGE_TRANSLATOR, DISCHARGE_CONFIRM
) = range(63, 71)

# مسار 9: علاج طبيعي / أجهزة تعويضية (71-81) - سيصبح مدمج (تم تصحيح التداخل)
(
    REHAB_TYPE, PHYSICAL_THERAPY_DETAILS, PHYSICAL_THERAPY_FOLLOWUP_DATE,
    PHYSICAL_THERAPY_FOLLOWUP_REASON,
    PHYSICAL_THERAPY_TRANSLATOR, PHYSICAL_THERAPY_CONFIRM,
    DEVICE_NAME_DETAILS, DEVICE_FOLLOWUP_DATE,
    DEVICE_FOLLOWUP_REASON, DEVICE_TRANSLATOR, DEVICE_CONFIRM
) = range(71, 82)

# مسار 10: أشعة وفحوصات (82-85) (تم تصحيح التداخل)
(
    RADIOLOGY_TYPE, RADIOLOGY_DELIVERY_DATE, RADIOLOGY_TRANSLATOR, RADIOLOGY_CONFIRM
) = range(82, 86)

# مسار 11: عودة بعد استخدام الأدوية - تم حذفه

# =============================
# دوال مساعدة للأزرار
# =============================

MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

WEEKDAYS_AR = ["س", "أ", "ث", "ر", "خ", "ج", "س"]


def _chunked(seq, size):
    return [seq[i: i + size] for i in range(0, len(seq), size)]


def _cancel_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء العملية", callback_data="nav:cancel")]])


def _nav_buttons(show_back=True):
    """أزرار التنقل الأساسية"""
    buttons = []

    if show_back:
        buttons.append([InlineKeyboardButton(
            "🔙 رجوع", callback_data="nav:back")])

    buttons.append([InlineKeyboardButton(
        "❌ إلغاء العملية", callback_data="nav:cancel")])

    return InlineKeyboardMarkup(buttons)


def format_time_12h(dt: datetime) -> str:
    """تحويل الوقت إلى صيغة 12 ساعة مع التمييز بين صباح/مساء"""
    hour = dt.hour
    minute = dt.minute
    if hour == 0:
        return f"12:{minute:02d} صباحاً"
    elif hour < 12:
        return f"{hour}:{minute:02d} صباحاً"
    else:
        return f"{hour-12}:{minute:02d} مساءً"


def _build_hour_keyboard():
    """بناء لوحة اختيار الساعات بصيغة 12 ساعة"""
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
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _build_minute_keyboard(hour: str):
    # دالة بناء لوحة دقائق للمتابعة (لمنع الخطأ)
    def _build_followup_minute_keyboard(hour: str):
        # بناء لوحة مفاتيح الدقائق (0، 15، 30، 45)
        minute_options = ["00", "15", "30", "45"]
        keyboard = [
            [InlineKeyboardButton(f"{hour}:{m}", callback_data=f"followup_time_minute:{hour}:{m}") for m in minute_options],
            [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"), InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ]
        return InlineKeyboardMarkup(keyboard)
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
            row.append(
    InlineKeyboardButton(
        label,
         callback_data=f"time_minute:{hour}:{m}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(
        "⏭️ بدون وقت", callback_data="time_skip")])
    keyboard.append([
        InlineKeyboardButton("🔙 تغيير الساعة", callback_data="time_back_hour"),
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
    ])
    keyboard.append([InlineKeyboardButton(
        "❌ إلغاء", callback_data="nav:cancel")])
    return InlineKeyboardMarkup(keyboard)

# =============================
# دوال الرجوع الذكي
# =============================


async def handle_cancel_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إلغاء العملية - تنظيف شامل لجميع البيانات"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    if query:
        await query.answer("تم إلغاء العملية")
        try:
            await query.edit_message_text("❌ تم إلغاء العملية.")
        except Exception as e:
            logger.debug(f"⚠️ Could not edit message: {e}")
            try:
                await query.message.reply_text("❌ تم إلغاء العملية.")
            except:
                pass
    elif update.message:
        await update.message.reply_text("❌ تم إلغاء العملية.")
    
    # تنظيف شامل لجميع البيانات
    try:
        # 1. تنظيف report_tmp (يحتوي على جميع بيانات التقرير)
        if "report_tmp" in context.user_data:
            report_tmp = context.user_data["report_tmp"]
            
            # تنظيف state_manager إذا كان موجوداً
            if "state_manager" in report_tmp:
                state_manager = report_tmp.get("state_manager")
                if state_manager and hasattr(state_manager, 'clear_history'):
                    state_manager.clear_history()
                    logger.info("✅ تم تنظيف state_manager history")
            
            # حذف report_tmp بالكامل
            context.user_data.pop("report_tmp", None)
            logger.info("✅ تم حذف report_tmp")
        
        # 2. تنظيف conversation state
        context.user_data.pop("_conversation_state", None)
        logger.info("✅ تم تنظيف _conversation_state")
        
        # 3. تنظيف search type
        context.user_data.pop("_current_search_type", None)
        logger.info("✅ تم تنظيف _current_search_type")
        
        # 4. تنظيف أي بيانات إضافية قد تكون متبقية
        keys_to_remove = [
            "patient_search_mode",
            "hospitals_search_mode",
            "departments_search_mode",
            "doctor_manual_mode",
            "step_history"
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        logger.info("✅ تم تنظيف جميع البيانات المتعلقة بالتقرير")
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف البيانات عند الإلغاء: {e}", exc_info=True)
        # حتى في حالة الخطأ، نحاول حذف report_tmp على الأقل
        context.user_data.pop("report_tmp", None)
        context.user_data.pop("_conversation_state", None)
        context.user_data.pop("_current_search_type", None)
    
    return ConversationHandler.END


# الدوال القديمة تم استبدالها بـ StateHistoryManager و Data Managers المنفصلة

async def handle_back_navigation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرجوع للخطوة السابقة - يعيد الـ state السابق فقط"""
    import logging
    logger = logging.getLogger(__name__)

    query = update.callback_query
    await query.answer()

    try:
        # الحصول على State History Manager
        state_manager = StateHistoryManager.get_state_manager(context)
        current_history = state_manager.get_history()

        logger.info(f"🔙 handle_back_navigation: current_history={current_history}")

        # إذا لم تكن هناك history
        if not current_history:
            logger.warning("🔙 handle_back_navigation: No history available")
            return ConversationHandler.END

        # الحصول على الـ state الحالي أولاً
        current_state = context.user_data.get('_conversation_state')
        
        # الحصول على الـ state السابق
        previous_step = state_manager.get_previous_state()

        logger.info(f"🔙 handle_back_navigation: current_state={current_state}, previous_step={previous_step}, history_length={len(current_history)}")
        logger.info(f"🔙 handle_back_navigation: FULL history={current_history}")
        logger.info(f"🔙 handle_back_navigation: Current context _conversation_state: {context.user_data.get('_conversation_state')}")
        logger.info(f"🔙 handle_back_navigation: Current context states: {context.user_data.get('report_tmp', {}).get('state_manager', {}).get_history() if 'report_tmp' in context.user_data else 'No report_tmp'}")

        # طباعة تفصيلية عن الـ states
        if 'report_tmp' in context.user_data and 'state_manager' in context.user_data['report_tmp']:
            manager = context.user_data['report_tmp']['state_manager']
            logger.info(f"🔙 StateManager history: {manager.get_history()}")
            logger.info(f"🔙 StateManager peek_state: {manager.peek_state()}")
            logger.info(f"🔙 StateManager get_previous_state: {manager.get_previous_state()}")

        # منطق بسيط: الرجوع خطوة واحدة للخلف فقط
        if previous_step is None:
            # إذا كانت هناك خطوة واحدة فقط، نرجع للبداية
            previous_step = STATE_SELECT_DATE
            state_manager.clear_history()
            logger.info("🔙 handle_back_navigation: Going to start (STATE_SELECT_DATE)")
        else:
            # إزالة الـ state الحالي من التاريخ
            popped = state_manager.pop_state()
            logger.info(f"🔙 handle_back_navigation: popped={popped}, Going back to {previous_step}, new_history={state_manager.get_history()}")

        # تحديث الـ conversation state للخطوة السابقة
        context.user_data['_conversation_state'] = previous_step

        # عرض رسالة تأكيد الرجوع
        step_names = {
            STATE_SELECT_DATE: "اختيار التاريخ",
            STATE_SELECT_PATIENT: "اختيار المريض",
            STATE_SELECT_HOSPITAL: "اختيار المستشفى",
            STATE_SELECT_DEPARTMENT: "اختيار القسم",
            STATE_SELECT_SUBDEPARTMENT: "اختيار القسم الفرعي",
            STATE_SELECT_DOCTOR: "اختيار الطبيب",
            R_ACTION_TYPE: "اختيار نوع الإجراء"
        }
        step_name = step_names.get(previous_step, "الخطوة السابقة")

        # إرسال رسالة تأكيد الرجوع
        await query.answer(f"🔙 تم الرجوع لـ: {step_name}", show_alert=False)

        # Rendering Logic: عرض الشاشة المناسبة حسب الـ state السابق
        logger.info(f"🔙 Rendering step: {previous_step}")

        if previous_step == STATE_SELECT_DATE:
            await query.message.delete()
            await render_date_selection(query.message, context)
            return STATE_SELECT_DATE

        elif previous_step == STATE_SELECT_PATIENT:
            PatientDataManager.clear_patient_data(context)
            await query.message.delete()
            await show_patient_selection(query.message, context)
            return STATE_SELECT_PATIENT

        elif previous_step == STATE_SELECT_HOSPITAL:
            await query.message.delete()
            await render_hospital_selection(query.message, context)
            return STATE_SELECT_HOSPITAL

        elif previous_step == STATE_SELECT_DEPARTMENT:
            DepartmentDataManager.clear_department_data(context, full_clear=False)
            await query.message.delete()
            await render_department_selection(query.message, context)
            return STATE_SELECT_DEPARTMENT

        elif previous_step == STATE_SELECT_SUBDEPARTMENT:
            # الرجوع من القسم الفرعي إلى القسم الرئيسي
            DepartmentDataManager.clear_department_data(context, full_clear=False)
            await query.message.delete()
            await render_department_selection(query.message, context)
            return STATE_SELECT_DEPARTMENT

        elif previous_step == STATE_SELECT_DOCTOR:
            DoctorDataManager.clear_doctor_data(context)
            await query.message.delete()
            await render_doctor_selection(query.message, context)
            return STATE_SELECT_DOCTOR

        elif previous_step == R_ACTION_TYPE:
            # الرجوع إلى شاشة نوع الإجراء
            context.user_data["report_tmp"].pop("medical_action", None)
            context.user_data["report_tmp"].pop("action_type", None)
            context.user_data["report_tmp"].pop("current_flow", None)
            await query.message.delete()
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE

        # معالجة عامة: للرجوع من أي state بعد R_ACTION_TYPE
        # نحاول إعادة عرض الشاشة المناسبة
        else:
            logger.info(f"🔙 handle_back_navigation: Generic handling for state {previous_step}")
            
            # محاولة إعادة عرض الشاشة المناسبة حسب الـ state
            # إذا كان الـ state السابق هو R_ACTION_TYPE، نعرض شاشة نوع الإجراء
            if previous_step == R_ACTION_TYPE:
                context.user_data["report_tmp"].pop("medical_action", None)
                context.user_data["report_tmp"].pop("action_type", None)
                context.user_data["report_tmp"].pop("current_flow", None)
                await query.message.delete()
                await show_action_type_menu(query.message, context)
                return R_ACTION_TYPE
            
            # للـ states الأخرى، نحاول إعادة عرض الشاشة المناسبة
            # نستخدم fallback بسيط - إعادة عرض نفس الشاشة
            try:
                await query.message.delete()
            except:
                pass
            # إعادة عرض نفس الشاشة (سيتم التعامل معها من خلال ConversationHandler)
            # نعيد الـ state السابق للسماح للـ ConversationHandler بالتعامل معه
            return previous_step

    except Exception as e:
        logger.error(f"❌ Error in handle_back_navigation: {e}", exc_info=True)
        return ConversationHandler.END


async def render_date_selection(message, context):
    """عرض شاشة اختيار التاريخ - rendering فقط"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 إدخال التاريخ الحالي",
        callback_data="date:now")],
        [InlineKeyboardButton("📅 إدخال من التقويم",
        callback_data="date:calendar")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "📅 **إضافة تقرير جديد** (الخطوة 1 من 5)\n\n"
        "اختر طريقة إدخال التاريخ:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def render_patient_selection(message, context):
    """عرض شاشة اختيار المريض - rendering فقط"""
    keyboard = []

    # زر البحث الذكي (inline search)
    keyboard.append([InlineKeyboardButton(
        "🔍 بحث عن مريض",
        switch_inline_query_current_chat=""
    )])
    
    # زر عرض قائمة كاملة مع pagination
    keyboard.append([InlineKeyboardButton(
        "📋 عرض جميع الأسماء",
        callback_data="patient:show_list:0"
    )])

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = "👤 **اسم المريض** (الخطوة 2 من 5)\n\n"
    text += "**خيارات البحث:**\n"
    text += "• 🔍 **بحث عن مريض:** للبحث السريع (حتى 50 نتيجة)\n"
    text += "• 📋 **عرض جميع الأسماء:** لعرض جميع الأسماء مع التنقل بين الصفحات\n\n"
    text += "اختر الطريقة المناسبة:"

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def render_hospital_selection(message, context):
    """عرض شاشة اختيار المستشفى - rendering فقط"""
    text, keyboard, search = _build_hospitals_keyboard(
        0, "", context)
    context.user_data["report_tmp"]["hospitals_search"] = search
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def render_department_selection(message, context):
    """عرض شاشة اختيار القسم - rendering فقط"""
    text, keyboard, search = _build_departments_keyboard(
        0, "", context)
    context.user_data["report_tmp"]["departments_search"] = search

    # محاولة حذف الرسالة القديمة إذا كانت موجودة
    try:
        if hasattr(message, 'delete') and message.chat_id:
            await message.delete()
    except Exception:
        pass

    # إرسال رسالة جديدة
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def render_doctor_selection(message, context):
    """عرض شاشة اختيار الطبيب - rendering فقط مع تحميل البيانات"""

    # تنظيف بيانات الطبيب القديمة
    DoctorDataManager.clear_doctor_data(context)

    # التحقق من وجود بيانات المستشفى والقسم
    report_tmp = context.user_data.get("report_tmp", {})
    hospital_name = report_tmp.get("hospital_name", "")
    department_name = report_tmp.get("department_name", "")

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🎯 render_doctor_selection: hospital='{hospital_name}', department='{department_name}'")
    logger.info(f"🎯 render_doctor_selection: all report_tmp keys: {list(report_tmp.keys())}")

    keyboard = []

    # زر البحث الذكي (inline search) - للأطباء فقط
    keyboard.append([InlineKeyboardButton(
        "🔍 بحث عن طبيب",
        switch_inline_query_current_chat=""
    )])

    # زر إدخال يدوي
    keyboard.append([InlineKeyboardButton(
        "✏️ إدخال يدوي",
        callback_data="doctor_manual"
    )])

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = "👨‍⚕️ **اسم الطبيب** (الخطوة 5 من 5)\n\n"

    if hospital_name and department_name:
        text += f"🏥 **المستشفى:** {hospital_name}\n"
        text += f"🏷️ **القسم:** {department_name}\n\n"
        text += "اضغط على زر '🔍 بحث عن طبيب' للبحث عن الطبيب.\n"
        text += "سيظهر اسم البوت في الكيبورد ويمكنك البحث والاختيار مباشرة.\n\n"
        text += "أو اضغط على '✏️ إدخال يدوي' إذا كان الطبيب غير موجود."
    else:
        text += "⚠️ **تحذير:** يرجى اختيار المستشفى والقسم أولاً للبحث عن الأطباء.\n\n"
        text += "اضغط على زر '🔙 رجوع' للعودة واختيار المستشفى والقسم."

    try:
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة اختيار الطبيب: {e}", exc_info=True)
        # محاولة بدون parse_mode
        try:
            await message.reply_text(
                text.replace("**", ""),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")

# =============================
# الخطوات الأساسية المشتركة
# =============================


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة تقرير جديد"""
    import logging
    logger = logging.getLogger(__name__)
    
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

        # تهيئة State History Manager
        state_manager = StateHistoryManager()
        state_manager.push_state(STATE_SELECT_DATE)

        # تهيئة البيانات مع State Manager
        context.user_data["report_tmp"] = {
            "state_manager": state_manager,
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


async def handle_date_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التاريخ"""
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
            from datetime import timezone, timedelta
            ist = timezone(timedelta(hours=5, minutes=30))
            now = datetime.now(timezone.utc).astimezone(ist)

        # حفظ الوقت بتوقيت الهند
        context.user_data["report_tmp"]["report_date"] = now
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DATE)

        # عرض التاريخ والوقت بتوقيت الهند
        days_ar = {
    0: 'الاثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
     6: 'الأحد'}
        day_name = days_ar.get(now.weekday(), '')

        # استخدام format_time_12h لعرض الوقت بصيغة 12 ساعة بتوقيت الهند
        time_str = format_time_12h(now)
        date_str = now.strftime('%Y-%m-%d')

        # حفظ الـ state في التاريخ قبل الانتقال للمريض
        state_manager = StateHistoryManager.get_state_manager(context)
        state_manager.push_state(STATE_SELECT_PATIENT)
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


async def handle_main_calendar_nav(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم التاريخ الرئيسي"""
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


async def handle_main_calendar_day(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ من التقويم الرئيسي"""
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


async def handle_date_time_back_hour(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
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


async def handle_date_time_hour(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
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
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
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


async def handle_date_time_minute(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
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
        dt = datetime.combine(
    pending_date.date(), time(
        int(hour), int(minute)))
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
    0: 'الاثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
     6: 'الأحد'}
        day_name = days_ar.get(dt.weekday(), '')
        date_str = f"📅🕐 {
    dt.strftime('%d')} {
        MONTH_NAMES_AR.get(
            dt.month, dt.month)} {
                dt.year} ({day_name}) - {time_display}"

        # حفظ الـ state في التاريخ قبل الانتقال للمريض
        state_manager = StateHistoryManager.get_state_manager(context)
        state_manager.push_state(STATE_SELECT_PATIENT)
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


async def handle_date_time_skip(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """تخطي اختيار الوقت"""
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
    0: 'الاثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
     6: 'الأحد'}
        day_name = days_ar.get(dt.weekday(), '')

        # حفظ الـ state في التاريخ قبل الانتقال للمريض
        state_manager = StateHistoryManager.get_state_manager(context)
        state_manager.push_state(STATE_SELECT_PATIENT)
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


async def show_patient_selection(message, context, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_PATIENT)

    # تحديث الـ conversation state للـ inline queries
    context.user_data['_conversation_state'] = STATE_SELECT_PATIENT
    context.user_data['_current_search_type'] = 'patient'  # علامة لتحديد نوع البحث

    # استدعاء rendering function
    await render_patient_selection(message, context)


async def show_patient_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """عرض قائمة المرضى مع pagination"""
    query = update.callback_query
    if query:
        await query.answer()
    
    items_per_page = 10  # 10 أسماء في كل صفحة
    
    with SessionLocal() as s:
        # جلب جميع المرضى مرتبين حسب الاسم
        all_patients = s.query(Patient).order_by(Patient.full_name).all()
        total = len(all_patients)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        patients_page = all_patients[start_idx:end_idx]
        
        keyboard = []
        
        # إضافة أزرار المرضى
        for patient in patients_page:
            keyboard.append([InlineKeyboardButton(
                f"👤 {patient.full_name}",
                callback_data=f"patient_idx:{patient.id}"
            )])
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"patient:show_list:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"patient:show_list:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # أزرار إضافية
        keyboard.append([
            InlineKeyboardButton("🔍 بحث سريع", switch_inline_query_current_chat=""),
            InlineKeyboardButton("🔙 رجوع", callback_data="patient:back_to_menu")
        ])
        
        text = f"👤 **قائمة المرضى**\n\n"
        text += f"📊 **العدد الإجمالي:** {total} مريض\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        text += "اختر المريض من القائمة:"
        
        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        return STATE_SELECT_PATIENT

async def handle_patient_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callbacks قائمة المرضى"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("patient:show_list:"):
        try:
            page = int(query.data.split(":")[-1])
            return await show_patient_list(update, context, page)
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing page number: {e}")
            await query.answer("⚠️ خطأ في رقم الصفحة", show_alert=True)
            return STATE_SELECT_PATIENT
    elif query.data == "patient:back_to_menu":
        await render_patient_selection(query.message, context)
        return STATE_SELECT_PATIENT
    
    return STATE_SELECT_PATIENT

async def handle_patient_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المريض من القائمة"""
    query = update.callback_query
    await query.answer()

    # معالجة callbacks قائمة المرضى
    if query.data.startswith("patient:show_list:") or query.data == "patient:back_to_menu":
        return await handle_patient_list_callback(update, context)

    # اختيار من القائمة
    patient_id = int(query.data.split(":", 1)[1])

    # جلب اسم المريض من قاعدة البيانات
    with SessionLocal() as s:
        patient = s.query(Patient).filter_by(id=patient_id).first()
        if patient:
            patient_name = patient.full_name
            context.user_data["report_tmp"]["patient_name"] = patient_name
            context.user_data["report_tmp"].setdefault("step_history", []).append(R_PATIENT)
            context.user_data["report_tmp"].pop("patient_search_mode", None)

            await query.edit_message_text(
                f"✅ **تم اختيار المريض**\n\n"
                f"👤 **المريض:**\n"
                f"{patient_name}"
            )
            await show_hospitals_menu(query.message, context)
            return STATE_SELECT_HOSPITAL
        else:
            await query.answer("⚠️ خطأ: لم يتم العثور على المريض", show_alert=True)
            await show_patient_selection(query.message, context)
            return STATE_SELECT_PATIENT


async def handle_patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المريض يدوياً أو اختياره من inline query"""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    # التحقق أولاً إذا كان المريض تم اختياره بالفعل
    report_tmp = context.user_data.get("report_tmp", {})
    if report_tmp.get("patient_name"):
        # المريض تم اختياره بالفعل، الانتقال إلى خطوة المستشفى
        print("handle_patient: Patient already selected, moving to hospital selection")
        sys.stdout.flush()
        logger.info("handle_patient: Patient already selected, moving to hospital selection")
        await show_hospitals_menu(update.message, context)
        return STATE_SELECT_HOSPITAL
    
    if not update.message or not update.message.text:
        # لا توجد رسالة نصية، إعادة عرض القائمة
        await show_patient_selection(update.message, context)
        return STATE_SELECT_PATIENT
    
    text = update.message.text.strip()

    # التحقق إذا كان هذا اختيار من inline query
    if text.startswith("__PATIENT_SELECTED__:"):
        parts = text.split(":", 2)
        if len(parts) == 3:
            try:
                patient_id = int(parts[1])
                patient_name = parts[2]

                # حفظ اسم المريض
                context.user_data.setdefault("report_tmp", {})["patient_name"] = patient_name
                context.user_data["report_tmp"]["patient_id"] = patient_id
                context.user_data["report_tmp"].setdefault("step_history", []).append(R_PATIENT)

                # حذف الرسالة الخاصة
                try:
                    await update.message.delete()
                except:
                    pass

                # إرسال رسالة تأكيد
                await update.message.reply_text(
                    f"✅ **تم اختيار المريض**\n\n"
                    f"👤 **المريض:**\n"
                    f"{patient_name}",
                    parse_mode="Markdown"
                )

                # الانتقال إلى خطوة المستشفى
                try:
                    print(f"handle_patient: Patient selected from inline query: {patient_name}, moving to hospital")
                    sys.stdout.flush()
                    logger.info(f"handle_patient: Patient selected from inline query: {patient_name}, moving to hospital")
                except UnicodeEncodeError:
                    # في حالة خطأ الترميز، استخدم repr
                    print(f"handle_patient: Patient selected from inline query, moving to hospital")
                    sys.stdout.flush()
                    logger.info(f"handle_patient: Patient selected from inline query, moving to hospital")
                await show_hospitals_menu(update.message, context)
                return STATE_SELECT_HOSPITAL
            except (ValueError, IndexError) as e:
                # معالجة خطأ الترميز عند تسجيل الخطأ
                try:
                    logger.error(f"handle_patient: Error parsing patient selection: {str(e)}")
                except UnicodeEncodeError:
                    logger.error("handle_patient: Error parsing patient selection (encoding error)")
                await update.message.reply_text("⚠️ خطأ في قراءة بيانات المريض")
                await show_patient_selection(update.message, context)
                return STATE_SELECT_PATIENT
        else:
            # تنسيق غير صحيح
            logger.warning(f"handle_patient: Invalid patient selection format: {text}")
            await show_patient_selection(update.message, context)
            return STATE_SELECT_PATIENT

    # التحقق إذا كان في وضع البحث
    search_mode = report_tmp.get("patient_search_mode", False)
    if search_mode:
        # البحث عن المرضى
        context.user_data["report_tmp"]["patient_search_mode"] = False
        if len(text) < 2:
            await update.message.reply_text(
                "⚠️ **خطأ: النص قصير جداً**\n\n"
                "يرجى إدخال حرفين على الأقل للبحث:",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]]),
                parse_mode="Markdown"
            )
            return STATE_SELECT_PATIENT
        await show_patient_selection(update.message, context, search_query=text)
        return STATE_SELECT_PATIENT

    # إذا لم يكن في وضع البحث ولم يتم اختيار المريض، نعيد عرض القائمة
    print("handle_patient: No patient selected, showing patient selection menu")
    sys.stdout.flush()
    logger.info("handle_patient: No patient selected, showing patient selection menu")
    await show_patient_selection(update.message, context)
    return STATE_SELECT_PATIENT


def _sort_hospitals_custom(hospitals_list):
    """ترتيب المستشفيات حسب الأولوية: Manipal -> Aster -> Bangalore -> البقية"""
    def get_sort_key(hospital):
        hospital_lower = hospital.lower()
        
        # 1. مستشفيات Manipal أولاً
        if 'manipal' in hospital_lower:
            return (0, hospital)
        
        # 2. مستشفيات Aster ثانياً
        if 'aster' in hospital_lower:
            return (1, hospital)
        
        # 3. مستشفيات Bangalore ثالثاً
        if 'bangalore' in hospital_lower or 'bengaluru' in hospital_lower:
            return (2, hospital)
        
        # 4. البقية
        return (3, hospital)
    
    return sorted(hospitals_list, key=get_sort_key)


def _build_hospitals_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح المستشفيات مع بحث"""
    items_per_page = 8

    # تصفية المستشفيات إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        filtered_hospitals = [
    h for h in PREDEFINED_HOSPITALS if search_lower in h.lower()]
        hospitals_list = _sort_hospitals_custom(filtered_hospitals)
    else:
        hospitals_list = _sort_hospitals_custom(PREDEFINED_HOSPITALS.copy())

    total = len(hospitals_list)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)

    keyboard = []

    # حفظ قائمة المستشفيات في user_data للوصول إليها لاحقاً
    if context:
        context.user_data.setdefault("report_tmp", {})[
        "hospitals_list"] = hospitals_list
        context.user_data["report_tmp"]["hospitals_page"] = page

    # عرض المستشفيات (سطر واحد لكل مستشفى)
    for i in range(start_idx, end_idx):
        hospital_index = i
        keyboard.append([InlineKeyboardButton(
            f"🏥 {hospitals_list[i]}",
            callback_data=f"hospital_idx:{hospital_index}"
        )])

    # أزرار التنقل
        nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(
    InlineKeyboardButton(
        "⬅️ السابق",
                    callback_data=f"hosp_page:{page - 1}"))
        nav_buttons.append(
    InlineKeyboardButton(
                f"📄 {page + 1}/{total_pages}",
             callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️ التالي",
                    callback_data=f"hosp_page:{page + 1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = (
        f"🏥 **اختيار المستشفى** (الخطوة 3 من 5)\n\n"
        f"📋 **العدد:** {total} مستشفى"
    )
    if search_query:
        text += f"\n🔍 **البحث:** {search_query}"
    text += f"\n📄 **الصفحة:** {page + 1} من {total_pages}\n\nاختر المستشفى:"

    return text, InlineKeyboardMarkup(keyboard), search_query


async def show_hospitals_menu(message, context, page=0, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_HOSPITAL)

    # تحديث الـ conversation state للـ inline queries
    context.user_data['_conversation_state'] = STATE_SELECT_HOSPITAL

    # استدعاء rendering function
    await render_hospital_selection(message, context)


async def handle_hospital_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار المستشفى"""
    query = update.callback_query
    await query.answer()

    # ملاحظة: زر الرجوع الآن يستخدم nav:back ويتم معالجته في handle_back_navigation
    # هذا الكود للتوافق مع الكود القديم فقط
    if query.data.startswith("hosp_search"):
        # استخدام nav:back بدلاً من hosp_search
        return await handle_back_navigation(update, context)

    # استخدام index بدلاً من الاسم الكامل
    if query.data.startswith("hospital_idx:"):
        hospital_index = int(query.data.split(":", 1)[1])
        hospitals_list = context.user_data.get(
            "report_tmp", {}).get(
            "hospitals_list", [])
        if 0 <= hospital_index < len(hospitals_list):
            choice = hospitals_list[hospital_index]
        else:
            # إذا فشل، نستخدم الطريقة القديمة كبديل
            choice = query.data.split(":", 1)[1] if ":" in query.data else ""
    else:
        choice = query.data.split(":", 1)[1]

    context.user_data["report_tmp"]["hospital_name"] = choice
    context.user_data["report_tmp"].pop("hospitals_search", None)
    context.user_data["report_tmp"].pop("hospitals_search_mode", None)
    context.user_data["report_tmp"].pop("hospitals_list", None)
    
    # حفظ الـ state في المستشفى قبل الانتقال للقسم
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_DEPARTMENT)
    context.user_data['_conversation_state'] = STATE_SELECT_DEPARTMENT

    await query.edit_message_text(
        f"✅ **تم اختيار المستشفى**\n\n"
        f"🏥 **المستشفى:**\n"
        f"{choice}"
    )
    await show_departments_menu(query.message, context)
    return STATE_SELECT_DEPARTMENT


async def handle_hospital_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات المستشفيات"""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    search = context.user_data.get(
    "report_tmp", {}).get(
        "hospitals_search", "")
    text, keyboard, search = _build_hospitals_keyboard(page, search, context)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return STATE_SELECT_HOSPITAL


async def handle_hospital_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث في المستشفيات"""
    if update.message:
        search_mode = context.user_data.get(
    "report_tmp", {}).get(
        "hospitals_search_mode", False)
        if search_mode:
            search_query = update.message.text.strip()
            context.user_data["report_tmp"]["hospitals_search"] = search_query
            context.user_data["report_tmp"]["hospitals_search_mode"] = False
            text, keyboard, _ = _build_hospitals_keyboard(
                0, search_query, context)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return STATE_SELECT_HOSPITAL
        else:
            # إذا لم يكن في وضع البحث، تجاهل النص
            return STATE_SELECT_HOSPITAL


def _build_departments_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح الأقسام مع بحث - يعرض الأقسام الرئيسية فقط"""
    items_per_page = 8

    # جمع الأقسام الرئيسية فقط (بدون الفروع) - بترتيب محدد
    all_departments = []
    
    # ترتيب محدد للأقسام الرئيسية:
    # 1. الجراحة أولاً
    # 2. الباطنية ثانياً
    # 3. طب الأطفال ثالثاً
    # 4. البقية بعد ذلك
    priority_departments = [
        "الجراحة | Surgery",
        "الباطنية | Internal Medicine",
        "طب الأطفال | Pediatrics",
        "طب وجراحة العيون | Ophthalmology"
    ]
    
    # إضافة الأقسام ذات الأولوية أولاً
    for priority_dept in priority_departments:
        if priority_dept in PREDEFINED_DEPARTMENTS:
            all_departments.append(priority_dept)
    
    # إضافة بقية الأقسام الرئيسية (إذا لم تكن في قائمة الأولوية)
    for main_dept in PREDEFINED_DEPARTMENTS.keys():
        if main_dept not in all_departments:
            all_departments.append(main_dept)

    # إضافة الأقسام المباشرة (التي لا تحتوي على فروع)
    all_departments.extend(DIRECT_DEPARTMENTS)

    # إزالة التكرار (لكن نحافظ على الترتيب)
    seen = set()
    unique_departments = []
    for dept in all_departments:
        if dept not in seen:
            seen.add(dept)
            unique_departments.append(dept)
    all_departments = unique_departments

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

    # حفظ قائمة الأقسام في user_data للوصول إليها لاحقاً
    if context:
        context.user_data.setdefault("report_tmp", {})[
        "departments_list"] = all_departments
        context.user_data["report_tmp"]["departments_page"] = page

    # عرض الأقسام - كل قسم في صف منفصل (سطر واحد فقط)
    for i in range(start_idx, end_idx):
        dept_name = all_departments[i]
        
        # التحقق إذا كان القسم رئيسي له فروع
        has_subdepartments = dept_name in PREDEFINED_DEPARTMENTS
        
        if has_subdepartments:
            # عرض القسم الرئيسي مع رمز ملف 📁 في صف منفصل
            display = f"📁 {dept_name[:22]}..." if len(dept_name) > 22 else f"📁 {dept_name}"
        else:
            # القسم العادي (بدون فروع) مع رمز 🏷️
            display = f"🏷️ {dept_name[:22]}..." if len(dept_name) > 22 else f"🏷️ {dept_name}"
        
        # كل قسم في صف منفصل
        keyboard.append([InlineKeyboardButton(
            display,
            callback_data=f"dept_idx:{i}"
        )])

    # أزرار التنقل
        nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(
    InlineKeyboardButton(
        "⬅️ السابق",
                    callback_data=f"dept_page:{page - 1}"))
        nav_buttons.append(
    InlineKeyboardButton(
                f"📄 {page + 1}/{total_pages}",
             callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️ التالي",
                    callback_data=f"dept_page:{page + 1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

    # أزرار التحكم
    control_buttons = []
    control_buttons.append(InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"))
    keyboard.append(control_buttons)

    text = (
        f"🏷️ **اختيار القسم** (الخطوة 4 من 5)\n\n"
        f"📋 **العدد:** {total} قسم"
    )
    if search_query:
        text += f"\n🔍 **البحث:** {search_query}"
    text += f"\n📄 **الصفحة:** {page + 1} من {total_pages}\n\nاختر القسم:"

    return text, InlineKeyboardMarkup(keyboard), search_query


async def show_departments_menu(message, context, page=0, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_DEPARTMENT)

    # تحديث الـ conversation state للـ inline queries
    context.user_data['_conversation_state'] = STATE_SELECT_DEPARTMENT

    # استدعاء rendering function
    await render_department_selection(message, context)


async def handle_department_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار القسم"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("dept_search"):
        await query.edit_message_text(
            "🔍 **البحث عن القسم**\n\n"
            "يرجى إدخال كلمة البحث:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]]),
            parse_mode="Markdown"
        )
        context.user_data["report_tmp"]["departments_search_mode"] = True
        return STATE_SELECT_DEPARTMENT

    # استخدام index بدلاً من الاسم الكامل
    if query.data.startswith("dept_idx:"):
        dept_index = int(query.data.split(":", 1)[1])
        departments_list = context.user_data.get(
    "report_tmp", {}).get(
        "departments_list", [])
        if 0 <= dept_index < len(departments_list):
            dept = departments_list[dept_index]
        else:
            # إذا فشل، نستخدم الطريقة القديمة كبديل
            dept = query.data.split(":", 1)[1] if ":" in query.data else ""
    else:
        dept = query.data.split(":", 1)[1]

    context.user_data["report_tmp"].pop("departments_search", None)
    context.user_data["report_tmp"].pop("departments_search_mode", None)
    context.user_data["report_tmp"].pop("departments_list", None)

    # التحقق إذا كان القسم هو "أشعة وفحوصات"
    if dept == "أشعة وفحوصات | Radiology":
        context.user_data["report_tmp"]["department_name"] = dept
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DEPARTMENT)
        await query.edit_message_text(
            f"✅ **تم اختيار القسم**\n\n"
            f"🏷️ **القسم:**\n"
            f"{dept}"
        )
        # بدء مسار radiology مباشرة (بدون طبيب)
        await start_radiology_flow(query.message, context)
        return RADIOLOGY_TYPE

    # التحقق إذا كان القسم المختار هو قسم رئيسي يحتوي على فروع
    if dept in PREDEFINED_DEPARTMENTS:
        # القسم الرئيسي يحتوي على فروع - عرض الفروع
        context.user_data["report_tmp"]["main_department"] = dept
        await query.edit_message_text(
            f"✅ **تم اختيار القسم الرئيسي**\n\n"
            f"🏷️ **القسم:**\n"
            f"{dept}\n\n"
            f"يرجى اختيار التخصص الفرعي:"
        )
        await show_subdepartment_options(query.message, context, dept)
        return R_SUBDEPARTMENT
    else:
        # القسم مباشر (لا يحتوي على فروع) - الانتقال مباشرة إلى اختيار الطبيب
        context.user_data["report_tmp"]["department_name"] = dept
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DEPARTMENT)
        
        # حفظ الـ state في القسم قبل الانتقال للطبيب
        state_manager = StateHistoryManager.get_state_manager(context)
        state_manager.push_state(STATE_SELECT_DOCTOR)
        context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

        await query.edit_message_text(
            f"✅ **تم اختيار القسم**\n\n"
            f"🏷️ **القسم:**\n"
            f"{dept}"
        )
        await show_doctor_input(query.message, context)
        return STATE_SELECT_DOCTOR


async def handle_department_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات الأقسام"""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    search = context.user_data.get(
    "report_tmp", {}).get(
        "departments_search", "")
    text, keyboard, search = _build_departments_keyboard(page, search, context)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return STATE_SELECT_DEPARTMENT


async def handle_department_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث في الأقسام"""
    if update.message:
        search_mode = context.user_data.get(
    "report_tmp", {}).get(
        "departments_search_mode", False)
        if search_mode:
            search_query = update.message.text.strip()
            context.user_data["report_tmp"]["departments_search"] = search_query
            context.user_data["report_tmp"]["departments_search_mode"] = False
            text, keyboard, _ = _build_departments_keyboard(
                0, search_query, context)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return STATE_SELECT_DEPARTMENT
        else:
            # إذا لم يكن في وضع البحث، تجاهل النص
            return STATE_SELECT_DEPARTMENT


async def show_subdepartment_options(message, context, main_dept, page=0):
    """عرض التخصصات الفرعية - مع إدارة State History"""
    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_SUBDEPARTMENT)

    # تحديث الـ conversation state
    context.user_data['_conversation_state'] = STATE_SELECT_SUBDEPARTMENT
    items_per_page = 8
    subdepts = PREDEFINED_DEPARTMENTS.get(main_dept, [])
    total = len(subdepts)
    total_pages = (total + items_per_page - 1) // items_per_page
    page = max(0, min(page, total_pages - 1))

    # حفظ قائمة الأقسام الفرعية في context لاستخدامها لاحقاً
    context.user_data["report_tmp"]["subdepartments_list"] = subdepts
    context.user_data["report_tmp"]["main_department"] = main_dept

    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)

    keyboard = []
    for i in range(start_idx, end_idx):
        # استخدام الفهرس بدلاً من الاسم الكامل لتجنب تجاوز حد 64 بايت
        keyboard.append([InlineKeyboardButton(
            f"🏥 {subdepts[i]}",
            callback_data=f"subdept_idx:{i}"
        )])

    if total_pages > 1:
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
    InlineKeyboardButton(
        "⬅️ السابق",
                    callback_data=f"subdept_page:{page - 1}"))
        nav_buttons.append(
    InlineKeyboardButton(
                f"📄 {page + 1}/{total_pages}",
             callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    "➡️ التالي",
                    callback_data=f"subdept_page:{page + 1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(
        "🔙 رجوع", callback_data="nav:back")])
    keyboard.append([InlineKeyboardButton(
        "❌ إلغاء", callback_data="nav:cancel")])

    await message.reply_text(
        f"🏥 **{main_dept}** (صفحة {page + 1}/{total_pages})\n\n"
        f"اختر التخصص الفرعي:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_subdepartment_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التخصص الفرعي"""
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":", 1)
    if len(data_parts) < 2:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return R_SUBDEPARTMENT

    choice = data_parts[1]

    # ملاحظة: زر الرجوع الآن يستخدم nav:back ويتم معالجته في handle_back_navigation
    # هذا الكود للتوافق مع الكود القديم فقط
    if choice == "back":
        await query.message.delete()
        await show_departments_menu(query.message, context)
        return STATE_SELECT_DEPARTMENT

    # إذا كان الاختيار فهرس، استرجاع الاسم من القائمة
    if choice.isdigit():
        idx = int(choice)
        subdepts = context.user_data.get("report_tmp", {}).get("subdepartments_list", [])
        if 0 <= idx < len(subdepts):
            choice = subdepts[idx]
        else:
            await query.answer("⚠️ خطأ في الفهرس", show_alert=True)
            return R_SUBDEPARTMENT

    context.user_data["report_tmp"]["department_name"] = choice
    context.user_data["report_tmp"].setdefault("step_history", []).append(R_SUBDEPARTMENT)

    # حفظ الـ state في القسم قبل الانتقال للطبيب
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_DOCTOR)
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

    await query.edit_message_text(f"✅ تم اختيار القسم: {choice}")
    await show_doctor_input(query.message, context)

    return STATE_SELECT_DOCTOR


async def handle_subdepartment_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة التنقل بين صفحات التخصصات الفرعية"""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":", 1)[1])
    main_dept = context.user_data["report_tmp"].get("main_department", "")
    await query.message.delete()
    await show_subdepartment_options(query.message, context, main_dept, page)
    return R_SUBDEPARTMENT


async def show_doctor_selection(message, context, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    # لا نحتاج لحفظ STATE_SELECT_DOCTOR هنا لأنه يتم حفظه في show_doctor_input

    # تحديث الـ conversation state للـ inline queries
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

    # استدعاء rendering function
    await render_doctor_selection(message, context)


async def show_doctor_input(message, context):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🏥 show_doctor_input: Called")

    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    logger.info(f"🏥 show_doctor_input: About to push STATE_SELECT_DOCTOR")
    state_manager.push_state(STATE_SELECT_DOCTOR)

    # تحديث الـ conversation state للـ inline queries
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR
    context.user_data['_current_search_type'] = 'doctor'  # علامة لتحديد نوع البحث

    logger.info(f"🏥 show_doctor_input: Set _conversation_state to STATE_SELECT_DOCTOR")

    # استدعاء rendering function
    await render_doctor_selection(message, context)


async def handle_doctor_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار زر الإدخال اليدوي أو اختيار طبيب من القائمة"""
    query = update.callback_query
    await query.answer()
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 handle_doctor_selection: callback_data='{query.data}'")

    if query.data == "doctor_manual":
        # ✅ التأكد من وجود report_tmp
        if "report_tmp" not in context.user_data:
            context.user_data["report_tmp"] = {}
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info("🔧 تم الضغط على زر الإدخال اليدوي للطبيب")
        
        try:
            await query.edit_message_text(
                "👨‍⚕️ **اسم الطبيب**\n\n"
                "✏️ يرجى إدخال اسم الطبيب:",
                reply_markup=_nav_buttons(show_back=False),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
            # محاولة إرسال رسالة جديدة بدلاً من التعديل
            try:
                await query.message.reply_text(
                    "👨‍⚕️ **اسم الطبيب**\n\n"
                    "✏️ يرجى إدخال اسم الطبيب:",
                    reply_markup=_nav_buttons(show_back=False),
                    parse_mode="Markdown"
                )
            except:
                pass
        
        # ✅ تفعيل وضع الإدخال اليدوي
        context.user_data["report_tmp"]["doctor_manual_mode"] = True
        logger.info("✅ تم تفعيل وضع الإدخال اليدوي للطبيب")
        logger.info(f"   الحالة الحالية: {context.user_data.get('_conversation_state', 'NOT SET')}")
        return STATE_SELECT_DOCTOR


async def handle_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم الطبيب يدوياً أو اختياره من inline query"""
    import logging
    logger = logging.getLogger(__name__)
    
    text = update.message.text.strip()
    logger.info(f"🔍 handle_doctor: received text='{text}'")
    
    # ✅ التأكد من وجود report_tmp
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}
    
    # التحقق إذا كان هذا اختيار من inline query
    if text.startswith("__DOCTOR_SELECTED__:"):
        parts = text.split(":", 2)
        if len(parts) == 3:
            doctor_id = int(parts[1])
            doctor_name = parts[2]

            # حفظ اسم الطبيب
            context.user_data.setdefault("report_tmp", {})["doctor_name"] = doctor_name
            context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
            context.user_data["report_tmp"].pop("doctor_manual_mode", None)

            # حذف الرسالة الخاصة
            try:
                await update.message.delete()
            except:
                pass

            # إرسال رسالة تأكيد
            await update.message.reply_text(
                f"✅ **تم اختيار الطبيب**\n\n"
                f"👨‍⚕️ **الطبيب:**\n"
                f"{doctor_name}",
            parse_mode="Markdown"
        )

            # الانتقال إلى خطوة نوع الإجراء
            import logging
            import sys
            logger = logging.getLogger(__name__)
            print("\n" + "=" * 80)
            print("HANDLE_DOCTOR: About to return R_ACTION_TYPE")
            print(f"HANDLE_DOCTOR: R_ACTION_TYPE value = {R_ACTION_TYPE}")
            print(f"HANDLE_DOCTOR: Current state before return = {context.user_data.get('_conversation_state', 'NOT SET')}")
            sys.stdout.flush()
            logger.info(f"➡️ Moving to R_ACTION_TYPE state after doctor selection")
            logger.info(f"HANDLE_DOCTOR: R_ACTION_TYPE value = {R_ACTION_TYPE}")
            # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
            context.user_data['_conversation_state'] = R_ACTION_TYPE
            await show_action_type_menu(update.message, context)
            logger.info(f"show_action_type_menu called, returning R_ACTION_TYPE")
            print(f"HANDLE_DOCTOR: Returning R_ACTION_TYPE = {R_ACTION_TYPE}")
            print("=" * 80)
            sys.stdout.flush()
            return R_ACTION_TYPE

    # التحقق إذا كان في وضع الإدخال اليدوي
    manual_mode = context.user_data.get("report_tmp", {}).get("doctor_manual_mode", False)
    logger.info(f"🔍 handle_doctor: manual_mode={manual_mode}")
    
    if manual_mode:
        # إدخال يدوي للطبيب
        valid, msg = validate_text_input(text, min_length=2, max_length=100)
        if not valid:
            await update.message.reply_text(
                f"⚠️ **خطأ: {msg}**\n\n"
                f"يرجى إدخال اسم الطبيب:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return STATE_SELECT_DOCTOR

        # ✅ حفظ اسم الطبيب
        context.user_data["report_tmp"]["doctor_name"] = text
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
        context.user_data["report_tmp"].pop("doctor_manual_mode", None)
        logger.info(f"✅ تم حفظ اسم الطبيب يدوياً: {text}")

        # حفظ الـ state في الطبيب قبل الانتقال لنوع الإجراء
        state_manager = StateHistoryManager.get_state_manager(context)
        state_manager.push_state(R_ACTION_TYPE)
        context.user_data['_conversation_state'] = R_ACTION_TYPE

        await update.message.reply_text(
            f"✅ **تم حفظ اسم الطبيب**\n\n"
            f"👨‍⚕️ **الطبيب:**\n"
            f"{text}",
            parse_mode="Markdown"
        )
        import logging
        import sys
        logger = logging.getLogger(__name__)
        print("\n" + "=" * 80)
        print("HANDLE_DOCTOR: About to return R_ACTION_TYPE (manual entry)")
        print(f"HANDLE_DOCTOR: R_ACTION_TYPE value = {R_ACTION_TYPE}")
        print(f"HANDLE_DOCTOR: Current state before return = {context.user_data.get('_conversation_state', 'NOT SET')}")
        sys.stdout.flush()
        logger.info(f"➡️ Moving to R_ACTION_TYPE state after manual doctor entry")
        logger.info(f"HANDLE_DOCTOR: R_ACTION_TYPE value = {R_ACTION_TYPE}")
        await show_action_type_menu(update.message, context)
        logger.info(f"show_action_type_menu called, returning R_ACTION_TYPE")
        print(f"HANDLE_DOCTOR: Returning R_ACTION_TYPE = {R_ACTION_TYPE}")
        print("=" * 80)
        sys.stdout.flush()
        return R_ACTION_TYPE

    # إذا لم يكن في وضع الإدخال اليدوي ولم يكن اختيار من inline query
    # قد يكون المستخدم يريد الرجوع أو إلغاء
    if text.lower() in ["إلغاء", "رجوع", "cancel", "back"]:
        await update.message.reply_text(
            "❌ تم إلغاء اختيار الطبيب",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 بحث الآن", switch_inline_query_current_chat="")],
                [InlineKeyboardButton("✏️ إدخال يدوي", callback_data="doctor_manual")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
            ])
        )
        return STATE_SELECT_DOCTOR
    
    # إذا لم يكن في وضع الإدخال اليدوي، نعيد عرض القائمة
    logger.warning(f"⚠️ handle_doctor: لم يتم التعرف على النص كاختيار طبيب أو إدخال يدوي. النص: '{text}'")
    logger.info("ℹ️ إعادة عرض قائمة اختيار الطبيب")
    await show_doctor_selection(update.message, context)
    return STATE_SELECT_DOCTOR

# =============================
# نظام نوع الإجراء - نظيف ومنظم
# =============================


def _get_action_routing():
    """الحصول على ربط أنواع الإجراءات بالمسارات - يتم استدعاؤه بعد تعريف الدوال"""
    routing_dict = {
        "استشارة جديدة": {
            "state": NEW_CONSULT_COMPLAINT,
            "flow": start_new_consultation_flow,
            "pre_process": None
        },
        "متابعة في الرقود": {
            "state": FOLLOWUP_COMPLAINT,
            "flow": start_followup_flow,
            "pre_process": None
        },
        "مراجعة / عودة دورية": {
            "state": FOLLOWUP_COMPLAINT,
            "flow": start_periodic_followup_flow,
            "pre_process": None
        },
        "استشارة مع قرار عملية": {
            "state": SURGERY_CONSULT_DIAGNOSIS,
            "flow": start_surgery_consult_flow,
            "pre_process": None
        },
        "طوارئ": {
            "state": EMERGENCY_COMPLAINT,
            "flow": start_emergency_flow,
            "pre_process": None
        },
        "عملية": {
            "state": OPERATION_DETAILS_AR,
            "flow": start_operation_flow,
            "pre_process": None
        },
        "استشارة أخيرة": {
            "state": FINAL_CONSULT_DIAGNOSIS,
            "flow": start_final_consult_flow,
            "pre_process": lambda context: context.user_data.setdefault("report_tmp", {}).update({"complaint_text": ""})
        },
        "علاج طبيعي وإعادة تأهيل": {
            "state": REHAB_TYPE,
            "flow": start_rehab_flow,
            "pre_process": None
        },
        "ترقيد": {
            "state": ADMISSION_REASON,
            "flow": start_admission_flow,
            "pre_process": None
        },
        "خروج من المستشفى": {
            "state": DISCHARGE_TYPE,
            "flow": start_discharge_flow,
            "pre_process": None
        },
    }

    # Logging للتحقق من المفاتيح
    print("=" * 80)
    print("_get_action_routing() called")
    print(f"Routing keys count: {len(routing_dict.keys())}")
    print(f"PREDEFINED_ACTIONS count: {len(PREDEFINED_ACTIONS)}")
    print("Checking if all PREDEFINED_ACTIONS are in routing:")
    for action in PREDEFINED_ACTIONS:
        in_routing = action in routing_dict
        print(f"   - Action index {PREDEFINED_ACTIONS.index(action)} in routing: {in_routing}")
    print("=" * 80)

    return routing_dict


def _build_action_type_keyboard(page=0):
    """بناء لوحة مفاتيح أنواع الإجراءات - جميع الأزرار في صفحة واحدة"""
    total = len(PREDEFINED_ACTIONS)
    keyboard = []

    # إضافة جميع أزرار أنواع الإجراءات - كل زر في صف منفصل (عمود واحد فقط)
    for i in range(total):
        action_name = PREDEFINED_ACTIONS[i]
        callback_data = f"action_idx:{i}"
        display = f"⚕️ {action_name[:20]}..." if len(action_name) > 20 else f"⚕️ {action_name}"
        keyboard.append([InlineKeyboardButton(display, callback_data=callback_data)])

    # أزرار التنقل الرئيسية (لا توجد أزرار صفحات)
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"⚕️ **نوع الإجراء** (الخطوة 6 من 6)\n\nاختر نوع الإجراء من القائمة:"

    return text, InlineKeyboardMarkup(keyboard), 1


async def show_action_type_menu(message, context, page=0):
    """عرض قائمة أنواع الإجراءات المتاحة - جميع الأزرار في صفحة واحدة"""
    # تحديث علامة نوع البحث
    context.user_data['_current_search_type'] = 'action_type'

    import logging
    import sys
    logger = logging.getLogger(__name__)

    print("\n" + "=" * 80)
    print("🎯 SHOW_ACTION_TYPE_MENU: Function called")
    print(f"🎯 SHOW_ACTION_TYPE_MENU: Total actions = {len(PREDEFINED_ACTIONS)}")
    print(f"🎯 SHOW_ACTION_TYPE_MENU: Current state = {context.user_data.get('_conversation_state', 'NOT SET')}")
    print(f"🎯 SHOW_ACTION_TYPE_MENU: Expected state = {R_ACTION_TYPE}")
    sys.stdout.flush()

    logger.info("=" * 80)
    logger.info("SHOW_ACTION_TYPE_MENU: Function called")
    logger.info(f"SHOW_ACTION_TYPE_MENU: Total actions = {len(PREDEFINED_ACTIONS)}")

    # تجاهل page parameter - عرض جميع الأزرار في صفحة واحدة
    text, keyboard, total_pages = _build_action_type_keyboard(0)

    print(f"🎯 SHOW_ACTION_TYPE_MENU: Keyboard has {len(keyboard.inline_keyboard)} button rows")
    for i, row in enumerate(keyboard.inline_keyboard):
        print(f"🎯   Row {i}: {[btn.text for btn in row]}")
        print(f"🎯   Callbacks: {[btn.callback_data for btn in row]}")
    sys.stdout.flush()

    try:
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        print("✅ SHOW_ACTION_TYPE_MENU: Message sent successfully")
        sys.stdout.flush()
        logger.info("SHOW_ACTION_TYPE_MENU: Message sent successfully")
    except Exception as e:
        print(f"❌ ERROR: SHOW_ACTION_TYPE_MENU - Failed to send message: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        logger.error(f"SHOW_ACTION_TYPE_MENU: Error sending message: {e}", exc_info=True)
        raise


async def handle_action_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات أنواع الإجراءات"""
    import logging
    import sys
    import traceback
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    if not query:
        logger.error("HANDLE_ACTION_PAGE: No callback_query in update!")
        error_monitor.log_error(
            error=Exception("No callback_query in update"),
            context=context,
            update=update,
            additional_info={"function": "handle_action_page", "error_type": "MissingCallbackQuery"}
        )
        return R_ACTION_TYPE

    print("\n" + "=" * 80)
    print("HANDLE_ACTION_PAGE: Function called")
    print(f"HANDLE_ACTION_PAGE: callback_data = {query.data}")
    print(f"HANDLE_ACTION_PAGE: Current state = {context.user_data.get('_conversation_state', 'NOT SET')}")
    sys.stdout.flush()
    
    logger.info("=" * 80)
    logger.info("HANDLE_ACTION_PAGE: Function called")
    logger.info(f"HANDLE_ACTION_PAGE: callback_data = {query.data}")
    logger.info(f"HANDLE_ACTION_PAGE: Current state = {context.user_data.get('_conversation_state', 'NOT SET')}")

    try:
        # التحقق من صيغة callback_data أولاً
        if not query.data or not query.data.startswith("action_page:"):
            error_msg = f"Invalid callback_data format: {query.data}"
            logger.error(f"HANDLE_ACTION_PAGE: {error_msg}")
            error_monitor.log_error(
                error=ValueError(error_msg),
                context=context,
                update=update,
                additional_info={
                    "function": "handle_action_page",
                    "callback_data": query.data,
                    "expected_format": "action_page:number"
                }
            )
            try:
                await query.answer("⚠️ خطأ في صيغة البيانات", show_alert=True)
            except Exception as e:
                logger.error(f"HANDLE_ACTION_PAGE: Error answering query: {e}")
            return R_ACTION_TYPE
        
        page = int(query.data.split(":", 1)[1])
        print(f"HANDLE_ACTION_PAGE: Navigating to page {page}")
        sys.stdout.flush()
        logger.info(f"HANDLE_ACTION_PAGE: Navigating to page {page}")
        
        # الإجابة على الـ callback query
        try:
            await query.answer()
        except Exception as e:
            logger.error(f"HANDLE_ACTION_PAGE: Error answering callback: {e}")
            error_monitor.log_error(
                error=e,
                context=context,
                update=update,
                additional_info={
                    "function": "handle_action_page",
                    "step": "query.answer()",
                    "page": page
                }
            )
        
        # تحديث الحالة
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        
        # بناء النص والـ keyboard للصفحة الجديدة
        try:
            text, keyboard, total_pages = _build_action_type_keyboard(page)
        except Exception as e:
            logger.error(f"HANDLE_ACTION_PAGE: Error building keyboard: {e}")
            error_monitor.log_error(
                error=e,
                context=context,
                update=update,
                additional_info={
                    "function": "handle_action_page",
                    "step": "_build_action_type_keyboard()",
                    "page": page
                }
            )
            raise
        
        # التحقق من أن رقم الصفحة صحيح
        if page < 0 or page >= total_pages:
            error_msg = f"Invalid page number {page}, total_pages = {total_pages}"
            logger.error(f"HANDLE_ACTION_PAGE: {error_msg}")
            error_monitor.log_error(
                error=IndexError(error_msg),
                context=context,
                update=update,
                additional_info={
                    "function": "handle_action_page",
                    "page": page,
                    "total_pages": total_pages
                }
            )
            try:
                await query.answer("⚠️ رقم الصفحة غير صحيح", show_alert=True)
            except Exception as e:
                logger.error(f"HANDLE_ACTION_PAGE: Error answering query: {e}")
            return R_ACTION_TYPE
        
        # تعديل الرسالة الحالية بدلاً من حذفها وإنشاء واحدة جديدة
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"HANDLE_ACTION_PAGE: Error editing message: {e}")
            error_monitor.log_error(
                error=e,
                context=context,
                update=update,
                additional_info={
                    "function": "handle_action_page",
                    "step": "edit_message_text()",
                    "page": page,
                    "total_pages": total_pages
                }
            )
            try:
                await query.answer("⚠️ خطأ في تحديث الرسالة", show_alert=True)
            except:
                pass
            return R_ACTION_TYPE
        
        print("HANDLE_ACTION_PAGE: Completed successfully")
        sys.stdout.flush()
        logger.info(f"HANDLE_ACTION_PAGE: Successfully navigated to page {page}")
        return R_ACTION_TYPE
        
    except (ValueError, IndexError) as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error parsing page number: {e}", exc_info=True)
        print(f"ERROR: HANDLE_ACTION_PAGE - Error parsing page number: {e}")
        traceback.print_exc()
        sys.stdout.flush()
        error_monitor.log_error(
            error=e,
            context=context,
            update=update,
            additional_info={
                "function": "handle_action_page",
                "error_type": "ParseError",
                "callback_data": query.data if query else None
            }
        )
        try:
            await query.answer("⚠️ خطأ في قراءة رقم الصفحة", show_alert=True)
        except Exception as answer_error:
            logger.error(f"HANDLE_ACTION_PAGE: Error answering query: {answer_error}")
        return R_ACTION_TYPE
        
    except Exception as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error in handle_action_page: {e}", exc_info=True)
        print(f"ERROR: HANDLE_ACTION_PAGE - Error: {e}")
        traceback.print_exc()
        sys.stdout.flush()
        error_monitor.log_error(
            error=e,
            context=context,
            update=update,
            additional_info={
                "function": "handle_action_page",
                "error_type": "UnexpectedError",
                "callback_data": query.data if query else None
            }
        )
        try:
            await query.answer("⚠️ خطأ في التنقل", show_alert=True)
        except Exception as answer_error:
            logger.error(f"HANDLE_ACTION_PAGE: Error answering query: {answer_error}")
        return R_ACTION_TYPE


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج لزر noop (لا يفعل شيئاً - يستخدم لعرض معلومات فقط)"""
    query = update.callback_query
    if query:
        await query.answer()
    return R_ACTION_TYPE

async def handle_stale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج للـ callbacks القديمة من حالات سابقة"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    if not query:
        return None
    
    try:
        # إجابة سريعة بدون انتظار
        await query.answer("⚠️ هذه القائمة لم تعد نشطة. يرجى استخدام القائمة الحالية.", show_alert=False)
    except Exception as e:
        logger.warning(f"⚠️ خطأ في إجابة stale callback: {e}")
    
    # محاولة حذف الرسالة القديمة
    try:
        await query.message.delete()
    except Exception as e:
        logger.debug(f"⚠️ لا يمكن حذف الرسالة القديمة: {e}")
    
    # إعادة عرض القائمة الحالية حسب الحالة
    current_state = context.user_data.get('_conversation_state', None)
    
    try:
        if current_state == STATE_SELECT_HOSPITAL:
            await show_hospitals_menu(query.message, context)
            return STATE_SELECT_HOSPITAL
        elif current_state == STATE_SELECT_DEPARTMENT:
            await show_departments_menu(query.message, context)
            return STATE_SELECT_DEPARTMENT
        elif current_state == STATE_SELECT_DOCTOR:
            await show_doctor_input(query.message, context)
            return STATE_SELECT_DOCTOR
        elif current_state == R_ACTION_TYPE:
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة عرض القائمة: {e}", exc_info=True)
    
    # إذا لم نتمكن من تحديد الحالة، نرجع R_ACTION_TYPE كحالة افتراضية
    return current_state if current_state is not None else R_ACTION_TYPE


async def debug_all_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة debug لالتقاط جميع callback queries في حالة R_ACTION_TYPE"""
    import logging
    import sys
    import traceback
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    if not query:
        return None
    
    # محاولة الحصول على الحالة من ConversationHandler مباشرة
    # ConversationHandler يحفظ الحالة في context.user_data تحت مفتاح خاص
    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    
    # محاولة الحصول على جميع مفاتيح user_data لمعرفة كيف يحفظ ConversationHandler الحالة
    all_keys = list(context.user_data.keys())
    
    print("\n" + "=" * 80)
    print("=" * 80)
    print("DEBUG_ALL_CALLBACKS: Callback query received!")
    print("=" * 80)
    print(f"DEBUG: Callback data = {query.data}")
    print(f"DEBUG: Current state (from _conversation_state) = {current_state}")
    print(f"DEBUG: Expected state = {R_ACTION_TYPE}")
    print(f"DEBUG: States match = {current_state == R_ACTION_TYPE}")
    print(f"DEBUG: All user_data keys = {all_keys}")
    print(f"DEBUG: Update ID = {update.update_id}")
    print(f"DEBUG: User ID = {update.effective_user.id if update.effective_user else 'N/A'}")
    print(f"DEBUG: Chat ID = {update.effective_chat.id if update.effective_chat else 'N/A'}")
    print(f"DEBUG: Message ID = {query.message.message_id if query.message else 'N/A'}")
    print(f"DEBUG: Pattern 'action_idx:' matches = {query.data.startswith('action_idx:') if query.data else False}")
    print("=" * 80)
    print("DEBUG: If pattern matches but this handler is called, it means handle_action_type_choice was not matched!")
    print("=" * 80)
    traceback.print_stack()
    print("=" * 80)
    sys.stdout.flush()
    
    logger.warning("DEBUG_ALL_CALLBACKS: Callback query received - handle_action_type_choice was NOT matched!")
    logger.warning(f"DEBUG: Callback data = {query.data}, Current state = {current_state}")
    logger.warning(f"DEBUG: All user_data keys = {all_keys}")
    
    # محاولة استدعاء handle_action_type_choice يدوياً إذا كان pattern يطابق
    if query.data and query.data.startswith('action_idx:'):
        print("DEBUG_ALL_CALLBACKS: Pattern matches! Attempting to call handle_action_type_choice manually...")
        sys.stdout.flush()
        try:
            return await handle_action_type_choice(update, context)
        except Exception as e:
            print(f"DEBUG_ALL_CALLBACKS: Error calling handle_action_type_choice manually: {e}")
            traceback.print_exc()
            sys.stdout.flush()
    
    return None


async def handle_action_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع الإجراء - جميع المسارات"""
    import logging
    import sys
    import traceback
    logger = logging.getLogger(__name__)

    # طباعة مباشرة في الكونسول + تسجيل
    print("\n" + "🚨🚨🚨" * 10)
    print("🎯 ACTION_TYPE_CHOICE: Function called - DEBUG MODE")
    print("🚨🚨🚨" * 10)
    sys.stdout.flush()

    logger.info("=" * 80)
    logger.info("ACTION_TYPE_CHOICE: Function called - DEBUG MODE")
    logger.info("=" * 80)

    # طباعة stack trace لمعرفة من أين تم الاستدعاء
    print("🎯 ACTION_TYPE_CHOICE: Call stack:")
    traceback.print_stack()
    print("🚨🚨🚨" * 10)
    sys.stdout.flush()

    query = update.callback_query
    if not query:
        print("ERROR: ACTION_TYPE_CHOICE - No callback_query in update!")
        print("ERROR: Update type =", type(update))
        print("ERROR: Update attributes =", dir(update))
        sys.stdout.flush()
        logger.error("ACTION_TYPE_CHOICE: CRITICAL - No callback_query in update!")
        return R_ACTION_TYPE

    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    
    print(f"ACTION_TYPE_CHOICE: Callback data = {query.data}")
    print(f"ACTION_TYPE_CHOICE: Update ID = {update.update_id}")
    print(f"ACTION_TYPE_CHOICE: User ID = {update.effective_user.id if update.effective_user else 'N/A'}")
    print(f"ACTION_TYPE_CHOICE: Current state = {current_state}")
    print(f"ACTION_TYPE_CHOICE: Expected state = {R_ACTION_TYPE}")
    print(f"ACTION_TYPE_CHOICE: States match = {current_state == R_ACTION_TYPE}")
    print(f"ACTION_TYPE_CHOICE: Pattern 'action_idx:' matches = {query.data.startswith('action_idx:') if query.data else False}")
    sys.stdout.flush()
    
    logger.info(f"ACTION_TYPE_CHOICE: Callback data = {query.data}")
    logger.info(f"ACTION_TYPE_CHOICE: Update ID = {update.update_id}")
    logger.info(f"ACTION_TYPE_CHOICE: User ID = {update.effective_user.id if update.effective_user else 'N/A'}")
    logger.info(f"ACTION_TYPE_CHOICE: Chat ID = {update.effective_chat.id if update.effective_chat else 'N/A'}")
    logger.info(f"ACTION_TYPE_CHOICE: Current state = {current_state}")
    logger.info(f"ACTION_TYPE_CHOICE: Expected state = {R_ACTION_TYPE}")
    logger.info(f"ACTION_TYPE_CHOICE: States match = {current_state == R_ACTION_TYPE}")
    logger.info(f"ACTION_TYPE_CHOICE: User data keys = {list(context.user_data.keys())}")

    # التحقق من أن هذا callback لا يتعلق بـ action_page - إذا كان كذلك، تجاهله تماماً
    if query.data and query.data.startswith("action_page:"):
        print("ACTION_TYPE_CHOICE: This is an action_page callback, ignoring (should be handled by handle_action_page)")
        sys.stdout.flush()
        logger.warning(f"ACTION_TYPE_CHOICE: Received action_page callback but this handler is for action_idx only. Data: {query.data}")
        # لا نجيب على الـ callback هنا ولا نفعل أي شيء - دع handle_action_page يتعامل معه
        return None

    # التحقق من أن هذا callback يتعلق بـ action_idx فقط
    if not query.data or not query.data.startswith("action_idx:"):
        logger.warning(f"ACTION_TYPE_CHOICE: Received unexpected callback data: {query.data}")
        await query.answer("⚠️ نوع بيانات غير متوقع", show_alert=True)
        return R_ACTION_TYPE

    # الرد الفوري على الـ callback
    try:
        await query.answer()
        logger.info("ACTION_TYPE_CHOICE: Callback answered successfully")
    except Exception as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error answering callback: {e}", exc_info=True)
        try:
            await query.answer(f"خطأ في الرد: {str(e)}", show_alert=True)
        except:
            pass

    try:
        # التحقق من صحة callback_data
        if not query.data or not query.data.startswith("action_idx:"):
            logger.error(f"ACTION_TYPE_CHOICE: Invalid callback_data format: {query.data}")
            try:
                await query.answer("⚠️ خطأ في صيغة البيانات", show_alert=True)
            except:
                pass
            return R_ACTION_TYPE

        # استخراج الفهرس
        action_idx = int(query.data.split(":", 1)[1])
        print(f"ACTION_TYPE_CHOICE: Extracted action_idx = {action_idx}")
        sys.stdout.flush()
        logger.info(f"ACTION_TYPE_CHOICE: Extracted action_idx = {action_idx}")

        # التحقق من صحة الفهرس
        if action_idx < 0 or action_idx >= len(PREDEFINED_ACTIONS):
            error_msg = f"Invalid action index: {action_idx}, max: {len(PREDEFINED_ACTIONS) - 1}"
            print(f"ERROR: {error_msg}")
            sys.stdout.flush()
            logger.error(f"ACTION_TYPE_CHOICE: {error_msg}")
            await query.answer("نوع الإجراء غير صحيح", show_alert=True)
            return R_ACTION_TYPE

        # الحصول على نوع الإجراء المختار
        action_name = PREDEFINED_ACTIONS[action_idx]
        # استخدام logger بدلاً من print لتجنب UnicodeEncodeError في Windows console
        logger.info(f"ACTION_TYPE_CHOICE: Selected action = '{action_name}' (index: {action_idx})")
        print(f"ACTION_TYPE_CHOICE: Selected action index = {action_idx}")
        sys.stdout.flush()
        logger.info(f"ACTION_TYPE_CHOICE: Total actions available = {len(PREDEFINED_ACTIONS)}")

        # حفظ نوع الإجراء في البيانات
        context.user_data.setdefault("report_tmp", {})["medical_action"] = action_name
        context.user_data["report_tmp"]["action_type"] = action_name
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_ACTION_TYPE)
        logger.info(f"ACTION_TYPE_CHOICE: Saved medical_action = '{action_name}'")

        # حفظ flow_type بناءً على نوع الإجراء المختار
        action_to_flow_type = {
            "استشارة جديدة": "new_consult",
            "متابعة في الرقود": "followup",
            "مراجعة / عودة دورية": "followup",  # نفس التدفق لكن medical_action مختلف
            "استشارة مع قرار عملية": "surgery_consult",
            "طوارئ": "emergency",
            "عملية": "operation",
            "استشارة أخيرة": "final_consult",
            "علاج طبيعي وإعادة تأهيل": "rehab_physical",
        }

        flow_type = action_to_flow_type.get(action_name, "new_consult")
        context.user_data["report_tmp"]["current_flow"] = flow_type
        logger.info(f"ACTION_TYPE_CHOICE: Flow type = '{flow_type}' for action '{action_name}'")

        # التحقق من وجود message target
        message_target = query.message if query.message else None
        if not message_target:
            logger.error("ACTION_TYPE_CHOICE: No message target available")
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{action_name}")
            return R_ACTION_TYPE

        # البحث عن المسار المناسب
        action_routing = _get_action_routing()
        logger.info(f"ACTION_TYPE_CHOICE: ACTION_ROUTING keys = {list(action_routing.keys())}")
        logger.info(f"ACTION_TYPE_CHOICE: Looking for action_name = '{action_name}'")

        routing = action_routing.get(action_name)
        if not routing:
            print(f"ERROR: ACTION_TYPE_CHOICE - No routing found for action index: {action_idx}")
            print(f"Available keys in ACTION_ROUTING:")
            for key in action_routing.keys():
                print(f"   - Key index: {list(action_routing.keys()).index(key)}")
            sys.stdout.flush()
            logger.error(f"ACTION_TYPE_CHOICE: CRITICAL - No routing found for action_name: '{action_name}'")
            logger.error(f"ACTION_TYPE_CHOICE: Available keys in ACTION_ROUTING:")
            for key in action_routing.keys():
                logger.error(f"   - '{key}' (type: {type(key)}, length: {len(key)}, repr: {repr(key)})")
            logger.warning(f"ACTION_TYPE_CHOICE: Unknown action type: '{action_name}', using default flow")
            # استخدام المسار الافتراضي (استشارة جديدة)
            routing = action_routing.get("استشارة جديدة")
            if not routing:
                print("CRITICAL ERROR: Default routing also not found!")
                sys.stdout.flush()
                logger.error("ACTION_TYPE_CHOICE: CRITICAL - Default routing also not found!")
                await query.answer("خطأ: نوع الإجراء غير مدعوم", show_alert=True)
                return R_ACTION_TYPE
        else:
            print(f"ACTION_TYPE_CHOICE: Found routing for action index: {action_idx}")
            print(f"ACTION_TYPE_CHOICE: Routing state = {routing['state']}")
            print(f"ACTION_TYPE_CHOICE: Routing flow function = {routing['flow'].__name__}")
            sys.stdout.flush()
            logger.info(f"ACTION_TYPE_CHOICE: Found routing for action_name: '{action_name}'")
            logger.info(f"ACTION_TYPE_CHOICE: Routing state = {routing['state']}")
            logger.info(f"ACTION_TYPE_CHOICE: Routing flow function = {routing['flow'].__name__}")

        # تنفيذ pre_process إذا كان موجوداً
        if routing.get("pre_process"):
            logger.info(f"ACTION_TYPE_CHOICE: Executing pre_process for action: {action_name}")
            try:
                routing["pre_process"](context)
                logger.info("ACTION_TYPE_CHOICE: pre_process completed successfully")
            except Exception as e:
                logger.error(f"ACTION_TYPE_CHOICE: Error in pre_process: {e}", exc_info=True)

        # تحديث الرسالة
        try:
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{action_name}")
            logger.info("ACTION_TYPE_CHOICE: Message updated successfully")
        except Exception as e:
            logger.error(f"ACTION_TYPE_CHOICE: Error updating message: {e}", exc_info=True)

        # توجيه للمسار المناسب
        logger.info(f"ACTION_TYPE_CHOICE: Routing to state = {routing['state']}")
        logger.info(f"ACTION_TYPE_CHOICE: Calling flow function = {routing['flow'].__name__}")
        logger.info(f"ACTION_TYPE_CHOICE: Message target type = {type(message_target)}")

        # ⚠️ مهم جداً: حفظ R_ACTION_TYPE في التاريخ قبل الانتقال إلى الـ flow التالي
        # هذا يضمن أن زر الرجوع يعمل بشكل صحيح
        state_manager = StateHistoryManager.get_state_manager(context)
        # التأكد من أن R_ACTION_TYPE موجود في التاريخ (يجب أن يكون موجوداً بالفعل)
        current_history = state_manager.get_history()
        if not current_history or current_history[-1] != R_ACTION_TYPE:
            logger.warning(f"ACTION_TYPE_CHOICE: R_ACTION_TYPE not in history! Current history: {current_history}")
            # إضافة R_ACTION_TYPE إذا لم يكن موجوداً
            state_manager.push_state(R_ACTION_TYPE)

        # تهيئة state_to_return بالقيمة الافتراضية من routing
        state_to_return = routing.get("state", R_ACTION_TYPE)

        try:
            print(f"ACTION_TYPE_CHOICE: Calling flow function '{routing['flow'].__name__}'...")
            print(f"ACTION_TYPE_CHOICE: message_target type = {type(message_target)}")
            print(f"ACTION_TYPE_CHOICE: message_target has reply_text = {hasattr(message_target, 'reply_text')}")
            print(f"ACTION_TYPE_CHOICE: query.message type = {type(query.message)}")
            print(f"ACTION_TYPE_CHOICE: query.message.chat.id = {query.message.chat.id if query.message and query.message.chat else 'N/A'}")
            sys.stdout.flush()
            logger.info(f"ACTION_TYPE_CHOICE: Calling flow function '{routing['flow'].__name__}'...")
            
            # استخدام query.message مباشرة كـ message_target لأنه يحتوي على chat ويمكن استخدام reply_text
            # query.message هو Message object صحيح يمكن استخدامه مع reply_text
            flow_result = await routing["flow"](query.message, context)
            print(f"ACTION_TYPE_CHOICE: Flow function '{routing['flow'].__name__}' completed successfully")
            print(f"ACTION_TYPE_CHOICE: Flow function returned: {flow_result}")
            print(f"ACTION_TYPE_CHOICE: Expected state from routing = {routing['state']}")
            print(f"ACTION_TYPE_CHOICE: Flow result matches routing state = {flow_result == routing['state']}")
            sys.stdout.flush()
            logger.info(f"ACTION_TYPE_CHOICE: Flow function '{routing['flow'].__name__}' completed successfully")
            logger.info(f"ACTION_TYPE_CHOICE: Flow function returned: {flow_result}")
            logger.info(f"ACTION_TYPE_CHOICE: Expected state from routing = {routing['state']}")
            
            # استخدام state من flow function إذا كان موجوداً، وإلا استخدام state من routing
            state_to_return = flow_result if flow_result is not None else routing["state"]
            print(f"ACTION_TYPE_CHOICE: Final state to return = {state_to_return}")
            print(f"ACTION_TYPE_CHOICE: State type = {type(state_to_return)}")
            print(f"ACTION_TYPE_CHOICE: NEW_CONSULT_COMPLAINT = {NEW_CONSULT_COMPLAINT}")
            print(f"ACTION_TYPE_CHOICE: States match = {state_to_return == NEW_CONSULT_COMPLAINT}")
            sys.stdout.flush()
            logger.info(f"ACTION_TYPE_CHOICE: Final state to return = {state_to_return}")
            # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
            context.user_data['_conversation_state'] = state_to_return
        except Exception as e:
            error_msg = f"ERROR in flow function '{routing['flow'].__name__}': {e}"
            print("\n" + "=" * 80)
            print(f"ERROR: {error_msg}")
            print("=" * 80)
            import traceback
            traceback.print_exc()
            print("=" * 80)
            sys.stdout.flush()
            logger.error(f"ACTION_TYPE_CHOICE: {error_msg}", exc_info=True)
            
            # محاولة الرد على callback
            try:
                await query.answer(f"خطأ في بدء المسار: {str(e)[:50]}", show_alert=True)
            except:
                pass
            
            # حتى في حالة الخطأ، نحاول إرجاع state الصحيح إذا كان متاحاً
            # هذا يضمن أن ConversationHandler يعرف الحالة الجديدة
            # لا نرفع الاستثناء هنا لأننا نريد إرجاع state للسماح بالانتقال
            state_to_return = routing.get("state", R_ACTION_TYPE)
            print(f"ACTION_TYPE_CHOICE: Returning state after error: {state_to_return}")
            print(f"ACTION_TYPE_CHOICE: Error has been logged, continuing with state transition")
            sys.stdout.flush()
            logger.warning(f"ACTION_TYPE_CHOICE: Error occurred but returning state {state_to_return} to allow transition")

        print("=" * 80)
        print(f"ACTION_TYPE_CHOICE: FINAL - About to return state: {state_to_return}")
        print(f"ACTION_TYPE_CHOICE: FINAL - State type: {type(state_to_return)}")
        print(f"ACTION_TYPE_CHOICE: FINAL - State value: {state_to_return}")
        print("=" * 80)
        sys.stdout.flush()
        logger.info(f"ACTION_TYPE_CHOICE: FINAL - Returning state = {state_to_return}")
        logger.info(f"ACTION_TYPE_CHOICE: FINAL - State type = {type(state_to_return)}")
        
        # التأكد من إرجاع state بشكل صحيح
        if state_to_return is None:
            logger.error("ACTION_TYPE_CHOICE: CRITICAL - state_to_return is None! Using routing state instead.")
            state_to_return = routing.get("state", R_ACTION_TYPE)
            print(f"ACTION_TYPE_CHOICE: CRITICAL - Fixed state_to_return to: {state_to_return}")
            sys.stdout.flush()
        
        return state_to_return

    except ValueError as e:
        error_msg = f"ACTION_TYPE_CHOICE: ValueError: {e}, callback_data: {query.data if query else 'N/A'}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        logger.error(error_msg, exc_info=True)
        if query:
            try:
                await query.answer("خطأ في قراءة البيانات", show_alert=True)
            except:
                pass
        return R_ACTION_TYPE
    except IndexError as e:
        error_msg = f"ACTION_TYPE_CHOICE: IndexError: {e}, callback_data: {query.data if query else 'N/A'}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        logger.error(error_msg, exc_info=True)
        if query:
            try:
                await query.answer("خطأ في الفهرس", show_alert=True)
            except:
                pass
        return R_ACTION_TYPE
    except Exception as e:
        error_msg = f"ACTION_TYPE_CHOICE: CRITICAL ERROR: {e}"
        print(f"CRITICAL ERROR: {error_msg}")
        print(f"Callback data: {query.data if query else 'N/A'}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        logger.error(error_msg, exc_info=True)
        logger.error(f"ACTION_TYPE_CHOICE: Callback data: {query.data if query else 'N/A'}")
        if query:
            try:
                await query.answer(f"خطأ: {str(e)[:50]}", show_alert=True)
            except:
                pass
        return R_ACTION_TYPE

# =============================
# مسار 1: استشارة جديدة (7 حقول)
# شكوى، تشخيص، قرار، فحوصات، تاريخ عودة، وقت، سبب عودة، مترجم
# =============================


async def start_new_consultation_flow(message, context):
    """بدء مسار استشارة جديدة - الحقل 1: شكوى المريض"""
    import logging
    import sys
    import traceback
    logger = logging.getLogger(__name__)

    print("\n" + "=" * 80)
    print("=" * 80)
    print("NEW_CONSULT_FLOW: Function called!")
    print("=" * 80)
    logger.debug(f"NEW_CONSULT_FLOW: message type = {type(message)}")
    logger.debug(f"NEW_CONSULT_FLOW: message has reply_text = {hasattr(message, 'reply_text')}")
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"NEW_CONSULT_FLOW: medical_action = {repr(medical_action)}")
    logger.debug(f"NEW_CONSULT_FLOW: current_flow = {repr(current_flow)}")
    current_state_before = context.user_data.get('_conversation_state', 'NOT SET')
    print(f"NEW_CONSULT_FLOW: Current state BEFORE = {current_state_before}")
    print(f"NEW_CONSULT_FLOW: NEW_CONSULT_COMPLAINT value = {NEW_CONSULT_COMPLAINT}")
    print(f"NEW_CONSULT_FLOW: Will set state to = {NEW_CONSULT_COMPLAINT}")
    print("=" * 80)
    sys.stdout.flush()
    
    logger.info("=" * 80)
    logger.info("NEW_CONSULT_FLOW: Function called")
    logger.info(f"NEW_CONSULT_FLOW: medical_action = {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"NEW_CONSULT_FLOW: current_flow = {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)

    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "استشارة جديدة"
    context.user_data["report_tmp"]["current_flow"] = "new_consult"
    logger.info("NEW_CONSULT_FLOW: Saved medical_action and current_flow")

    try:
        print("NEW_CONSULT_FLOW: Sending message to user...")
        print(f"NEW_CONSULT_FLOW: NEW_CONSULT_COMPLAINT state value = {NEW_CONSULT_COMPLAINT}")
        sys.stdout.flush()
        
        # ⚠️ مهم جداً: حفظ NEW_CONSULT_COMPLAINT في التاريخ قبل إرسال الرسالة
        # هذا يضمن أن زر الرجوع يعمل بشكل صحيح
        StateHistoryManager.transition_to_state(context, NEW_CONSULT_COMPLAINT)
        
        result = await message.reply_text(
            "شكوى المريض\n\n"
            "يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        print(f"NEW_CONSULT_FLOW: Message sent successfully, message_id = {result.message_id}")
        print(f"NEW_CONSULT_FLOW: Waiting for user input in state NEW_CONSULT_COMPLAINT = {NEW_CONSULT_COMPLAINT}")
        print(f"NEW_CONSULT_FLOW: ConversationHandler should now be in state = {NEW_CONSULT_COMPLAINT}")
        print(f"NEW_CONSULT_FLOW: Returning state = {NEW_CONSULT_COMPLAINT}")
        print("=" * 80)
        sys.stdout.flush()
        logger.info("NEW_CONSULT_FLOW: Message sent successfully, waiting for user input")
        logger.info(f"NEW_CONSULT_FLOW: Returning state = {NEW_CONSULT_COMPLAINT}")
        
        # إرجاع state للتأكد من أن ConversationHandler يعرف الحالة الجديدة
        return NEW_CONSULT_COMPLAINT
    except Exception as e:
        error_msg = f"ERROR: NEW_CONSULT_FLOW - Error sending message: {e}"
        print(error_msg)
        traceback.print_exc()
        sys.stdout.flush()
        logger.error(error_msg, exc_info=True)
        raise


@debug_state_monitor("NEW_CONSULT_COMPLAINT")
async def handle_new_consult_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض"""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    logger.info("NEW_CONSULT_COMPLAINT: Handler called")
    logger.info(f"NEW_CONSULT_COMPLAINT: Current state = {current_state}, Expected = {NEW_CONSULT_COMPLAINT}")
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = NEW_CONSULT_COMPLAINT
    
    if not update.message:
        logger.error("NEW_CONSULT_COMPLAINT: No message in update!")
        return NEW_CONSULT_COMPLAINT
    
    text = update.message.text.strip()
    logger.info(f"NEW_CONSULT_COMPLAINT: Received text length = {len(text)}")
    
    try:
        valid, msg = validate_text_input(text, min_length=3, max_length=500)
        logger.info(f"NEW_CONSULT_COMPLAINT: Validation result = {valid}, message = {msg}")
    except Exception as e:
        logger.error(f"NEW_CONSULT_COMPLAINT: Error in validation: {e}", exc_info=True)
        return NEW_CONSULT_COMPLAINT

    if not valid:
        logger.warning(f"NEW_CONSULT_COMPLAINT: Validation failed, returning to same state")
        try:
            await update.message.reply_text(
                f"خطأ: {msg}\n\n"
                f"يرجى إدخال شكوى المريض:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"NEW_CONSULT_COMPLAINT: Failed to send error message: {e}", exc_info=True)
            # محاولة بديلة
            try:
                await update.message.reply_text("⚠️ خطأ في التحقق. يرجى المحاولة مرة أخرى.")
            except:
                pass
        return NEW_CONSULT_COMPLAINT

    # إذا وصلنا هنا، التحقق نجح
    logger.info(f"NEW_CONSULT_COMPLAINT: Validation passed, saving complaint")
    context.user_data.setdefault("report_tmp", {})["complaint"] = text

    try:
        logger.info("NEW_CONSULT_COMPLAINT: Sending decision request message...")
        await update.message.reply_text(
            "✅ تم الحفظ\n\n"
            "📝 **قرار الطبيب**\n\n"
            "يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        logger.info("NEW_CONSULT_COMPLAINT: Message sent, returning NEW_CONSULT_DECISION")
        return NEW_CONSULT_DECISION
    except Exception as e:
        logger.error(f"NEW_CONSULT_COMPLAINT: Error sending decision request: {e}", exc_info=True)
        # محاولة بديلة
        try:
            await update.message.reply_text(
                "✅ تم الحفظ\n\nيرجى إدخال قرار الطبيب:",
                parse_mode="Markdown"
            )
            return NEW_CONSULT_DECISION
        except Exception as fallback_error:
            logger.error(f"NEW_CONSULT_COMPLAINT: Fallback also failed: {fallback_error}")
            # إرجاع state آمن
            return NEW_CONSULT_COMPLAINT


@debug_state_monitor("NEW_CONSULT_DIAGNOSIS")
async def handle_new_consult_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("NEW_CONSULT_DIAGNOSIS: Handler called")
    
    if not update.message:
        logger.error("NEW_CONSULT_DIAGNOSIS: No message in update!")
        return NEW_CONSULT_DIAGNOSIS
    
    text = update.message.text.strip()
    logger.info(f"NEW_CONSULT_DIAGNOSIS: Received text length = {len(text)}")
    
    try:
        valid, msg = validate_text_input(text, min_length=3, max_length=500)
        logger.info(f"NEW_CONSULT_DIAGNOSIS: Validation result = {valid}, message = {msg}")
    except Exception as e:
        logger.error(f"NEW_CONSULT_DIAGNOSIS: Error in validation: {e}", exc_info=True)
        return NEW_CONSULT_DIAGNOSIS

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return NEW_CONSULT_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب**\n\n"
        "يرجى إدخال قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return NEW_CONSULT_DECISION


@debug_state_monitor("NEW_CONSULT_DECISION")
async def handle_new_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return NEW_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    # حفظ الـ state في التاريخ قبل الانتقال
    StateHistoryManager.transition_to_state(context, NEW_CONSULT_TESTS)

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **الفحوصات المطلوبة**\n\n"
        "يرجى إدخال الفحوصات المطلوبة قبل العملية:\n"
        "(أو اكتب 'لا يوجد' إذا لم تكن هناك فحوصات)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    context.user_data['_conversation_state'] = NEW_CONSULT_TESTS
    return NEW_CONSULT_TESTS


@debug_state_monitor("NEW_CONSULT_TESTS")
async def handle_new_consult_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: الفحوصات المطلوبة"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"
    else:
        valid, msg = validate_text_input(text, min_length=3, max_length=500)
        if not valid:
            await update.message.reply_text(
                f"⚠️ **خطأ: {msg}**\n\n"
                f"يرجى إدخال الفحوصات المطلوبة:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )
            return NEW_CONSULT_TESTS

    context.user_data["report_tmp"]["tests"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return NEW_CONSULT_FOLLOWUP_DATE


async def handle_new_consult_followup_date_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي تاريخ العودة"""
    query = update.callback_query
    await query.answer()

    # عدم حفظ تاريخ العودة
    context.user_data["report_tmp"]["followup_date"] = None
    context.user_data["report_tmp"]["followup_time"] = None

    # تحديد الحالة التالية بناءً على نوع الإجراء
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    if current_flow == "followup":
        next_state = FOLLOWUP_REASON
    elif current_flow == "emergency":
        next_state = EMERGENCY_REASON
    elif current_flow == "admission":
        next_state = ADMISSION_FOLLOWUP_REASON
    elif current_flow == "surgery_consult":
        next_state = SURGERY_CONSULT_FOLLOWUP_REASON
    elif current_flow == "operation":
        next_state = OPERATION_FOLLOWUP_REASON
    elif current_flow == "discharge":
        next_state = DISCHARGE_FOLLOWUP_REASON
    elif current_flow == "rehab_physical":
        next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
    elif current_flow == "device":
        next_state = DEVICE_FOLLOWUP_REASON
    else:
        next_state = NEW_CONSULT_FOLLOWUP_REASON

    await query.edit_message_text(
        "✅ تم التخطي\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return next_state


async def handle_new_consult_followup_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم تاريخ العودة"""
    query = update.callback_query
    await query.answer()

    # query.data format: "followup_cal_prev:2025-11" or "followup_cal_next:2025-11"
    parts = query.data.split(":", 1)
    if len(parts) != 2:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return NEW_CONSULT_FOLLOWUP_DATE

    action_part = parts[0]  # "followup_cal_prev" or "followup_cal_next"
    date_str = parts[1]  # "2025-11"

    # استخراج action
    if "prev" in action_part:
        action = "prev"
    elif "next" in action_part:
        action = "next"
    else:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return NEW_CONSULT_FOLLOWUP_DATE

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

    # تحديد الحالة الحالية بناءً على نوع الإجراء
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    if current_flow == "followup":
        current_state = FOLLOWUP_DATE_TIME
    elif current_flow == "emergency":
        current_state = EMERGENCY_DATE_TIME
    elif current_flow == "admission":
        current_state = ADMISSION_FOLLOWUP_DATE
    elif current_flow == "surgery_consult":
        current_state = SURGERY_CONSULT_FOLLOWUP_DATE
    elif current_flow == "operation":
        current_state = OPERATION_FOLLOWUP_DATE
    elif current_flow == "discharge":
        current_state = DISCHARGE_FOLLOWUP_DATE
    elif current_flow == "rehab_physical":
        current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
    elif current_flow == "device":
        current_state = DEVICE_FOLLOWUP_DATE
    else:
        current_state = NEW_CONSULT_FOLLOWUP_DATE

    await _render_followup_calendar(query, context, year, month)
    return current_state


async def handle_new_consult_followup_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ العودة من التقويم"""
    query = update.callback_query
    await query.answer()

    date_str = query.data.split(":", 1)[1]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        context.user_data["report_tmp"]["_pending_followup_date"] = dt.date()

        # بناء لوحة مفاتيح الساعات مع callback_data صحيح
        keyboard = []
        # أوقات شائعة أولاً (صباحاً)
        common_morning = [
            ("🌅 8:00 صباحاً", "08"),
            ("🌅 9:00 صباحاً", "09"),
            ("🌅 10:00 صباحاً", "10"),
            ("🌅 11:00 صباحاً", "11"),
        ]
        keyboard.append([InlineKeyboardButton(label,
    callback_data=f"followup_time_hour:{val}") for label,
     val in common_morning])

        # الظهر
        keyboard.append([InlineKeyboardButton("☀️ 12:00 ظهراً", callback_data="followup_time_hour:12")])

        # بعد الظهر
        common_afternoon = [
            ("🌆 1:00 مساءً", "13"),
            ("🌆 2:00 مساءً", "14"),
            ("🌆 3:00 مساءً", "15"),
            ("🌆 4:00 مساءً", "16"),
        ]
        keyboard.append([InlineKeyboardButton(label,
    callback_data=f"followup_time_hour:{val}") for label,
     val in common_afternoon])

        keyboard.append([InlineKeyboardButton("🕐 أوقات أخرى", callback_data="followup_time_hour:more")])
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ])

        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow == "followup":
            next_state = FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            next_state = EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_DATE
        else:
            next_state = NEW_CONSULT_FOLLOWUP_TIME

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{date_str}\n\n"
            f"🕐 **الوقت** (اختياري)\n\n"
            f"اختر الساعة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return next_state
    except ValueError:
        # تحديد الحالة الحالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow == "followup":
            current_state = FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            current_state = EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            current_state = ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            current_state = SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            current_state = OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            current_state = DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            current_state = DEVICE_FOLLOWUP_DATE
        else:
            current_state = NEW_CONSULT_FOLLOWUP_DATE

        await query.answer("⚠️ خطأ في التاريخ", show_alert=True)
        return current_state


async def handle_new_consult_followup_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الساعة لتاريخ العودة"""
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
                InlineKeyboardButton(label, callback_data=f"followup_time_hour:{val}")
                for label, val in zip(chunk_labels, chunk_values)
            ]
            keyboard.append(row)
        
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
        ])
        
        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow == "followup":
            next_state = FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            next_state = EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_DATE
        else:
            next_state = NEW_CONSULT_FOLLOWUP_TIME
        
        await query.edit_message_text(
            "🕐 **اختيار الساعة**\n\nاختر الساعة من القائمة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return next_state
    
    # حفظ الوقت مباشرة بدون اختيار الدقائق (الدقائق = 00)
    minute = "00"
    time_value = f"{hour}:{minute}"
    
    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_followup_date")
    if pending_date:
        from datetime import time
        # إنشاء datetime object
        dt = datetime.combine(pending_date, time(int(hour), int(minute)))
        
        data_tmp["followup_date"] = pending_date
        data_tmp["followup_time"] = time_value
        data_tmp.pop("_pending_followup_date", None)
        data_tmp.pop("_pending_followup_hour", None)
        
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
            0: 'الاثنين',
            1: 'الثلاثاء',
            2: 'الأربعاء',
            3: 'الخميس',
            4: 'الجمعة',
            5: 'السبت',
            6: 'الأحد'
        }
        day_name = days_ar.get(dt.weekday(), '')
        date_str = f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name}) - {time_display}"

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ والوقت**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})\n\n"
            f"🕐 **الوقت:**\n"
            f"{time_display}",
            parse_mode="Markdown"
        )
        
        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow == "followup":
            next_state = FOLLOWUP_REASON
        elif current_flow == "emergency":
            next_state = EMERGENCY_REASON
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_REASON
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_REASON
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_REASON
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_REASON
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_REASON
        else:
            next_state = NEW_CONSULT_FOLLOWUP_REASON
        
        # الانتقال إلى خطوة سبب العودة
        await query.message.reply_text(
            "✅ تم الحفظ\n\n"
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = next_state
        
        return next_state
    else:
        # إذا لم يكن هناك تاريخ معلق، نعود إلى اختيار التاريخ
        await query.edit_message_text(
            "⚠️ **خطأ**\n\n"
            "لم يتم اختيار التاريخ. يرجى اختيار التاريخ أولاً.",
            parse_mode="Markdown"
        )
        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow == "followup":
            return FOLLOWUP_DATE_TIME
        elif current_flow == "emergency":
            return EMERGENCY_DATE_TIME
        elif current_flow == "admission":
            return ADMISSION_FOLLOWUP_DATE
        elif current_flow == "surgery_consult":
            return SURGERY_CONSULT_FOLLOWUP_DATE
        elif current_flow == "operation":
            return OPERATION_FOLLOWUP_DATE
        elif current_flow == "discharge":
            return DISCHARGE_FOLLOWUP_DATE
        elif current_flow == "rehab_physical":
            return PHYSICAL_THERAPY_FOLLOWUP_DATE
        elif current_flow == "device":
            return DEVICE_FOLLOWUP_DATE
        else:
            return NEW_CONSULT_FOLLOWUP_DATE

async def handle_new_consult_followup_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الدقائق لتاريخ العودة"""
    query = update.callback_query
    await query.answer()
    _, hour, minute = query.data.split(":")
    time_value = f"{hour}:{minute}"
    
    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_followup_date")
    if pending_date:
        from datetime import time
        # إنشاء datetime object أولاً
        dt = datetime.combine(pending_date, time(int(hour), int(minute)))
        
        data_tmp["followup_date"] = pending_date
        data_tmp["followup_time"] = time_value
        data_tmp.pop("_pending_followup_date", None)
        data_tmp.pop("_pending_followup_hour", None)
        
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
            0: 'الاثنين',
            1: 'الثلاثاء',
            2: 'الأربعاء',
            3: 'الخميس',
            4: 'الجمعة',
            5: 'السبت',
            6: 'الأحد'
        }
        day_name = days_ar.get(dt.weekday(), '')
        date_str = f"📅🕐 {
    dt.strftime('%d')} {
        MONTH_NAMES_AR.get(
            dt.month, dt.month)} {
                dt.year} ({day_name}) - {time_display}"

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ والوقت**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})\n\n"
            f"🕐 **الوقت:**\n"
            f"{time_display}",
            parse_mode="Markdown"
        )
        
        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        if current_flow == "followup":
            next_state = FOLLOWUP_REASON
        elif current_flow == "emergency":
            next_state = EMERGENCY_REASON
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_REASON
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_REASON
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_REASON
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_REASON
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_REASON
        else:
            next_state = NEW_CONSULT_FOLLOWUP_REASON
        
        # الانتقال إلى خطوة سبب العودة
        await query.message.reply_text(
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return next_state

    # تحديد الحالة الحالية بناءً على نوع الإجراء
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    if current_flow == "followup":
        current_state = FOLLOWUP_DATE_TIME
    elif current_flow == "emergency":
        current_state = EMERGENCY_DATE_TIME
    elif current_flow == "admission":
        current_state = ADMISSION_FOLLOWUP_DATE
    elif current_flow == "surgery_consult":
        current_state = SURGERY_CONSULT_FOLLOWUP_DATE
    elif current_flow == "operation":
        current_state = OPERATION_FOLLOWUP_DATE
    elif current_flow == "discharge":
        current_state = DISCHARGE_FOLLOWUP_DATE
    elif current_flow == "rehab_physical":
        current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
    elif current_flow == "device":
        current_state = DEVICE_FOLLOWUP_DATE
    else:
        current_state = NEW_CONSULT_FOLLOWUP_TIME
    
    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return current_state


async def handle_new_consult_followup_time_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي اختيار الوقت لتاريخ العودة"""
    query = update.callback_query
    await query.answer()
    
    data_tmp = context.user_data.setdefault("report_tmp", {})
    pending_date = data_tmp.get("_pending_followup_date")
    if pending_date:
        data_tmp["followup_date"] = pending_date
        data_tmp["followup_time"] = None
        data_tmp.pop("_pending_followup_date", None)
        data_tmp.pop("_pending_followup_hour", None)
        
        days_ar = {
    0: 'الاثنين',
    1: 'الثلاثاء',
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
     6: 'الأحد'}
        day_name = days_ar.get(pending_date.weekday(), '')

        await query.edit_message_text(
            f"✅ تم اختيار التاريخ\n\n"
            f"📅 **التاريخ:**\n"
            f"{pending_date.strftime('%d')} {MONTH_NAMES_AR.get(pending_date.month, pending_date.month)} {pending_date.year} ({day_name})"
        )
        
        # تحديد الحالة التالية بناءً على نوع الإجراء
        current_flow = data_tmp.get("current_flow", "new_consult")
        if current_flow == "followup":
            next_state = FOLLOWUP_REASON
        elif current_flow == "emergency":
            next_state = EMERGENCY_REASON
        elif current_flow == "admission":
            next_state = ADMISSION_FOLLOWUP_REASON
        elif current_flow == "surgery_consult":
            next_state = SURGERY_CONSULT_FOLLOWUP_REASON
        elif current_flow == "operation":
            next_state = OPERATION_FOLLOWUP_REASON
        elif current_flow == "discharge":
            next_state = DISCHARGE_FOLLOWUP_REASON
        elif current_flow == "rehab_physical":
            next_state = PHYSICAL_THERAPY_FOLLOWUP_REASON
        elif current_flow == "device":
            next_state = DEVICE_FOLLOWUP_REASON
        else:
            next_state = NEW_CONSULT_FOLLOWUP_REASON
        
        # الانتقال إلى خطوة سبب العودة
        await query.message.reply_text(
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return next_state
    
    # تحديد الحالة الحالية بناءً على نوع الإجراء
    current_flow = data_tmp.get("current_flow", "new_consult")
    if current_flow == "followup":
        current_state = FOLLOWUP_DATE_TIME
    elif current_flow == "emergency":
        current_state = EMERGENCY_DATE_TIME
    elif current_flow == "admission":
        current_state = ADMISSION_FOLLOWUP_DATE
    elif current_flow == "surgery_consult":
        current_state = SURGERY_CONSULT_FOLLOWUP_DATE
    elif current_flow == "operation":
        current_state = OPERATION_FOLLOWUP_DATE
    elif current_flow == "discharge":
        current_state = DISCHARGE_FOLLOWUP_DATE
    elif current_flow == "rehab_physical":
        current_state = PHYSICAL_THERAPY_FOLLOWUP_DATE
    elif current_flow == "device":
        current_state = DEVICE_FOLLOWUP_DATE
    else:
        current_state = NEW_CONSULT_FOLLOWUP_TIME

    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return current_state


@debug_state_monitor("NEW_CONSULT_FOLLOWUP_REASON")
async def handle_new_consult_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 7: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return NEW_CONSULT_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "new_consult")

    return NEW_CONSULT_TRANSLATOR

# =============================
# مسار 2: مراجعة الطبيب / عودة دورية (6 حقول)
# شكوى، تشخيص، قرار، تاريخ ووقت عودة، سبب عودة، مترجم
# =============================


async def start_followup_flow(message, context):
    """بدء مسار مراجعة/عودة دورية - الحقل 1: شكوى المريض"""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_followup_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={FOLLOWUP_COMPLAINT}")
    
    logger.info("=" * 80)
    logger.info("start_followup_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "متابعة في الرقود"
    context.user_data["report_tmp"]["current_flow"] = "followup"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(FOLLOWUP_COMPLAINT)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    await message.reply_text(
        "💬 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return FOLLOWUP_COMPLAINT


async def start_periodic_followup_flow(message, context):
    """بدء مسار مراجعة / عودة دورية - الحقل 1: شكوى المريض"""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_periodic_followup_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={FOLLOWUP_COMPLAINT}")
    
    logger.info("=" * 80)
    logger.info("start_periodic_followup_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "مراجعة / عودة دورية"
    context.user_data["report_tmp"]["current_flow"] = "followup"  # نفس التدفق
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    await message.reply_text(
        "💬 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return FOLLOWUP_COMPLAINT

async def handle_followup_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض"""
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FOLLOWUP_COMPLAINT
    
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_COMPLAINT

    context.user_data["report_tmp"]["complaint"] = text

    # حفظ الـ state في التاريخ قبل الانتقال
    StateHistoryManager.transition_to_state(context, FOLLOWUP_DIAGNOSIS)

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FOLLOWUP_DIAGNOSIS

async def handle_followup_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    # حفظ الـ state في التاريخ قبل الانتقال
    StateHistoryManager.transition_to_state(context, FOLLOWUP_DECISION)

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب**\n\n"
        "يرجى إدخال قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FOLLOWUP_DECISION

async def handle_followup_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🏥 **رقم الغرفة والطابق**\n\n"
        "يرجى إدخال رقم الغرفة والطابق:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FOLLOWUP_ROOM_FLOOR


@debug_state_monitor("FOLLOWUP_ROOM_FLOOR")
async def handle_followup_room_floor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: رقم الغرفة والطابق"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})

    text = update.message.text.strip()

    # التحقق من صحة الإدخال (يمكن أن يكون رقم غرفة أو طابق أو كليهما)
    if not text or len(text) < 1 or len(text) > 50:
        await update.message.reply_text(
            "⚠️ **خطأ في الإدخال**\n\n"
            "يرجى إدخال رقم الغرفة والطابق (مثال: غرفة 205 - الطابق 2):",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_ROOM_FLOOR

    context.user_data["report_tmp"]["room_floor"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return FOLLOWUP_DATE_TIME

# تم إزالة handle_followup_date_time_text - الآن نستخدم التقويم
# سيتم استخدام handle_new_consult_followup_calendar_day و handle_new_consult_followup_time_hour و handle_new_consult_followup_time_minute

async def handle_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "followup")

    return FOLLOWUP_TRANSLATOR

# =============================
# مسار 3: طوارئ (7 حقول)
# شكوى، تشخيص، قرار وماذا تم، وضع الحالة، تاريخ ووقت عودة، سبب عودة، مترجم
# =============================

async def start_emergency_flow(message, context):
    """بدء مسار طوارئ - الحقل 1: شكوى المريض"""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_emergency_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={EMERGENCY_COMPLAINT}")
    
    logger.info("=" * 80)
    logger.info("start_emergency_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "طوارئ"
    context.user_data["report_tmp"]["current_flow"] = "emergency"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(EMERGENCY_COMPLAINT)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = EMERGENCY_COMPLAINT
    
    await message.reply_text(
        "💬 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return EMERGENCY_COMPLAINT

async def handle_emergency_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = EMERGENCY_COMPLAINT
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_COMPLAINT

    context.user_data["report_tmp"]["complaint"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص الطبي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_DIAGNOSIS

async def handle_emergency_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب وماذا تم للحالة في الطوارئ**\n\n"
        "يرجى إدخال قرار الطبيب وتفاصيل ما تم للحالة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_DECISION

async def handle_emergency_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب وماذا تم"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب وتفاصيل ما تم للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_DECISION

    context.user_data["report_tmp"]["decision"] = text

    # أزرار سريعة لوضع الحالة (نبقيها - مفيدة!)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 تم الخروج من الطوارئ", callback_data="emerg_status:discharged")],
        [InlineKeyboardButton("🛏️ تم الترقيد", callback_data="emerg_status:admitted")],
        [InlineKeyboardButton("⚕️ تم إجراء عملية", callback_data="emerg_status:operation")],
        [InlineKeyboardButton("✍️ إدخال يدوي", callback_data="emerg_status:manual")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🏥 **وضع الحالة**\n\n"
        "ما هو وضع الحالة الآن؟",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    return EMERGENCY_STATUS

async def handle_emergency_status_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار وضع الحالة"""
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)[1]

    if data == "manual":
        await query.edit_message_text(
            "🏥 **وضع الحالة**\n\n"
            "يرجى إدخال وضع الحالة:",
            parse_mode="Markdown"
        )
        return EMERGENCY_STATUS

    # تحديد النص بناءً على الاختيار
    status_text = {
        "discharged": "تم الخروج من الطوارئ",
        "admitted": "تم الترقيد",
        "operation": "تم إجراء عملية"
    }.get(data, "غير محدد")

    context.user_data["report_tmp"]["status"] = status_text

    # إذا اختار "تم الترقيد"، نعرض خيارات إضافية
    if data == "admitted":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏥 العناية المركزة", callback_data="emerg_admission:icu")],
            [InlineKeyboardButton("🛏️ الرقود", callback_data="emerg_admission:ward")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        
        await query.edit_message_text(
            f"✅ تم اختيار: {status_text}\n\n"
            "أين تم الترقيد؟",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return EMERGENCY_ADMISSION_TYPE
    
    # للخيارات الأخرى (discharged, operation)، نكمل مباشرة
    await query.edit_message_text(f"✅ تم اختيار: {status_text}")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(query.message, context)

    return EMERGENCY_DATE_TIME

async def handle_emergency_status_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: وضع الحالة (إدخال يدوي)"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال وضع الحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_STATUS

    context.user_data["report_tmp"]["status"] = text

    # إدخال مباشر للتاريخ والوقت (بدون أزرار)
    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📅 **تاريخ ووقت العودة**\n\n"
        "يرجى إدخال التاريخ والوقت:\n"
        "الصيغة: YYYY-MM-DD HH:MM\n"
        "مثال: 2025-10-30 14:30",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_DATE_TIME

async def handle_emergency_admission_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع الترقيد (العناية المركزة أو الرقود)"""
    query = update.callback_query
    await query.answer()

    data = query.data.split(":", 1)[1]

    admission_type_text = {
        "icu": "العناية المركزة",
        "ward": "الرقود"
    }.get(data, "غير محدد")

    context.user_data["report_tmp"]["admission_type"] = admission_type_text

    # إذا اختار "الرقود"، نطلب رقم الغرفة
    if data == "ward":
        await query.edit_message_text(
            f"✅ تم اختيار: {admission_type_text}\n\n"
            "🛏️ **رقم الغرفة**\n\n"
            "يرجى إدخال رقم الغرفة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ROOM_NUMBER
    
    # إذا اختار "العناية المركزة"، نكمل مباشرة
    await query.edit_message_text(f"✅ تم اختيار: {admission_type_text}")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(query.message, context)

    return EMERGENCY_DATE_TIME

async def handle_emergency_room_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل: رقم الغرفة (عند اختيار الرقود)"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1, max_length=50)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال رقم الغرفة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ROOM_NUMBER

    context.user_data["report_tmp"]["room_number"] = text

    await update.message.reply_text(f"✅ تم الحفظ: رقم الغرفة {text}")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return EMERGENCY_DATE_TIME

async def handle_emergency_date_time_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: تاريخ ووقت العودة"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-10-30 14:30",
            reply_markup=_nav_buttons(show_back=True)
        )
        return EMERGENCY_DATE_TIME

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return EMERGENCY_REASON

async def handle_emergency_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 6: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "emergency")

    return EMERGENCY_TRANSLATOR

# =============================
# مسار 4: ترقيد (6 حقول)
# سبب الرقود، رقم الغرفة، ملاحظات، تاريخ عودة، سبب عودة، مترجم
# =============================

async def start_admission_flow(message, context):
    """بدء مسار ترقيد - الحقل 1: سبب الرقود"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "ترقيد"
    context.user_data["report_tmp"]["current_flow"] = "admission"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(ADMISSION_REASON)
    
    context.user_data['_conversation_state'] = ADMISSION_REASON
    
    await message.reply_text(
        "🛏️ **سبب الرقود**\n\n"
        "يرجى إدخال سبب رقود المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return ADMISSION_REASON

async def handle_admission_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: سبب الرقود"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب الرقود:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return ADMISSION_REASON

    context.user_data["report_tmp"]["admission_reason"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🚪 **رقم الغرفة والطابق**\n\n"
        "يرجى إدخال رقم الغرفة والطابق:\n"
        "مثال: غرفة 205 - الطابق 2\n"
        "أو: Room 205, Floor 2\n\n"
        "(أو اكتب 'لم يتم التحديد' إذا لم يتم تحديدها بعد)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return ADMISSION_ROOM

async def handle_admission_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: رقم الغرفة والطابق"""
    text = update.message.text.strip()

    if text.lower() in ['لم يتم التحديد', 'لا يوجد', 'لا', 'no']:
        text = "لم يتم التحديد"

    # حفظ رقم الغرفة والطابق معاً
    context.user_data["report_tmp"]["room_number"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **ملاحظات**\n\n"
        "يرجى إدخال أي ملاحظات إضافية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return ADMISSION_NOTES

async def handle_admission_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: ملاحظات"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["notes"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return ADMISSION_FOLLOWUP_DATE

async def handle_admission_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-10-30 10:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return ADMISSION_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return ADMISSION_FOLLOWUP_REASON

async def handle_admission_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return ADMISSION_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "admission")

    return ADMISSION_TRANSLATOR

# =============================
# مسار 5: استشارة مع قرار عملية (8 حقول)
# التشخيص، قرار الطبيب وتفاصيل العملية، اسم العملية بالانجليزي، 
# نسبة نجاح العملية، الفحوصات والأشعة، تاريخ ووقت عودة، سبب عودة، مترجم
# =============================


async def start_surgery_consult_flow(message, context):
    """بدء مسار استشارة مع قرار عملية - الحقل 1: التشخيص"""
    import logging
    import sys
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_surgery_consult_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}, state={SURGERY_CONSULT_DIAGNOSIS}")
    
    logger.info("=" * 80)
    logger.info("start_surgery_consult_flow CALLED!")
    logger.info(f"medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.info(f"current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.info("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "استشارة مع قرار عملية"
    context.user_data["report_tmp"]["current_flow"] = "surgery_consult"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(SURGERY_CONSULT_DIAGNOSIS)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_DIAGNOSIS
    
    await message.reply_text(
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص الطبي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return SURGERY_CONSULT_DIAGNOSIS

async def handle_surgery_consult_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_DIAGNOSIS
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب وتفاصيل العملية**\n\n"
        "يرجى إدخال قرار الطبيب وتفاصيل العملية المقترحة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_DECISION

async def handle_surgery_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: قرار الطبيب وتفاصيل العملية"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب وتفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔤 **اسم العملية بالإنجليزي**\n\n"
        "يرجى إدخال اسم العملية بالإنجليزي:\n"
        "مثال: Laparoscopic Cholecystectomy",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_NAME_EN

async def handle_surgery_consult_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: اسم العملية بالإنجليزي"""
    text = update.message.text.strip()
    valid, msg = validate_english_only(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم العملية بالإنجليزي فقط:\n"
            f"مثال: Laparoscopic Cholecystectomy",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_NAME_EN

    context.user_data["report_tmp"]["operation_name_en"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📊 **نسبة نجاح العملية**\n\n"
        "يرجى إدخال نسبة نجاح العملية المتوقعة:\n"
        "مثال: 95%",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_SUCCESS_RATE

async def handle_surgery_consult_success_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: نسبة نجاح العملية"""
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_SUCCESS_RATE
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=1, max_length=100)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نسبة نجاح العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_SUCCESS_RATE

    context.user_data.setdefault("report_tmp", {})["success_rate"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "💡 **نسبة الاستفادة من العملية**\n\n"
        "يرجى إدخال نسبة الاستفادة المتوقعة من العملية:\n"
        "مثال: تحسن كامل، تحسن جزئي، تحسن طفيف",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_BENEFIT_RATE

    return SURGERY_CONSULT_BENEFIT_RATE

async def handle_surgery_consult_benefit_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: نسبة الاستفادة من العملية"""
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_BENEFIT_RATE
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نسبة الاستفادة من العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_BENEFIT_RATE

    context.user_data.setdefault("report_tmp", {})["benefit_rate"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **الفحوصات والأشعة المطلوبة**\n\n"
        "يرجى إدخال الفحوصات والأشعة المطلوبة قبل العملية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_TESTS

    return SURGERY_CONSULT_TESTS

async def handle_surgery_consult_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: الفحوصات والأشعة"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["tests"] = text
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = SURGERY_CONSULT_FOLLOWUP_DATE

    # عرض خيارات تاريخ العودة: التقويم أو إدخال نص
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اختيار من التقويم", callback_data="surgery_followup:calendar")],
        [InlineKeyboardButton("✏️ إدخال نص (مثل: الإدارة سوف تقرر)", callback_data="surgery_followup:text")],
        [InlineKeyboardButton("⏭️ تخطي", callback_data="surgery_followup:skip")],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ]
    ])
    
    await update.message.reply_text(
        "📅 **تاريخ ووقت العودة**\n\n"
        "اختر طريقة إدخال تاريخ العودة:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    return SURGERY_CONSULT_FOLLOWUP_DATE

async def handle_surgery_consult_followup_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار طريقة إدخال تاريخ العودة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "surgery_followup:calendar":
        # عرض التقويم
        await query.edit_message_text("📅 جارٍ تحميل التقويم...")
        await _render_followup_calendar(query.message, context)
        return SURGERY_CONSULT_FOLLOWUP_DATE
    elif query.data == "surgery_followup:text":
        # طلب إدخال نص
        await query.edit_message_text(
            "✏️ **إدخال نص تاريخ العودة**\n\n"
            "يرجى إدخال نص يوضح تاريخ العودة:\n"
            "مثال: الإدارة سوف تقرر التاريخ\n"
            "أو: سيتم تحديد التاريخ لاحقاً\n"
            "أو: حسب جدول الطبيب",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        # تعيين علامة أن المستخدم يريد إدخال نص
        context.user_data["report_tmp"]["followup_date_text_mode"] = True
        return SURGERY_CONSULT_FOLLOWUP_DATE
    elif query.data == "surgery_followup:skip":
        # تخطي تاريخ العودة
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        context.user_data["report_tmp"]["followup_date_text"] = None
        
        await query.edit_message_text(
            "✅ تم تخطي تاريخ العودة\n\n"
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_FOLLOWUP_REASON
    
    return SURGERY_CONSULT_FOLLOWUP_DATE

async def handle_surgery_consult_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 6: تاريخ ووقت العودة - نص أو تاريخ"""
    text = update.message.text.strip()
    
    # التحقق إذا كان المستخدم في وضع إدخال النص
    if context.user_data.get("report_tmp", {}).get("followup_date_text_mode"):
        # حفظ النص مباشرة
        context.user_data["report_tmp"]["followup_date_text"] = text
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        context.user_data["report_tmp"].pop("followup_date_text_mode", None)
        
        await update.message.reply_text(
            f"✅ تم الحفظ: {text}\n\n"
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_FOLLOWUP_REASON
    
    # محاولة parse التاريخ والوقت (للتوافق مع الإدخال القديم)
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
        context.user_data["report_tmp"]["followup_date_text"] = None
        
        await update.message.reply_text(
            "✅ تم الحفظ\n\n"
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_FOLLOWUP_REASON
    except ValueError:
        # إذا فشل parse، اعتباره نص
        context.user_data["report_tmp"]["followup_date_text"] = text
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        
        await update.message.reply_text(
            f"✅ تم الحفظ: {text}\n\n"
            "✍️ **سبب العودة**\n\n"
            "يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_FOLLOWUP_REASON

async def handle_surgery_consult_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 8: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return SURGERY_CONSULT_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "surgery_consult")

    return SURGERY_CONSULT_TRANSLATOR

# =============================
# مسار 6: عملية (6 حقول)
# تفاصيل العملية بالعربي، اسم العملية بالانجليزي، ملاحظات،
# تاريخ عودة، سبب عودة، مترجم
# =============================


async def start_operation_flow(message, context):
    """بدء مسار عملية - الحقل 1: تفاصيل العملية"""
    import logging
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_operation_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}")
    
    logger.error("=" * 80)
    logger.error("🔴 start_operation_flow CALLED!")
    logger.error(f"🔴 medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.error(f"🔴 current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.error("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "عملية"
    context.user_data["report_tmp"]["current_flow"] = "operation"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(OPERATION_DETAILS_AR)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = OPERATION_DETAILS_AR
    
    await message.reply_text(
        "⚕️ **تفاصيل العملية التي تمت للحالة**\n\n"
        "يرجى إدخال تفاصيل العملية بالعربي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return OPERATION_DETAILS_AR

async def handle_operation_details_ar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: تفاصيل العملية بالعربي"""
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = OPERATION_DETAILS_AR
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return OPERATION_DETAILS_AR

    context.user_data["report_tmp"]["operation_details"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔤 **اسم العملية بالإنجليزي**\n\n"
        "يرجى إدخال اسم العملية بالإنجليزي:\n"
        "مثال: Appendectomy",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return OPERATION_NAME_EN

async def handle_operation_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: اسم العملية بالإنجليزي"""
    text = update.message.text.strip()
    valid, msg = validate_english_only(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم العملية بالإنجليزي فقط:\n"
            f"مثال: Appendectomy",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return OPERATION_NAME_EN

    context.user_data["report_tmp"]["operation_name_en"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **ملاحظات**\n\n"
        "يرجى إدخال أي ملاحظات إضافية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return OPERATION_NOTES

async def handle_operation_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: ملاحظات"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["notes"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return OPERATION_FOLLOWUP_DATE

async def handle_operation_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-11-01 09:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return OPERATION_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return OPERATION_FOLLOWUP_REASON

async def handle_operation_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return OPERATION_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "operation")

    return OPERATION_TRANSLATOR

# =============================
# مسار 7: استشارة أخيرة (4 حقول)
# التشخيص، تفاصيل قرار الطبيب، التوصيات الطبية، مترجم
# =============================


async def start_final_consult_flow(message, context):
    """بدء مسار استشارة أخيرة - الحقل 1: التشخيص"""
    import logging
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_final_consult_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}")
    
    logger.error("=" * 80)
    logger.error("🔴 start_final_consult_flow CALLED!")
    logger.error(f"🔴 medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.error(f"🔴 current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.error("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "استشارة أخيرة"
    context.user_data["report_tmp"]["current_flow"] = "final_consult"
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FINAL_CONSULT_DIAGNOSIS
    
    await message.reply_text(
        "🔬 **التشخيص النهائي**\n\n"
        "يرجى إدخال التشخيص النهائي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return FINAL_CONSULT_DIAGNOSIS

async def handle_final_consult_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = FINAL_CONSULT_DIAGNOSIS
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FINAL_CONSULT_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **تفاصيل قرار الطبيب**\n\n"
        "يرجى إدخال تفاصيل قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FINAL_CONSULT_DECISION

async def handle_final_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: تفاصيل قرار الطبيب"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FINAL_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "💡 **التوصيات الطبية**\n\n"
        "يرجى إدخال التوصيات الطبية النهائية:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return FINAL_CONSULT_RECOMMENDATIONS

async def handle_final_consult_recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: التوصيات الطبية"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التوصيات الطبية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FINAL_CONSULT_RECOMMENDATIONS

    context.user_data["report_tmp"]["recommendations"] = text
    context.user_data["report_tmp"]["followup_date"] = None
    context.user_data["report_tmp"]["followup_reason"] = "استشارة أخيرة - لا يوجد عودة"

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "final_consult")

    return FINAL_CONSULT_TRANSLATOR

# =============================
# مسار 8: خروج من المستشفى (متفرع - خيارين)
# =============================

async def start_discharge_flow(message, context):
    """بدء مسار خروج من المستشفى - اختيار النوع"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "خروج من المستشفى"
    context.user_data["report_tmp"]["current_flow"] = "discharge"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(DISCHARGE_TYPE)
    
    context.user_data['_conversation_state'] = DISCHARGE_TYPE
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛏️ خروج بعد رقود طبي", callback_data="discharge_type:admission")],
        [InlineKeyboardButton("⚕️ خروج بعد عملية", callback_data="discharge_type:operation")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "🏠 **خروج من المستشفى**\n\n"
        "اختر نوع الخروج:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    return DISCHARGE_TYPE

async def handle_discharge_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نوع الخروج"""
    query = update.callback_query
    await query.answer()

    discharge_type = query.data.split(":", 1)[1]
    context.user_data["report_tmp"]["discharge_type"] = discharge_type

    if discharge_type == "admission":
        await query.edit_message_text("✅ اخترت: خروج بعد رقود طبي")
        await query.message.reply_text(
            "📋 **أبرز ما تم للحالة أثناء الرقود**\n\n"
            "يرجى إدخال ملخص ما تم للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_ADMISSION_SUMMARY

    elif discharge_type == "operation":
        await query.edit_message_text("✅ اخترت: خروج بعد عملية")
        await query.message.reply_text(
            "⚕️ **تفاصيل العملية التي تمت للحالة**\n\n"
            "يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_OPERATION_DETAILS

# فرع 1: خروج بعد رقود
async def handle_discharge_admission_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج بعد رقود - الحقل 1: ملخص الرقود"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال ملخص ما تم للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_ADMISSION_SUMMARY

    context.user_data["report_tmp"]["admission_summary"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return DISCHARGE_FOLLOWUP_DATE

# فرع 2: خروج بعد عملية
async def handle_discharge_operation_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج بعد عملية - الحقل 1: تفاصيل العملية"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=1000)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_OPERATION_DETAILS

    context.user_data["report_tmp"]["operation_details"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔤 **اسم العملية بالإنجليزي**\n\n"
        "يرجى إدخال اسم العملية بالإنجليزي:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return DISCHARGE_OPERATION_NAME_EN

async def handle_discharge_operation_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج بعد عملية - الحقل 2: اسم العملية بالإنجليزي"""
    text = update.message.text.strip()
    valid, msg = validate_english_only(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم العملية بالإنجليزي فقط:\n"
            f"مثال: Appendectomy",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_OPERATION_NAME_EN

    context.user_data["report_tmp"]["operation_name_en"] = text

    # عرض تقويم تاريخ العودة (بدلاً من الإدخال النصي)
    await _render_followup_calendar(update.message, context)

    return DISCHARGE_FOLLOWUP_DATE

async def handle_discharge_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج (كلا الفرعين) - تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-11-10 10:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return DISCHARGE_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return DISCHARGE_FOLLOWUP_REASON

async def handle_discharge_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج (كلا الفرعين) - سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DISCHARGE_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "discharge")

    return DISCHARGE_TRANSLATOR

# =============================
# مسار 9: علاج طبيعي / أجهزة تعويضية (متفرع)
# =============================

async def start_rehab_flow(message, context):
    """بدء مسار علاج طبيعي/أجهزة - اختيار النوع"""
    import logging
    logger = logging.getLogger(__name__)
    
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"start_rehab_flow CALLED! medical_action={repr(medical_action)}, current_flow={repr(current_flow)}")
    
    logger.error("=" * 80)
    logger.error("🔴 start_rehab_flow CALLED!")
    logger.error(f"🔴 medical_action: {context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')}")
    logger.error(f"🔴 current_flow: {context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')}")
    logger.error("=" * 80)
    
    # التأكد من حفظ medical_action
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "علاج طبيعي وإعادة تأهيل"
    context.user_data["report_tmp"]["current_flow"] = "rehab_physical"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(REHAB_TYPE)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = REHAB_TYPE
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏃 علاج طبيعي", callback_data="rehab_type:physical_therapy")],
        [InlineKeyboardButton("🦾 أجهزة تعويضية", callback_data="rehab_type:device")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        "🏃 **علاج طبيعي / أجهزة تعويضية**\n\n"
        "اختر النوع:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    return REHAB_TYPE

async def handle_rehab_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نوع العلاج التأهيلي"""
    query = update.callback_query
    await query.answer()

    rehab_type = query.data.split(":", 1)[1]
    context.user_data.setdefault("report_tmp", {})["rehab_type"] = rehab_type

    if rehab_type == "physical_therapy":
        await query.edit_message_text("✅ اخترت: علاج طبيعي")
        context.user_data["report_tmp"]["current_flow"] = "rehab_physical"
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = PHYSICAL_THERAPY_DETAILS
        await query.message.reply_text(
            "🏃 **تفاصيل جلسة العلاج الطبيعي**\n\n"
            "يرجى إدخال تفاصيل الجلسة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return PHYSICAL_THERAPY_DETAILS

    elif rehab_type == "device":
        await query.edit_message_text("✅ اخترت: أجهزة تعويضية")
        context.user_data["report_tmp"]["current_flow"] = "rehab_device"
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = DEVICE_NAME_DETAILS
        await query.message.reply_text(
            "🦾 **اسم الجهاز الذي تم توفيره مع التفاصيل**\n\n"
            "يرجى إدخال اسم الجهاز والتفاصيل:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DEVICE_NAME_DETAILS

# فرع 1: علاج طبيعي
async def handle_physical_therapy_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - الحقل 1: تفاصيل الجلسة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال تفاصيل جلسة العلاج الطبيعي:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return PHYSICAL_THERAPY_DETAILS

    context.user_data["report_tmp"]["therapy_details"] = text

    # عرض التقويم مباشرة
    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📅 **تاريخ العودة**\n\n"
        "يرجى اختيار تاريخ العودة من التقويم:",
        parse_mode="Markdown"
    )
    
    await _render_followup_calendar(update.message, context)

    return PHYSICAL_THERAPY_FOLLOWUP_DATE

async def handle_physical_therapy_followup_date_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار وجود تاريخ عودة"""
    query = update.callback_query
    await query.answer()

    if query.data == "physical_date:no":
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        context.user_data["report_tmp"]["followup_reason"] = "لا يوجد"

        await query.edit_message_text("✅ لا يوجد تاريخ عودة")
        await ask_translator_name(query.message, context, "rehab_physical")
        return PHYSICAL_THERAPY_TRANSLATOR

    elif query.data == "physical_date:yes":
        await _render_followup_calendar(query.message, context)
        return PHYSICAL_THERAPY_FOLLOWUP_DATE

async def handle_physical_therapy_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-10-30 10:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return PHYSICAL_THERAPY_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return PHYSICAL_THERAPY_FOLLOWUP_REASON

async def handle_physical_therapy_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - الحقل 4: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return PHYSICAL_THERAPY_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "rehab_physical")

    return PHYSICAL_THERAPY_TRANSLATOR

# فرع 2: أجهزة تعويضية
async def handle_device_name_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - الحقل 1: اسم الجهاز والتفاصيل"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=5, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم الجهاز والتفاصيل:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DEVICE_NAME_DETAILS

    context.user_data["report_tmp"]["device_details"] = text

    # عرض تقويم تاريخ العودة مباشرة
    await _render_followup_calendar(update.message, context)

    return DEVICE_FOLLOWUP_DATE

async def handle_device_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - تاريخ ووقت العودة مدمج"""
    text = update.message.text.strip()

    # parse التاريخ والوقت معاً
    try:
        dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
        context.user_data["report_tmp"]["followup_date"] = dt.date()
        context.user_data["report_tmp"]["followup_time"] = dt.strftime("%H:%M")
    except ValueError:
        await update.message.reply_text(
            "⚠️ **صيغة غير صحيحة!**\n\n"
            "يرجى استخدام الصيغة الصحيحة:\n"
            "YYYY-MM-DD HH:MM\n"
            "مثال: 2025-11-15 11:00",
            reply_markup=_nav_buttons(show_back=True)
        )
        return DEVICE_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return DEVICE_FOLLOWUP_REASON

async def handle_device_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - الحقل 4: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=200)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return DEVICE_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await ask_translator_name(update.message, context, "rehab_device")

    return DEVICE_TRANSLATOR

# =============================
# مسار 10: أشعة وفحوصات
# =============================

async def start_radiology_flow(message, context):
    """بدء مسار أشعة وفحوصات"""
    # التأكد من حفظ medical_action و current_flow
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "أشعة وفحوصات"
    context.user_data["report_tmp"]["current_flow"] = "radiology"
    
    # حفظ الـ state في التاريخ
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(RADIOLOGY_TYPE)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = RADIOLOGY_TYPE
    
    await message.reply_text(
        "🔬 **نوع الأشعة والفحوصات**\n\n"
        "يرجى إدخال نوع الأشعة أو الفحوصات:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    return RADIOLOGY_TYPE

async def handle_radiology_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: نوع الأشعة"""
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = RADIOLOGY_TYPE
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3, max_length=500)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال نوع الأشعة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return RADIOLOGY_TYPE

    context.user_data.setdefault("report_tmp", {})["radiology_type"] = text
    context.user_data["report_tmp"]["current_flow"] = "radiology"
    context.user_data["report_tmp"]["medical_action"] = "أشعة وفحوصات"

    # استخدام التقويم مباشرة
    await update.message.reply_text("✅ تم الحفظ")
    await _render_radiology_calendar(update.message, context)
    
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = RADIOLOGY_DELIVERY_DATE

    return RADIOLOGY_DELIVERY_DATE

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
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"📅 **اختيار تاريخ التقرير**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)

def _build_followup_calendar_markup(year: int, month: int):
    """بناء تقويم تاريخ العودة"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []

    # تقويم الشهر مع أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"followup_cal_prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"followup_cal_next:{year}-{month:02d}"),
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
                            row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"followup_cal_day:{date_str}"))
                        else:
                            row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"followup_cal_day:{date_str}"))
                except Exception:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"📅 **تاريخ ووقت العودة**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)

async def _render_followup_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم تاريخ العودة"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = data_tmp.get("followup_calendar_year", now.year)
        month = data_tmp.get("followup_calendar_month", now.month)

    text, markup = _build_followup_calendar_markup(year, month)
    data_tmp["followup_calendar_year"] = year
    data_tmp["followup_calendar_month"] = month

    if hasattr(message_or_query, 'edit_message_text'):
        # query object
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        # message object
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")

def _build_followup_minute_keyboard(hour: str):
    """بناء لوحة اختيار الدقائق لتاريخ العودة"""
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
        row = [
            InlineKeyboardButton(
                f"{hour_display}:{min}", callback_data=f"followup_time_minute:{hour}:{min}"
            )
            for min in chunk
        ]
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    return InlineKeyboardMarkup(keyboard)

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

def _build_radiology_calendar_markup(year: int, month: int):
    """بناء تقويم تاريخ تسليم نتائج الأشعة"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []

    # تقويم الشهر مع أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"radiology_cal_prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
        InlineKeyboardButton("➡️", callback_data=f"radiology_cal_next:{year}-{month:02d}"),
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
                            row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"radiology_cal_day:{date_str}"))
                        else:
                            row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"radiology_cal_day:{date_str}"))
                except Exception:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = f"📅 **اختيار تاريخ تسليم النتائج**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)

async def _render_radiology_calendar(message_or_query, context, year=None, month=None):
    """عرض تقويم تاريخ تسليم نتائج الأشعة"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month

    text, markup = _build_radiology_calendar_markup(year, month)
    data_tmp["radiology_calendar_year"] = year
    data_tmp["radiology_calendar_month"] = month

    # التحقق إذا كان message أو query
    if hasattr(message_or_query, 'edit_message_text'):
        # query object
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        # message object
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")

async def handle_radiology_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم radiology"""
    query = update.callback_query
    await query.answer()
    prefix, ym = query.data.split(":", 1)
    year, month = map(int, ym.split("-"))
    if prefix == "radiology_cal_prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif prefix == "radiology_cal_next":
        month += 1
        if month > 12:
            month = 1
            year += 1
    await _render_radiology_calendar(query.message, context, year, month)
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = RADIOLOGY_DELIVERY_DATE
    return RADIOLOGY_DELIVERY_DATE

async def handle_radiology_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ تسليم نتائج الأشعة"""
    query = update.callback_query
    await query.answer()
    date_str = query.data.split(":", 1)[1]
    try:
        delivery_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data.setdefault("report_tmp", {})["radiology_delivery_date"] = delivery_date
        context.user_data["report_tmp"]["followup_date"] = delivery_date
        context.user_data["report_tmp"]["followup_reason"] = "تسليم نتائج الأشعة والفحوصات"

        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(delivery_date.weekday(), '')
        date_display = f"📅 {delivery_date.strftime('%d')} {MONTH_NAMES_AR.get(delivery_date.month, delivery_date.month)} {delivery_date.year} ({day_name})"

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **تاريخ التسليم:**\n"
            f"{date_display}"
        )
        await ask_translator_name(query.message, context, "radiology")
        
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = RADIOLOGY_TRANSLATOR

        return RADIOLOGY_TRANSLATOR
    except ValueError:
        await query.answer("صيغة غير صالحة", show_alert=True)
        return RADIOLOGY_DELIVERY_DATE

# =============================
# دالة مشتركة: اسم المترجم
# =============================

async def render_translator_selection(message, context, flow_type):
    """عرض شاشة اختيار المترجم - rendering فقط (مثل render_patient_selection)"""
    keyboard = []

    # زر البحث الذكي (inline search)
    keyboard.append([InlineKeyboardButton(
        "🔍 بحث عن مترجم",
        switch_inline_query_current_chat=""
    )])
    
    # زر عرض قائمة كاملة مع pagination
    keyboard.append([InlineKeyboardButton(
        "📋 عرض جميع الأسماء",
        callback_data=f"translator:show_list:{flow_type}:0"
    )])
    
    # زر إضافة مترجم جديد
    keyboard.append([InlineKeyboardButton(
        "➕ إضافة مترجم جديد",
        callback_data=f"translator:{flow_type}:add_new"
    )])

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = "👤 **اسم المترجم**\n\n"
    text += "**خيارات البحث:**\n"
    text += "• 🔍 **بحث عن مترجم:** للبحث السريع (حتى 50 نتيجة)\n"
    text += "• 📋 **عرض جميع الأسماء:** لعرض جميع الأسماء مع التنقل بين الصفحات\n"
    text += "• ➕ **إضافة مترجم جديد:** لإضافة مترجم جديد\n"
    text += "\nاختر الطريقة المناسبة:"

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def ask_translator_name(message, context, flow_type):
    """طلب اسم المترجم - مشترك لجميع المسارات (يستخدم render_translator_selection)"""
    # تعيين نوع البحث للمترجمين
    context.user_data['_current_search_type'] = 'translator'
    await render_translator_selection(message, context, flow_type)


async def show_translator_list(update: Update, context: ContextTypes.DEFAULT_TYPE, flow_type: str, page: int = 0):
    """عرض قائمة المترجمين مع pagination"""
    query = update.callback_query
    if query:
        await query.answer()
    
    items_per_page = 10  # 10 أسماء في كل صفحة
    
    with SessionLocal() as s:
        # جلب جميع المترجمين من قاعدة البيانات (من جدول users/translators)
        # فقط المترجمين المعتمدين (is_approved = True)
        all_translators = s.query(Translator).filter(
            Translator.is_approved == True,
            Translator.full_name.isnot(None),
            Translator.full_name != ""
        ).order_by(Translator.full_name).all()
        
        total = len(all_translators)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        translators_page = all_translators[start_idx:end_idx]
        
        keyboard = []
        
        # إضافة أزرار المترجمين
        for translator in translators_page:
            keyboard.append([InlineKeyboardButton(
                f"👤 {translator.full_name}",
                callback_data=f"translator_idx:{flow_type}:{translator.id}"
            )])
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"translator:show_list:{flow_type}:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"translator:show_list:{flow_type}:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # أزرار إضافية
        keyboard.append([
            InlineKeyboardButton("🔍 بحث سريع", switch_inline_query_current_chat=""),
            InlineKeyboardButton("🔙 رجوع", callback_data=f"translator:back_to_menu:{flow_type}")
        ])
        
        text = f"👤 **قائمة المترجمين**\n\n"
        text += f"📊 **العدد الإجمالي:** {total} مترجم\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        text += "اختر المترجم من القائمة:"
        
        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        # إرجاع state المترجم المناسب
        return get_translator_state(flow_type)


async def handle_translator_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callbacks قائمة المترجمين"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("translator:show_list:"):
        try:
            parts = query.data.split(":")
            flow_type = parts[2]
            page = int(parts[3])
            return await show_translator_list(update, context, flow_type, page)
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing page number: {e}")
            await query.answer("⚠️ خطأ في رقم الصفحة", show_alert=True)
            flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
            return get_translator_state(flow_type)
    elif query.data.startswith("translator:back_to_menu:"):
        flow_type = query.data.split(":")[-1]
        await render_translator_selection(query.message, context, flow_type)
        return get_translator_state(flow_type)
    
    flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    return get_translator_state(flow_type)


async def handle_translator_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المترجم"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    flow_type = parts[1]
    
    # معالجة اختيار المترجم من القائمة (translator_idx)
    if query.data.startswith("translator_idx:"):
        try:
            translator_id = int(parts[2])
            with SessionLocal() as s:
                translator = s.query(Translator).filter_by(id=translator_id).first()
                if translator:
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = translator.full_name
                    context.user_data["report_tmp"]["translator_id"] = translator.id
                else:
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = "غير محدد"
                    context.user_data["report_tmp"]["translator_id"] = None
            
            await query.edit_message_text("✅ تم اختيار المترجم")
            await show_final_summary(query.message, context, flow_type)
            
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing translator ID: {e}")
            await query.answer("⚠️ خطأ في اختيار المترجم", show_alert=True)
            return get_translator_state(flow_type)
    
    # معالجة الخيارات القديمة (auto, manual, add_new)
    if len(parts) > 2:
        choice = parts[2]
        
        if choice == "auto":
            user_id = query.from_user.id
            with SessionLocal() as s:
                translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
                if translator:
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = translator.full_name
                    context.user_data["report_tmp"]["translator_id"] = translator.id
                else:
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = "غير محدد"
                    context.user_data["report_tmp"]["translator_id"] = None

            await query.edit_message_text("✅ تم اختيار المترجم")
            await show_final_summary(query.message, context, flow_type)

            # إرجاع state التأكيد المناسب
            confirm_state = get_confirm_state(flow_type)
            # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state

        elif choice == "manual":
            await query.edit_message_text(
                "👤 **إدخال اسم المترجم**\n\n"
                "يرجى إدخال اسم المترجم:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )

            context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type
            translator_state = get_translator_state(flow_type)
            context.user_data['_conversation_state'] = translator_state
            return translator_state
        
        elif choice == "add_new":
            await query.edit_message_text(
                "➕ **إضافة مترجم جديد**\n\n"
                "يرجى إدخال اسم المترجم الجديد:",
                reply_markup=_nav_buttons(show_back=True),
                parse_mode="Markdown"
            )

            context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type
            context.user_data.setdefault("report_tmp", {})["translator_add_new"] = True  # علامة لإضافة المترجم الجديد
            translator_state = get_translator_state(flow_type)
            context.user_data['_conversation_state'] = translator_state
            return translator_state

async def handle_translator_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المترجم من inline query (عند إرسال الرسالة)"""
    text = update.message.text.strip()
    
    if text.startswith("__TRANSLATOR_SELECTED__:"):
        try:
            parts = text.split(":")
            translator_id = int(parts[1])
            translator_name = parts[2] if len(parts) > 2 else ""
            
            flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
            
            with SessionLocal() as s:
                translator = s.query(Translator).filter_by(id=translator_id).first()
                if translator:
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = translator.full_name
                    context.user_data["report_tmp"]["translator_id"] = translator.id
                else:
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = translator_name or "غير محدد"
                    context.user_data["report_tmp"]["translator_id"] = None
            
            await update.message.reply_text("✅ تم اختيار المترجم")
            await show_final_summary(update.message, context, flow_type)
            
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state
                
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing inline translator selection: {e}")
            await update.message.reply_text(
                "❌ **خطأ**\n\n"
                "حدث خطأ في معالجة الاختيار.",
                parse_mode="Markdown"
            )
            flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
            return get_translator_state(flow_type)
    
    # إذا لم يكن inline selection، نتعامل معه كإدخال نصي عادي
    return await handle_translator_text(update, context)


async def show_translator_list(update: Update, context: ContextTypes.DEFAULT_TYPE, flow_type: str, page: int = 0):
    """عرض قائمة المترجمين مع pagination"""
    query = update.callback_query
    if query:
        await query.answer()
    
    items_per_page = 10  # 10 أسماء في كل صفحة
    
    with SessionLocal() as s:
        # جلب جميع المترجمين من قاعدة البيانات (من جدول users/translators)
        # فقط المترجمين المعتمدين (is_approved = True)
        all_translators = s.query(Translator).filter(
            Translator.is_approved == True,
            Translator.full_name.isnot(None),
            Translator.full_name != ""
        ).order_by(Translator.full_name).all()
        
        total = len(all_translators)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        translators_page = all_translators[start_idx:end_idx]
        
        keyboard = []
        
        # إضافة أزرار المترجمين
        for translator in translators_page:
            keyboard.append([InlineKeyboardButton(
                f"👤 {translator.full_name}",
                callback_data=f"translator_idx:{flow_type}:{translator.id}"
            )])
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"translator:show_list:{flow_type}:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"translator:show_list:{flow_type}:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # أزرار إضافية
        keyboard.append([
            InlineKeyboardButton("🔍 بحث سريع", switch_inline_query_current_chat=""),
            InlineKeyboardButton("🔙 رجوع", callback_data=f"translator:back_to_menu:{flow_type}")
        ])
        
        text = f"👤 **قائمة المترجمين**\n\n"
        text += f"📊 **العدد الإجمالي:** {total} مترجم\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        text += "اختر المترجم من القائمة:"
        
        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        # إرجاع state المترجم المناسب
        return get_translator_state(flow_type)


async def handle_translator_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callbacks قائمة المترجمين"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("translator:show_list:"):
        try:
            parts = query.data.split(":")
            flow_type = parts[2]
            page = int(parts[3])
            return await show_translator_list(update, context, flow_type, page)
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing page number: {e}")
            await query.answer("⚠️ خطأ في رقم الصفحة", show_alert=True)
            flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
            return get_translator_state(flow_type)
    elif query.data.startswith("translator:back_to_menu:"):
        flow_type = query.data.split(":")[-1]
        await render_translator_selection(query.message, context, flow_type)
        return get_translator_state(flow_type)
    
    flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    return get_translator_state(flow_type)


async def handle_translator_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المترجم يدوياً"""
    text = update.message.text.strip()
    
    # التحقق إذا كان من inline query
    if text.startswith("__TRANSLATOR_SELECTED__:"):
        return await handle_translator_inline_selection(update, context)
    
    valid, msg = validate_text_input(text, min_length=2, max_length=100)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم المترجم:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        # إرجاع نفس state المترجم
        flow_type = context.user_data["report_tmp"].get("current_flow", "new_consult")
        return get_translator_state(flow_type)

    flow_type = context.user_data["report_tmp"].get("current_flow", "new_consult")
    
    # إذا كان زر "إضافة مترجم جديد"، نحفظ المترجم في قاعدة البيانات
    if context.user_data.get("report_tmp", {}).get("translator_add_new"):
        try:
            with SessionLocal() as s:
                # التحقق إذا كان المترجم موجوداً بالفعل
                existing_translator = s.query(Translator).filter(
                    Translator.full_name.ilike(text)
                ).first()
                
                if existing_translator:
                    # إذا كان موجوداً، نستخدمه
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = existing_translator.full_name
                    context.user_data["report_tmp"]["translator_id"] = existing_translator.id
                    await update.message.reply_text(f"✅ تم استخدام المترجم الموجود: {existing_translator.full_name}")
                else:
                    # إنشاء مترجم جديد في قاعدة البيانات
                    new_translator = Translator(
                        full_name=text,
                        is_approved=True,
                        is_active=True,
                        role="translator",
                        status="approved"
                    )
                    s.add(new_translator)
                    s.commit()
                    s.refresh(new_translator)
                    
                    context.user_data.setdefault("report_tmp", {})["translator_name"] = new_translator.full_name
                    context.user_data["report_tmp"]["translator_id"] = new_translator.id
                    await update.message.reply_text(f"✅ تم إضافة المترجم الجديد: {text}")
                
                # إزالة العلامة
                context.user_data["report_tmp"].pop("translator_add_new", None)
        except Exception as e:
            logger.error(f"❌ Error adding new translator: {e}", exc_info=True)
            await update.message.reply_text(
                "⚠️ **خطأ**\n\n"
                "حدث خطأ أثناء إضافة المترجم. سيتم استخدام الاسم فقط في التقرير.",
                parse_mode="Markdown"
            )
            context.user_data.setdefault("report_tmp", {})["translator_name"] = text
            context.user_data["report_tmp"]["translator_id"] = None
            context.user_data["report_tmp"].pop("translator_add_new", None)
    else:
        # إدخال عادي (لا نحفظ في قاعدة البيانات)
        context.user_data.setdefault("report_tmp", {})["translator_name"] = text
        context.user_data["report_tmp"]["translator_id"] = None

    await show_final_summary(update.message, context, flow_type)

    confirm_state = get_confirm_state(flow_type)
    # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
    context.user_data['_conversation_state'] = confirm_state
    return confirm_state

def get_translator_state(flow_type):
    """الحصول على state المترجم المناسب"""
    states = {
        "new_consult": NEW_CONSULT_TRANSLATOR,
        "followup": FOLLOWUP_TRANSLATOR,
        "surgery_consult": SURGERY_CONSULT_TRANSLATOR,
        "emergency": EMERGENCY_TRANSLATOR,
        "admission": ADMISSION_TRANSLATOR,
        "operation": OPERATION_TRANSLATOR,
        "final_consult": FINAL_CONSULT_TRANSLATOR,
        "discharge": DISCHARGE_TRANSLATOR,
        "rehab_physical": PHYSICAL_THERAPY_TRANSLATOR,
        "rehab_device": DEVICE_TRANSLATOR,
        "radiology": RADIOLOGY_TRANSLATOR
    }
    return states.get(flow_type, NEW_CONSULT_TRANSLATOR)

def get_confirm_state(flow_type):
    """الحصول على state التأكيد المناسب"""
    states = {
        "new_consult": NEW_CONSULT_CONFIRM,
        "followup": FOLLOWUP_CONFIRM,
        "surgery_consult": SURGERY_CONSULT_CONFIRM,
        "emergency": EMERGENCY_CONFIRM,
        "admission": ADMISSION_CONFIRM,
        "operation": OPERATION_CONFIRM,
        "final_consult": FINAL_CONSULT_CONFIRM,
        "discharge": DISCHARGE_CONFIRM,
        "rehab_physical": PHYSICAL_THERAPY_CONFIRM,
        "device": DEVICE_CONFIRM,
        "radiology": RADIOLOGY_CONFIRM
    }
    return states.get(flow_type, NEW_CONSULT_CONFIRM)

def get_first_state(flow_type):
    """الحصول على state الخطوة الأولى من التدفق"""
    states = {
        "new_consult": NEW_CONSULT_COMPLAINT,
        "followup": FOLLOWUP_COMPLAINT,
        "surgery_consult": SURGERY_CONSULT_DIAGNOSIS,
        "emergency": EMERGENCY_COMPLAINT,
        "admission": ADMISSION_REASON,
        "operation": OPERATION_DETAILS_AR,
        "final_consult": FINAL_CONSULT_DIAGNOSIS,
        "discharge": DISCHARGE_TYPE,
        "rehab_physical": REHAB_TYPE,
        "rehab_device": REHAB_TYPE,  # يبدأ من نفس state ثم يختار نوع العلاج
        "radiology": RADIOLOGY_TYPE
    }
    return states.get(flow_type, NEW_CONSULT_COMPLAINT)

def get_editable_fields_by_flow_type(flow_type):
    """الحصول على الحقول القابلة للتعديل حسب نوع التدفق"""
    fields_map = {
        "new_consult": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("tests", "🧪 الفحوصات والأشعة"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "followup": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "emergency": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب وماذا تم"),
            ("status", "🏥 وضع الحالة"),
            ("admission_type", "🛏️ نوع الترقيد"),
            ("room_number", "🚪 رقم الغرفة والطابق"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "admission": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("admission_reason", "🛏️ سبب الرقود"),
            ("room_number", "🚪 رقم الغرفة والطابق"),
            ("notes", "📝 ملاحظات"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "surgery_consult": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("diagnosis", "🔬 التشخيص"),
            ("decision", "📝 قرار الطبيب وتفاصيل العملية"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("success_rate", "📊 نسبة نجاح العملية"),
            ("benefit_rate", "💡 نسبة الاستفادة"),
            ("tests", "🧪 الفحوصات والأشعة"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "operation": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("operation_details", "⚕️ تفاصيل العملية بالعربي"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("notes", "📝 ملاحظات"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "final_consult": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("diagnosis", "🔬 التشخيص النهائي"),
            ("decision", "📝 قرار الطبيب"),
            ("recommendations", "💡 التوصيات الطبية"),
        ],
        "discharge": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("discharge_type", "🚪 نوع الخروج"),
            ("admission_summary", "📋 ملخص الرقود"),
            ("operation_details", "⚕️ تفاصيل العملية"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "rehab_physical": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("therapy_details", "🏃 تفاصيل جلسة العلاج الطبيعي"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "rehab_device": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("device_name", "🦾 اسم الجهاز والتفاصيل"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "radiology": [
            ("report_date", "📅 التاريخ والوقت"),
            ("patient_name", "👤 اسم المريض"),
            ("hospital_name", "🏥 المستشفى"),
            ("department_name", "🏷️ القسم"),
            ("doctor_name", "👨‍⚕️ اسم الطبيب"),
            ("radiology_type", "🔬 نوع الأشعة/الفحص"),
            ("delivery_date", "📅 تاريخ الاستلام"),
        ],
    }
    return fields_map.get(flow_type, [])

async def show_edit_fields_menu(query, context, flow_type):
    """عرض قائمة الحقول القابلة للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        data = context.user_data.get("report_tmp", {})
        editable_fields = get_editable_fields_by_flow_type(flow_type)
        
        if not editable_fields:
            await query.edit_message_text(
                "⚠️ **لا توجد حقول قابلة للتعديل**\n\n"
                "يرجى استخدام زر '🔙 رجوع' للرجوع إلى الخطوات السابقة.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        text = "✏️ **تعديل التقرير**\n\n"
        text += "اختر الحقل الذي تريد تعديله:\n\n"
        
        keyboard = []
        for field_key, field_display in editable_fields:
            # الحصول على القيمة الحالية
            current_value = data.get(field_key, "غير محدد")
            if isinstance(current_value, datetime):
                current_value = current_value.strftime('%Y-%m-%d %H:%M')
            elif current_value and len(str(current_value)) > 30:
                current_value = str(current_value)[:27] + "..."
            
            button_text = f"{field_display}"
            if current_value and current_value != "غير محدد":
                button_text += f" ({str(current_value)[:20]})"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"edit_field:{flow_type}:{field_key}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"review:{flow_type}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ تم عرض قائمة الحقول القابلة للتعديل ({len(editable_fields)} حقل)")
        return f"EDIT_FIELDS_{flow_type.upper()}"
        
    except Exception as e:
        logger.error(f"❌ خطأ في show_edit_fields_menu: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ أثناء عرض قائمة التعديل**\n\n"
            "يرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def handle_edit_before_save(query, context, flow_type=None):
    """معالجة التعديل قبل الحفظ - عرض قائمة الحقول القابلة للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # إذا لم يتم تمرير flow_type، نحاول استخراجه من callback_data أو report_tmp
        if flow_type is None:
            if hasattr(query, 'data') and query.data:
                # استخراج من callback_data مثل "edit:admission"
                if query.data.startswith("edit:"):
                    flow_type = query.data.split(":")[1]
                else:
                    flow_type = context.user_data.get("report_tmp", {}).get("current_flow")
            else:
                flow_type = context.user_data.get("report_tmp", {}).get("current_flow")
        
        if not flow_type:
            logger.error("❌ لم يتم العثور على flow_type")
            await query.edit_message_text(
                "❌ **حدث خطأ**\n\n"
                "لم يتم العثور على نوع التدفق.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        logger.info(f"✏️ handle_edit_before_save: flow_type={flow_type}")
        
        # حفظ flow_type في report_tmp
        context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type
        
        # عرض قائمة الحقول القابلة للتعديل
        edit_state = await show_edit_fields_menu(query, context, flow_type)
        return edit_state
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_before_save: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ أثناء التعديل**\n\n"
            "يرجى المحاولة مرة أخرى أو استخدام زر '🔙 رجوع'.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

async def handle_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper لمعالجة callback edit:"""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("edit:"):
        flow_type = query.data.split(":")[1]
        # إذا كان المستخدم في EDIT_FIELD state، نعيده إلى confirm state
        current_state = context.user_data.get('_conversation_state')
        if current_state == "EDIT_FIELD":
            # إعادة عرض الملخص والعودة إلى confirm state
            await show_final_summary(query.message, context, flow_type)
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state
        else:
            # إذا لم يكن في EDIT_FIELD، نعرض قائمة الحقول
            return await handle_edit_before_save(query, context, flow_type)
    return ConversationHandler.END

async def handle_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper لمعالجة callback save:"""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("save:"):
        flow_type = query.data.split(":")[1]
        # إعادة عرض الملخص
        await show_final_summary(query.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    return ConversationHandler.END

async def handle_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار حقل للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        await query.answer()
        
        # استخراج flow_type و field_key
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        flow_type = parts[1]
        field_key = parts[2]
        
        logger.info(f"✏️ handle_edit_field_selection: flow_type={flow_type}, field_key={field_key}")
        
        data = context.user_data.get("report_tmp", {})
        current_value = data.get(field_key, "غير محدد")
        
        # حفظ معلومات التعديل
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        
        # عرض واجهة التعديل حسب نوع الحقل
        if field_key in ["report_date", "followup_date", "delivery_date"]:
            # للحقول التاريخية - عرض التقويم
            await query.edit_message_text(
                f"📅 **تعديل {get_field_display_name(field_key)}**\n\n"
                f"**القيمة الحالية:** {format_field_value(current_value)}\n\n"
                f"اختر التاريخ من التقويم:",
                parse_mode="Markdown"
            )
            # TODO: إضافة التقويم هنا
            # مؤقتاً: استخدام state عام للتعديل
            context.user_data['_conversation_state'] = "EDIT_FIELD"
            return "EDIT_FIELD"
        else:
            # للحقول النصية - طلب إدخال جديد
            await query.edit_message_text(
                f"✏️ **تعديل {get_field_display_name(field_key)}**\n\n"
                f"**القيمة الحالية:**\n{format_field_value(current_value)}\n\n"
                f"أرسل القيمة الجديدة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"edit:{flow_type}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                ]),
                parse_mode="Markdown"
            )
            # استخدام state عام للتعديل
            context.user_data['_conversation_state'] = "EDIT_FIELD"
            return "EDIT_FIELD"
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_field_selection: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ أثناء اختيار الحقل**\n\n"
            "يرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

def get_field_display_name(field_key):
    """الحصول على اسم الحقل للعرض"""
    names = {
        "report_date": "📅 التاريخ والوقت",
        "patient_name": "👤 اسم المريض",
        "hospital_name": "🏥 المستشفى",
        "department_name": "🏷️ القسم",
        "doctor_name": "👨‍⚕️ اسم الطبيب",
        "complaint": "💬 شكوى المريض",
        "diagnosis": "🔬 التشخيص",
        "decision": "📝 قرار الطبيب",
        "tests": "🧪 الفحوصات",
        "followup_date": "📅 موعد العودة",
        "followup_time": "⏰ وقت العودة",
        "followup_reason": "✍️ سبب العودة",
    }
    return names.get(field_key, field_key)

def format_field_value(value):
    """تنسيق قيمة الحقل للعرض"""
    if value is None or value == "":
        return "غير محدد"
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)

async def handle_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال النص بعد اختيار حقل للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        text = update.message.text.strip()
        field_key = context.user_data.get("edit_field_key")
        flow_type = context.user_data.get("edit_flow_type")
        
        if not field_key or not flow_type:
            logger.error("❌ لم يتم العثور على field_key أو flow_type")
            await update.message.reply_text(
                "❌ **حدث خطأ**\n\n"
                "لم يتم العثور على معلومات التعديل.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        logger.info(f"✏️ handle_edit_field_input: field_key={field_key}, flow_type={flow_type}, text={text[:50]}")
        
        # التحقق من صحة الإدخال
        if not text or len(text) < 1:
            await update.message.reply_text(
                "⚠️ **خطأ:** النص فارغ\n\n"
                f"يرجى إدخال {get_field_display_name(field_key)}:",
                parse_mode="Markdown"
            )
            return "EDIT_FIELD"
        
        # حفظ القيمة الجديدة
        data = context.user_data.get("report_tmp", {})
        data[field_key] = text
        
        # مسح معلومات التعديل
        context.user_data.pop("edit_field_key", None)
        context.user_data.pop("edit_flow_type", None)
        
        logger.info(f"✅ تم حفظ التعديل: {field_key} = {text[:50]}")
        
        # إعادة عرض الملخص
        await update.message.reply_text(
            f"✅ **تم حفظ التعديل**\n\n"
            f"**{get_field_display_name(field_key)}:**\n{text[:100]}",
            parse_mode="Markdown"
        )
        
        # إعادة عرض الملخص الكامل
        await show_final_summary(update.message, context, flow_type)
        
        # العودة إلى state التأكيد (سيظهر زر "مراجعة التقرير")
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_field_input: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ **حدث خطأ أثناء حفظ التعديل**\n\n"
            "يرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

# =============================
# عرض الملخص النهائي
# =============================

async def show_final_summary(message, context, flow_type):
    """عرض ملخص التقرير النهائي قبل الحفظ"""
    import logging
    logger = logging.getLogger(__name__)
    
    data = context.user_data.get("report_tmp", {})

    # بناء الملخص بناءً على نوع المسار
    report_date = data.get("report_date")
    if report_date and hasattr(report_date, 'strftime'):
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 
                   4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(report_date.weekday(), '')
        date_str = f"{report_date.strftime('%Y-%m-%d')} ({day_name}) {report_date.strftime('%H:%M')}"
    else:
        date_str = str(report_date) if report_date else 'غير محدد'

    summary = f"📋 **ملخص التقرير**\n\n"
    summary += f"📅 **التاريخ:** {date_str}\n"
    summary += f"👤 **المريض:** {data.get('patient_name', 'غير محدد')}\n"
    summary += f"🏥 **المستشفى:** {data.get('hospital_name', 'غير محدد')}\n"
    summary += f"🏷️ **القسم:** {data.get('department_name', 'غير محدد')}\n"
    summary += f"👨‍⚕️ **الطبيب:** {data.get('doctor_name', 'غير محدد')}\n\n"

    # نوع الإجراء
    action_names = {
        "new_consult": "استشارة جديدة",
        "followup": "متابعة في الرقود",
        "surgery_consult": "استشارة مع قرار عملية",
        "emergency": "طوارئ",
        "admission": "ترقيد",
        "operation": "عملية",
        "final_consult": "استشارة أخيرة",
        "discharge": "خروج من المستشفى",
        "rehab_physical": "علاج طبيعي",
        "rehab_device": "أجهزة تعويضية",
        "radiology": "أشعة وفحوصات"
    }
    
    # استخدام medical_action من data إذا كان موجوداً، وإلا استخدام flow_type
    medical_action_display = data.get("medical_action") or action_names.get(flow_type, 'غير محدد')

    summary += f"⚕️ **نوع الإجراء:** {medical_action_display}\n\n"

    # تفاصيل حسب نوع المسار
    if flow_type in ["new_consult", "followup", "emergency"]:
        summary += f"💬 **الشكوى:** {data.get('complaint', 'غير محدد')}\n"
        summary += f"🔬 **التشخيص:** {data.get('diagnosis', 'غير محدد')}\n"
        summary += f"📝 **قرار الطبيب:** {data.get('decision', 'غير محدد')}\n"

        if flow_type == "new_consult":
            summary += f"🔬 **الفحوصات المطلوبة:** {data.get('tests', 'لا يوجد')}\n"

        if flow_type == "emergency":
            summary += f"🏥 **وضع الحالة:** {data.get('status', 'غير محدد')}\n"

        # تاريخ العودة
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {followup_time}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"

    elif flow_type == "admission":
        summary += f"🛏️ **سبب الرقود:** {data.get('admission_reason', 'غير محدد')}\n"
        summary += f"🚪 **رقم الغرفة والطابق:** {data.get('room_number', 'لم يتم التحديد')}\n"
        summary += f"📝 **ملاحظات:** {data.get('notes', 'لا يوجد')}\n"
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
    elif flow_type == "operation":
        summary += f"⚕️ **تفاصيل العملية بالعربي:** {data.get('operation_details', 'غير محدد')}\n"
        summary += f"🔤 **اسم العملية بالإنجليزي:** {data.get('operation_name_en', 'غير محدد')}\n"
        summary += f"📝 **ملاحظات:** {data.get('notes', 'لا يوجد')}\n"
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {followup_time}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
    elif flow_type == "surgery_consult":
        summary += f"🔬 **التشخيص:** {data.get('diagnosis', 'غير محدد')}\n"
        summary += f"📝 **قرار الطبيب:** {data.get('decision', 'غير محدد')}\n"
        summary += f"🔤 **اسم العملية بالإنجليزي:** {data.get('operation_name_en', 'غير محدد')}\n"
        summary += f"📊 **نسبة نجاح العملية:** {data.get('success_rate', 'غير محدد')}\n"
        summary += f"💡 **نسبة الاستفادة من العملية:** {data.get('benefit_rate', 'غير محدد')}\n"
        summary += f"🔬 **الفحوصات المطلوبة:** {data.get('tests', 'لا يوجد')}\n"
        # التحقق من وجود نص تاريخ العودة أولاً
        followup_date_text = data.get('followup_date_text')
        if followup_date_text:
            summary += f"📅 **تاريخ العودة:** {followup_date_text}\n"
        else:
            followup_date = data.get('followup_date')
            if followup_date:
                if hasattr(followup_date, 'strftime'):
                    date_str = followup_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(followup_date)
                followup_time = data.get('followup_time', '')
                if followup_time:
                    summary += f"📅 **تاريخ العودة:** {date_str} الساعة {followup_time}\n"
                else:
                    summary += f"📅 **تاريخ العودة:** {date_str}\n"
            else:
                summary += f"📅 **تاريخ العودة:** لا يوجد\n"
        summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
    
    elif flow_type == "final_consult":
        summary += f"🔬 **التشخيص النهائي:** {data.get('diagnosis', 'غير محدد')}\n"
        summary += f"📝 **قرار الطبيب:** {data.get('decision', 'غير محدد')}\n"
        summary += f"💡 **التوصيات الطبية:** {data.get('recommendations', 'غير محدد')}\n"
    
    elif flow_type == "rehab_physical":
        summary += f"🏃 **تفاصيل جلسة العلاج الطبيعي:** {data.get('therapy_details', 'غير محدد')}\n"
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {followup_time}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
    elif flow_type == "rehab_device":
        summary += f"🦾 **اسم الجهاز والتفاصيل:** {data.get('device_details', 'غير محدد')}\n"
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {followup_time}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
    elif flow_type == "radiology":
        summary += f"🔬 **نوع الأشعة والفحوصات:** {data.get('radiology_type', 'غير محدد')}\n"
        delivery_date = data.get('radiology_delivery_date') or data.get('followup_date')
        if delivery_date:
            if hasattr(delivery_date, 'strftime'):
                date_str = delivery_date.strftime('%Y-%m-%d')
            else:
                date_str = str(delivery_date)
            summary += f"📅 **تاريخ تسليم النتائج:** {date_str}\n"
        else:
            summary += f"📅 **تاريخ تسليم النتائج:** غير محدد\n"
    
    elif flow_type == "discharge":
        discharge_type = data.get("discharge_type", "")
        if discharge_type == "admission":
            summary += f"📋 **ملخص الرقود:** {data.get('admission_summary', 'غير محدد')}\n"
        elif discharge_type == "operation":
            summary += f"⚕️ **تفاصيل العملية:** {data.get('operation_details', 'غير محدد')}\n"
            summary += f"🔤 **اسم العملية بالإنجليزي:** {data.get('operation_name_en', 'غير محدد')}\n"
        
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {followup_time}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"

    # إضافة معلومات المترجم
    summary += f"\n👤 **المترجم:** {data.get('translator_name', 'غير محدد')}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مراجعة التقرير", callback_data=f"review:{flow_type}")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        summary,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# =============================
# شاشة المراجعة قبل النشر
# =============================

async def show_review_screen(query, context, flow_type):
    """عرض شاشة المراجعة مع خيارات التعديل والنشر"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        data = context.user_data.get("report_tmp", {})
        
        # بناء رسالة المراجعة
        review_text = "📋 **مراجعة التقرير**\n\n"
        review_text += "يمكنك الآن:\n"
        review_text += "• ✏️ تعديل أي حقل في التقرير\n"
        review_text += "• 📤 نشر التقرير مباشرة\n"
        review_text += "• 🔙 الرجوع للملخص\n\n"
        review_text += "اختر الإجراء المطلوب:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ تعديل الحقول", callback_data=f"edit:{flow_type}")],
            [InlineKeyboardButton("📤 نشر التقرير", callback_data=f"publish:{flow_type}")],
            [InlineKeyboardButton("🔙 رجوع للملخص", callback_data=f"back_to_summary:{flow_type}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        
        await query.edit_message_text(
            review_text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ تم عرض شاشة المراجعة لـ flow_type: {flow_type}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في show_review_screen: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ أثناء عرض شاشة المراجعة**\n\n"
            "يرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )

# =============================
# معالجة التأكيد والحفظ
# =============================

async def handle_final_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التأكيد النهائي"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    if not query:
        logger.error("❌ handle_final_confirm: No query found")
        return ConversationHandler.END
    
    await query.answer()
    
    logger.info("=" * 80)
    logger.info(f"📋 CALLBACK RECEIVED: {query.data}")
    logger.info(f"💾 Current state: {context.user_data.get('_conversation_state', 'NOT SET')}")
    logger.info(f"💾 User data keys: {list(context.user_data.keys())}")
    logger.info(f"💾 Report tmp keys: {list(context.user_data.get('report_tmp', {}).keys())}")
    logger.info("=" * 80)

    parts = query.data.split(":")
    action = parts[0]
    flow_type = parts[1] if len(parts) > 1 else "new_consult"
    
    # التحقق من flow_type من report_tmp إذا كان flow_type غير صحيح
    data = context.user_data.get("report_tmp", {})
    current_flow = data.get("current_flow", "")
    if flow_type not in ["new_consult", "followup", "emergency", "admission", "surgery_consult", 
                         "operation", "final_consult", "discharge", "rehab_physical", "rehab_device", "radiology"]:
        if current_flow:
            flow_type = current_flow
            logger.info(f"💾 Using current_flow from report_tmp: {flow_type}")
    
    logger.info(f"💾 Action: {action}, Flow type: {flow_type}")
    logger.info(f"💾 Current flow from report_tmp: {current_flow}")

    if action == "review":
        logger.info(f"📋 Review button clicked for flow_type: {flow_type}")
        # عرض شاشة المراجعة
        await show_review_screen(query, context, flow_type)
        return get_confirm_state(flow_type)
    elif action == "back_to_summary":
        logger.info(f"🔙 Back to summary clicked for flow_type: {flow_type}")
        # إعادة عرض الملخص
        await show_final_summary(query.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    elif action == "publish":
        logger.info(f"💾 Starting publish process for flow_type: {flow_type}")
        try:
            await save_report_to_database(query, context, flow_type)
            logger.info(f"Publish completed successfully for flow_type: {flow_type}")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"❌ Error in save_report_to_database: {e}", exc_info=True)
            await query.answer(f"خطأ في النشر: {str(e)[:50]}", show_alert=True)
            return get_confirm_state(flow_type)
    elif action == "save":
        # للتوافق مع النظام القديم - يعامل كـ review
        logger.info(f"📋 Save button clicked (treating as review) for flow_type: {flow_type}")
        await show_review_screen(query, context, flow_type)
        return get_confirm_state(flow_type)
    elif action == "edit":
        logger.info(f"✏️ Edit button clicked for flow_type: {flow_type}")
        # إعادة المستخدم إلى الخطوة الأولى من التدفق الحالي
        await handle_edit_before_save(query, context, flow_type)

# =============================
# حفظ التقرير في قاعدة البيانات
# =============================

async def save_report_to_database(query, context, flow_type):
    """حفظ التقرير في قاعدة البيانات"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("💾 save_report_to_database CALLED")
    logger.info(f"💾 Flow type: {flow_type}")
    
    data = context.user_data.get("report_tmp", {})
    logger.info(f"💾 Report tmp data keys: {list(data.keys())}")
    logger.info(f"💾 Report tmp data: {data}")
    logger.info(f"💾 Department name in data: {data.get('department_name', 'NOT FOUND')}")
    logger.info(f"💾 Hospital name in data: {data.get('hospital_name', 'NOT FOUND')}")
    logger.info(f"💾 Patient name in data: {data.get('patient_name', 'NOT FOUND')}")
    logger.info(f"💾 Doctor name in data: {data.get('doctor_name', 'NOT FOUND')}")
    logger.info(f"💾 Current flow in data: {data.get('current_flow', 'NOT FOUND')}")
    logger.info(f"💾 Flow type parameter: {flow_type}")
    
    # التحقق من flow_type من report_tmp إذا كان flow_type غير صحيح
    current_flow = data.get("current_flow", "")
    valid_flow_types = ["new_consult", "followup", "emergency", "admission", "surgery_consult", 
                         "operation", "final_consult", "discharge", "rehab_physical", "rehab_device", "radiology"]
    if flow_type not in valid_flow_types:
        if current_flow and current_flow in valid_flow_types:
            flow_type = current_flow
            logger.info(f"💾 Using current_flow from report_tmp: {flow_type}")
        else:
            logger.warning(f"💾 ⚠️ Invalid flow_type '{flow_type}' and current_flow '{current_flow}', defaulting to 'new_consult'")
            flow_type = "new_consult"
    
    logger.info(f"💾 Final flow_type to use: {flow_type}")
    logger.info("=" * 80)

    session = None
    try:
        session = SessionLocal()

        # حفظ المريض
        patient_name = data.get("patient_name", "غير محدد")
        patient = session.query(Patient).filter_by(full_name=patient_name).first()
        if not patient:
            patient = Patient(full_name=patient_name)
            session.add(patient)
            session.flush()

        # حفظ المستشفى
        hospital_name = data.get("hospital_name", "غير محدد")
        hospital = session.query(Hospital).filter_by(name=hospital_name).first()
        if not hospital:
            hospital = Hospital(name=hospital_name)
            session.add(hospital)
            session.flush()

        # حفظ القسم
        dept_name = data.get("department_name")
        logger.info(f"💾 Department name from data: {dept_name}")
        logger.info(f"💾 All data keys: {list(data.keys())}")
        logger.info(f"💾 Full data content: {data}")
        department = None
        dept_name_for_display = dept_name  # حفظ الاسم الكامل للعرض
        if dept_name:
            # تنظيف اسم القسم (إزالة أي نص إضافي مثل "| Radiology") للحفظ في قاعدة البيانات
            dept_name_clean = dept_name.split("|")[0].strip()
            logger.info(f"💾 Cleaned department name: {dept_name_clean}")
            department = session.query(Department).filter_by(name=dept_name_clean).first()
            if not department:
                logger.info(f"💾 Creating new department: {dept_name_clean}")
                department = Department(name=dept_name_clean)
                session.add(department)
                session.flush()
            else:
                logger.info(f"💾 Found existing department: {department.name} (ID: {department.id})")
        else:
            logger.warning("💾 ⚠️ No department_name in data!")
            logger.warning(f"💾 Available keys in data: {list(data.keys())}")

        # حفظ الطبيب
        doctor_name = data.get("doctor_name")
        doctor = None
        if doctor_name:
            doctor = session.query(Doctor).filter_by(full_name=doctor_name).first()
            if not doctor:
                doctor = Doctor(full_name=doctor_name)
                session.add(doctor)
                session.flush()

        # تحديد نوع الإجراء
        action_names = {
            "new_consult": "استشارة جديدة",
            "followup": "متابعة في الرقود",  # سيتم استخدام medical_action من data إذا كان مختلفاً
            "surgery_consult": "استشارة مع قرار عملية",
            "emergency": "طوارئ",
            "admission": "ترقيد",
            "operation": "عملية",
            "final_consult": "استشارة أخيرة",
            "discharge": "خروج من المستشفى",
            "rehab_physical": "علاج طبيعي",
            "rehab_device": "أجهزة تعويضية",
            "radiology": "أشعة وفحوصات"
        }
        
        # استخدام medical_action من data إذا كان موجوداً، وإلا استخدام flow_type
        medical_action_from_data = data.get("medical_action")
        current_flow_from_data = data.get("current_flow")
        
        logger.info("=" * 80)
        logger.info("save_report_to_database - Medical Action Check:")
        logger.info(f"flow_type parameter: {flow_type}")
        logger.info(f"data.get('medical_action'): {medical_action_from_data}")
        logger.info(f"data.get('current_flow'): {current_flow_from_data}")
        logger.info(f"action_names.get(flow_type): {action_names.get(flow_type)}")
        logger.info("=" * 80)
        
        # استخدام medical_action من data إذا كان موجوداً
        final_medical_action = medical_action_from_data or action_names.get(flow_type, "غير محدد")
        
        logger.info(f"Final medical_action to save: {repr(final_medical_action)}")

        # بناء نص التقرير بناءً على نوع المسار
        complaint_text = ""
        decision_text = ""

        if flow_type == "operation":
            operation_details = data.get("operation_details", "")
            operation_name = data.get("operation_name_en", "")
            notes = data.get("notes", "لا يوجد")
            # لا يوجد شكوى للمريض وقرار الطبيب في نوع الإجراء "عملية"
            complaint_text = ""
            decision_text = f"تفاصيل العملية: {operation_details}\n\nاسم العملية بالإنجليزي: {operation_name}\n\nملاحظات: {notes}"
        elif flow_type == "surgery_consult":
            diagnosis = data.get("diagnosis", "")
            decision = data.get("decision", "")
            operation_name = data.get("operation_name_en", "")
            success_rate = data.get("success_rate", "")
            benefit_rate = data.get("benefit_rate", "")
            tests = data.get("tests", "لا يوجد")
            # لا يوجد شكوى للمريض في نوع الإجراء "استشارة مع قرار عملية"
            complaint_text = ""
            # بناء decision_text مع تضمين جميع الحقول
            decision_text = f"التشخيص: {diagnosis}\n\nقرار الطبيب: {decision}"
            if operation_name:
                decision_text += f"\n\nاسم العملية بالإنجليزي: {operation_name}"
            if success_rate:
                decision_text += f"\n\nنسبة نجاح العملية: {success_rate}"
            if benefit_rate:
                decision_text += f"\n\nنسبة الاستفادة من العملية: {benefit_rate}"
            if tests and tests != "لا يوجد":
                decision_text += f"\n\nالفحوصات المطلوبة: {tests}"
            # إضافة نص تاريخ العودة إذا كان موجوداً
            followup_date_text = data.get("followup_date_text")
            if followup_date_text:
                decision_text += f"\n\nتاريخ العودة: {followup_date_text}"
        elif flow_type == "final_consult":
            diagnosis = data.get("diagnosis", "")
            decision = data.get("decision", "")
            recommendations = data.get("recommendations", "")
            complaint_text = ""
            decision_text = f"التشخيص النهائي: {diagnosis}\n\nقرار الطبيب: {decision}\n\nالتوصيات الطبية: {recommendations}"
        elif flow_type == "admission":
            admission_reason = data.get('admission_reason', '')
            room = data.get("room_number", "لم يتم التحديد")
            notes = data.get("notes", "لا يوجد")
            # لا يوجد شكوى للمريض في نوع الإجراء "ترقيد"
            complaint_text = ""
            decision_text = f"سبب الرقود: {admission_reason}\n\nرقم الغرفة والطابق: {room}\n\nملاحظات: {notes}"
        elif flow_type == "discharge":
            discharge_type = data.get("discharge_type", "")
            if discharge_type == "admission":
                summary = data.get("admission_summary", "")
                # لا يوجد شكوى للمريض في نوع الإجراء "خروج بعد رقود"
                complaint_text = ""
                decision_text = f"ملخص الرقود: {summary}"
            else:
                operation_details = data.get("operation_details", "")
                operation_name = data.get("operation_name_en", "")
                # لا يوجد شكوى للمريض في نوع الإجراء "خروج بعد عملية"
                complaint_text = ""
                decision_text = f"تفاصيل العملية: {operation_details}\n\nاسم العملية بالإنجليزي: {operation_name}"
        elif flow_type == "rehab_physical":
            therapy_details = data.get("therapy_details", "")
            # لا يوجد شكوى للمريض في نوع الإجراء "علاج طبيعي"
            complaint_text = ""
            decision_text = f"تفاصيل الجلسة: {therapy_details}"
        elif flow_type == "rehab_device":
            device_details = data.get("device_details", "")
            # لا يوجد شكوى للمريض في نوع الإجراء "أجهزة تعويضية"
            complaint_text = ""
            decision_text = f"تفاصيل الجهاز: {device_details}"
        elif flow_type == "radiology":
            radiology_type = data.get("radiology_type", "")
            # لا يوجد شكوى للمريض في نوع الإجراء "أشعة وفحوصات"
            complaint_text = ""
            decision_text = f"نوع الأشعة والفحوصات: {radiology_type}"
        elif flow_type in ["new_consult", "followup", "emergency"]:
            complaint_text = data.get("complaint", "")
            diagnosis = data.get("diagnosis", "")
            decision = data.get("decision", "")
            decision_text = f"التشخيص: {diagnosis}\n\nقرار الطبيب: {decision}"
            
            if flow_type == "new_consult":
                tests = data.get("tests", "لا يوجد")
                decision_text += f"\n\nالفحوصات المطلوبة: {tests}"
            elif flow_type == "emergency":
                status = data.get("status", "")
                decision_text += f"\n\nوضع الحالة: {status}"

        # التحقق من وضع التعديل
        is_edit_mode = data.get("is_edit_mode", False)
        edit_report_id = data.get("edit_report_id")
        
        if is_edit_mode and edit_report_id:
            # تحديث التقرير الموجود
            logger.info(f"✏️ Updating existing report #{edit_report_id}")
            existing_report = session.query(Report).filter_by(id=edit_report_id).first()
            
            if not existing_report:
                logger.error(f"❌ Report #{edit_report_id} not found for update")
                await query.edit_message_text(
                    "❌ **خطأ:** لم يتم العثور على التقرير للتحديث",
                    parse_mode="Markdown"
                )
                session.close()
                return
            
            # تحديث الحقول
            existing_report.patient_id = patient.id
            existing_report.hospital_id = hospital.id
            existing_report.department_id = department.id if department else None
            existing_report.doctor_id = doctor.id if doctor else None
            existing_report.complaint_text = complaint_text
            existing_report.doctor_decision = decision_text
            existing_report.medical_action = final_medical_action
            existing_report.followup_date = data.get("followup_date")
            existing_report.followup_reason = data.get("followup_reason", "لا يوجد")
            existing_report.report_date = data.get("report_date", datetime.now())
            
            session.commit()
            session.refresh(existing_report)
            
            report_id = existing_report.id
            logger.info(f"✅ Report #{report_id} updated successfully")
        else:
            # إنشاء تقرير جديد
            new_report = Report(
                patient_id=patient.id,
                hospital_id=hospital.id,
                department_id=department.id if department else None,
                doctor_id=doctor.id if doctor else None,
                translator_id=data.get("translator_id"),
                complaint_text=complaint_text,
                doctor_decision=decision_text,
                medical_action=final_medical_action,
                followup_date=data.get("followup_date"),
                followup_reason=data.get("followup_reason", "لا يوجد"),
                report_date=data.get("report_date", datetime.now()),
                created_at=datetime.now()
            )

            session.add(new_report)
            session.commit()
            session.refresh(new_report)

            report_id = new_report.id
            logger.info(f"✅ New report #{report_id} created successfully")

        # الحصول على اسم المترجم و ID
        translator_name = "غير محدد"
        translator_id = data.get("translator_id")
        if translator_id:
            translator = session.query(Translator).filter_by(id=translator_id).first()
            if translator:
                translator_name = translator.full_name

        # الحصول على اسم القسم للعرض (استخدام الاسم الكامل من data)
        # نستخدم dept_name_for_display (الاسم الكامل) للعرض في البث
        final_dept_name = dept_name_for_display if dept_name_for_display else 'غير محدد'
        if not final_dept_name or final_dept_name == 'غير محدد':
            # إذا لم يكن موجوداً، نستخدم department.name كبديل
            if department:
                final_dept_name = department.name
                logger.info(f"💾 Using department.name as fallback: {final_dept_name}")
            else:
                logger.warning("💾 ⚠️ No department found, using default 'غير محدد'")
                logger.warning(f"💾 Department object: {department}")
                logger.warning(f"💾 dept_name_for_display: {dept_name_for_display}")
                logger.warning(f"💾 All data keys: {list(data.keys())}")
        else:
            logger.info(f"💾 Using dept_name_for_display: {final_dept_name}")

        session.close()

        # 📢 إرسال التقرير للمجموعة فقط

        try:
            from services.broadcast_service import broadcast_new_report

            # تجهيز بيانات البث
            followup_display = 'لا يوجد'
            if data.get('followup_date'):
                followup_display = data['followup_date'].strftime('%Y-%m-%d')
                if data.get('followup_time'):
                    followup_display += f" الساعة {data['followup_time']}"

            broadcast_data = {
                'report_date': data.get('report_date', datetime.now()).strftime('%Y-%m-%d %H:%M'),
                'patient_name': patient_name,
                'hospital_name': hospital_name,
                'department_name': final_dept_name,
                'doctor_name': doctor_name or 'لم يتم التحديد',
                'medical_action': final_medical_action,  # استخدام final_medical_action بدلاً من action_names.get(flow_type)
                'complaint_text': complaint_text,
                'doctor_decision': decision_text,
                'followup_date': followup_display,
                'followup_reason': data.get('followup_reason', 'لا يوجد'),
                'translator_name': translator_name,
                'translator_id': translator_id  # إضافة translator_id للتنبيهات
            }
            
            # إضافة الحقول الفردية لـ surgery_consult لعرضها بشكل منفصل
            if flow_type == "surgery_consult":
                broadcast_data['diagnosis'] = data.get('diagnosis', '')
                broadcast_data['decision'] = data.get('decision', '')
                broadcast_data['operation_name_en'] = data.get('operation_name_en', '')
                broadcast_data['success_rate'] = data.get('success_rate', '')
                broadcast_data['benefit_rate'] = data.get('benefit_rate', '')
                broadcast_data['tests'] = data.get('tests', 'لا يوجد')

            # 📢 إرسال التقرير للمجموعة فقط (يتم تلقائياً في broadcast_new_report)
            await broadcast_new_report(context.bot, broadcast_data)
            logger.info(f"✅ تم إرسال التقرير #{report_id} للمجموعة")
        except Exception as e:
            logger.error(f"❌ خطأ في إرسال التقرير: {e}", exc_info=True)

        # الرد للمستخدم
        if is_edit_mode and edit_report_id:
            success_message = (
                f"✅ **تم تحديث التقرير بنجاح!**\n\n"
                f"📋 رقم التقرير: {report_id}\n"
                f"👤 المريض: {patient_name}\n"
                f"⚕️ نوع الإجراء: {action_names.get(flow_type, 'غير محدد')}\n"
            )
        else:
            success_message = (
                f"✅ **تم حفظ التقرير بنجاح!**\n\n"
                f"📋 رقم التقرير: {report_id}\n"
                f"👤 المريض: {patient_name}\n"
                f"⚕️ نوع الإجراء: {action_names.get(flow_type, 'غير محدد')}\n"
            )
        
        # إضافة اسم العملية بالإنجليزية لمسار "استشارة مع قرار عملية"
        if flow_type == "surgery_consult" and data.get("operation_name_en"):
            success_message += f"🏥 **اسم العملية:** {data.get('operation_name_en')}\n"
        
        if is_edit_mode and edit_report_id:
            success_message += f"\nتم تحديث التقرير وإرساله للمجموعة."
        else:
            success_message += f"\nتم إرسال التقرير للمجموعة."
        
        try:
            await query.edit_message_text(
                success_message,
                parse_mode="Markdown"
            )
        except Exception as msg_error:
            logger.error(f"❌ خطأ في تعديل رسالة النجاح: {msg_error}")
            # محاولة بديلة: إرسال رسالة جديدة
            try:
                await query.message.reply_text(
                    success_message,
                    parse_mode="Markdown"
                )
            except Exception as fallback_error:
                logger.error(f"❌ فشل إرسال رسالة بديلة: {fallback_error}")

        # مسح البيانات المؤقتة (لكن نحتفظ بها في وضع التعديل للرجوع)
        if not is_edit_mode:
            context.user_data.pop("report_tmp", None)
        else:
            # في وضع التعديل، نحتفظ بالبيانات لكن نزيل علامة التعديل
            context.user_data.get("report_tmp", {}).pop("is_edit_mode", None)
            context.user_data.get("report_tmp", {}).pop("edit_report_id", None)

        logger.info(f"تم حفظ التقرير #{report_id} - نوع: {flow_type}")


    except Exception as e:
        logger.error(f"❌ خطأ في حفظ التقرير: {e}", exc_info=True)

        # تنظيف الجلسة بشكل آمن
        if session:
            try:
                session.rollback()
            except Exception as rollback_error:
                logger.error(f"❌ خطأ في rollback: {rollback_error}")
            try:
                session.close()
            except Exception as close_error:
                logger.error(f"❌ خطأ في إغلاق الجلسة: {close_error}")
            session = None

        await query.edit_message_text(
            f"❌ **حدث خطأ أثناء الحفظ**\n\n"
            f"الخطأ: {str(e)}\n\n"
            f"يرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )

# =============================
# =============================

async def debug_unhandled_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug handler to catch unhandled messages in ConversationHandler"""
    import sys
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    
    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    report_tmp = context.user_data.get("report_tmp", {})
    
    print("\n" + "=" * 80)
    print("=" * 80)
    print("DEBUG_UNHANDLED_MESSAGE: Unhandled message caught!")
    print("=" * 80)
    print(f"DEBUG: Update ID = {update.update_id}")
    print(f"DEBUG: User ID = {update.effective_user.id if update.effective_user else 'N/A'}")
    print(f"DEBUG: Current state = {current_state}")
    print(f"DEBUG: State type = {type(current_state)}")
    try:
        msg_text = update.message.text if update.message else 'N/A'
        print(f"DEBUG: Message text = '{msg_text[:50] if isinstance(msg_text, str) else msg_text}'")
    except UnicodeEncodeError:
        print(f"DEBUG: Message text = [Unicode text - see logs]")
    print(f"DEBUG: User data keys = {list(context.user_data.keys())}")
    print(f"DEBUG: report_tmp keys = {list(report_tmp.keys())}")
    print(f"DEBUG: report_tmp content = {report_tmp}")
    print("=" * 80)
    traceback.print_stack()
    print("=" * 80)
    sys.stdout.flush()
    
    logger.warning("DEBUG_UNHANDLED_MESSAGE: Unhandled message in ConversationHandler")
    logger.warning(f"DEBUG: State = {current_state}")
    logger.warning(f"DEBUG: Message = {update.message.text if update.message else 'N/A'}")
    logger.warning(f"DEBUG: report_tmp keys = {list(report_tmp.keys())}")
    
    # محاولة تحديد الحالة بناءً على البيانات المتاحة
    if not update.message:
        return None
    
    # التحقق من البيانات المتاحة لتحديد الحالة
    medical_action = report_tmp.get("medical_action")
    current_flow = report_tmp.get("current_flow")
    complaint = report_tmp.get("complaint")
    diagnosis = report_tmp.get("diagnosis")
    decision = report_tmp.get("decision")
    tests = report_tmp.get("tests")
    followup_reason = report_tmp.get("followup_reason")
    translator_name = report_tmp.get("translator_name")
    
    logger.debug(f"DEBUG: medical_action = {repr(medical_action)}")
    logger.debug(f"DEBUG: current_flow = {repr(current_flow)}")
    logger.debug(f"DEBUG: complaint = {repr(complaint)}")
    logger.debug(f"DEBUG: diagnosis = {repr(diagnosis)}")
    logger.debug(f"DEBUG: decision = {repr(decision)}")
    print(f"DEBUG: tests = {tests}")
    print(f"DEBUG: followup_reason = {followup_reason}")
    print(f"DEBUG: translator_name = {translator_name}")
    sys.stdout.flush()
    
    # محاولة تحديد الحالة بناءً على البيانات
    # استشارة جديدة
    if medical_action == "استشارة جديدة" or current_flow == "new_consult":
        if not complaint:
            print("DEBUG: No complaint found, routing to NEW_CONSULT_COMPLAINT")
            sys.stdout.flush()
            try:
                return await handle_new_consult_complaint(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle NEW_CONSULT_COMPLAINT: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif not diagnosis:
            print("DEBUG: No diagnosis found, routing to NEW_CONSULT_DIAGNOSIS")
            sys.stdout.flush()
            try:
                return await handle_new_consult_diagnosis(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle NEW_CONSULT_DIAGNOSIS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif not decision:
            print("DEBUG: No decision found, routing to NEW_CONSULT_DECISION")
            sys.stdout.flush()
            try:
                return await handle_new_consult_decision(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle NEW_CONSULT_DECISION: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif not tests:
            print("DEBUG: No tests found, routing to NEW_CONSULT_TESTS")
            sys.stdout.flush()
            try:
                return await handle_new_consult_tests(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle NEW_CONSULT_TESTS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif not followup_reason:
            print("DEBUG: No followup_reason found, routing to NEW_CONSULT_FOLLOWUP_REASON")
            sys.stdout.flush()
            try:
                return await handle_new_consult_followup_reason(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle NEW_CONSULT_FOLLOWUP_REASON: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif not translator_name:
            print("DEBUG: No translator_name found, routing to NEW_CONSULT_TRANSLATOR")
            sys.stdout.flush()
            try:
                await ask_translator_name(update.message, context, "new_consult")
                return NEW_CONSULT_TRANSLATOR
            except Exception as e:
                print(f"ERROR: Failed to handle NEW_CONSULT_TRANSLATOR: {e}")
                traceback.print_exc()
                sys.stdout.flush()
    # استشارة مع قرار عملية
    elif medical_action == "استشارة مع قرار عملية" or current_flow == "surgery_consult":
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        name_en = report_tmp.get("name_en")
        success_rate = report_tmp.get("success_rate")
        benefit_rate = report_tmp.get("benefit_rate")
        tests = report_tmp.get("tests")
        followup_reason = report_tmp.get("followup_reason")
        
        logger.debug(f"DEBUG: surgery_consult flow - diagnosis={repr(diagnosis)}, decision={repr(decision)}, name_en={repr(name_en)}, success_rate={repr(success_rate)}, benefit_rate={repr(benefit_rate)}, tests={repr(tests)}, followup_reason={repr(followup_reason)}")
        sys.stdout.flush()
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == SURGERY_CONSULT_DIAGNOSIS or not diagnosis:
            print("DEBUG: Routing to SURGERY_CONSULT_DIAGNOSIS")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_diagnosis(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_DIAGNOSIS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == SURGERY_CONSULT_DECISION or not decision:
            print("DEBUG: Routing to SURGERY_CONSULT_DECISION")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_decision(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_DECISION: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == SURGERY_CONSULT_NAME_EN or not name_en:
            print("DEBUG: Routing to SURGERY_CONSULT_NAME_EN")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_name_en(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_NAME_EN: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == SURGERY_CONSULT_SUCCESS_RATE or not success_rate:
            print("DEBUG: Routing to SURGERY_CONSULT_SUCCESS_RATE")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_success_rate(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_SUCCESS_RATE: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == SURGERY_CONSULT_BENEFIT_RATE or not report_tmp.get("benefit_rate"):
            print("DEBUG: Routing to SURGERY_CONSULT_BENEFIT_RATE")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_benefit_rate(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_BENEFIT_RATE: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == SURGERY_CONSULT_TESTS or not tests:
            print("DEBUG: Routing to SURGERY_CONSULT_TESTS")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_tests(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_TESTS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == SURGERY_CONSULT_FOLLOWUP_REASON or not followup_reason:
            print("DEBUG: Routing to SURGERY_CONSULT_FOLLOWUP_REASON")
            sys.stdout.flush()
            try:
                return await handle_surgery_consult_followup_reason(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle SURGERY_CONSULT_FOLLOWUP_REASON: {e}")
                traceback.print_exc()
                sys.stdout.flush()
    # استشارة أخيرة
    elif medical_action == "استشارة أخيرة" or current_flow == "final_consult":
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        recommendations = report_tmp.get("recommendations")
        
        logger.debug(f"DEBUG: final_consult flow - diagnosis={repr(diagnosis)}, decision={repr(decision)}, recommendations={repr(recommendations)}")
        sys.stdout.flush()
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == FINAL_CONSULT_DIAGNOSIS or not diagnosis:
            print("DEBUG: Routing to FINAL_CONSULT_DIAGNOSIS")
            sys.stdout.flush()
            try:
                return await handle_final_consult_diagnosis(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FINAL_CONSULT_DIAGNOSIS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == FINAL_CONSULT_DECISION or not decision:
            print("DEBUG: Routing to FINAL_CONSULT_DECISION")
            sys.stdout.flush()
            try:
                return await handle_final_consult_decision(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FINAL_CONSULT_DECISION: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == FINAL_CONSULT_RECOMMENDATIONS or not recommendations:
            print("DEBUG: Routing to FINAL_CONSULT_RECOMMENDATIONS")
            sys.stdout.flush()
            try:
                return await handle_final_consult_recommendations(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FINAL_CONSULT_RECOMMENDATIONS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
    # طوارئ
    elif medical_action == "طوارئ" or current_flow == "emergency":
        complaint = report_tmp.get("complaint")
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        status = report_tmp.get("status")
        followup_reason = report_tmp.get("followup_reason")
        
        logger.debug(f"DEBUG: emergency flow - complaint={repr(complaint)}, diagnosis={repr(diagnosis)}, decision={repr(decision)}, status={repr(status)}, followup_reason={repr(followup_reason)}")
        sys.stdout.flush()
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == EMERGENCY_COMPLAINT or not complaint:
            print("DEBUG: Routing to EMERGENCY_COMPLAINT")
            sys.stdout.flush()
            try:
                return await handle_emergency_complaint(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle EMERGENCY_COMPLAINT: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == EMERGENCY_DIAGNOSIS or not diagnosis:
            print("DEBUG: Routing to EMERGENCY_DIAGNOSIS")
            sys.stdout.flush()
            try:
                return await handle_emergency_diagnosis(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle EMERGENCY_DIAGNOSIS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == EMERGENCY_DECISION or not decision:
            print("DEBUG: Routing to EMERGENCY_DECISION")
            sys.stdout.flush()
            try:
                return await handle_emergency_decision(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle EMERGENCY_DECISION: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == EMERGENCY_STATUS or not status:
            print("DEBUG: Routing to EMERGENCY_STATUS")
            sys.stdout.flush()
            try:
                return await handle_emergency_status_text(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle EMERGENCY_STATUS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == EMERGENCY_REASON or not followup_reason:
            print("DEBUG: Routing to EMERGENCY_REASON")
            sys.stdout.flush()
            try:
                return await handle_emergency_reason(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle EMERGENCY_REASON: {e}")
                traceback.print_exc()
                sys.stdout.flush()
    # متابعة في الرقود
    elif medical_action == "متابعة في الرقود" or current_flow == "followup":
        complaint = report_tmp.get("complaint")
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        followup_reason = report_tmp.get("followup_reason")
        
        logger.debug(f"DEBUG: followup flow - complaint={repr(complaint)}, diagnosis={repr(diagnosis)}, decision={repr(decision)}, followup_reason={repr(followup_reason)}")
        sys.stdout.flush()
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == FOLLOWUP_COMPLAINT or not complaint:
            print("DEBUG: Routing to FOLLOWUP_COMPLAINT")
            sys.stdout.flush()
            try:
                return await handle_followup_complaint(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FOLLOWUP_COMPLAINT: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == FOLLOWUP_DIAGNOSIS or not diagnosis:
            print("DEBUG: Routing to FOLLOWUP_DIAGNOSIS")
            sys.stdout.flush()
            try:
                return await handle_followup_diagnosis(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FOLLOWUP_DIAGNOSIS: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == FOLLOWUP_DECISION or not decision:
            print("DEBUG: Routing to FOLLOWUP_DECISION")
            sys.stdout.flush()
            try:
                return await handle_followup_decision(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FOLLOWUP_DECISION: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == FOLLOWUP_REASON or not followup_reason:
            print("DEBUG: Routing to FOLLOWUP_REASON")
            sys.stdout.flush()
            try:
                return await handle_followup_reason(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle FOLLOWUP_REASON: {e}")
                traceback.print_exc()
                sys.stdout.flush()
    # عملية
    elif medical_action == "عملية" or current_flow == "operation":
        operation_details = report_tmp.get("operation_details")
        operation_name_en = report_tmp.get("operation_name_en")
        notes = report_tmp.get("notes")
        followup_reason = report_tmp.get("followup_reason")
        
        print(f"DEBUG: operation flow - operation_details={operation_details}, operation_name_en={operation_name_en}, notes={notes}, followup_reason={followup_reason}")
        sys.stdout.flush()
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == OPERATION_DETAILS_AR or not operation_details:
            print("DEBUG: Routing to OPERATION_DETAILS_AR")
            sys.stdout.flush()
            try:
                return await handle_operation_details_ar(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle OPERATION_DETAILS_AR: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == OPERATION_NAME_EN or not operation_name_en:
            print("DEBUG: Routing to OPERATION_NAME_EN")
            sys.stdout.flush()
            try:
                return await handle_operation_name_en(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle OPERATION_NAME_EN: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == OPERATION_NOTES or not notes:
            print("DEBUG: Routing to OPERATION_NOTES")
            sys.stdout.flush()
            try:
                return await handle_operation_notes(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle OPERATION_NOTES: {e}")
                traceback.print_exc()
                sys.stdout.flush()
        elif current_state == OPERATION_FOLLOWUP_REASON or not followup_reason:
            print("DEBUG: Routing to OPERATION_FOLLOWUP_REASON")
            sys.stdout.flush()
            try:
                return await handle_operation_followup_reason(update, context)
            except Exception as e:
                print(f"ERROR: Failed to handle OPERATION_FOLLOWUP_REASON: {e}")
                traceback.print_exc()
                sys.stdout.flush()
    
    # Try to reply to user
    if update.message:
        try:
            await update.message.reply_text(
                f"لم يتم التعرف على هذه الرسالة.\n"
                f"الحالة الحالية: {current_state}\n"
                f"يرجى المحاولة مرة أخرى أو استخدام /cancel للإلغاء."
            )
        except Exception as e:
            error_msg = f"ERROR: Failed to send debug message: {e}"
            print(error_msg)
            sys.stdout.flush()
    
    # Return current state to stay in conversation
    print(f"DEBUG: Returning current state: {current_state}")
    sys.stdout.flush()
    return current_state if current_state != 'NOT SET' else None

# =============================
# تسجيل الـ ConversationHandler
# =============================

def ensure_default_translators():
    """إضافة المترجمين الافتراضيين إلى قاعدة البيانات إذا لم يكونوا موجودين"""
    translator_names = [
        "مصطفى",
        "واصل",
        "نجم الدين",
        "محمد علي",
        "سعيد",
        "مهدي",
        "صبري",
        "عزي",
        "معتز",
        "ادريس",
        "هاشم",
        "ادم",
        "زيد",
        "عصام",
        "عزالدين",
        "حسن",
        "زين العابدين",
        "عبدالسلام"
    ]
    
    try:
        with SessionLocal() as s:
            added_count = 0
            for name in translator_names:
                # التحقق إذا كان المترجم موجوداً بالفعل
                existing = s.query(Translator).filter(
                    Translator.full_name.ilike(name)
                ).first()
                
                if not existing:
                    # إضافة المترجم الجديد
                    new_translator = Translator(
                        full_name=name,
                        is_approved=True,
                        is_active=True,
                        role="translator",
                        status="approved"
                    )
                    s.add(new_translator)
                    added_count += 1
                    logger.info(f"✅ Added default translator: {name}")
            
            if added_count > 0:
                s.commit()
                logger.info(f"✅ Added {added_count} default translators to database")
            else:
                logger.info("ℹ️ All default translators already exist in database")
    except Exception as e:
        logger.error(f"❌ Error adding default translators: {e}", exc_info=True)


def register(app):
    """تسجيل جميع handlers للمرحلة 1"""
    
    # إضافة المترجمين الافتراضيين عند بدء التطبيق
    ensure_default_translators()

    # =============================
    # Handlers منفصلة للبحث الذكي - فصل كامل بين المرضى والأطباء
    # =============================

    async def patient_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler منفصل للبحث عن المرضى فقط - لا يتداخل مع الأطباء"""
        import logging
        logger = logging.getLogger(__name__)

        query_text = update.inline_query.query.strip() if update.inline_query.query else ""
        logger.info(f"🔍 patient_inline_query_handler: Searching patients with query='{query_text}'")

        results = []

        try:
            with SessionLocal() as s:
                if query_text:
                    # عند البحث، عرض جميع النتائج المطابقة (حتى 50 - الحد الأقصى لـ Telegram)
                    patients = s.query(Patient).filter(
                        Patient.full_name.ilike(f"%{query_text}%")
                    ).order_by(Patient.full_name).limit(50).all()
                else:
                    # عند عدم وجود بحث، عرض آخر 50 مريض (الحد الأقصى لـ Telegram Inline Query)
                    patients = s.query(Patient).order_by(Patient.full_name).limit(50).all()

                for patient in patients:
                    result = InlineQueryResultArticle(
                        id=f"patient_{patient.id}",
                        title=f"👤 {patient.full_name}",
                        description=f"اختر هذا المريض",
                        input_message_content=InputTextMessageContent(
                            message_text=f"__PATIENT_SELECTED__:{patient.id}:{patient.full_name}"
                        )
                    )
                    results.append(result)

            logger.info(f"patient_inline_query_handler: Found {len(results)} patients from database")

        except Exception as db_error:
            logger.error(f"❌ خطأ في البحث عن المرضى من قاعدة البيانات: {db_error}", exc_info=True)
            # Fallback: قراءة من الملف
            try:
                import os
                file_path = "data/patient_names.txt"
                if os.path.exists(file_path):
                    names = []
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                names.append(line)

                    # فلترة حسب query_text
                    if query_text:
                        names = [n for n in names if query_text.lower() in n.lower()]

                    # إنشاء نتائج من الملف (حتى 50 - الحد الأقصى لـ Telegram)
                    for idx, name in enumerate(names[:50]):
                        result = InlineQueryResultArticle(
                            id=f"patient_file_{idx}",
                            title=f"👤 {name}",
                            description=f"اختر هذا المريض",
                            input_message_content=InputTextMessageContent(
                                message_text=f"__PATIENT_SELECTED__:0:{name}"
                            )
                        )
                        results.append(result)

                    logger.info(f"patient_inline_query_handler: Found {len(results)} patients from file (fallback)")
            except Exception as file_error:
                logger.error(f"❌ خطأ في قراءة ملف المرضى: {file_error}")

        # إرسال النتائج
        if not results:
            result = InlineQueryResultArticle(
                id="patient_no_results",
                title="❌ لا توجد نتائج",
                description="لم يتم العثور على مرضى",
                input_message_content=InputTextMessageContent(
                    message_text="__PATIENT_SELECTED__:0:لا يوجد"
                )
            )
            results.append(result)

        await update.inline_query.answer(results, cache_time=1)
        logger.info(f"patient_inline_query_handler: Sent {len(results)} results to Telegram")

    async def translator_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler منفصل للبحث عن المترجمين فقط"""
        import logging
        logger = logging.getLogger(__name__)

        query_text = update.inline_query.query.strip() if update.inline_query.query else ""
        logger.info(f"🔍 translator_inline_query_handler: Searching translators with query='{query_text}'")

        results = []

        try:
            with SessionLocal() as s:
                # جلب المترجمين المعتمدين فقط
                if query_text:
                    translators = s.query(Translator).filter(
                        Translator.is_approved == True,
                        Translator.full_name.isnot(None),
                        Translator.full_name != "",
                        Translator.full_name.ilike(f"%{query_text}%")
                    ).order_by(Translator.full_name).limit(50).all()
                else:
                    translators = s.query(Translator).filter(
                        Translator.is_approved == True,
                        Translator.full_name.isnot(None),
                        Translator.full_name != ""
                    ).order_by(Translator.full_name).limit(50).all()

                for translator in translators:
                    result = InlineQueryResultArticle(
                        id=f"translator_{translator.id}",
                        title=f"👤 {translator.full_name}",
                        description=f"اختر هذا المترجم",
                        input_message_content=InputTextMessageContent(
                            message_text=f"__TRANSLATOR_SELECTED__:{translator.id}:{translator.full_name}"
                        )
                    )
                    results.append(result)

            logger.info(f"translator_inline_query_handler: Found {len(results)} translators from database")

        except Exception as db_error:
            logger.error(f"❌ خطأ في البحث عن المترجمين من قاعدة البيانات: {db_error}")

        # إرسال النتائج
        if not results:
            result = InlineQueryResultArticle(
                id="translator_no_results",
                title="❌ لا توجد نتائج",
                description="لم يتم العثور على مترجمين",
                input_message_content=InputTextMessageContent(
                    message_text="__TRANSLATOR_SELECTED__:0:غير محدد"
                )
            )
            results.append(result)
        
        await update.inline_query.answer(results, cache_time=1)
        logger.info(f"translator_inline_query_handler: Sent {len(results)} results to Telegram")

    async def doctor_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler بسيط للبحث عن الأطباء مع فلترة حسب المستشفى والقسم"""
        print("🎯 DOCTOR SEARCH STARTED")
        try:
            # الحصول على البيانات
            query_text = update.inline_query.query.strip() if update.inline_query.query else ""

            # الحصول على بيانات المستشفى والقسم المحددين
            report_tmp = context.user_data.get("report_tmp", {})
            hospital_name = report_tmp.get("hospital_name", "").strip()
            department_name = report_tmp.get("department_name", "").strip()

            # تحويل أسماء المستشفيات المختصرة إلى الأسماء الكاملة في قاعدة البيانات
            hospital_mapping = {
                "Aster CMI": "Aster CMI Hospital, Bangalore",
                "Aster RV": "Aster RV Hospital, Bangalore",
                "Aster Whitefield": "Aster Whitefield Hospital, Bangalore",
                "Manipal Hospital - Old Airport Road": "Manipal Hospital, Old Airport Road, Bangalore",
                "Manipal Hospital - Millers Road": "Manipal Hospital, Millers Road, Bangalore",
                "Manipal Hospital - Whitefield": "Manipal Hospital, Whitefield, Bangalore",
                "Manipal Hospital - Yeshwanthpur": "Manipal Hospital, Yeshwanthpur, Bangalore",
                "Manipal Hospital - Sarjapur Road": "Manipal Hospital, Sarjapur Road, Bangalore",
            }

            # استخدام الاسم الكامل إذا كان متوفراً
            search_hospital = hospital_mapping.get(hospital_name, hospital_name)

            print(f"Query: '{query_text}', Hospital: '{hospital_name}' -> '{search_hospital}', Department: '{department_name}'")

            # البحث عن الأطباء مع الفلترة
            doctors_results = search_doctors(
                query=query_text if query_text else "",
                hospital=search_hospital if search_hospital else None,
                department=department_name if department_name else None,
                limit=20  # زيادة العدد للحصول على نتائج أكثر
            )

            print(f"Found {len(doctors_results)} doctors (filtered by hospital='{hospital_name}' and department='{department_name}')")

            # بناء النتائج
            results = []
            for idx, doctor in enumerate(doctors_results):
                name = doctor.get('name', 'طبيب بدون اسم')
                hospital = doctor.get('hospital', 'مستشفى غير محدد')
                department = doctor.get('department_ar', doctor.get('department_en', 'قسم غير محدد'))

                result = InlineQueryResultArticle(
                    id=f"doc_{idx}",
                    title=f"👨‍⚕️ {name}",
                    description=f"🏥 {hospital[:30]} | 📋 {department[:30]}",
                    input_message_content=InputTextMessageContent(
                        message_text=f"__DOCTOR_SELECTED__:{idx}:{name}"
                    )
                )
                results.append(result)

            # إرسال النتائج
            await update.inline_query.answer(results, cache_time=1)
            print(f"✅ Sent {len(results)} results to Telegram")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            # إرسال نتائج فارغة في حالة الخطأ
            await update.inline_query.answer([], cache_time=1)

    async def handle_chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """معالجة اختيار من inline query"""
        result_id = update.chosen_inline_result.result_id
        query_text = update.chosen_inline_result.query
        
        if result_id.startswith("patient_"):
            patient_id = int(result_id.split("_")[1])
            report_tmp = context.user_data.setdefault("report_tmp", {})
            with SessionLocal() as s:
                patient = s.query(Patient).filter_by(id=patient_id).first()
                if patient:
                    report_tmp["patient_name"] = patient.full_name
                    report_tmp["patient_id"] = patient_id
        elif result_id.startswith("doctor_"):
            # النظام الجديد: ID هو index وليس doctor.id
            # اسم الطبيب سيأتي من message_text في handle_doctor
            # هنا نحفظ فقط أن الطبيب تم اختياره
            report_tmp = context.user_data.setdefault("report_tmp", {})
            # محاولة البحث عن الطبيب من اسمه في قاعدة البيانات (اختياري)
            # لكن handle_doctor سيتعامل مع الرسالة مباشرة
            pass

    app.add_handler(ChosenInlineResultHandler(handle_chosen_inline_result))

    # تسجيل ConversationHandler لإضافة التقارير
    conv_handler = ConversationHandler(
        entry_points=[
            # ✅ السماح فقط في الدردشة الخاصة (Private Chat) - منع إضافة التقارير من المجموعات
            MessageHandler(filters.ChatType.PRIVATE & filters.Regex(r"^📝\s*إضافة\s*تقرير\s*جديد\s*$"), start_report),
            MessageHandler(filters.ChatType.PRIVATE & filters.Regex(r"^📝\s*إضافة تقرير جديد\s*$"), start_report),
            MessageHandler(filters.ChatType.PRIVATE & filters.Regex(r"^📝 إضافة تقرير جديد$"), start_report),
            MessageHandler(filters.ChatType.PRIVATE & filters.Regex(r"إضافة تقرير جديد"), start_report),
            MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & filters.Regex(r"📝.*إضافة.*تقرير.*جديد"), start_report),
        ],
        states={
            STATE_SELECT_DATE: [
                CallbackQueryHandler(handle_date_choice, pattern="^(date:|nav:)"),
                CallbackQueryHandler(handle_main_calendar_nav, pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(handle_main_calendar_day, pattern="^main_cal_day:"),
            ],
            R_DATE: [
                CallbackQueryHandler(handle_date_choice, pattern="^(date:|nav:)"),
                CallbackQueryHandler(handle_main_calendar_nav, pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(handle_main_calendar_day, pattern="^main_cal_day:"),
            ],
            R_DATE_TIME: [
                CallbackQueryHandler(handle_date_time_hour, pattern="^time_hour:"),
                CallbackQueryHandler(handle_date_time_minute, pattern="^time_minute:"),
                CallbackQueryHandler(handle_date_time_skip, pattern="^time_skip"),
                CallbackQueryHandler(handle_date_time_back_hour, pattern="^time_back_hour$"),
            ],
            STATE_SELECT_PATIENT: [
                CallbackQueryHandler(handle_patient_selection, pattern="^patient_idx:"),
                CallbackQueryHandler(handle_patient_list_callback, pattern="^patient:(show_list:|back_to_menu)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            R_PATIENT: [
                CallbackQueryHandler(handle_patient_selection, pattern="^patient_idx:"),
                CallbackQueryHandler(handle_patient_list_callback, pattern="^patient:(show_list:|back_to_menu)"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            STATE_SELECT_HOSPITAL: [
                CallbackQueryHandler(handle_hospital_selection, pattern="^hospital_idx:"),
                CallbackQueryHandler(handle_hospital_page, pattern="^(hospital_page|hosp_page):"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_search),
            ],
            STATE_SELECT_DEPARTMENT: [
                CallbackQueryHandler(handle_department_selection, pattern="^dept_idx:"),
                CallbackQueryHandler(handle_department_page, pattern="^dept_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
            ],
            R_DEPARTMENT: [
                CallbackQueryHandler(handle_department_selection, pattern="^dept_idx:"),
                CallbackQueryHandler(handle_department_page, pattern="^dept_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
            ],
            R_SUBDEPARTMENT: [
                CallbackQueryHandler(handle_subdepartment_choice, pattern="^subdept(?:_idx)?:"),
                CallbackQueryHandler(handle_subdepartment_page, pattern="^subdept_page:"),
            ],
            STATE_SELECT_DOCTOR: [
                CallbackQueryHandler(handle_doctor_selection, pattern="^(doctor_idx:|doctor_manual)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            R_DOCTOR: [
                CallbackQueryHandler(handle_doctor_selection, pattern="^(doctor_idx:|doctor_manual)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            R_ACTION_TYPE: [
                # جميع الأزرار في صفحة واحدة - لا حاجة لـ handle_action_page
                CallbackQueryHandler(handle_action_type_choice, pattern="^action_idx:"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
                # معالجة callbacks القديمة (من حالات سابقة)
                CallbackQueryHandler(handle_stale_callback, pattern="^(hosp_page|hospital_page|dept_page|department_page|subdept_page|subdepartment_page|doctor_idx|hospital_idx|dept_idx|subdept|subdept_idx):"),
            ],
            # إضافة جميع المسارات الخاصة بأنواع الإجراءات:
            NEW_CONSULT_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_consult_complaint),
            ],
            NEW_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_consult_decision),
            ],
            NEW_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_consult_tests),
            ],
            NEW_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
            ],
            NEW_CONSULT_FOLLOWUP_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            NEW_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_consult_followup_reason),
            ],
            NEW_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            NEW_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار استشارة مع قرار عملية
            SURGERY_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_diagnosis),
            ],
            SURGERY_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_decision),
            ],
            SURGERY_CONSULT_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_name_en),
            ],
            SURGERY_CONSULT_SUCCESS_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_success_rate),
            ],
            SURGERY_CONSULT_BENEFIT_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_benefit_rate),
            ],
            SURGERY_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_tests),
            ],
            SURGERY_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_surgery_consult_followup_choice, pattern="^surgery_followup:(calendar|text|skip)"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_followup_date_text),
            ],
            SURGERY_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_surgery_consult_followup_reason),
            ],
            SURGERY_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            SURGERY_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار استشارة أخيرة
            FINAL_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_final_consult_diagnosis),
            ],
            FINAL_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_final_consult_decision),
            ],
            FINAL_CONSULT_RECOMMENDATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_final_consult_recommendations),
            ],
            FINAL_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            FINAL_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار متابعة في الرقود
            FOLLOWUP_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_complaint),
            ],
            FOLLOWUP_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_diagnosis),
            ],
            FOLLOWUP_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_decision),
            ],
            FOLLOWUP_ROOM_FLOOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_room_floor),
            ],
            FOLLOWUP_DATE_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_reason),
            ],
            FOLLOWUP_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            FOLLOWUP_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار طوارئ
            EMERGENCY_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_complaint),
            ],
            EMERGENCY_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_diagnosis),
            ],
            EMERGENCY_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_decision),
            ],
            EMERGENCY_STATUS: [
                CallbackQueryHandler(handle_emergency_status_choice, pattern="^emerg_status:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_status_text),
            ],
            EMERGENCY_ADMISSION_TYPE: [
                CallbackQueryHandler(handle_emergency_admission_type_choice, pattern="^emerg_admission:"),
            ],
            EMERGENCY_ROOM_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_room_number),
            ],
            EMERGENCY_DATE_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_date_time_text),
            ],
            EMERGENCY_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_emergency_reason),
            ],
            EMERGENCY_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            EMERGENCY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار عملية
            OPERATION_DETAILS_AR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operation_details_ar),
            ],
            OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operation_name_en),
            ],
            OPERATION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operation_notes),
            ],
            OPERATION_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operation_followup_date_text),
            ],
            OPERATION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_operation_followup_reason),
            ],
            OPERATION_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            OPERATION_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار علاج طبيعي / أجهزة تعويضية
            REHAB_TYPE: [
                CallbackQueryHandler(handle_rehab_type, pattern="^rehab_type:"),
            ],
            PHYSICAL_THERAPY_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_physical_therapy_details),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_physical_therapy_followup_reason),
            ],
            PHYSICAL_THERAPY_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            PHYSICAL_THERAPY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            DEVICE_NAME_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_device_name_details),
            ],
            DEVICE_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            DEVICE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_device_followup_reason),
            ],
            DEVICE_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            DEVICE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار أشعة وفحوصات
            RADIOLOGY_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiology_type),
            ],
            RADIOLOGY_DELIVERY_DATE: [
                CallbackQueryHandler(handle_radiology_calendar_nav, pattern="^radiology_cal_(prev|next):"),
                CallbackQueryHandler(handle_radiology_calendar_day, pattern="^radiology_cal_day:"),
            ],
            RADIOLOGY_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            RADIOLOGY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار ترقيد
            ADMISSION_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admission_reason),
            ],
            ADMISSION_ROOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admission_room),
            ],
            ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admission_notes),
            ],
            ADMISSION_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admission_followup_date_text),
            ],
            ADMISSION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admission_followup_reason),
            ],
            ADMISSION_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            ADMISSION_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # مسار خروج من المستشفى
            DISCHARGE_TYPE: [
                CallbackQueryHandler(handle_discharge_type, pattern="^discharge_type:"),
            ],
            DISCHARGE_ADMISSION_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discharge_admission_summary),
            ],
            DISCHARGE_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discharge_operation_details),
            ],
            DISCHARGE_OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discharge_operation_name_en),
            ],
            DISCHARGE_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discharge_followup_date_text),
            ],
            DISCHARGE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_discharge_followup_reason),
            ],
            DISCHARGE_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_choice, pattern="^translator:"),
                CallbackQueryHandler(handle_translator_list_callback, pattern="^translator:(show_list|back_to_menu):"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__TRANSLATOR_SELECTED__:"), handle_translator_inline_selection),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_text),
            ],
            DISCHARGE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|review|publish|back_to_summary|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^edit_field:"),
            ],
            # State عام لمعالجة التعديل
            "EDIT_FIELD": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_field_input),
                CallbackQueryHandler(handle_edit_callback, pattern="^edit:"),
            ],
            # أضف هنا باقي المسارات بنفس الطريقة (FOLLOWUP_COMPLAINT، ADMISSION_COMPLAINT، ...)
        },
        fallbacks=[
            # معالجات للمستشفيات
            CallbackQueryHandler(handle_hospital_page, pattern="^hosp_page:"),
            CallbackQueryHandler(handle_hospital_selection, pattern="^select_hospital:"),

            CallbackQueryHandler(handle_cancel_navigation, pattern="^nav:cancel"),
            CommandHandler("cancel", handle_cancel_navigation),
            # معالج للرسائل التي تحتوي على "إضافة تقرير جديد" (للتعامل مع الأزرار) - فقط في الدردشة الخاصة
            MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & filters.Regex(r".*إضافة.*تقرير.*جديد.*"), start_report),
            # معالج زر الرجوع - يعمل في جميع الـ states
            CallbackQueryHandler(handle_back_navigation, pattern="^nav:back$"),
            # معالج زر الإلغاء - يعمل في جميع الـ states
            CallbackQueryHandler(handle_cancel_navigation, pattern="^nav:cancel$"),
            # DEBUG: إضافة fallback لالتقاط جميع callbacks غير متطابقة في حالة R_ACTION_TYPE
            CallbackQueryHandler(debug_all_callbacks, pattern=".*"),
        ],
        per_message=False,  # ✅ False لأن لدينا MessageHandler في entry_points
        per_chat=True,
        per_user=True,
    )
    # تسجيل InlineQueryHandler موحد للبحث عن المرضى والأطباء - قبل ConversationHandler
    async def unified_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler موحد للبحث - يحدد النوع بناءً على علامة البحث"""
        import logging
        logger = logging.getLogger(__name__)
        
        query_text = update.inline_query.query.strip() if update.inline_query.query else ""
        logger.info("🎯🎯🎯 UNIFIED_INLINE_QUERY_HANDLER TRIGGERED! 🎯🎯🎯")

        report_tmp = context.user_data.get("report_tmp", {})
        search_type = context.user_data.get('_current_search_type', 'patient')
        initial_case_search = context.user_data.get("initial_case_search")
        
        logger.info(f"🎯 Report TMP exists: {bool(report_tmp)}")
        logger.info(f"🎯 Search type: {search_type}")
        logger.info(f"🎯 Initial case search: {initial_case_search}")
        logger.info(f"🎯 Query text: '{query_text}'")
        
        # ✅ التحقق: هل المستخدم في وضع التقرير الأولي فقط (وليس في وضع إضافة تقرير جديد)؟
        # إذا كان في وضع التقرير الأولي وليس في وضع إضافة تقرير جديد، نستخدم handle_initial_case_inline_query
        if initial_case_search is not None and initial_case_search.get("active") is True and not report_tmp:
            # المستخدم في وضع التقرير الأولي فقط - نستدعي handle_initial_case_inline_query
            logger.info("🎯 User is in initial case search mode - calling initial case handler")
            from bot.handlers.user.user_initial_case import handle_initial_case_inline_query
            await handle_initial_case_inline_query(update, context)
            return

        # ✅ تحديد نوع البحث بناءً على search_type أولاً (قبل التحقق من report_tmp)
        # هذا يضمن أن البحث عن الأطباء والمترجمين يعمل بشكل صحيح
        
        # البحث عن الأطباء
        if search_type == 'doctor':
            if not report_tmp:
                logger.info("🎯 No report_tmp for doctor search, returning empty results")
                await update.inline_query.answer([], cache_time=1)
                return
            logger.info("🎯 Calling doctor search")
            await doctor_inline_query_handler(update, context)
            return
        
        # البحث عن المترجمين
        if search_type == 'translator':
            logger.info("🎯 Calling translator search")
            await translator_inline_query_handler(update, context)
            return
        
        # البحث عن المرضى (افتراضي)
        # السماح بالبحث عن المرضى دائماً (حتى لو لم يكن report_tmp موجوداً)
        # لأن البحث عن المرضى يمكن أن يحدث في أي وقت
        if search_type == 'patient' or not search_type or search_type not in ['doctor', 'translator']:
            logger.info("🎯 Calling patient search (default)")
            await patient_inline_query_handler(update, context)
            return

    # تسجيل InlineQueryHandler أولاً لضمان أنه يلتقط inline queries قبل ConversationHandler
    # group=0 (افتراضي) - سيتم استدعاؤه مع handle_initial_case_inline_query
    # لكن unified_inline_query_handler سيعمل كـ fallback إذا لم يرسل handle_initial_case_inline_query إجابة
    app.add_handler(InlineQueryHandler(unified_inline_query_handler), group=0)
    # تسجيل InlineQueryHandler للمترجمين
    app.add_handler(InlineQueryHandler(translator_inline_query_handler), group=2)

    # ثم تسجيل ConversationHandler
    app.add_handler(conv_handler)
