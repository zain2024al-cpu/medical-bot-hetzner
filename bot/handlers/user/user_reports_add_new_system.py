# =============================
# bot/handlers/user/user_reports_add_new_system.py
# 🎨 نظام إضافة التقارير الطبية المتقدم - النظام الكامل
# نظام ذكي مع مسارات مخصصة لكل نوع إجراء
# 10 مسارات - تاريخ ووقت مدمج - أزرار تفاعلية في كل خطوة
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, filters
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
import os
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
            [InlineKeyboardButton("⬅️ رجوع للمستشفيات", callback_data="hosp_search")]
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
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])

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

# مسار 1: استشارة جديدة (7-16) - تاريخ ووقت منفصلان
(
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DIAGNOSIS, NEW_CONSULT_DECISION,
    NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_TIME,
    NEW_CONSULT_FOLLOWUP_REASON, NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM
) = range(7, 16)

# مسار 2: مراجعة/عودة دورية (16-23) - 5 حقول (تم حذف رقم الغرفة والطابق)
(
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,  # FOLLOWUP_ROOM_FLOOR غير مستخدم
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

# مسار 11: تأجيل موعد (86-91)
(
    APP_RESCHEDULE_REASON, APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON,
    APP_RESCHEDULE_TRANSLATOR, APP_RESCHEDULE_CONFIRM
) = range(86, 91)

# =============================
# دوال مساعدة للأزرار
# =============================

MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

# ترتيب أيام الأسبوع عندما يكون السبت أول يوم (firstweekday=5)
# السبت، الأحد، الاثنين، الثلاثاء، الأربعاء، الخميس، الجمعة
WEEKDAYS_AR = ["س", "ح", "ن", "ث", "ر", "خ", "ج"]


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


def format_time_string_12h(time_str: str) -> str:
    """
    تحويل وقت من صيغة 24 ساعة (مثل "13:00") إلى صيغة 12 ساعة بالعربية
    مثال: "13:00" -> "1 الظهر"
    مثال: "08:00" -> "8 صباحاً"
    مثال: "20:00" -> "8 مساءً"
    """
    if not time_str:
        return ""
    
    try:
        # تحليل الوقت من صيغة "HH:MM"
        parts = time_str.split(":")
        if len(parts) != 2:
            return time_str
        
        hour = int(parts[0])
        minute = int(parts[1])
        
        # تحويل إلى صيغة 12 ساعة
        if hour == 0:
            return f"12:{minute:02d} صباحاً"
        elif hour == 12:
            return f"12:{minute:02d} الظهر"
        elif hour < 12:
            return f"{hour}:{minute:02d} صباحاً"
        else:
            hour_12 = hour - 12
            if hour_12 == 0:
                return f"12:{minute:02d} الظهر"
            else:
                return f"{hour_12}:{minute:02d} مساءً"
    except (ValueError, IndexError):
        return time_str


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


class SmartCancelManager:
    """
    مدير إلغاء ذكي يفهم السياق ويتعامل مع كل حالة بشكل مناسب
    """

    @staticmethod
    def get_cancel_context(context):
        """
        تحديد سياق الإلغاء بناءً على البيانات الحالية
        """
        user_data = context.user_data

        # إذا كان في وضع تعديل مؤقت
        if user_data.get('editing_draft'):
            return 'draft_edit'

        # إذا كان في وضع تعديل تقرير موجود
        if 'current_report_data' in user_data and user_data['current_report_data']:
            return 'report_edit'

        # إذا كان هناك بيانات تقرير مؤقتة (إنشاء تقرير جديد)
        if 'report_tmp' in user_data and user_data['report_tmp']:
            return 'report_creation'

        # إذا كان في وضع بحث
        search_context = smart_nav_manager.get_search_context()
        if search_context and search_context.get('current_search_type'):
            return 'search'

        # إلغاء عام
        return 'general'

    @staticmethod
    async def handle_contextual_cancel(update, context, cancel_context):
        """
        التعامل مع الإلغاء حسب السياق - يعيد نتيجة الإلغاء للـ ConversationHandler
        """
        if cancel_context == 'draft_edit':
            # إلغاء التعديل المؤقت - العودة للملخص
            return await cancel_draft_edit(update, context)

        elif cancel_context == 'report_edit':
            # إلغاء تعديل تقرير موجود - العودة لقائمة التقارير
            return await cancel_report_edit(update, context)

        elif cancel_context == 'report_creation':
            # إلغاء إنشاء تقرير جديد - تنظيف البيانات والعودة للبداية
            return await cancel_report_creation(update, context)

        elif cancel_context == 'search':
            # إلغاء البحث - العودة للخطوة السابقة
            return await cancel_search(update, context)

        else:
            # إلغاء عام - تنظيف كل شيء
            return await cancel_general(update, context)

async def handle_smart_cancel_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة إلغاء ذكية تفهم السياق وتتصرف بطريقة مناسبة
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("❌ SMART CANCEL NAVIGATION TRIGGERED")
    logger.info("=" * 80)

    try:
        # تحديد سياق الإلغاء
        cancel_context = SmartCancelManager.get_cancel_context(context)

        logger.info(f"❌ Cancel context determined: {cancel_context}")

        # التعامل مع الإلغاء حسب السياق - نستخدم result للتحكم في الرجوع
        result = await SmartCancelManager.handle_contextual_cancel(update, context, cancel_context)

        logger.info(f"❌ Successfully handled cancel for context: {cancel_context}")
        
        # ✅ إرجاع نتيجة الإلغاء للـ ConversationHandler
        return result if result is not None else ConversationHandler.END

    except Exception as e:
        logger.error(f"❌ Error in handle_smart_cancel_navigation: {e}", exc_info=True)
        # في حالة الخطأ، إلغاء عام
        await SmartCancelManager.cancel_general(update, context)
        return ConversationHandler.END

# دوال الإلغاء المخصصة لكل سياق

async def cancel_draft_edit(update, context):
    """
    إلغاء التعديل المؤقت - العودة للملخص دون حفظ التغييرات
    """
    query = update.callback_query
    if query:
        await query.answer("تم إلغاء التعديل")

        try:
            await query.edit_message_text(
                "❌ تم إلغاء التعديل المؤقت\n\n"
                "لم يتم حفظ أي تغييرات\n"
                "يمكنك إعادة التعديل أو الحفظ الآن",
                reply_markup=None
            )
        except:
            pass

    # مسح بيانات التعديل المؤقت
    context.user_data.pop('editing_draft', None)
    context.user_data.pop('draft_flow_type', None)
    context.user_data.pop('draft_medical_action', None)
    context.user_data.pop('editing_field', None)

    # العودة للملخص النهائي
    flow_type = context.user_data.get('report_tmp', {}).get('current_flow', 'new_consult')
    await show_final_summary(query.message if query else update.message, context, flow_type)

    confirm_state = get_confirm_state(flow_type)
    context.user_data['_conversation_state'] = confirm_state
    return confirm_state

async def cancel_report_edit(update, context):
    """
    إلغاء تعديل تقرير موجود - العودة للقائمة الرئيسية
    """
    query = update.callback_query
    if query:
        await query.answer("تم إلغاء تعديل التقرير")

        try:
            await query.edit_message_text(
                "❌ تم إلغاء تعديل التقرير\n\n"
                "لم يتم حفظ أي تغييرات على التقرير الأصلي.\n"
                "اختر *✏️ تعديل التقارير* من القائمة للعودة لقائمة التقارير.",
                parse_mode="Markdown"
            )
        except:
            pass

    # مسح بيانات التعديل
    context.user_data.pop('current_report_data', None)
    context.user_data.pop('editing_field', None)

    return ConversationHandler.END

async def cancel_report_creation(update, context):
    """
    إلغاء إنشاء تقرير جديد - تنظيف البيانات والعودة للبداية
    """
    # ✅ تنظيف جميع البيانات المتعلقة بالتقرير
    keys_to_clear = [
        "report_tmp", "_conversation_state", "last_valid_state", 
        "editing_field", "current_report_data", "edit_draft_field",
        "editing_draft", "draft_flow_type", "draft_medical_action",
        "editing_field_original", "_current_search_type",
        "_state_history",  # ✅ مسح تاريخ الحالات أيضاً
        "_doctors_list", "_doctors_page"  # ✅ مسح بيانات قائمة الأطباء
    ]
    for key in keys_to_clear:
        context.user_data.pop(key, None)
    
    # ✅ مسح تاريخ الحالات من StateHistoryManager
    try:
        state_mgr = StateHistoryManager.get_state_manager(context)
        if state_mgr:
            state_mgr.clear_history()
    except:
        pass
    
    # إعادة تعيين سياق البحث
    try:
        smart_nav_manager.clear_search_context()
    except:
        pass
    
    query = update.callback_query
    if query:
        await query.answer("تم إلغاء إنشاء التقرير")

        try:
            await query.edit_message_text(
                "❌ تم إلغاء إنشاء التقرير\n\n"
                "للبدء من جديد، اضغط على *📝 إضافة تقرير جديد* من القائمة الرئيسية.",
                parse_mode="Markdown"
            )
        except:
            pass
    elif update.message:
        await update.message.reply_text(
            "❌ تم إلغاء إنشاء التقرير\n\n"
            "للبدء من جديد، اضغط على *📝 إضافة تقرير جديد* من القائمة الرئيسية.",
            parse_mode="Markdown"
        )

    return ConversationHandler.END

async def cancel_search(update, context):
    """
    إلغاء البحث - العودة للخطوة السابقة
    """
    query = update.callback_query
    if query:
        await query.answer("تم إلغاء البحث")

        try:
            await query.edit_message_text(
                "❌ تم إلغاء البحث\n\n"
                "العودة للخطوة السابقة...",
                reply_markup=None
            )
        except:
            pass

    # مسح سياق البحث
    smart_nav_manager.clear_search_context()

    # العودة للخطوة السابقة
    current_state = context.user_data.get('_conversation_state')
    flow_type = context.user_data.get('report_tmp', {}).get('current_flow', 'new_consult')

    previous_step = smart_nav_manager.get_previous_step(flow_type, current_state)

    if previous_step:
        await execute_smart_state_action(previous_step, flow_type, update, context)
        return previous_step
    else:
        # إذا لم يكن هناك خطوة سابقة، إلغاء عام
        return await cancel_general(update, context)

async def cancel_general(update, context):
    """
    إلغاء عام - تنظيف كل شيء والعودة للبداية
    """
    query = update.callback_query
    if query:
        await query.answer("تم إلغاء العملية")

        try:
            await query.edit_message_text(
                "❌ تم إلغاء العملية\n\n"
                "للبدء من جديد، اضغط على *📝 إضافة تقرير جديد* من القائمة الرئيسية.",
                parse_mode="Markdown"
            )
        except:
            pass
    elif update.message:
        await update.message.reply_text(
            "❌ تم إلغاء العملية\n\n"
            "للبدء من جديد، اضغط على *📝 إضافة تقرير جديد* من القائمة الرئيسية.",
            parse_mode="Markdown"
        )

    # تنظيف جميع البيانات
    context.user_data.clear()

    # إعادة تعيين سياق البحث
    try:
        smart_nav_manager.clear_search_context()
    except:
        pass

    return ConversationHandler.END

# استبدال الدالة القديمة بالجديدة
handle_cancel_navigation = handle_smart_cancel_navigation

def test_smart_cancel_system():
    """
    دالة اختبار لنظام الإلغاء الذكي
    """

    # اختبار تحديد السياق
    test_contexts = [
        ({'editing_draft': True}, 'draft_edit'),
        ({'current_report_data': {}}, 'report_edit'),
        ({'report_tmp': {}}, 'report_creation'),
        ({}, 'general')
    ]

    for user_data, expected in test_contexts:
        # محاكاة context
        class MockContext:
            def __init__(self, user_data):
                self.user_data = user_data

        context = MockContext(user_data)
        result = SmartCancelManager.get_cancel_context(context)

        status = '✅' if result == expected else '❌'

    cancel_types = [
        'draft_edit: إلغاء التعديل المؤقت',
        'report_edit: إلغاء تعديل تقرير موجود',
        'report_creation: إلغاء إنشاء تقرير جديد',
        'search: إلغاء البحث',
        'general: إلغاء عام'
    ]

    # cancel_types متاح للاستخدام
    return True


# =============================
# نظام التنقل الذكي الجديد - Smart Navigation System
# =============================

class SmartNavigationManager:
    """
    مدير تنقل ذكي يتتبع الخطوات بدقة ويعرف كيفية الرجوع خطوة واحدة فقط
    يحل مشكلة الخلطة في أزرار البحث ويضمن الرجوع الدقيق
    """

    def __init__(self):
        # خريطة الخطوات لكل نوع تدفق مع الخطوة السابقة بدقة
        self.step_flows = {
            # تدفق استشارة جديدة
            'new_consult': {
                STATE_SELECT_DATE: None,  # البداية
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'NEW_CONSULT_COMPLAINT': STATE_SELECT_ACTION_TYPE,
                'NEW_CONSULT_DIAGNOSIS': 'NEW_CONSULT_COMPLAINT',
                'NEW_CONSULT_DECISION': 'NEW_CONSULT_DIAGNOSIS',
                'NEW_CONSULT_TESTS': 'NEW_CONSULT_DECISION',
                'NEW_CONSULT_FOLLOWUP_DATE': 'NEW_CONSULT_TESTS',
                'NEW_CONSULT_FOLLOWUP_REASON': 'NEW_CONSULT_FOLLOWUP_DATE',
                'NEW_CONSULT_TRANSLATOR': 'NEW_CONSULT_FOLLOWUP_REASON',
                'NEW_CONSULT_CONFIRM': 'NEW_CONSULT_TRANSLATOR',
            },

            # تدفق استشارة مع قرار عملية
            'surgery_consult': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'SURGERY_CONSULT_DIAGNOSIS': STATE_SELECT_ACTION_TYPE,
                'SURGERY_CONSULT_DECISION': 'SURGERY_CONSULT_DIAGNOSIS',
                'SURGERY_CONSULT_OPERATION_NAME': 'SURGERY_CONSULT_DECISION',
                'SURGERY_CONSULT_SUCCESS_RATE': 'SURGERY_CONSULT_OPERATION_NAME',
                'SURGERY_CONSULT_TESTS': 'SURGERY_CONSULT_SUCCESS_RATE',
                'SURGERY_CONSULT_FOLLOWUP_DATE': 'SURGERY_CONSULT_TESTS',
                'SURGERY_CONSULT_FOLLOWUP_REASON': 'SURGERY_CONSULT_FOLLOWUP_DATE',
                'SURGERY_CONSULT_TRANSLATOR': 'SURGERY_CONSULT_FOLLOWUP_REASON',
                'SURGERY_CONSULT_CONFIRM': 'SURGERY_CONSULT_TRANSLATOR',
            },

            # تدفق استشارة أخيرة
            'final_consult': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'FINAL_CONSULT_DIAGNOSIS': STATE_SELECT_ACTION_TYPE,
                'FINAL_CONSULT_DECISION': 'FINAL_CONSULT_DIAGNOSIS',
                'FINAL_CONSULT_RECOMMENDATIONS': 'FINAL_CONSULT_DECISION',
                'FINAL_CONSULT_TRANSLATOR': 'FINAL_CONSULT_RECOMMENDATIONS',
                'FINAL_CONSULT_CONFIRM': 'FINAL_CONSULT_TRANSLATOR',
            },

            # تدفق طوارئ
            'emergency': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'EMERGENCY_COMPLAINT': STATE_SELECT_ACTION_TYPE,
                'EMERGENCY_DIAGNOSIS': 'EMERGENCY_COMPLAINT',
                'EMERGENCY_DECISION': 'EMERGENCY_DIAGNOSIS',
                'EMERGENCY_STATUS': 'EMERGENCY_DECISION',
                'EMERGENCY_DATE_TIME': 'EMERGENCY_STATUS',
                'EMERGENCY_REASON': 'EMERGENCY_DATE_TIME',
                'EMERGENCY_TRANSLATOR': 'EMERGENCY_REASON',
                'EMERGENCY_CONFIRM': 'EMERGENCY_TRANSLATOR',
            },

            # تدفق متابعة في الرقود
            'followup': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'FOLLOWUP_COMPLAINT': STATE_SELECT_ACTION_TYPE,
                'FOLLOWUP_DIAGNOSIS': 'FOLLOWUP_COMPLAINT',
                'FOLLOWUP_DECISION': 'FOLLOWUP_DIAGNOSIS',
                'FOLLOWUP_DATE_TIME': 'FOLLOWUP_DECISION',
                'FOLLOWUP_REASON': 'FOLLOWUP_DATE_TIME',
                'FOLLOWUP_TRANSLATOR': 'FOLLOWUP_REASON',
                'FOLLOWUP_CONFIRM': 'FOLLOWUP_TRANSLATOR',
            },

            # تدفق عملية
            'operation': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'OPERATION_DETAILS_AR': STATE_SELECT_ACTION_TYPE,
                'OPERATION_NAME_EN': 'OPERATION_DETAILS_AR',
                'OPERATION_NOTES': 'OPERATION_NAME_EN',
                'OPERATION_FOLLOWUP_DATE': 'OPERATION_NOTES',
                'OPERATION_FOLLOWUP_REASON': 'OPERATION_FOLLOWUP_DATE',
                'OPERATION_TRANSLATOR': 'OPERATION_FOLLOWUP_REASON',
                'OPERATION_CONFIRM': 'OPERATION_TRANSLATOR',
            },

            # تدفق علاج طبيعي
            'rehab': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'REHAB_TYPE': STATE_SELECT_ACTION_TYPE,
                'PHYSICAL_THERAPY_DETAILS': 'REHAB_TYPE',
                'PHYSICAL_THERAPY_DEVICES': 'PHYSICAL_THERAPY_DETAILS',
                'PHYSICAL_THERAPY_NOTES': 'PHYSICAL_THERAPY_DEVICES',
                'PHYSICAL_THERAPY_FOLLOWUP_DATE': 'PHYSICAL_THERAPY_NOTES',
                'PHYSICAL_THERAPY_FOLLOWUP_REASON': 'PHYSICAL_THERAPY_FOLLOWUP_DATE',
                'PHYSICAL_THERAPY_TRANSLATOR': 'PHYSICAL_THERAPY_FOLLOWUP_REASON',
                'PHYSICAL_THERAPY_CONFIRM': 'PHYSICAL_THERAPY_TRANSLATOR',

                'DEVICE_NAME_DETAILS': 'REHAB_TYPE',
                'DEVICE_NOTES': 'DEVICE_NAME_DETAILS',
                'DEVICE_FOLLOWUP_DATE': 'DEVICE_NOTES',
                'DEVICE_FOLLOWUP_REASON': 'DEVICE_FOLLOWUP_DATE',
                'DEVICE_TRANSLATOR': 'DEVICE_FOLLOWUP_REASON',
                'DEVICE_CONFIRM': 'DEVICE_TRANSLATOR',
            },

            # تدفق أشعة وفحوصات
            'radiology': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'RADIOLOGY_TYPE': STATE_SELECT_ACTION_TYPE,
                'RADIOLOGY_DELIVERY_DATE': 'RADIOLOGY_TYPE',
                'RADIOLOGY_TRANSLATOR': 'RADIOLOGY_DELIVERY_DATE',
                'RADIOLOGY_CONFIRM': 'RADIOLOGY_TRANSLATOR',
            },

            # تدفق ترقيد
            'admission': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'ADMISSION_REASON': STATE_SELECT_ACTION_TYPE,
                'ADMISSION_ROOM': 'ADMISSION_REASON',
                'ADMISSION_NOTES': 'ADMISSION_ROOM',
                'ADMISSION_FOLLOWUP_DATE': 'ADMISSION_NOTES',
                'ADMISSION_FOLLOWUP_REASON': 'ADMISSION_FOLLOWUP_DATE',
                'ADMISSION_TRANSLATOR': 'ADMISSION_FOLLOWUP_REASON',
                'ADMISSION_CONFIRM': 'ADMISSION_TRANSLATOR',
            },

            # تدفق خروج من المستشفى
            'discharge': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'DISCHARGE_TYPE': STATE_SELECT_ACTION_TYPE,
                'DISCHARGE_ADMISSION_SUMMARY': 'DISCHARGE_TYPE',
                'DISCHARGE_OPERATION_DETAILS': 'DISCHARGE_ADMISSION_SUMMARY',
                'DISCHARGE_OPERATION_NAME_EN': 'DISCHARGE_OPERATION_DETAILS',
                'DISCHARGE_FOLLOWUP_DATE': 'DISCHARGE_OPERATION_NAME_EN',
                'DISCHARGE_FOLLOWUP_REASON': 'DISCHARGE_FOLLOWUP_DATE',
                'DISCHARGE_TRANSLATOR': 'DISCHARGE_FOLLOWUP_REASON',
                'DISCHARGE_CONFIRM': 'DISCHARGE_TRANSLATOR',
            },

            # تدفق تأجيل موعد
            'app_reschedule': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'APP_RESCHEDULE_REASON': STATE_SELECT_ACTION_TYPE,
                'APP_RESCHEDULE_RETURN_DATE': 'APP_RESCHEDULE_REASON',
                'APP_RESCHEDULE_RETURN_REASON': 'APP_RESCHEDULE_RETURN_DATE',
                'APP_RESCHEDULE_TRANSLATOR': 'APP_RESCHEDULE_RETURN_REASON',
                'APP_RESCHEDULE_CONFIRM': 'APP_RESCHEDULE_TRANSLATOR',
            },
        }

        # تتبع نوع البحث الحالي لمنع الخلطة
        self.search_context = {
            'current_search_type': None,  # 'patient', 'doctor', 'translator', 'hospital', 'department', 'subdepartment'
            'search_query': None,
            'last_results': None
        }

    def get_previous_step(self, flow_type, current_step):
        """
        الحصول على الخطوة السابقة بدقة لنوع التدفق المحدد
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if flow_type not in self.step_flows:
            logger.warning(f"⚠️ Flow type '{flow_type}' not found in step_flows")
            return STATE_SELECT_ACTION_TYPE
        
        flow_map = self.step_flows[flow_type]
        
        # ✅ أولاً: تحقق إذا كان current_step موجود مباشرة في flow_map (كرقم)
        if current_step in flow_map:
            prev_step = flow_map[current_step]
            logger.info(f"✅ Found direct match for state {current_step}, prev_step = {prev_step}")
            return prev_step
        
        # ربط أسماء الـ states بقيمها الفعلية (لتحويل الأرقام لأسماء)
        state_name_to_value = {
            # الـ states الأساسية
            'STATE_SELECT_DATE': STATE_SELECT_DATE,
            'STATE_SELECT_PATIENT': STATE_SELECT_PATIENT,
            'STATE_SELECT_HOSPITAL': STATE_SELECT_HOSPITAL,
            'STATE_SELECT_DEPARTMENT': STATE_SELECT_DEPARTMENT,
            'STATE_SELECT_SUBDEPARTMENT': STATE_SELECT_SUBDEPARTMENT,
            'STATE_SELECT_DOCTOR': STATE_SELECT_DOCTOR,
            'STATE_SELECT_ACTION_TYPE': STATE_SELECT_ACTION_TYPE,
            # states التدفقات
            'NEW_CONSULT_COMPLAINT': NEW_CONSULT_COMPLAINT,
            'NEW_CONSULT_DIAGNOSIS': NEW_CONSULT_DIAGNOSIS,
            'NEW_CONSULT_DECISION': NEW_CONSULT_DECISION,
            'NEW_CONSULT_TESTS': NEW_CONSULT_TESTS,
            'NEW_CONSULT_FOLLOWUP_DATE': NEW_CONSULT_FOLLOWUP_DATE,
            'NEW_CONSULT_FOLLOWUP_REASON': NEW_CONSULT_FOLLOWUP_REASON,
            'NEW_CONSULT_TRANSLATOR': NEW_CONSULT_TRANSLATOR,
            'FOLLOWUP_COMPLAINT': FOLLOWUP_COMPLAINT,
            'FOLLOWUP_DIAGNOSIS': FOLLOWUP_DIAGNOSIS,
            'FOLLOWUP_DECISION': FOLLOWUP_DECISION,
            'FOLLOWUP_DATE_TIME': FOLLOWUP_DATE_TIME,
            'FOLLOWUP_REASON': FOLLOWUP_REASON,
            'FOLLOWUP_TRANSLATOR': FOLLOWUP_TRANSLATOR,
            'EMERGENCY_COMPLAINT': EMERGENCY_COMPLAINT,
            'EMERGENCY_DIAGNOSIS': EMERGENCY_DIAGNOSIS,
            'EMERGENCY_DECISION': EMERGENCY_DECISION,
            'EMERGENCY_STATUS': EMERGENCY_STATUS,
            'EMERGENCY_ADMISSION_TYPE': EMERGENCY_ADMISSION_TYPE,
            'EMERGENCY_ROOM_NUMBER': EMERGENCY_ROOM_NUMBER,
            'EMERGENCY_DATE_TIME': EMERGENCY_DATE_TIME,
            'EMERGENCY_REASON': EMERGENCY_REASON,
            'EMERGENCY_TRANSLATOR': EMERGENCY_TRANSLATOR,
            'ADMISSION_REASON': ADMISSION_REASON,
            'ADMISSION_ROOM': ADMISSION_ROOM,
            'ADMISSION_NOTES': ADMISSION_NOTES,
            'ADMISSION_FOLLOWUP_DATE': ADMISSION_FOLLOWUP_DATE,
            'ADMISSION_FOLLOWUP_REASON': ADMISSION_FOLLOWUP_REASON,
            'ADMISSION_TRANSLATOR': ADMISSION_TRANSLATOR,
            'SURGERY_CONSULT_DIAGNOSIS': SURGERY_CONSULT_DIAGNOSIS,
            'SURGERY_CONSULT_DECISION': SURGERY_CONSULT_DECISION,
            'SURGERY_CONSULT_NAME_EN': SURGERY_CONSULT_NAME_EN,
            'SURGERY_CONSULT_SUCCESS_RATE': SURGERY_CONSULT_SUCCESS_RATE,
            'SURGERY_CONSULT_BENEFIT_RATE': SURGERY_CONSULT_BENEFIT_RATE,
            'SURGERY_CONSULT_TESTS': SURGERY_CONSULT_TESTS,
            'SURGERY_CONSULT_FOLLOWUP_DATE': SURGERY_CONSULT_FOLLOWUP_DATE,
            'SURGERY_CONSULT_FOLLOWUP_REASON': SURGERY_CONSULT_FOLLOWUP_REASON,
            'SURGERY_CONSULT_TRANSLATOR': SURGERY_CONSULT_TRANSLATOR,
            'OPERATION_DETAILS_AR': OPERATION_DETAILS_AR,
            'OPERATION_NAME_EN': OPERATION_NAME_EN,
            'OPERATION_NOTES': OPERATION_NOTES,
            'OPERATION_FOLLOWUP_DATE': OPERATION_FOLLOWUP_DATE,
            'OPERATION_FOLLOWUP_REASON': OPERATION_FOLLOWUP_REASON,
            'OPERATION_TRANSLATOR': OPERATION_TRANSLATOR,
            'FINAL_CONSULT_DIAGNOSIS': FINAL_CONSULT_DIAGNOSIS,
            'FINAL_CONSULT_DECISION': FINAL_CONSULT_DECISION,
            'FINAL_CONSULT_RECOMMENDATIONS': FINAL_CONSULT_RECOMMENDATIONS,
            'FINAL_CONSULT_TRANSLATOR': FINAL_CONSULT_TRANSLATOR,
            'DISCHARGE_TYPE': DISCHARGE_TYPE,
            'DISCHARGE_ADMISSION_SUMMARY': DISCHARGE_ADMISSION_SUMMARY,
            'DISCHARGE_OPERATION_DETAILS': DISCHARGE_OPERATION_DETAILS,
            'DISCHARGE_OPERATION_NAME_EN': DISCHARGE_OPERATION_NAME_EN,
            'DISCHARGE_FOLLOWUP_DATE': DISCHARGE_FOLLOWUP_DATE,
            'DISCHARGE_FOLLOWUP_REASON': DISCHARGE_FOLLOWUP_REASON,
            'DISCHARGE_TRANSLATOR': DISCHARGE_TRANSLATOR,
            'REHAB_TYPE': REHAB_TYPE,
            'PHYSICAL_THERAPY_DETAILS': PHYSICAL_THERAPY_DETAILS,
            'PHYSICAL_THERAPY_FOLLOWUP_DATE': PHYSICAL_THERAPY_FOLLOWUP_DATE,
            'PHYSICAL_THERAPY_FOLLOWUP_REASON': PHYSICAL_THERAPY_FOLLOWUP_REASON,
            'PHYSICAL_THERAPY_TRANSLATOR': PHYSICAL_THERAPY_TRANSLATOR,
            'DEVICE_NAME_DETAILS': DEVICE_NAME_DETAILS,
            'DEVICE_FOLLOWUP_DATE': DEVICE_FOLLOWUP_DATE,
            'DEVICE_FOLLOWUP_REASON': DEVICE_FOLLOWUP_REASON,
            'DEVICE_TRANSLATOR': DEVICE_TRANSLATOR,
            'RADIOLOGY_TYPE': RADIOLOGY_TYPE,
            'RADIOLOGY_DELIVERY_DATE': RADIOLOGY_DELIVERY_DATE,
            'RADIOLOGY_TRANSLATOR': RADIOLOGY_TRANSLATOR,
            'RADIOLOGY_CONFIRM': RADIOLOGY_CONFIRM,
            'APP_RESCHEDULE_REASON': APP_RESCHEDULE_REASON,
            'APP_RESCHEDULE_RETURN_DATE': APP_RESCHEDULE_RETURN_DATE,
            'APP_RESCHEDULE_RETURN_REASON': APP_RESCHEDULE_RETURN_REASON,
            'APP_RESCHEDULE_TRANSLATOR': APP_RESCHEDULE_TRANSLATOR,
            'APP_RESCHEDULE_CONFIRM': APP_RESCHEDULE_CONFIRM,
            # إضافة جميع states التأكيد
            'NEW_CONSULT_CONFIRM': NEW_CONSULT_CONFIRM,
            'FOLLOWUP_CONFIRM': FOLLOWUP_CONFIRM,
            'SURGERY_CONSULT_CONFIRM': SURGERY_CONSULT_CONFIRM,
            'EMERGENCY_CONFIRM': EMERGENCY_CONFIRM,
            'ADMISSION_CONFIRM': ADMISSION_CONFIRM,
            'OPERATION_CONFIRM': OPERATION_CONFIRM,
            'FINAL_CONSULT_CONFIRM': FINAL_CONSULT_CONFIRM,
            'DISCHARGE_CONFIRM': DISCHARGE_CONFIRM,
            'PHYSICAL_THERAPY_CONFIRM': PHYSICAL_THERAPY_CONFIRM,
            'DEVICE_CONFIRM': DEVICE_CONFIRM,
        }
        
        # بناء قاموس عكسي (قيمة -> اسم)
        value_to_state_name = {v: k for k, v in state_name_to_value.items()}
        
        logger.info(f"🔍 Looking for previous step: current_step={current_step}, type={type(current_step).__name__}")
        
        # تحويل current_step إلى اسم إذا كان رقماً
        if isinstance(current_step, int):
            current_step_name = value_to_state_name.get(current_step)
            logger.info(f"🔍 Converted int {current_step} to name: {current_step_name}")
            
            if current_step_name and current_step_name in flow_map:
                prev_step = flow_map[current_step_name]
                logger.info(f"✅ Found in flow_map: {current_step_name} -> {prev_step}")
                # تحويل اسم الخطوة السابقة إلى قيمة رقمية إذا كان نصاً
                if isinstance(prev_step, str) and prev_step in state_name_to_value:
                    result = state_name_to_value[prev_step]
                    logger.info(f"✅ Converted prev_step '{prev_step}' to int: {result}")
                    return result
                return prev_step
            else:
                logger.warning(f"⚠️ current_step_name '{current_step_name}' not found in flow_map for '{flow_type}'")
                logger.warning(f"⚠️ Available keys in flow_map: {list(flow_map.keys())}")
        elif isinstance(current_step, str) and current_step in flow_map:
            prev_step = flow_map[current_step]
            logger.info(f"✅ Found string key in flow_map: {current_step} -> {prev_step}")
            if isinstance(prev_step, str) and prev_step in state_name_to_value:
                return state_name_to_value[prev_step]
            return prev_step
        
        logger.warning(f"⚠️ Returning default STATE_SELECT_ACTION_TYPE for unhandled case")
        return STATE_SELECT_ACTION_TYPE  # الرجوع لقائمة نوع الإجراء

    def get_next_step(self, flow_type, current_step):
        """
        الحصول على الخطوة التالية (للتنقل للأمام إذا لزم)
        """
        if flow_type not in self.step_flows:
            return None

        flow_map = self.step_flows[flow_type]

        # العثور على الخطوة التالية
        for step_name, prev_step in flow_map.items():
            if prev_step == current_step:
                return step_name

        return None

    def set_search_context(self, search_type, query=None):
        """
        تعيين سياق البحث الحالي لمنع الخلطة
        """
        self.search_context = {
            'current_search_type': search_type,
            'search_query': query,
            'last_results': None
        }

    def get_search_context(self):
        """
        الحصول على سياق البحث الحالي
        """
        return self.search_context

    def clear_search_context(self):
        """
        مسح سياق البحث
        """
        self.search_context = {
            'current_search_type': None,
            'search_query': None,
            'last_results': None
        }

# إنشاء instance واحد من SmartNavigationManager
smart_nav_manager = SmartNavigationManager()

def get_translator_state(flow_type):
    """
    الحصول على حالة المترجم المناسبة حسب نوع التدفق
    """
    translator_states = {
        'new_consult': 'FOLLOWUP_TRANSLATOR',
        'followup': 'FOLLOWUP_TRANSLATOR',
        'emergency': 'EMERGENCY_TRANSLATOR',
        'operation': 'OPERATION_TRANSLATOR',
        'diagnosis': 'DIAGNOSIS_TRANSLATOR',
        'discharge': 'DISCHARGE_TRANSLATOR',
        'radiology': 'RADIOLOGY_TRANSLATOR',
        'physical_therapy': 'PHYSICAL_THERAPY_TRANSLATOR',
        'device': 'DEVICE_TRANSLATOR'
    }

    return translator_states.get(flow_type, 'FOLLOWUP_TRANSLATOR')

class SmartStateRenderer:
    """
    مدير ذكي لإعادة عرض الشاشات بعد الرجوع أو التعديل
    يضمن أن جميع البيانات والأسماء تظهر بشكل صحيح دائماً
    """

    @staticmethod
    async def render_patient_selection(message, context, search_query=""):
        """
        إعادة عرض شاشة اختيار المريض مع ضمان ظهور الأسماء دائماً
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info("🎯 Rendering patient selection with FRESH data")

        # تنظيف أي بيانات قديمة للمريض لضمان البداية من جديد
        PatientDataManager.clear_patient_data(context)

        # إعداد سياق البحث من جديد
        smart_nav_manager.set_search_context('patient')
        context.user_data['_current_search_type'] = 'patient'

        # تحديث الحالة بدقة
        context.user_data['_conversation_state'] = STATE_SELECT_PATIENT

        # التأكد من وجود report_tmp
        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        # إضافة علامة للتحقق من أن البيانات محدثة
        context.user_data['report_tmp']['_patient_data_fresh'] = True

        logger.info("✅ Patient selection fully refreshed and ready")
        # عرض شاشة المريض مع البحث
        await show_patient_selection(message, context, search_query)

    @staticmethod
    async def render_doctor_selection(message, context, search_query=""):
        """
        إعادة عرض شاشة اختيار الطبيب مع ضمان ظهور الأسماء دائماً
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info("🎯 Rendering doctor selection with FRESH data")

        # تنظيف أي بيانات قديمة للطبيب لضمان البداية من جديد
        DoctorDataManager.clear_doctor_data(context)

        # إعداد سياق البحث من جديد
        smart_nav_manager.set_search_context('doctor')
        context.user_data['_current_search_type'] = 'doctor'

        # تحديث الحالة بدقة
        context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

        # التأكد من وجود report_tmp
        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        # إضافة علامة للتحقق من أن البيانات محدثة
        context.user_data['report_tmp']['_doctor_data_fresh'] = True

        logger.info("✅ Doctor selection fully refreshed and ready")
        # عرض شاشة الطبيب مع البحث
        await show_doctor_input(message, context)

    @staticmethod
    async def render_translator_selection(message, context, flow_type):
        """
        إعادة عرض شاشة اختيار المترجم مع ضمان ظهور الأسماء دائماً
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info("🎯 Rendering translator selection with FRESH data")

        # تنظيف أي بيانات قديمة للمترجم لضمان البداية من جديد
        if 'report_tmp' in context.user_data:
            context.user_data['report_tmp'].pop('translator_name', None)
            context.user_data['report_tmp'].pop('translator_id', None)

        # تحديث الحالة بدقة
        translator_state = get_translator_state(flow_type)
        context.user_data['_conversation_state'] = translator_state

        # التأكد من وجود report_tmp
        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        # إضافة علامة للتحقق من أن البيانات محدثة
        context.user_data['report_tmp']['_translator_data_fresh'] = True

        logger.info("✅ Translator selection fully refreshed and ready")
        # عرض شاشة المترجم
        await show_translator_selection(message, context, flow_type)

    @staticmethod
    async def ensure_search_context(context, search_type):
        """
        التأكد من أن سياق البحث صحيح ومحدث دائماً
        """
        current_type = context.user_data.get('_current_search_type')
        if current_type != search_type:
            # إعادة تهيئة سياق البحث بالكامل
            smart_nav_manager.clear_search_context()
            smart_nav_manager.set_search_context(search_type)
            context.user_data['_current_search_type'] = search_type

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🔄 FORCE reset search context from {current_type} to {search_type}")

    @staticmethod
    async def validate_data_consistency(context):
        """
        التحقق من تناسق البيانات وإصلاح أي مشاكل
        """
        import logging
        logger = logging.getLogger(__name__)

        report_tmp = context.user_data.get('report_tmp', {})
        current_state = context.user_data.get('_conversation_state')

        # فحص تناسق بيانات المريض
        if current_state == STATE_SELECT_PATIENT:
            if not report_tmp.get('_patient_data_fresh'):
                logger.warning("⚠️ Patient data not fresh, forcing refresh")
                await SmartStateRenderer.ensure_search_context(context, 'patient')
                report_tmp['_patient_data_fresh'] = True

        # فحص تناسق بيانات الطبيب
        elif current_state == STATE_SELECT_DOCTOR:
            if not report_tmp.get('_doctor_data_fresh'):
                logger.warning("⚠️ Doctor data not fresh, forcing refresh")
                await SmartStateRenderer.ensure_search_context(context, 'doctor')
                report_tmp['_doctor_data_fresh'] = True

        # فحص تناسق بيانات المترجم
        elif 'TRANSLATOR' in str(current_state):
            if not report_tmp.get('_translator_data_fresh'):
                logger.warning("⚠️ Translator data not fresh, forcing refresh")
                flow_type = report_tmp.get('current_flow', 'new_consult')
                translator_state = get_translator_state(flow_type)
                context.user_data['_conversation_state'] = translator_state
                report_tmp['_translator_data_fresh'] = True

        logger.info("✅ Data consistency validated")

    @staticmethod
    async def force_data_refresh(context, data_type):
        """
        إجبار تحديث البيانات بالكامل
        """
        import logging
        logger = logging.getLogger(__name__)

        if data_type == 'all':
            # تحديث جميع البيانات
            PatientDataManager.clear_patient_data(context)
            DoctorDataManager.clear_doctor_data(context)
            smart_nav_manager.clear_search_context()

            if 'report_tmp' in context.user_data:
                context.user_data['report_tmp'].pop('translator_name', None)
                context.user_data['report_tmp'].pop('translator_id', None)

            logger.info("🔄 All data forcefully refreshed")

        elif data_type == 'patient':
            PatientDataManager.clear_patient_data(context)
            await SmartStateRenderer.ensure_search_context(context, 'patient')
            logger.info("🔄 Patient data forcefully refreshed")

        elif data_type == 'doctor':
            DoctorDataManager.clear_doctor_data(context)
            await SmartStateRenderer.ensure_search_context(context, 'doctor')
            logger.info("🔄 Doctor data forcefully refreshed")

        elif data_type == 'translator':
            if 'report_tmp' in context.user_data:
                context.user_data['report_tmp'].pop('translator_name', None)
                context.user_data['report_tmp'].pop('translator_id', None)
            logger.info("🔄 Translator data forcefully refreshed")

async def execute_smart_state_action(target_step, flow_type, update, context):
    """
    تنفيذ الإجراء المناسب للخطوة المستهدفة مع ضمان إعادة العرض الصحيح
    يتعامل مع جميع الخطوات في جميع التدفقات
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"🎯 Executing SMART action for step: {target_step}, flow: {flow_type}")
    
    # تحديث الـ conversation state
    context.user_data['_conversation_state'] = target_step
    
    # ربط قيم الـ states بأسمائها للمقارنة
    state_value_to_name = {
        NEW_CONSULT_COMPLAINT: 'COMPLAINT',
        NEW_CONSULT_DIAGNOSIS: 'DIAGNOSIS',
        NEW_CONSULT_DECISION: 'DECISION',
        NEW_CONSULT_TESTS: 'TESTS',
        NEW_CONSULT_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        NEW_CONSULT_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        NEW_CONSULT_TRANSLATOR: 'TRANSLATOR',
        FOLLOWUP_COMPLAINT: 'COMPLAINT',
        FOLLOWUP_DIAGNOSIS: 'DIAGNOSIS',
        FOLLOWUP_DECISION: 'DECISION',
        FOLLOWUP_DATE_TIME: 'FOLLOWUP_DATE',
        FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        FOLLOWUP_TRANSLATOR: 'TRANSLATOR',
        EMERGENCY_COMPLAINT: 'COMPLAINT',
        EMERGENCY_DIAGNOSIS: 'DIAGNOSIS',
        EMERGENCY_DECISION: 'DECISION',
        EMERGENCY_STATUS: 'STATUS',
        EMERGENCY_ADMISSION_TYPE: 'ADMISSION_TYPE',
        EMERGENCY_ROOM_NUMBER: 'ROOM',
        EMERGENCY_DATE_TIME: 'FOLLOWUP_DATE',
        EMERGENCY_REASON: 'FOLLOWUP_REASON',
        EMERGENCY_TRANSLATOR: 'TRANSLATOR',
        ADMISSION_REASON: 'REASON',
        ADMISSION_ROOM: 'ROOM',
        ADMISSION_NOTES: 'NOTES',
        ADMISSION_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        ADMISSION_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        ADMISSION_TRANSLATOR: 'TRANSLATOR',
        SURGERY_CONSULT_DIAGNOSIS: 'DIAGNOSIS',
        SURGERY_CONSULT_DECISION: 'DECISION',
        SURGERY_CONSULT_NAME_EN: 'NAME_EN',
        SURGERY_CONSULT_SUCCESS_RATE: 'SUCCESS_RATE',
        SURGERY_CONSULT_BENEFIT_RATE: 'BENEFIT_RATE',
        SURGERY_CONSULT_TESTS: 'TESTS',
        SURGERY_CONSULT_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        SURGERY_CONSULT_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        SURGERY_CONSULT_TRANSLATOR: 'TRANSLATOR',
        OPERATION_DETAILS_AR: 'DETAILS_AR',
        OPERATION_NAME_EN: 'NAME_EN',
        OPERATION_NOTES: 'NOTES',
        OPERATION_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        OPERATION_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        OPERATION_TRANSLATOR: 'TRANSLATOR',
        FINAL_CONSULT_DIAGNOSIS: 'DIAGNOSIS',
        FINAL_CONSULT_DECISION: 'DECISION',
        FINAL_CONSULT_RECOMMENDATIONS: 'RECOMMENDATIONS',
        FINAL_CONSULT_TRANSLATOR: 'TRANSLATOR',
        DISCHARGE_TYPE: 'DISCHARGE_TYPE',
        DISCHARGE_ADMISSION_SUMMARY: 'ADMISSION_SUMMARY',
        DISCHARGE_OPERATION_DETAILS: 'OPERATION_DETAILS',
        DISCHARGE_OPERATION_NAME_EN: 'NAME_EN',
        DISCHARGE_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        DISCHARGE_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        DISCHARGE_TRANSLATOR: 'TRANSLATOR',
        REHAB_TYPE: 'REHAB_TYPE',
        PHYSICAL_THERAPY_DETAILS: 'THERAPY_DETAILS',
        PHYSICAL_THERAPY_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        PHYSICAL_THERAPY_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        PHYSICAL_THERAPY_TRANSLATOR: 'TRANSLATOR',
        DEVICE_NAME_DETAILS: 'DEVICE_DETAILS',
        DEVICE_FOLLOWUP_DATE: 'FOLLOWUP_DATE',
        DEVICE_FOLLOWUP_REASON: 'FOLLOWUP_REASON',
        DEVICE_TRANSLATOR: 'TRANSLATOR',
        RADIOLOGY_TYPE: 'RADIOLOGY_TYPE',
        RADIOLOGY_DELIVERY_DATE: 'DELIVERY_DATE',
        RADIOLOGY_TRANSLATOR: 'TRANSLATOR',
        RADIOLOGY_CONFIRM: 'CONFIRM',
        APP_RESCHEDULE_REASON: 'RESCHEDULE_REASON',
        APP_RESCHEDULE_RETURN_DATE: 'RETURN_DATE',
        APP_RESCHEDULE_RETURN_REASON: 'RETURN_REASON',
        APP_RESCHEDULE_TRANSLATOR: 'TRANSLATOR',
        APP_RESCHEDULE_CONFIRM: 'CONFIRM',
        # جميع states التأكيد
        NEW_CONSULT_CONFIRM: 'CONFIRM',
        FOLLOWUP_CONFIRM: 'CONFIRM',
        SURGERY_CONSULT_CONFIRM: 'CONFIRM',
        EMERGENCY_CONFIRM: 'CONFIRM',
        ADMISSION_CONFIRM: 'CONFIRM',
        OPERATION_CONFIRM: 'CONFIRM',
        FINAL_CONSULT_CONFIRM: 'CONFIRM',
        DISCHARGE_CONFIRM: 'CONFIRM',
        PHYSICAL_THERAPY_CONFIRM: 'CONFIRM',
        DEVICE_CONFIRM: 'CONFIRM',
    }
    
    # تحويل target_step إلى نص لاستخدامه في المقارنة
    if isinstance(target_step, int):
        step_name = state_value_to_name.get(target_step, str(target_step))
    else:
        step_name = str(target_step)
    
    logger.info(f"🎯 Step name for comparison: {step_name}")

    try:
        # ============================================
        # الخطوات الأساسية المشتركة
        # ============================================
        if target_step == STATE_SELECT_DATE:
            from services.inline_calendar import create_date_selection_keyboard
            keyboard = create_date_selection_keyboard()
            await update.callback_query.edit_message_text(
                "📅 اختر تاريخ التقرير:",
                reply_markup=keyboard
            )
            return target_step

        elif target_step == STATE_SELECT_PATIENT:
            await SmartStateRenderer.ensure_search_context(context, 'patient')
            await SmartStateRenderer.render_patient_selection(update.callback_query.message, context)
            return target_step

        elif target_step == STATE_SELECT_HOSPITAL:
            await SmartStateRenderer.ensure_search_context(context, 'hospital')
            await show_hospitals_menu(update.callback_query.message, context)
            return target_step

        elif target_step == STATE_SELECT_DEPARTMENT:
            await SmartStateRenderer.ensure_search_context(context, 'department')
            await show_departments_menu(update.callback_query.message, context)
            return target_step

        elif target_step == STATE_SELECT_SUBDEPARTMENT:
            await SmartStateRenderer.ensure_search_context(context, 'subdepartment')
            main_dept = context.user_data.get('report_tmp', {}).get('main_department', 'الجراحة')
            await show_subdepartment_options(update.callback_query.message, context, main_dept)
            return target_step

        elif target_step == STATE_SELECT_DOCTOR:
            await SmartStateRenderer.ensure_search_context(context, 'doctor')
            await SmartStateRenderer.render_doctor_selection(update.callback_query.message, context)
            return target_step

        elif target_step == STATE_SELECT_ACTION_TYPE:
            await show_action_type_menu(update.callback_query.message, context)
            return target_step

        # ============================================
        # خطوات المترجم
        # ============================================
        elif 'TRANSLATOR' in step_name:
            await SmartStateRenderer.render_translator_selection(update.callback_query.message, context, flow_type)
            return target_step

        # ============================================
        # خطوات تاريخ العودة - إظهار التقويم
        # ============================================
        elif 'FOLLOWUP_DATE' in step_name or 'DELIVERY_DATE' in step_name or 'RETURN_DATE' in step_name:
            # تحديد نوع التقويم المناسب
            if 'DELIVERY_DATE' in step_name and flow_type == 'radiology':
                # تقويم خاص بالأشعة
                await _render_radiology_calendar(update.callback_query.message, context)
            elif 'RETURN_DATE' in step_name and flow_type == 'app_reschedule':
                # تقويم خاص بتأجيل المواعيد
                await _show_reschedule_calendar(update.callback_query.message, context)
            else:
                # تقويم المتابعة العادي
                await _render_followup_calendar(update.callback_query.message, context)
            return target_step

        # ============================================
        # خطوات سبب العودة
        # ============================================
        elif 'FOLLOWUP_REASON' in step_name or 'RETURN_REASON' in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل سبب موعد المتابعة:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات الشكوى
        # ============================================
        elif 'COMPLAINT' in step_name:
            await update.callback_query.edit_message_text(
                "💬 أدخل شكوى المريض:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات التشخيص
        # ============================================
        elif 'DIAGNOSIS' in step_name:
            await update.callback_query.edit_message_text(
                "🔬 أدخل التشخيص الطبي:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات القرار
        # ============================================
        elif 'DECISION' in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل قرار الطبيب:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات الفحوصات
        # ============================================
        elif 'TESTS' in step_name:
            await update.callback_query.edit_message_text(
                "🔬 أدخل الفحوصات المطلوبة:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات نوع العملية
        # ============================================
        elif 'NAME_EN' in step_name:
            await update.callback_query.edit_message_text(
                "🏥 أدخل اسم العملية بالإنجليزية:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات تفاصيل العملية
        # ============================================
        elif 'DETAILS_AR' in step_name or 'OPERATION_DETAILS' in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل تفاصيل العملية:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات الملاحظات
        # ============================================
        elif 'NOTES' in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل الملاحظات:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات الغرفة
        # ============================================
        elif 'ROOM' in step_name:
            await update.callback_query.edit_message_text(
                "🏥 أدخل رقم الغرفة:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات السبب (Admission, Reschedule, etc.)
        # ============================================
        elif 'REASON' in step_name and 'FOLLOWUP' not in step_name and 'RETURN' not in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل السبب:",
                reply_markup=_nav_buttons()
            )
            return target_step
        
        # ============================================
        # خطوات سبب التأجيل
        # ============================================
        elif 'RESCHEDULE_REASON' in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل سبب تأجيل الموعد:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات نسبة النجاح
        # ============================================
        elif 'SUCCESS_RATE' in step_name:
            await update.callback_query.edit_message_text(
                "📊 أدخل نسبة نجاح العملية:",
                reply_markup=_nav_buttons()
            )
            return target_step
        
        # ============================================
        # خطوات نسبة الفائدة
        # ============================================
        elif 'BENEFIT_RATE' in step_name:
            await update.callback_query.edit_message_text(
                "📊 أدخل نسبة الفائدة المتوقعة:",
                reply_markup=_nav_buttons()
            )
            return target_step
        
        # ============================================
        # خطوات التوصيات
        # ============================================
        elif 'RECOMMENDATIONS' in step_name:
            await update.callback_query.edit_message_text(
                "📝 أدخل التوصيات الطبية:",
                reply_markup=_nav_buttons()
            )
            return target_step

        # ============================================
        # خطوات نوع (REHAB_TYPE, DISCHARGE_TYPE, etc.)
        # ============================================
        elif 'TYPE' in step_name and target_step != STATE_SELECT_ACTION_TYPE:
            # عرض خيارات النوع حسب التدفق
            if 'REHAB' in step_name:
                await update.callback_query.edit_message_text(
                    "🏥 اختر نوع العلاج الطبيعي:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💪 جلسات علاج طبيعي", callback_data="rehab_type:physical")],
                        [InlineKeyboardButton("🦿 أجهزة تعويضية", callback_data="rehab_type:device")],
                        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                    ])
                )
            elif 'DISCHARGE' in step_name:
                await update.callback_query.edit_message_text(
                    "🏥 اختر نوع الخروج:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ خروج عادي", callback_data="discharge_type:normal")],
                        [InlineKeyboardButton("⚠️ خروج ضد النصيحة الطبية", callback_data="discharge_type:ama")],
                        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                    ])
                )
            elif 'RADIOLOGY' in step_name:
                # إدخال نص لنوع الأشعة (مثل start_radiology_flow)
                await update.callback_query.edit_message_text(
                    "🔬 **نوع الأشعة والفحوصات**\n\n"
                    "يرجى إدخال نوع الأشعة أو الفحوصات:",
                    reply_markup=_nav_buttons(show_back=True),
                    parse_mode="Markdown"
                )
            else:
                await update.callback_query.edit_message_text(
                    "📝 اختر النوع:",
                    reply_markup=_nav_buttons()
                )
            return target_step

        # ============================================
        # خطوات الحالة (STATUS)
        # ============================================
        elif 'STATUS' in step_name:
            await update.callback_query.edit_message_text(
                "📊 اختر حالة المريض:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏥 تم ترقيده", callback_data="status:admitted")],
                    [InlineKeyboardButton("✅ تم صرفه", callback_data="status:discharged")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                ])
            )
            return target_step

        # ============================================
        # خطوات التأكيد - إعادة عرض الملخص
        # ============================================
        elif 'CONFIRM' in step_name:
            await show_final_summary(update.callback_query.message, context, flow_type)
            return target_step

        # ============================================
        # خطوات ملخص الترقيد
        # ============================================
        elif 'ADMISSION_SUMMARY' in step_name:
            await update.callback_query.edit_message_text(
                "📋 أدخل ملخص فترة الترقيد:",
                reply_markup=_nav_buttons()
            )
            return target_step
        
        # ============================================
        # خطوات تفاصيل العلاج الطبيعي
        # ============================================
        elif 'THERAPY_DETAILS' in step_name:
            await update.callback_query.edit_message_text(
                "💪 أدخل تفاصيل جلسات العلاج الطبيعي:",
                reply_markup=_nav_buttons()
            )
            return target_step
        
        # ============================================
        # خطوات تفاصيل الجهاز التعويضي
        # ============================================
        elif 'DEVICE_DETAILS' in step_name:
            await update.callback_query.edit_message_text(
                "🦿 أدخل تفاصيل الجهاز التعويضي:",
                reply_markup=_nav_buttons()
            )
            return target_step

        else:
            # خطوة غير معروفة
            logger.warning(f"⚠️ Unknown target step: {target_step}")
            await update.callback_query.edit_message_text(
                f"⚠️ خطأ في التنقل\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                ]])
            )
            return target_step

    except Exception as e:
        logger.error(f"❌ Error in execute_smart_state_action: {e}", exc_info=True)
        try:
            await update.callback_query.edit_message_text(
                "❌ حدث خطأ في إعادة العرض\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                ]])
            )
        except:
            pass
        return target_step

async def handle_smart_back_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج زر الرجوع الذكي - يرجع خطوة واحدة فقط بدقة
    يحل مشكلة الخلطة في أزرار البحث ويضمن الرجوع الصحيح
    """
    import logging
    logger = logging.getLogger(__name__)

    query = update.callback_query
    if not query:
        logger.error("❌ handle_smart_back_navigation: No query found")
        return ConversationHandler.END

    await query.answer()

    logger.info("=" * 80)
    logger.info("🔙 SMART BACK NAVIGATION TRIGGERED")
    logger.info("=" * 80)

    try:
        # الحصول على البيانات الحالية
        current_state = context.user_data.get('_conversation_state')
        flow_type = context.user_data.get('report_tmp', {}).get('current_flow', 'new_consult')

        logger.info(f"🔙 Current state: {current_state}")
        logger.info(f"🔙 Flow type: {flow_type}")

        # الحصول على الخطوة السابقة باستخدام SmartNavigationManager
        previous_step = smart_nav_manager.get_previous_step(flow_type, current_state)

        logger.info(f"🔙 Previous step determined: {previous_step}")

        if previous_step is None:
            # الرجوع للبداية
            logger.info("🔙 No previous step, going to start")
            await start_report(update, context)
            return STATE_SELECT_DATE

        # تحديث الـ conversation state
        context.user_data['_conversation_state'] = previous_step

        # تنفيذ الإجراء المناسب للخطوة السابقة
        await execute_smart_state_action(previous_step, flow_type, update, context)

        logger.info(f"🔙 Successfully went back to {previous_step}")
        return previous_step

    except Exception as e:
        logger.error(f"❌ Error in handle_smart_back_navigation: {e}", exc_info=True)
        # في حالة الخطأ، الرجوع للبداية بأمان
        await start_report(update, context)
        return STATE_SELECT_DATE

# الدوال القديمة تم استبدالها بـ Smart Navigation System

async def handle_back_navigation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """
    معالج زر الرجوع الذكي - يستخدم SmartNavigationManager
    يرجع خطوة واحدة فقط بدقة ويحل مشكلة الخلطة في أزرار البحث
    """
    # استدعاء النظام الذكي الجديد
    return await handle_smart_back_navigation(update, context)


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

def _get_patients_from_database():
    """جلب أسماء المرضى من الخدمة الموحدة - مرتبة أبجدياً"""
    try:
        from services.patients_service import get_all_patients
        patients = get_all_patients()
        if patients:
            # ترتيب المرضى أبجدياً حسب الاسم
            patients_list = [(p['id'], p['name']) for p in patients if p.get('name')]
            patients_list.sort(key=lambda x: x[1])  # ترتيب حسب الاسم
            return patients_list
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ فشل تحميل المرضى: {e}")
    
    return []


def _build_patients_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح المرضى مع صفحات"""
    items_per_page = 8

    # جلب المرضى من قاعدة البيانات
    all_patients = _get_patients_from_database()

    # تصفية المرضى إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        filtered_patients = [(pid, name) for pid, name in all_patients if search_lower in name.lower()]
        patients_list = filtered_patients
    else:
        patients_list = all_patients

    total = len(patients_list)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)

    keyboard = []

    # حفظ قائمة المرضى في user_data للوصول إليها لاحقاً
    if context:
        context.user_data.setdefault("report_tmp", {})["patients_list"] = patients_list
        context.user_data["report_tmp"]["patients_page"] = page

    # عرض المرضى (سطر واحد لكل مريض)
    for i in range(start_idx, end_idx):
        patient_id, patient_name = patients_list[i]
        keyboard.append([InlineKeyboardButton(
            f"👤 {patient_name}",
            callback_data=f"patient_idx:{patient_id}"
        )])

    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                "⬅️ السابق",
                callback_data=f"user_patient_page:{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(
            f"📄 {page + 1}/{total_pages}",
            callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                "➡️ التالي",
                callback_data=f"user_patient_page:{page + 1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

    # ✅ أزرار البحث والتنقل
    # زر البحث في صف منفصل واضح
    # استخدام switch_inline_query_current_chat مع نص افتراضي لضمان فتح البحث
    keyboard.append([
        InlineKeyboardButton(
            "🔍 بحث عن مريض",
            switch_inline_query_current_chat="بحث: "
        )
    ])
    
    keyboard.append([InlineKeyboardButton(
        "❌ إلغاء", callback_data="nav:cancel")])

    text = (
        f"👤 **اختيار المريض** (الخطوة 2 من 5)\n\n"
        f"📋 **العدد:** {total} مريض"
    )
    if search_query:
        text += f"\n🔍 **البحث:** {search_query}"
    text += f"\n📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
    text += "**اختر اسم المريض من القائمة أو استخدم زر البحث:**"

    return text, InlineKeyboardMarkup(keyboard), search_query


async def render_patient_selection(message, context, page=0, search_query=""):
    """عرض شاشة اختيار المريض - rendering فقط مع قائمة أزرار"""
    text, keyboard, _ = _build_patients_keyboard(page, search_query, context)
    
    await message.reply_text(
        text,
        reply_markup=keyboard,
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

# =============================
# خدمة الأطباء الموحدة - فلترة دقيقة وسريعة
# =============================

def _get_doctors_from_database(hospital_name: str = "", department_name: str = ""):
    """
    جلب الأطباء من قاعدة البيانات الموحدة مع فلترة دقيقة
    """
    try:
        from services.doctors_service import get_doctors_for_selection
        doctors = get_doctors_for_selection(hospital_name, department_name)
        logger.info(f"تم جلب {len(doctors)} طبيب من الخدمة الموحدة")
        return doctors
    except ImportError:
        logger.warning("خدمة الأطباء غير متوفرة، استخدام الطريقة القديمة")
        return _get_doctors_fallback(hospital_name, department_name)
    except Exception as e:
        logger.error(f"خطأ في جلب الأطباء: {e}")
        return []


def _get_doctors_fallback(hospital_name: str = "", department_name: str = ""):
    """طريقة احتياطية لجلب الأطباء من ملف doctors.txt"""
    doctors_list = []
    
    try:
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'doctors.txt'),
            'data/doctors.txt',
        ]
        
        txt_file = None
        for path in possible_paths:
            if os.path.exists(path):
                txt_file = path
                break
        
        if not txt_file:
            return []
        
        with open(txt_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        hospital_lower = hospital_name.lower() if hospital_name else ""
        dept_lower = department_name.lower() if department_name else ""
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('|')
            if len(parts) >= 4:
                doc_name = parts[0].strip()
                doc_hospital = parts[1].strip()
                doc_dept_ar = parts[2].strip()
                doc_dept_en = parts[3].strip()
                
                # فلترة
                if hospital_lower and hospital_lower not in doc_hospital.lower():
                    continue
                if dept_lower and dept_lower not in doc_dept_ar.lower() and dept_lower not in doc_dept_en.lower():
                    continue
                
                doctors_list.append({
                    'name': doc_name,
                    'hospital': doc_hospital,
                    'department_ar': doc_dept_ar,
                    'department_en': doc_dept_en
                })
    except Exception as e:
        logger.warning(f"خطأ في الطريقة الاحتياطية: {e}")
    
    return sorted(doctors_list, key=lambda x: x['name'])


def _build_doctors_keyboard(page: int, doctors: list, context):
    """
    بناء لوحة مفاتيح الأطباء مع التصفح (pagination)
    """
    DOCTORS_PER_PAGE = 8
    total_doctors = len(doctors)
    total_pages = max(1, (total_doctors + DOCTORS_PER_PAGE - 1) // DOCTORS_PER_PAGE)
    
    # التأكد من أن الصفحة في النطاق الصحيح
    page = max(0, min(page, total_pages - 1))
    
    # حفظ قائمة الأطباء في context
    context.user_data['_doctors_list'] = doctors
    context.user_data['_doctors_page'] = page
    
    keyboard = []
    
    if total_doctors > 0:
        # حساب نطاق الأطباء للصفحة الحالية
        start_idx = page * DOCTORS_PER_PAGE
        end_idx = min(start_idx + DOCTORS_PER_PAGE, total_doctors)
        
        # أزرار الأطباء (2 في كل صف)
        row = []
        for i in range(start_idx, end_idx):
            doctor = doctors[i]
            btn = InlineKeyboardButton(
                f"👨‍⚕️ {doctor['name'][:25]}",
                callback_data=f"doctor_idx:{i}"
            )
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        
        # إضافة الصف الأخير إذا كان فيه أزرار
        if row:
            keyboard.append(row)
        
        # أزرار التنقل بين الصفحات
        if total_pages > 1:
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"doctor_page:{page-1}"))
            nav_row.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
            if page < total_pages - 1:
                nav_row.append(InlineKeyboardButton("➡️ التالي", callback_data=f"doctor_page:{page+1}"))
            keyboard.append(nav_row)
    
    # زر الإدخال اليدوي دائماً
    keyboard.append([InlineKeyboardButton("✏️ إدخال يدوي", callback_data="doctor_manual")])
    
    # زر الإلغاء
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
    
    return InlineKeyboardMarkup(keyboard), total_doctors


async def render_doctor_selection(message, context, page=0):
    """عرض شاشة اختيار الطبيب - نظام الأزرار مع فلترة"""

    # تنظيف بيانات الطبيب القديمة
    DoctorDataManager.clear_doctor_data(context)

    # التحقق من وجود بيانات المستشفى والقسم
    report_tmp = context.user_data.get("report_tmp", {})
    hospital_name = report_tmp.get("hospital_name", "")
    department_name = report_tmp.get("department_name", "")

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🎯 render_doctor_selection: hospital='{hospital_name}', department='{department_name}'")

    # جلب الأطباء المفلترين من قاعدة البيانات
    doctors = _get_doctors_from_database(hospital_name, department_name)
    
    # بناء الكيبورد
    keyboard, total_doctors = _build_doctors_keyboard(page, doctors, context)

    # بناء النص
    text = "👨‍⚕️ **اسم الطبيب** (الخطوة 5 من 5)\n\n"

    if hospital_name:
        text += f"🏥 **المستشفى:** {hospital_name}\n"
    if department_name:
        text += f"🏷️ **القسم:** {department_name}\n"
    
    text += "\n"
    
    if total_doctors > 0:
        text += f"📋 **عدد الأطباء:** {total_doctors}\n\n"
        text += "👇 اختر الطبيب من القائمة أدناه:\n"
        text += "أو اضغط '✏️ إدخال يدوي' إذا لم يكن الطبيب موجوداً."
    else:
        text += "⚠️ **لا يوجد أطباء مسجلين لهذا المستشفى/القسم**\n\n"
        text += "👇 اضغط '✏️ إدخال يدوي' لإدخال اسم الطبيب.\n"
        text += "سيتم حفظه تلقائياً للاستخدام المستقبلي."

    try:
        await message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة اختيار الطبيب: {e}", exc_info=True)
        try:
            await message.reply_text(
                text.replace("**", ""),
                reply_markup=keyboard
            )
        except Exception as e2:
            logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")

# =============================
# الخطوات الأساسية المشتركة
# =============================


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة تقرير جديد - يدعم النص والأزرار"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"start_report called by user {update.effective_user.id if update.effective_user else 'N/A'}")
        
        # معالجة CallbackQuery إذا كان موجوداً
        query = update.callback_query
        if query:
            await query.answer()
        
        if not await ensure_approved(update, context):
            return ConversationHandler.END

        # تهيئة State History Manager
        state_manager = StateHistoryManager()
        state_manager.push_state(STATE_SELECT_DATE)

        # تهيئة البيانات مع State Manager - تنظيف كامل قبل البدء
        context.user_data["report_tmp"] = {
            "state_manager": state_manager,
            "action_type": None
        }
        # ✅ حفظ معرف المستخدم لاستخدامه عند حفظ التقرير
        context.user_data['_user_id'] = update.effective_user.id if update.effective_user else None
        
        # مسح أي حالة سابقة
        context.user_data.pop('_conversation_state', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('current_report_data', None)

        # تحديث الـ conversation state
        context.user_data['_conversation_state'] = STATE_SELECT_DATE

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 إدخال التاريخ الحالي",
            callback_data="date:now")],
            [InlineKeyboardButton("📅 إدخال من التقويم",
            callback_data="date:calendar")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])

        text = "📅 **إضافة تقرير جديد**\n\n" \
               "اختر طريقة إدخال التاريخ:"

        # إرسال الرسالة - دعم كلا الحالتين (نص أو زر)
        if query:
            try:
                await query.edit_message_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception:
                # إذا فشل التعديل، نرسل رسالة جديدة
                await query.message.reply_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
        logger.info("start_report completed successfully")
        return STATE_SELECT_DATE
    except Exception as e:
        logger.error(f"Error in start_report: {e}", exc_info=True)
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message:
            try:
                await message.reply_text("❌ حدث خطأ في بدء العملية، يرجى المحاولة مرة أخرى.")
            except:
                pass
        return ConversationHandler.END


async def handle_date_choice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التاريخ"""
    query = update.callback_query
    await query.answer()

    if query.data == "date:now":
        # استخدام توقيت الهند مباشرة (IST = UTC+5:30)
        try:
            tz = ZoneInfo("Asia/Kolkata")  # توقيت الهند مباشرة
            now = datetime.now(tz)
        except Exception:
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

    date_str = query.data.split(":", 1)[1]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        context.user_data["report_tmp"]["_pending_date"] = dt
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DATE)

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

        await query.edit_message_text(
            f"✅ **تم حفظ التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{dt.strftime('%d')} {MONTH_NAMES_AR.get(dt.month, dt.month)} {dt.year} ({day_name})"
        )
        await show_patient_selection(query.message, context)
        return STATE_SELECT_PATIENT

    await query.answer("خطأ: لم يتم تحديد التاريخ", show_alert=True)
    return R_DATE_TIME


async def show_patient_selection(message, context, search_query="", page=0):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    # تحديث State History - إضافة الـ state الحالي
    state_manager = StateHistoryManager.get_state_manager(context)
    state_manager.push_state(STATE_SELECT_PATIENT)

    # تحديث الـ conversation state للـ inline queries
    context.user_data['_conversation_state'] = STATE_SELECT_PATIENT
    context.user_data['_current_search_type'] = 'patient'  # علامة لتحديد نوع البحث

    # استدعاء rendering function
    await render_patient_selection(message, context, page, search_query)


async def handle_patient_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المريض من القائمة"""
    query = update.callback_query
    await query.answer()

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


async def handle_patient_btn_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المريض من زر القائمة (patient_idx:)"""
    query = update.callback_query
    await query.answer()

    # استخراج معرف المريض
    patient_id = query.data.split(":", 1)[1]

    # جلب اسم المريض من القائمة المحفوظة
    report_tmp = context.user_data.get("report_tmp", {})
    patients_list = report_tmp.get("patients_list", [])

    patient_name = None
    try:
        patient_id_int = int(patient_id)
        # البحث في قائمة المرضى
        for pid, pname in patients_list:
            if pid == patient_id_int:
                patient_name = pname
                break
        
        # إذا لم نجد في القائمة المحفوظة، نبحث في قاعدة البيانات
        if not patient_name:
            with SessionLocal() as s:
                patient = s.query(Patient).filter_by(id=patient_id_int).first()
                if patient:
                    patient_name = patient.full_name
    except (ValueError, TypeError):
        # إذا كان ID ليس رقماً، نستخدمه كاسم مباشرة
        patient_name = patient_id

    if patient_name:
        context.user_data.setdefault("report_tmp", {})["patient_name"] = patient_name
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_PATIENT)
        context.user_data["report_tmp"].pop("patient_search_mode", None)

        await query.edit_message_text(
            f"✅ **تم اختيار المريض**\n\n"
            f"👤 **المريض:**\n"
            f"{patient_name}",
            parse_mode="Markdown"
        )
        await show_hospitals_menu(query.message, context)
        return STATE_SELECT_HOSPITAL
    else:
        await query.answer("⚠️ خطأ: لم يتم العثور على المريض", show_alert=True)
        text, keyboard, _ = _build_patients_keyboard(0, "", context)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        return STATE_SELECT_PATIENT


async def handle_patient_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة التنقل بين صفحات المرضى - للمستخدم"""
    query = update.callback_query
    await query.answer()

    # استخراج رقم الصفحة من user_patient_page:X
    page = int(query.data.split(":", 1)[1])

    # بناء لوحة المفاتيح للصفحة المطلوبة
    text, keyboard, _ = _build_patients_keyboard(page, "", context)

    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return STATE_SELECT_PATIENT


async def handle_patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المريض يدوياً أو اختياره من inline query"""
    import logging
    import sys
    logger = logging.getLogger(__name__)

    # Diagnostic logging: capture incoming update and current report_tmp
    try:
        msg_text = update.message.text if hasattr(update, 'message') and update.message else None
    except Exception:
        msg_text = None
    logger.info(f"DEBUG handle_patient called: update.message_present={hasattr(update,'message') and update.message is not None}, message_text={repr(msg_text)}, user_id={(update.effective_user.id if update.effective_user else None)}")
    try:
        logger.info(f"DEBUG report_tmp snapshot: {context.user_data.get('report_tmp', {})}")
    except Exception:
        logger.info("DEBUG report_tmp snapshot: <unavailable>")
    
    # التحقق أولاً إذا كان المريض تم اختياره بالفعل
    report_tmp = context.user_data.get("report_tmp", {})
    if report_tmp.get("patient_name"):
        # المريض تم اختياره بالفعل، الانتقال إلى خطوة المستشفى
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
                    logger.info(f"handle_patient: Patient selected from inline query: {patient_name}, moving to hospital")
                except UnicodeEncodeError:
                    # في حالة خطأ الترميز، استخدم repr
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
    # إذا المستخدم أدخل اسمًا يدوياً (نص عادي)، نقبله كمريض جديد ونمضي للخطوة التالية
    if text:
        try:
            # حفظ اسم المريض بدون رقم تعريف (سيتم إنشاؤه لاحقًا عند الحفظ)
            context.user_data.setdefault("report_tmp", {})["patient_name"] = text
            context.user_data.setdefault("report_tmp", {})["patient_id"] = None
            context.user_data["report_tmp"].setdefault("step_history", []).append(R_PATIENT)

            try:
                await update.message.delete()
            except:
                pass

            await update.message.reply_text(
                f"✅ **تم إدخال اسم المريض**\n\n"
                f"👤 **المريض:**\n"
                f"{text}",
                parse_mode="Markdown"
            )

            await show_hospitals_menu(update.message, context)
            return STATE_SELECT_HOSPITAL
        except Exception as ex:
            logger.error(f"handle_patient: Error handling manual patient input: {ex}", exc_info=True)
            await show_patient_selection(update.message, context)
            return STATE_SELECT_PATIENT

    logger.info("handle_patient: No patient selected, showing patient selection menu")
    await show_patient_selection(update.message, context)
    return STATE_SELECT_PATIENT


def _sort_hospitals_custom(hospitals_list):
    """
    تم تعطيل الترتيب التلقائي - الآن يتم الاحتفاظ بالترتيب من ملف doctors_unified.json
    الترتيب المخصص من المستخدم محفوظ في ملف البيانات
    """
    # إرجاع القائمة كما هي بدون ترتيب
    return list(hospitals_list)

def _sort_hospitals_custom_OLD_DISABLED(hospitals_list):
    """ترتيب المستشفيات حسب الأولوية: Manipal -> Aster -> Bangalore -> البقية - معطل"""
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


def _get_hospitals_from_database_or_predefined():
    """جلب المستشفيات من الخدمة الموحدة"""
    try:
        from services.hospitals_service import get_all_hospitals
        hospitals = get_all_hospitals()
        if hospitals:
            return hospitals
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ فشل تحميل المستشفيات: {e}")
    # Fallback: استخدام القائمة الثابتة
    return PREDEFINED_HOSPITALS.copy()


def _build_hospitals_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح المستشفيات مع بحث"""
    items_per_page = 8

    # جلب المستشفيات من قاعدة البيانات أو القائمة الثابتة
    all_hospitals = _get_hospitals_from_database_or_predefined()

    # تصفية المستشفيات إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        filtered_hospitals = [
    h for h in all_hospitals if search_lower in h.lower()]
        hospitals_list = _sort_hospitals_custom(filtered_hospitals)
    else:
        hospitals_list = _sort_hospitals_custom(all_hospitals)

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
    keyboard.append([InlineKeyboardButton(
        "❌ إلغاء", callback_data="nav:cancel")])

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

    if query.data.startswith("hosp_search"):
        await query.edit_message_text(
            "🔍 **البحث عن المستشفى**\n\n"
            "يرجى إدخال كلمة البحث:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]]),
            parse_mode="Markdown"
        )
        context.user_data["report_tmp"]["hospitals_search_mode"] = True
        return STATE_SELECT_HOSPITAL

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

    # ✅ التأكد من وجود report_tmp
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}
    
    # ✅ حفظ اسم المستشفى مع logging
    context.user_data["report_tmp"]["hospital_name"] = choice
    logger.info(f"✅ تم حفظ المستشفى: {choice}")
    context.user_data["report_tmp"].pop("hospitals_search", None)
    context.user_data["report_tmp"].pop("hospitals_search_mode", None)
    context.user_data["report_tmp"].pop("hospitals_list", None)
    # State history is managed by StateHistoryManager now

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

    # ✅ التأكد من وجود report_tmp
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}
    
    # ✅ تم نقل "أشعة وفحوصات" إلى قائمة أنواع الإجراءات
    # لا حاجة لمعالج خاص هنا - يجب اختيارها من قائمة أنواع الإجراءات

    # التحقق إذا كان القسم المختار هو قسم رئيسي يحتوي على فروع
    if dept in PREDEFINED_DEPARTMENTS:
        # القسم الرئيسي يحتوي على فروع - عرض الفروع
        context.user_data["report_tmp"]["main_department"] = dept
        logger.info(f"✅ تم حفظ القسم الرئيسي: {dept}")
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
        logger.info(f"✅ تم حفظ القسم: {dept}")
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DEPARTMENT)
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
        "🔙 رجوع", callback_data="subdept:back")])
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

    # ✅ التأكد من وجود report_tmp
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}
    
    context.user_data["report_tmp"]["department_name"] = choice
    logger.info(f"✅ تم حفظ القسم الفرعي: {choice}")
    context.user_data["report_tmp"].setdefault("step_history", []).append(R_SUBDEPARTMENT)

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


async def handle_doctor_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التنقل بين صفحات الأطباء"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = int(query.data.split(":")[1])
    
    # جلب قائمة الأطباء المحفوظة
    doctors = context.user_data.get('_doctors_list', [])
    
    # بناء الكيبورد الجديد
    keyboard, total_doctors = _build_doctors_keyboard(page, doctors, context)
    
    # تحديث الرسالة
    report_tmp = context.user_data.get("report_tmp", {})
    hospital_name = report_tmp.get("hospital_name", "")
    department_name = report_tmp.get("department_name", "")
    
    text = "👨‍⚕️ **اسم الطبيب** (الخطوة 5 من 5)\n\n"
    if hospital_name:
        text += f"🏥 **المستشفى:** {hospital_name}\n"
    if department_name:
        text += f"🏷️ **القسم:** {department_name}\n"
    text += f"\n📋 **عدد الأطباء:** {total_doctors}\n\n"
    text += "👇 اختر الطبيب من القائمة أدناه:"
    
    try:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        pass
    
    return STATE_SELECT_DOCTOR


async def handle_doctor_btn_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار طبيب من الأزرار"""
    query = update.callback_query
    await query.answer("✅ تم اختيار الطبيب")
    
    import logging
    logger = logging.getLogger(__name__)
    
    # استخراج index الطبيب
    idx = int(query.data.split(":")[1])
    
    # جلب الطبيب من القائمة المحفوظة
    doctors = context.user_data.get('_doctors_list', [])
    
    if idx < len(doctors):
        doctor = doctors[idx]
        doctor_name = doctor['name']
        
        # ✅ حفظ اسم الطبيب مع logging
        if "report_tmp" not in context.user_data:
            context.user_data["report_tmp"] = {}
        context.user_data["report_tmp"]["doctor_name"] = doctor_name
        logger.info(f"✅ تم حفظ الطبيب: {doctor_name}")
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
        context.user_data["report_tmp"].pop("doctor_manual_mode", None)
        
        logger.info(f"✅ تم اختيار الطبيب: {doctor_name}")
        
        # إرسال رسالة تأكيد
        await query.edit_message_text(
            f"✅ **تم اختيار الطبيب**\n\n"
            f"👨‍⚕️ **الطبيب:** {doctor_name}",
            parse_mode="Markdown"
        )
        
        # الانتقال لخطوة نوع الإجراء
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        await show_action_type_menu(query.message, context)
        return R_ACTION_TYPE
    else:
        await query.edit_message_text("❌ خطأ في اختيار الطبيب، يرجى المحاولة مرة أخرى")
        return STATE_SELECT_DOCTOR


async def handle_doctor_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار زر الإدخال اليدوي"""
    query = update.callback_query
    await query.answer()
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 handle_doctor_selection: callback_data='{query.data}'")

    if query.data == "doctor_manual":
        # ✅ التأكد من وجود report_tmp
        if "report_tmp" not in context.user_data:
            context.user_data["report_tmp"] = {}
        
        logger.info("🔧 تم الضغط على زر الإدخال اليدوي للطبيب")
        
        try:
            await query.edit_message_text(
                "👨‍⚕️ **اسم الطبيب**\n\n"
                "✏️ يرجى إدخال اسم الطبيب:\n\n"
                "💡 سيتم حفظ الاسم تلقائياً للاستخدام المستقبلي.",
                reply_markup=_nav_buttons(show_back=False),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
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
        return STATE_SELECT_DOCTOR


async def handle_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم الطبيب يدوياً"""
    import logging
    logger = logging.getLogger(__name__)
    
    text = update.message.text.strip()
    logger.info(f"🔍 handle_doctor: received text='{text}'")
    
    # ✅ التأكد من وجود report_tmp
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}

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

        # ✅ حفظ اسم الطبيب في report_tmp
        context.user_data["report_tmp"]["doctor_name"] = text
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
        context.user_data["report_tmp"].pop("doctor_manual_mode", None)
        logger.info(f"✅ تم حفظ اسم الطبيب يدوياً: {text}")
        
        # ✅ حفظ الطبيب في قاعدة البيانات الموحدة (JSON)
        report_tmp = context.user_data.get("report_tmp", {})
        hospital_name = report_tmp.get("hospital_name", "")
        department_name = report_tmp.get("department_name", "")
        
        try:
            from services.doctors_service import add_doctor
            if add_doctor(text, hospital_name, department_name):
                logger.info(f"Doctor saved to unified database: {text}")
            else:
                logger.warning(f"Failed to save doctor to unified database: {text}")
        except ImportError:
            logger.warning("doctors_service not available")
        except Exception as e:
            logger.warning(f"Error saving doctor: {e}")

        await update.message.reply_text(
            f"✅ **تم حفظ اسم الطبيب**\n\n"
            f"👨‍⚕️ **الطبيب:** {text}\n\n"
            f"💾 تم حفظه للاستخدام المستقبلي.",
            parse_mode="Markdown"
        )
        
        logger.info(f"➡️ Moving to R_ACTION_TYPE state after manual doctor entry")
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        await show_action_type_menu(update.message, context)
        return R_ACTION_TYPE

    # إذا لم يكن في وضع الإدخال اليدوي
    if text.lower() in ["إلغاء", "رجوع", "cancel", "back"]:
        await update.message.reply_text(
            "❌ تم إلغاء اختيار الطبيب",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ إدخال يدوي", callback_data="doctor_manual")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
            ])
        )
        return STATE_SELECT_DOCTOR
    
    # إعادة عرض القائمة
    logger.warning(f"⚠️ handle_doctor: لم يتم التعرف على النص. النص: '{text}'")
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
        "تأجيل موعد": {
            "state": APP_RESCHEDULE_REASON,
            "flow": start_appointment_reschedule_flow,
            "pre_process": None
        },
        "أشعة وفحوصات": {  # ✅ تم إضافتها بعد نقلها من الأقسام إلى أنواع الإجراءات
            "state": RADIOLOGY_TYPE,
            "flow": start_radiology_flow,
            "pre_process": None
        },
    }

    # Logging للتحقق من المفاتيح
    for action in PREDEFINED_ACTIONS:
        in_routing = action in routing_dict

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


    logger.info("=" * 80)
    logger.info("SHOW_ACTION_TYPE_MENU: Function called")
    logger.info(f"SHOW_ACTION_TYPE_MENU: Total actions = {len(PREDEFINED_ACTIONS)}")

    # تجاهل page parameter - عرض جميع الأزرار في صفحة واحدة
    text, keyboard, total_pages = _build_action_type_keyboard(0)

    try:
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info("SHOW_ACTION_TYPE_MENU: Message sent successfully")
    except Exception as e:
        import traceback
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
        
        logger.info(f"HANDLE_ACTION_PAGE: Successfully navigated to page {page}")
        return R_ACTION_TYPE
        
    except (ValueError, IndexError) as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error parsing page number: {e}", exc_info=True)
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
    
    traceback.print_stack()
    
    logger.warning("DEBUG_ALL_CALLBACKS: Callback query received - handle_action_type_choice was NOT matched!")
    logger.warning(f"DEBUG: Callback data = {query.data}, Current state = {current_state}")
    logger.warning(f"DEBUG: All user_data keys = {all_keys}")
    
    # محاولة استدعاء handle_action_type_choice يدوياً إذا كان pattern يطابق
    if query.data and query.data.startswith('action_idx:'):
        try:
            return await handle_action_type_choice(update, context)
        except Exception as e:
            logger.error(f"Error in action type choice: {e}")
            return None
    
    return None


async def handle_action_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع الإجراء - جميع المسارات"""
    import logging
    import sys
    import traceback
    logger = logging.getLogger(__name__)

    # طباعة مباشرة في الكونسول + تسجيل

    logger.info("=" * 80)
    logger.info("ACTION_TYPE_CHOICE: Function called - DEBUG MODE")
    logger.info("=" * 80)

    # طباعة stack trace لمعرفة من أين تم الاستدعاء
    traceback.print_stack()

    query = update.callback_query
    if not query:
        logger.error("ACTION_TYPE_CHOICE: CRITICAL - No callback_query in update!")
        return R_ACTION_TYPE

    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    
    
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
        logger.info(f"ACTION_TYPE_CHOICE: Extracted action_idx = {action_idx}")

        # التحقق من صحة الفهرس
        if action_idx < 0 or action_idx >= len(PREDEFINED_ACTIONS):
            error_msg = f"Invalid action index: {action_idx}, max: {len(PREDEFINED_ACTIONS) - 1}"
            logger.error(f"ACTION_TYPE_CHOICE: {error_msg}")
            await query.answer("نوع الإجراء غير صحيح", show_alert=True)
            return R_ACTION_TYPE

        # الحصول على نوع الإجراء المختار
        action_name = PREDEFINED_ACTIONS[action_idx]
        # استخدام logger بدلاً من print لتجنب UnicodeEncodeError في Windows console
        logger.info(f"ACTION_TYPE_CHOICE: Selected action = '{action_name}' (index: {action_idx})")
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
            "أشعة وفحوصات": "radiology",  # ✅ تم إضافتها بعد نقلها من الأقسام
            "تأجيل موعد": "appointment_reschedule",  # ✅ تم إضافتها
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
            logger.error(f"ACTION_TYPE_CHOICE: CRITICAL - No routing found for action_name: '{action_name}'")
            logger.error(f"ACTION_TYPE_CHOICE: Available keys in ACTION_ROUTING:")
            for key in action_routing.keys():
                logger.error(f"   - '{key}' (type: {type(key)}, length: {len(key)}, repr: {repr(key)})")
            logger.warning(f"ACTION_TYPE_CHOICE: Unknown action type: '{action_name}', using default flow")
            # استخدام المسار الافتراضي (استشارة جديدة)
            routing = action_routing.get("استشارة جديدة")
            if not routing:
                logger.error("ACTION_TYPE_CHOICE: CRITICAL - Default routing also not found!")
                await query.answer("خطأ: نوع الإجراء غير مدعوم", show_alert=True)
                return R_ACTION_TYPE
        else:
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

        # تهيئة state_to_return بالقيمة الافتراضية من routing
        state_to_return = routing.get("state", R_ACTION_TYPE)

        try:
            logger.info(f"ACTION_TYPE_CHOICE: Calling flow function '{routing['flow'].__name__}'...")
            
            # استخدام query.message مباشرة كـ message_target لأنه يحتوي على chat ويمكن استخدام reply_text
            # query.message هو Message object صحيح يمكن استخدامه مع reply_text
            flow_result = await routing["flow"](query.message, context)
            logger.info(f"ACTION_TYPE_CHOICE: Flow function '{routing['flow'].__name__}' completed successfully")
            logger.info(f"ACTION_TYPE_CHOICE: Flow function returned: {flow_result}")
            logger.info(f"ACTION_TYPE_CHOICE: Expected state from routing = {routing['state']}")
            
            # استخدام state من flow function إذا كان موجوداً، وإلا استخدام state من routing
            state_to_return = flow_result if flow_result is not None else routing["state"]
            logger.info(f"ACTION_TYPE_CHOICE: Final state to return = {state_to_return}")
            # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
            context.user_data['_conversation_state'] = state_to_return
        except Exception as e:
            error_msg = f"ERROR in flow function '{routing['flow'].__name__}': {e}"
            import traceback
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
            logger.warning(f"ACTION_TYPE_CHOICE: Error occurred but returning state {state_to_return} to allow transition")

        logger.info(f"ACTION_TYPE_CHOICE: FINAL - Returning state = {state_to_return}")
        logger.info(f"ACTION_TYPE_CHOICE: FINAL - State type = {type(state_to_return)}")
        
        # التأكد من إرجاع state بشكل صحيح
        if state_to_return is None:
            logger.error("ACTION_TYPE_CHOICE: CRITICAL - state_to_return is None! Using routing state instead.")
            state_to_return = routing.get("state", R_ACTION_TYPE)
        
        return state_to_return

    except ValueError as e:
        error_msg = f"ACTION_TYPE_CHOICE: ValueError: {e}, callback_data: {query.data if query else 'N/A'}"
        import traceback
        logger.error(error_msg, exc_info=True)
        if query:
            try:
                await query.answer("خطأ في قراءة البيانات", show_alert=True)
            except:
                pass
        return R_ACTION_TYPE
    except IndexError as e:
        error_msg = f"ACTION_TYPE_CHOICE: IndexError: {e}, callback_data: {query.data if query else 'N/A'}"
        import traceback
        logger.error(error_msg, exc_info=True)
        if query:
            try:
                await query.answer("خطأ في الفهرس", show_alert=True)
            except:
                pass
        return R_ACTION_TYPE
    except Exception as e:
        error_msg = f"ACTION_TYPE_CHOICE: CRITICAL ERROR: {e}"
        import traceback
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

    logger.debug(f"NEW_CONSULT_FLOW: message type = {type(message)}")
    logger.debug(f"NEW_CONSULT_FLOW: message has reply_text = {hasattr(message, 'reply_text')}")
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action', 'NOT SET')
    current_flow = context.user_data.get('report_tmp', {}).get('current_flow', 'NOT SET')
    logger.debug(f"NEW_CONSULT_FLOW: medical_action = {repr(medical_action)}")
    logger.debug(f"NEW_CONSULT_FLOW: current_flow = {repr(current_flow)}")
    current_state_before = context.user_data.get('_conversation_state', 'NOT SET')
    
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
        
        result = await message.reply_text(
            "شكوى المريض\n\n"
            "يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        logger.info("NEW_CONSULT_FLOW: Message sent successfully, waiting for user input")
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = NEW_CONSULT_COMPLAINT
        logger.info(f"NEW_CONSULT_FLOW: Returning state = {NEW_CONSULT_COMPLAINT}")
        
        # إرجاع state للتأكد من أن ConversationHandler يعرف الحالة الجديدة
        return NEW_CONSULT_COMPLAINT
    except Exception as e:
        error_msg = f"ERROR: NEW_CONSULT_FLOW - Error sending message: {e}"
        logger.error(error_msg, exc_info=True)
        raise


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
        valid, msg = validate_text_input(text, min_length=3)
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
        return NEW_CONSULT_COMPLAINT

    logger.info(f"NEW_CONSULT_COMPLAINT: Validation passed, saving complaint")
    context.user_data["report_tmp"]["complaint"] = text

    try:
        logger.info("NEW_CONSULT_COMPLAINT: Sending decision request message...")
        await update.message.reply_text(
            "تم الحفظ\n\n"
            "📝 **قرار الطبيب**\n\n"
            "يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        logger.info("NEW_CONSULT_COMPLAINT: Message sent, returning NEW_CONSULT_DECISION")
    except Exception as e:
        logger.error(f"NEW_CONSULT_COMPLAINT: Error sending decision request: {e}", exc_info=True)
        raise

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = NEW_CONSULT_DECISION
    return NEW_CONSULT_DECISION


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
        valid, msg = validate_text_input(text, min_length=3)
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = NEW_CONSULT_DECISION
    return NEW_CONSULT_DECISION


async def handle_new_consult_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return NEW_CONSULT_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **الفحوصات المطلوبة**\n\n"
        "يرجى إدخال الفحوصات المطلوبة قبل العملية:\n"
        "(أو اكتب 'لا يوجد' إذا لم تكن هناك فحوصات)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = NEW_CONSULT_TESTS
    return NEW_CONSULT_TESTS


async def handle_new_consult_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 4: الفحوصات المطلوبة"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"
    else:
        valid, msg = validate_text_input(text, min_length=3)
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = NEW_CONSULT_FOLLOWUP_DATE
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


async def handle_followup_date_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال تاريخ العودة يدوياً - يقبل أي نص"""
    text = update.message.text.strip()
    
    if not text or len(text) < 2:
        await update.message.reply_text(
            "⚠️ **يرجى إدخال نص صحيح**\n\n"
            "أمثلة:\n"
            "• 15/1/2026\n"
            "• بعد أسبوع\n"
            "• الأحد القادم\n"
            "• 20 يناير\n\n"
            "أو اختر من التقويم أعلاه.",
            parse_mode="Markdown"
        )
        return context.user_data.get('_conversation_state')
    
    # حفظ النص كما هو
    context.user_data["report_tmp"]["followup_date"] = text
    context.user_data["report_tmp"]["followup_time"] = None  # لا يوجد وقت محدد
    
    # تحديد الحالة التالية - الانتقال مباشرة لسبب العودة
    current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
    
    reason_state_map = {
        "followup": FOLLOWUP_REASON,
        "emergency": EMERGENCY_REASON,
        "admission": ADMISSION_FOLLOWUP_REASON,
        "surgery_consult": SURGERY_CONSULT_FOLLOWUP_REASON,
        "operation": OPERATION_FOLLOWUP_REASON,
        "discharge": DISCHARGE_FOLLOWUP_REASON,
        "rehab_physical": PHYSICAL_THERAPY_FOLLOWUP_REASON,
        "device": DEVICE_FOLLOWUP_REASON,
    }
    next_state = reason_state_map.get(current_flow, NEW_CONSULT_FOLLOWUP_REASON)
    
    await update.message.reply_text(
        f"✅ **تم حفظ موعد العودة**\n\n"
        f"📅 {text}\n\n"
        f"✍️ **سبب العودة**\n\n"
        f"يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )
    
    context.user_data['_conversation_state'] = next_state
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


async def handle_new_consult_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 7: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "new_consult")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = NEW_CONSULT_TRANSLATOR
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
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_COMPLAINT

    context.user_data["report_tmp"]["complaint"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "🔬 **التشخيص الطبي**\n\n"
        "يرجى إدخال التشخيص:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FOLLOWUP_DIAGNOSIS
    return FOLLOWUP_DIAGNOSIS

async def handle_followup_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال التشخيص:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DIAGNOSIS

    context.user_data["report_tmp"]["diagnosis"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **قرار الطبيب**\n\n"
        "يرجى إدخال قرار الطبيب:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FOLLOWUP_DECISION
    return FOLLOWUP_DECISION

async def handle_followup_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال قرار الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return FOLLOWUP_DECISION

    context.user_data["report_tmp"]["decision"] = text

    await update.message.reply_text("✅ تم الحفظ")
    
    # الانتقال مباشرة لتقويم تاريخ العودة (تم حذف حقل رقم الغرفة والطابق)
    await _render_followup_calendar(update.message, context)

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FOLLOWUP_DATE_TIME
    return FOLLOWUP_DATE_TIME

# تم إزالة handle_followup_date_time_text - الآن نستخدم التقويم
# سيتم استخدام handle_new_consult_followup_calendar_day و handle_new_consult_followup_time_hour و handle_new_consult_followup_time_minute

async def handle_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "followup")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FOLLOWUP_TRANSLATOR
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
    valid, msg = validate_text_input(text, min_length=3)

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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = EMERGENCY_DIAGNOSIS
    return EMERGENCY_DIAGNOSIS

async def handle_emergency_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: التشخيص"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = EMERGENCY_DECISION
    return EMERGENCY_DECISION

async def handle_emergency_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: قرار الطبيب وماذا تم"""
    # التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = EMERGENCY_STATUS
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
    valid, msg = validate_text_input(text, min_length=3)

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
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "emergency")

    return EMERGENCY_TRANSLATOR

# =============================
# مسار 4: ترقيد (6 حقول)
# سبب الرقود، رقم الغرفة، ملاحظات، تاريخ عودة، سبب عودة، مترجم
# =============================

async def start_admission_flow(message, context):
    """بدء مسار ترقيد - الحقل 1: سبب الرقود"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "ترقيد"
    context.user_data["report_tmp"]["current_flow"] = "admission"
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
    valid, msg = validate_text_input(text, min_length=3)

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
        "🚪 **رقم الغرفة**\n\n"
        "يرجى إدخال رقم الغرفة:\n"
        "(أو اكتب 'لم يتم التحديد' إذا لم يتم تحديدها بعد)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = ADMISSION_ROOM
    return ADMISSION_ROOM

async def handle_admission_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: رقم الغرفة"""
    text = update.message.text.strip()

    if text.lower() in ['لم يتم التحديد', 'لا يوجد', 'لا', 'no']:
        text = "لم يتم التحديد"

    context.user_data["report_tmp"]["room_number"] = text

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "📝 **ملاحظات**\n\n"
        "يرجى إدخال أي ملاحظات إضافية:\n"
        "(أو اكتب 'لا يوجد')",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = ADMISSION_NOTES
    return ADMISSION_NOTES

async def handle_admission_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: ملاحظات"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["notes"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = ADMISSION_FOLLOWUP_DATE
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = ADMISSION_FOLLOWUP_REASON
    return ADMISSION_FOLLOWUP_REASON

async def handle_admission_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "admission")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = ADMISSION_TRANSLATOR
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
    valid, msg = validate_text_input(text, min_length=3)

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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = SURGERY_CONSULT_DECISION
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = SURGERY_CONSULT_NAME_EN
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = SURGERY_CONSULT_SUCCESS_RATE
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
    valid, msg = validate_text_input(text, min_length=3)

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

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    return SURGERY_CONSULT_FOLLOWUP_DATE

async def handle_surgery_consult_followup_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 6: تاريخ ووقت العودة مدمج"""
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
        return SURGERY_CONSULT_FOLLOWUP_DATE

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب العودة**\n\n"
        "يرجى إدخال سبب العودة:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = SURGERY_CONSULT_FOLLOWUP_REASON
    return SURGERY_CONSULT_FOLLOWUP_REASON

async def handle_surgery_consult_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 8: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "surgery_consult")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = SURGERY_CONSULT_TRANSLATOR
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = OPERATION_NAME_EN
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = OPERATION_NOTES
    return OPERATION_NOTES

async def handle_operation_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: ملاحظات"""
    text = update.message.text.strip()

    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"

    context.user_data["report_tmp"]["notes"] = text

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = OPERATION_FOLLOWUP_DATE
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = OPERATION_FOLLOWUP_REASON
    return OPERATION_FOLLOWUP_REASON

async def handle_operation_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 5: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "operation")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = OPERATION_TRANSLATOR
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
    valid, msg = validate_text_input(text, min_length=3)

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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FINAL_CONSULT_DECISION
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FINAL_CONSULT_RECOMMENDATIONS
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
    await show_translator_selection(update.message, context, "final_consult")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = FINAL_CONSULT_TRANSLATOR
    return FINAL_CONSULT_TRANSLATOR

# =============================
# مسار 8: خروج من المستشفى (متفرع - خيارين)
# =============================

async def start_discharge_flow(message, context):
    """بدء مسار خروج من المستشفى - اختيار النوع"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "خروج من المستشفى"
    context.user_data["report_tmp"]["current_flow"] = "discharge"
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
        # ✅ تحديث الـ state للخطوة التالية
        context.user_data['_conversation_state'] = DISCHARGE_ADMISSION_SUMMARY
        return DISCHARGE_ADMISSION_SUMMARY

    elif discharge_type == "operation":
        await query.edit_message_text("✅ اخترت: خروج بعد عملية")
        await query.message.reply_text(
            "⚕️ **تفاصيل العملية التي تمت للحالة**\n\n"
            "يرجى إدخال تفاصيل العملية:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        # ✅ تحديث الـ state للخطوة التالية
        context.user_data['_conversation_state'] = DISCHARGE_OPERATION_DETAILS
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DISCHARGE_FOLLOWUP_DATE
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DISCHARGE_OPERATION_NAME_EN
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DISCHARGE_FOLLOWUP_DATE
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DISCHARGE_FOLLOWUP_REASON
    return DISCHARGE_FOLLOWUP_REASON

async def handle_discharge_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خروج (كلا الفرعين) - سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "discharge")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DISCHARGE_TRANSLATOR
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

    # عرض رسالة تأكيد الحفظ ثم التقويم
    await update.message.reply_text("✅ تم الحفظ", parse_mode="Markdown")
    
    # عرض التقويم مع خيار الإدخال اليدوي
    await _render_followup_calendar(update.message, context)

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = PHYSICAL_THERAPY_FOLLOWUP_DATE
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
        await show_translator_selection(query.message, context, "rehab_physical")
        # ✅ تحديث الـ state للخطوة التالية
        context.user_data['_conversation_state'] = PHYSICAL_THERAPY_TRANSLATOR
        return PHYSICAL_THERAPY_TRANSLATOR

    elif query.data == "physical_date:yes":
        await _render_followup_calendar(query.message, context)
        # ✅ تحديث الـ state للخطوة التالية
        context.user_data['_conversation_state'] = PHYSICAL_THERAPY_FOLLOWUP_DATE
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = PHYSICAL_THERAPY_FOLLOWUP_REASON
    return PHYSICAL_THERAPY_FOLLOWUP_REASON

async def handle_physical_therapy_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """علاج طبيعي - الحقل 4: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "rehab_physical")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = PHYSICAL_THERAPY_TRANSLATOR
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DEVICE_FOLLOWUP_DATE
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

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DEVICE_FOLLOWUP_REASON
    return DEVICE_FOLLOWUP_REASON

async def handle_device_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أجهزة تعويضية - الحقل 4: سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

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
    await show_translator_selection(update.message, context, "rehab_device")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = DEVICE_TRANSLATOR
    return DEVICE_TRANSLATOR

# =============================
# مسار 10: أشعة وفحوصات
# =============================

async def start_radiology_flow(message, context):
    """بدء مسار أشعة وفحوصات"""
    # التأكد من حفظ medical_action و current_flow
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "أشعة وفحوصات"
    context.user_data["report_tmp"]["current_flow"] = "radiology"
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
    valid, msg = validate_text_input(text, min_length=3)

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
    """بناء تقويم التاريخ الرئيسي للتقرير - يسمح باختيار أي تاريخ سابق"""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = []

    # تقويم الشهر مع أزرار التنقل (للشهور السابقة والقادمة)
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
                    # ✅ السماح باختيار أي تاريخ سابق أو اليوم (لا يُسمح بالمستقبل)
                    if date_obj > today:
                        # التواريخ المستقبلية معطلة
                        row.append(InlineKeyboardButton(f"·{day:02d}·", callback_data="noop"))
                    elif date_obj == today:
                        # تمييز اليوم بعلامة خاصة
                        row.append(InlineKeyboardButton(f"📍{day:02d}", callback_data=f"main_cal_day:{date_str}"))
                    else:
                        # ✅ التواريخ السابقة متاحة للاختيار
                        row.append(InlineKeyboardButton(f"{day:02d}", callback_data=f"main_cal_day:{date_str}"))
                except Exception:
                    row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])

    text = f"📅 **اختيار تاريخ التقرير**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\n✅ يمكنك اختيار أي تاريخ سابق\n\nاختر التاريخ من التقويم:"
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

    text = f"📅 **تاريخ ووقت العودة**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\n✅ اختر التاريخ من التقويم\n✅ أو اكتب يدوياً (مثال: 15/1/2026 أو بعد أسبوع)"
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
        await show_translator_selection(query.message, context, "radiology")
        
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = RADIOLOGY_TRANSLATOR

        return RADIOLOGY_TRANSLATOR
    except ValueError:
        await query.answer("صيغة غير صالحة", show_alert=True)
        return RADIOLOGY_DELIVERY_DATE

# =============================
# مسار 11: تأجيل موعد
# =============================

async def start_appointment_reschedule_flow(message, context):
    """بدء مسار تأجيل موعد"""
    context.user_data.setdefault("report_tmp", {})["medical_action"] = "تأجيل موعد"
    context.user_data["report_tmp"]["current_flow"] = "appointment_reschedule"
    context.user_data['_conversation_state'] = APP_RESCHEDULE_REASON

    await message.reply_text(
        "📅 **تأجيل موعد**\n\n"
        "يرجى إدخال سبب تأجيل الموعد:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown"
    )

    return APP_RESCHEDULE_REASON


async def handle_app_reschedule_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج سبب تأجيل الموعد"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب تأجيل الموعد:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return APP_RESCHEDULE_REASON

    # ✅ التأكد من وجود report_tmp
    context.user_data.setdefault("report_tmp", {})
    context.user_data["report_tmp"]["app_reschedule_reason"] = text
    context.user_data["report_tmp"]["current_flow"] = "appointment_reschedule"
    context.user_data["report_tmp"]["medical_action"] = "تأجيل موعد"
    
    logger.info(f"💾 تم حفظ app_reschedule_reason: {text}")

    await update.message.reply_text("✅ تم الحفظ")
    
    # عرض تقويم لاختيار تاريخ العودة
    await _show_reschedule_calendar(update.message, context)

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = APP_RESCHEDULE_RETURN_DATE
    return APP_RESCHEDULE_RETURN_DATE


async def _show_reschedule_calendar(message, context, year=None, month=None):
    """عرض تقويم لاختيار تاريخ العودة"""
    today = datetime.now(ZoneInfo(TIMEZONE))
    year = year or today.year
    month = month or today.month

    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdatescalendar(year, month)

    keyboard = []
    keyboard.append([InlineKeyboardButton(f"📅 {MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop")])
    keyboard.append([InlineKeyboardButton(d, callback_data="noop") for d in ["س", "أ", "ث", "ر", "خ", "ج", "س"]])

    for week in weeks:
        row = []
        for day in week:
            if day.month == month and day >= today.date():
                row.append(InlineKeyboardButton(
                    str(day.day),
                    callback_data=f"reschedule_cal_day:{day.strftime('%Y-%m-%d')}"
                ))
            else:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
        keyboard.append(row)

    nav_row = []
    if month > today.month or year > today.year:
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"reschedule_cal_nav:prev:{prev_year}:{prev_month}"))
    nav_row.append(InlineKeyboardButton("➡️ التالي", callback_data=f"reschedule_cal_nav:next:{year}:{month + 1 if month < 12 else 1}"))
    keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])

    await message.reply_text(
        "📅 **اختر تاريخ العودة الجديد:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_reschedule_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم تأجيل الموعد"""
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split(":")
    direction = parts[1]
    year = int(parts[2])
    month = int(parts[3])
    
    await query.delete_message()
    await _show_reschedule_calendar(query.message, context, year, month)
    
    return APP_RESCHEDULE_RETURN_DATE


async def handle_reschedule_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار تاريخ العودة"""
    query = update.callback_query
    await query.answer()
    
    date_str = query.data.split(":", 1)[1]
    try:
        return_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data["report_tmp"]["app_reschedule_return_date"] = return_date
        context.user_data["report_tmp"]["followup_date"] = return_date

        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(return_date.weekday(), '')
        date_display = f"📅 {return_date.strftime('%d')} {MONTH_NAMES_AR.get(return_date.month, return_date.month)} {return_date.year} ({day_name})"

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **تاريخ العودة الجديد:**\n"
            f"{date_display}\n\n"
            f"يرجى إدخال سبب العودة:",
            parse_mode="Markdown"
        )
        
        context.user_data['_conversation_state'] = APP_RESCHEDULE_RETURN_REASON
        return APP_RESCHEDULE_RETURN_REASON
        
    except ValueError:
        await query.answer("صيغة غير صالحة", show_alert=True)
        return APP_RESCHEDULE_RETURN_DATE


async def handle_app_reschedule_return_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج سبب العودة"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return APP_RESCHEDULE_RETURN_REASON

    context.user_data["report_tmp"]["app_reschedule_return_reason"] = text
    context.user_data["report_tmp"]["followup_reason"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await show_translator_selection(update.message, context, "appointment_reschedule")

    # ✅ تحديث الـ state للخطوة التالية
    context.user_data['_conversation_state'] = APP_RESCHEDULE_TRANSLATOR
    return APP_RESCHEDULE_TRANSLATOR


# =============================
# دالة مشتركة: اسم المترجم
# =============================

async def ask_translator_name(message, context, flow_type):
    """طلب اسم المترجم - مشترك لجميع المسارات"""
    user_id = message.chat.id
    translator_name = "غير محدد"

    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if translator:
            translator_name = translator.full_name

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ {translator_name}", callback_data=f"translator:{flow_type}:auto")],
        [InlineKeyboardButton("✏️ إدخال اسم آخر", callback_data=f"translator:{flow_type}:manual")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await message.reply_text(
        f"👤 **اسم المترجم**\n\n"
        f"المترجم الحالي: {translator_name}\n\n"
        f"اختر أحد الخيارات:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_translator_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المترجم"""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    flow_type = parts[1]
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

        # تخزين نوع المسار للاستخدام لاحقاً
        context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type

        # إرجاع state المترجم المناسب
        translator_state = get_translator_state(flow_type)
        # حفظ الحالة يدوياً في user_data للمساعدة في التتبع
        context.user_data['_conversation_state'] = translator_state
        return translator_state

async def handle_translator_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المترجم يدوياً"""
    text = update.message.text.strip()
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

    context.user_data.setdefault("report_tmp", {})["translator_name"] = text
    context.user_data["report_tmp"]["translator_id"] = None

    await update.message.reply_text("✅ تم الحفظ")

    flow_type = context.user_data["report_tmp"].get("current_flow", "new_consult")
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
            ("room_number", "🚪 رقم الغرفة"),
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
            ("room_number", "🚪 رقم الغرفة"),
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
        fields_count = 0
        
        for field_key, field_display in editable_fields:
            # الحصول على القيمة الحالية
            current_value = data.get(field_key, "")
            
            # ✅ عرض فقط الحقول التي لها قيم
            if not current_value or str(current_value).strip() == "" or current_value == "غير محدد":
                continue
            
            fields_count += 1
            
            if isinstance(current_value, datetime):
                current_value = current_value.strftime('%Y-%m-%d %H:%M')
            elif len(str(current_value)) > 30:
                current_value = str(current_value)[:27] + "..."
            
            button_text = f"{field_display}: {str(current_value)[:20]}"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"edit_field:{flow_type}:{field_key}"
                )
            ])
        
        if fields_count == 0:
            text = "⚠️ **لا توجد حقول مدخلة للتعديل**"
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")])
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
        
        # العودة إلى state التأكيد
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
    
    # ✅ Debug: تسجيل جميع البيانات الموجودة
    logger.info("=" * 80)
    logger.info("📋 SHOW_FINAL_SUMMARY: All data in report_tmp:")
    logger.info(f"  - patient_name: {data.get('patient_name', 'NOT FOUND')}")
    logger.info(f"  - hospital_name: {data.get('hospital_name', 'NOT FOUND')}")
    logger.info(f"  - department_name: {data.get('department_name', 'NOT FOUND')}")
    logger.info(f"  - doctor_name: {data.get('doctor_name', 'NOT FOUND')}")
    logger.info(f"  - report_date: {data.get('report_date', 'NOT FOUND')}")
    logger.info(f"  - All keys in report_tmp: {list(data.keys())}")
    logger.info("=" * 80)

    # بناء الملخص بناءً على نوع المسار
    report_date = data.get("report_date")
    if report_date and hasattr(report_date, 'strftime'):
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 
                   4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        day_name = days_ar.get(report_date.weekday(), '')
        date_str = f"{report_date.strftime('%Y-%m-%d')} ({day_name}) {report_date.strftime('%H:%M')}"
    else:
        date_str = str(report_date) if report_date else 'غير محدد'

    # ✅ استخدام .get() مع قيم افتراضية واضحة
    patient_name = data.get('patient_name') or data.get('patient_id') or 'غير محدد'
    hospital_name = data.get('hospital_name') or 'غير محدد'
    department_name = data.get('department_name') or data.get('main_department') or 'غير محدد'
    doctor_name = data.get('doctor_name') or 'غير محدد'

    summary = f"📋 **ملخص التقرير**\n\n"
    summary += f"📅 **التاريخ:** {date_str}\n"
    summary += f"👤 **المريض:** {patient_name}\n"
    summary += f"🏥 **المستشفى:** {hospital_name}\n"
    summary += f"🏷️ **القسم:** {department_name}\n"
    summary += f"👨‍⚕️ **الطبيب:** {doctor_name}\n\n"

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
        "radiology": "أشعة وفحوصات",
        "appointment_reschedule": "تأجيل موعد"
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
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"

    elif flow_type == "admission":
        summary += f"🛏️ **سبب الرقود:** {data.get('admission_reason', 'غير محدد')}\n"
        summary += f"🚪 **رقم الغرفة:** {data.get('room_number', 'لم يتم التحديد')}\n"
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
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
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
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
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
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
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
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
    elif flow_type == "radiology":
        radiology_type = data.get('radiology_type', 'غير محدد')
        # تقسيم النص إلى أسطر إذا كان يحتوي على فواصل أو أسطر متعددة
        if '\n' in radiology_type or ',' in radiology_type or '،' in radiology_type:
            # تقسيم النص
            if '\n' in radiology_type:
                lines = [line.strip() for line in radiology_type.split('\n') if line.strip()]
            elif ',' in radiology_type:
                lines = [line.strip() for line in radiology_type.split(',') if line.strip()]
            else:
                lines = [line.strip() for line in radiology_type.split('،') if line.strip()]
            
            # ترقيم وتنظيم الأسطر
            summary += "🔬 **نوع الأشعة والفحوصات:**\n"
            for i, line in enumerate(lines, 1):
                summary += f"{i}. {line}\n"
        else:
            # إذا كان نص واحد، نعرضه في سطر منفصل
            summary += f"🔬 **نوع الأشعة والفحوصات:**\n{radiology_type}\n"
        
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
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
            else:
                summary += f"📅 **تاريخ العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"
        else:
            summary += f"📅 **تاريخ العودة:** لا يوجد\n"
    
    elif flow_type == "appointment_reschedule":
        # سبب تأجيل الموعد
        app_reschedule_reason = data.get('app_reschedule_reason', '')
        if app_reschedule_reason:
            summary += f"📅 **سبب تأجيل الموعد:** {app_reschedule_reason}\n"
        else:
            summary += f"📅 **سبب تأجيل الموعد:** غير محدد\n"
        
        # موعد العودة (تاريخ العودة الجديد)
        return_date = data.get('app_reschedule_return_date') or data.get('followup_date')
        if return_date:
            if hasattr(return_date, 'strftime'):
                date_str = return_date.strftime('%Y-%m-%d')
            else:
                date_str = str(return_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                time_display = format_time_string_12h(followup_time)
                summary += f"📅🕐 **موعد العودة:** {date_str} الساعة {time_display}\n"
            else:
                summary += f"📅 **موعد العودة:** {date_str}\n"
        else:
            summary += f"📅 **موعد العودة:** غير محدد\n"
        
        # سبب العودة
        return_reason = data.get('app_reschedule_return_reason') or data.get('followup_reason', '')
        if return_reason:
            summary += f"✍️ **سبب العودة:** {return_reason}\n"
        else:
            summary += f"✍️ **سبب العودة:** غير محدد\n"

    # إضافة معلومات المترجم
    summary += f"\n👤 **المترجم:** {data.get('translator_name', 'غير محدد')}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 نشر التقرير", callback_data=f"save:{flow_type}"),
            InlineKeyboardButton("✏️ تعديل التقرير", callback_data=f"edit_draft:{flow_type}")
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    try:
        await message.reply_text(
            summary,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        # Fallback بدون Markdown إذا كان النص يحتوي على أحرف خاصة
        summary_plain = summary.replace("**", "")
        await message.reply_text(
            summary_plain,
            reply_markup=keyboard
        )

# =============================
# معالجة التأكيد والحفظ
# =============================

async def handle_edit_draft_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة تعديل التقرير المؤقت قبل الحفظ
    """
    import logging
    logger = logging.getLogger(__name__)

    query = update.callback_query
    await query.answer()

    try:
        # استخراج نوع التدفق
        callback_data = query.data
        if ":" not in callback_data:
            await query.edit_message_text("❌ خطأ في البيانات")
            return

        flow_type = callback_data.split(":", 1)[1]

        # الحصول على البيانات المؤقتة
        data = context.user_data.get("report_tmp", {})
        medical_action = data.get("medical_action", "")

        if not medical_action:
            await query.edit_message_text("❌ خطأ: نوع الإجراء غير محدد")
            return

        # استيراد دالة get_editable_fields_by_action_type من ملف التعديل
        try:
            from bot.handlers.user.user_reports_edit import get_editable_fields_by_action_type
        except ImportError:
            await query.edit_message_text("❌ خطأ في تحميل نظام التعديل")
            return

        # الحصول على الحقول القابلة للتعديل
        editable_fields = get_editable_fields_by_action_type(medical_action)

        if not editable_fields:
            await query.edit_message_text("❌ لا توجد حقول قابلة للتعديل لهذا النوع من الإجراءات")
            return

        # حفظ معلومات التعديل في context
        context.user_data['editing_draft'] = True
        context.user_data['draft_flow_type'] = flow_type
        context.user_data['draft_medical_action'] = medical_action
        context.user_data['current_edit_field_index'] = 0

        # عرض قائمة الحقول للاختيار
        await show_draft_edit_fields(query.message, context, editable_fields, flow_type)

        # إرجاع state التأكيد نفسه (لأن الـ edit handlers مسجلة فيه)
        confirm_state = get_confirm_state(flow_type)
        return confirm_state

    except Exception as e:
        logger.error(f"خطأ في handle_edit_draft_report: {e}")
        await query.edit_message_text("❌ حدث خطأ في بدء عملية التعديل")
        return

async def show_draft_edit_fields(message, context, editable_fields, flow_type):
    """
    عرض قائمة الحقول القابلة للتعديل في التقرير المؤقت
    """
    # ربط المفاتيح من نظام التعديل إلى المفاتيح في report_tmp
    field_key_mapping = {
        'complaint_text': 'complaint',
        'doctor_decision': 'decision',
        'diagnosis': 'diagnosis',
        'notes': 'notes',
        'treatment_plan': 'treatment_plan',
        'followup_date': 'followup_date',
        'followup_reason': 'followup_reason',
        'medications': 'medications',
        'case_status': 'status',
        'admission_reason': 'admission_reason',
        'room_number': 'room_number',
        'operation_details': 'operation_details',
        'operation_name_en': 'operation_name_en',
        'tests': 'tests',
    }

    data = context.user_data.get("report_tmp", {})

    text = "✏️ **تعديل التقرير المؤقت**\n\n"
    text += "اختر الحقل الذي تريد تعديله:\n\n"

    keyboard_buttons = []
    fields_with_values = 0
    
    for edit_field_key, field_name in editable_fields:
        # تحويل مفتاح التعديل إلى مفتاح report_tmp
        report_key = field_key_mapping.get(edit_field_key, edit_field_key)
        
        # الحصول على القيمة الحالية للحقل
        current_value = data.get(report_key, "")
        
        # ✅ عرض فقط الحقول التي لها قيم (تخطي الحقول الفارغة)
        if not current_value or str(current_value).strip() == "":
            continue  # تخطي الحقول الفارغة
        
        fields_with_values += 1
        
        if len(str(current_value)) > 20:
            display_value = str(current_value)[:17] + "..."
        else:
            display_value = str(current_value)

        button_text = f"{field_name}: {display_value}"
        keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"edit_field_draft:{edit_field_key}")])
    
    # إذا لم توجد حقول مدخلة
    if fields_with_values == 0:
        text = "⚠️ **لا توجد حقول مدخلة للتعديل**\n\n"
        text += "لم يتم إدخال أي بيانات بعد."

    # أزرار إضافية
    keyboard_buttons.extend([
        [InlineKeyboardButton("✅ انتهيت من التعديل", callback_data=f"finish_edit_draft:{flow_type}")],
        [InlineKeyboardButton("🔙 رجوع للملخص", callback_data=f"back_to_summary:{flow_type}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    try:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception:
        await message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

async def handle_edit_draft_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة تعديل حقل محدد في التقرير المؤقت
    """
    import logging
    logger = logging.getLogger(__name__)

    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        if ":" not in callback_data:
            await query.edit_message_text("❌ خطأ في البيانات")
            return

        edit_field_key = callback_data.split(":", 1)[1]

        # ربط المفاتيح
        field_key_mapping = {
            'complaint_text': 'complaint',
            'doctor_decision': 'decision',
            'diagnosis': 'diagnosis',
            'notes': 'notes',
            'treatment_plan': 'treatment_plan',
            'followup_date': 'followup_date',
            'followup_reason': 'followup_reason',
            'medications': 'medications',
            'case_status': 'status',
            'admission_reason': 'admission_reason',
            'room_number': 'room_number',
            'operation_details': 'operation_details',
            'operation_name_en': 'operation_name_en',
            'tests': 'tests',
        }

        # تحويل مفتاح التعديل إلى مفتاح report_tmp
        report_key = field_key_mapping.get(edit_field_key, edit_field_key)

        # حفظ كلا المفتاحين
        context.user_data['editing_field'] = report_key
        context.user_data['editing_field_original'] = edit_field_key

        # الحصول على معلومات الحقل
        field_names = {
            'complaint_text': 'الشكوى',
            'complaint': 'الشكوى',
            'diagnosis': 'التشخيص',
            'doctor_decision': 'قرار الطبيب',
            'decision': 'قرار الطبيب',
            'notes': 'الملاحظات',
            'treatment_plan': 'خطة العلاج',
            'medications': 'الأدوية',
            'followup_date': 'تاريخ العودة',
            'followup_reason': 'سبب العودة',
            'case_status': 'حالة الطوارئ',
            'status': 'حالة الطوارئ',
            'admission_reason': 'سبب الرقود',
            'room_number': 'رقم الغرفة',
            'operation_details': 'تفاصيل العملية',
            'operation_name_en': 'اسم العملية بالإنجليزي',
            'tests': 'الفحوصات المطلوبة',
        }

        field_display_name = field_names.get(edit_field_key, edit_field_key)

        # الحقول التي تحتاج تقويم بدلاً من إدخال نصي
        date_fields = ['followup_date']
        
        if edit_field_key in date_fields:
            # عرض التقويم بدلاً من طلب إدخال نصي
            context.user_data['editing_draft_date'] = True
            await _render_draft_edit_followup_calendar(query, context)
            return "EDIT_DRAFT_FOLLOWUP_CALENDAR"

        # عرض رسالة طلب إدخال القيمة الجديدة
        data = context.user_data.get("report_tmp", {})
        current_value = data.get(report_key, "")
        
        text = f"✏️ **تعديل: {field_display_name}**\n\n"
        text += f"القيمة الحالية: {current_value or 'غير محدد'}\n\n"
        text += "📝 أدخل القيمة الجديدة:"

        flow_type = context.user_data.get('draft_flow_type', 'unknown')
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع لقائمة الحقول", callback_data=f"back_to_edit_fields:{flow_type}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])

        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        # إرجاع state انتظار الإدخال
        return "EDIT_DRAFT_FIELD"

    except Exception as e:
        logger.error(f"خطأ في handle_edit_draft_field: {e}")
        await query.edit_message_text("❌ حدث خطأ في بدء تعديل الحقل")
        return


# =============================
# دوال تعديل تاريخ العودة بالتقويم (للمسودة)
# =============================

async def _render_draft_edit_followup_calendar(query, context, year=None, month=None):
    """عرض تقويم تاريخ العودة لتعديل المسودة"""
    data_tmp = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = data_tmp.get("draft_edit_calendar_year", now.year)
        month = data_tmp.get("draft_edit_calendar_month", now.month)

    flow_type = context.user_data.get('draft_flow_type', 'unknown')
    text, markup = _build_draft_edit_calendar_markup(year, month, flow_type)
    data_tmp["draft_edit_calendar_year"] = year
    data_tmp["draft_edit_calendar_month"] = month

    try:
        await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"خطأ في عرض تقويم تعديل المسودة: {e}")


def _build_draft_edit_calendar_markup(year: int, month: int, flow_type: str = "unknown"):
    """بناء تقويم لتعديل تاريخ العودة في المسودة"""
    # الحصول على التاريخ الحالي
    today = datetime.now()
    
    # أيام الأسبوع
    week_header = ["س", "ح", "ن", "ث", "ر", "خ", "ج"]
    
    # أسماء الأشهر بالعربي
    arabic_months = {
        1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
        5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
        9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }
    
    month_name = arabic_months.get(month, str(month))
    
    text = f"📅 **تعديل تاريخ العودة**\n\n"
    text += f"**{month_name} {year}**\n"
    text += "اختر تاريخ العودة الجديد:"
    
    # بناء الكيبورد
    keyboard = []
    
    # صف أيام الأسبوع
    keyboard.append([InlineKeyboardButton(d, callback_data="ignore") for d in week_header])
    
    # الحصول على أيام الشهر
    cal = calendar.Calendar(firstweekday=5)  # السبت أول يوم
    month_days = cal.monthdayscalendar(year, month)
    
    for week in month_days:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                day_date = datetime(year, month, day).date()
                # السماح بالتواريخ المستقبلية فقط لتاريخ العودة
                if day_date >= today.date():
                    row.append(InlineKeyboardButton(
                        str(day), 
                        callback_data=f"draft_edit_cal_day:{year}-{month:02d}-{day:02d}"
                    ))
                else:
                    row.append(InlineKeyboardButton("·", callback_data="ignore"))
        keyboard.append(row)
    
    # أزرار التنقل
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    
    nav_row = [
        InlineKeyboardButton("◀️ السابق", callback_data=f"draft_edit_cal_nav:{prev_year}-{prev_month}"),
        InlineKeyboardButton("▶️ التالي", callback_data=f"draft_edit_cal_nav:{next_year}-{next_month}")
    ]
    keyboard.append(nav_row)
    
    # زر لتخطي تاريخ العودة
    keyboard.append([InlineKeyboardButton("⏭️ بدون تاريخ عودة", callback_data="draft_edit_cal_skip")])
    
    # زر الرجوع
    keyboard.append([InlineKeyboardButton("🔙 رجوع لقائمة الحقول", callback_data=f"back_to_edit_fields:{flow_type}")])
    
    return text, InlineKeyboardMarkup(keyboard)


async def handle_draft_edit_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل في تقويم تعديل المسودة"""
    query = update.callback_query
    await query.answer()
    
    try:
        nav_data = query.data.replace("draft_edit_cal_nav:", "")
        year, month = map(int, nav_data.split("-"))
        await _render_draft_edit_followup_calendar(query, context, year, month)
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"
    except Exception as e:
        logger.error(f"خطأ في التنقل في تقويم تعديل المسودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_calendar_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار يوم من تقويم تعديل المسودة"""
    query = update.callback_query
    await query.answer()
    
    try:
        date_str = query.data.replace("draft_edit_cal_day:", "")
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        
        # حفظ التاريخ المؤقت
        context.user_data["report_tmp"]["_pending_draft_edit_date"] = dt.date()
        
        # عرض اختيار الساعة
        await _show_draft_edit_hour_selection(query, context)
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"
    except Exception as e:
        logger.error(f"خطأ في اختيار يوم من تقويم تعديل المسودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def _show_draft_edit_hour_selection(query, context):
    """عرض اختيار الساعة لتعديل تاريخ العودة"""
    text = "🕐 **اختر ساعة الموعد:**"
    
    # ساعات من 8 صباحاً حتى 10 مساءً
    hours = []
    for h in range(8, 23):
        if h < 12:
            display = f"{h} ص"
        elif h == 12:
            display = "12 ظ"
        else:
            display = f"{h-12} م"
        hours.append((str(h).zfill(2), display))
    
    keyboard = []
    for i in range(0, len(hours), 4):
        row = []
        for hour, display in hours[i:i+4]:
            row.append(InlineKeyboardButton(display, callback_data=f"draft_edit_time_hour:{hour}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("⏭️ بدون وقت محدد", callback_data="draft_edit_time_skip")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع للتقويم", callback_data="draft_edit_back_calendar")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def handle_draft_edit_time_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الساعة لتعديل المسودة"""
    query = update.callback_query
    await query.answer()
    
    try:
        hour = query.data.replace("draft_edit_time_hour:", "")
        context.user_data["report_tmp"]["_pending_draft_edit_hour"] = hour
        
        # عرض اختيار الدقائق
        await _show_draft_edit_minute_selection(query, context, hour)
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"
    except Exception as e:
        logger.error(f"خطأ في اختيار الساعة لتعديل المسودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def _show_draft_edit_minute_selection(query, context, hour):
    """عرض اختيار الدقائق لتعديل تاريخ العودة"""
    hour_int = int(hour)
    if hour_int < 12:
        period = "صباحاً"
        h_display = str(hour_int) if hour_int > 0 else "12"
    elif hour_int == 12:
        period = "ظهراً"
        h_display = "12"
    else:
        period = "مساءً"
        h_display = str(hour_int - 12)
    
    text = f"🕐 **الساعة {h_display} {period}**\n\nاختر الدقائق:"
    
    minutes = ["00", "15", "30", "45"]
    keyboard = []
    row = []
    for m in minutes:
        row.append(InlineKeyboardButton(f":{m}", callback_data=f"draft_edit_time_minute:{m}"))
    keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع لاختيار الساعة", callback_data="draft_edit_back_hour")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def handle_draft_edit_time_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار الدقائق لتعديل المسودة"""
    query = update.callback_query
    await query.answer()
    
    try:
        minute = query.data.replace("draft_edit_time_minute:", "")
        hour = context.user_data["report_tmp"].get("_pending_draft_edit_hour", "09")
        date = context.user_data["report_tmp"].get("_pending_draft_edit_date")
        
        # حفظ التاريخ والوقت
        context.user_data["report_tmp"]["followup_date"] = date
        context.user_data["report_tmp"]["followup_time"] = f"{hour}:{minute}"
        
        # تنظيف البيانات المؤقتة
        context.user_data["report_tmp"].pop("_pending_draft_edit_date", None)
        context.user_data["report_tmp"].pop("_pending_draft_edit_hour", None)
        context.user_data.pop("editing_draft_date", None)
        context.user_data.pop("editing_field", None)
        
        # العودة لقائمة الحقول
        flow_type = context.user_data.get('draft_flow_type', 'unknown')
        await query.edit_message_text(
            f"✅ تم تحديث تاريخ العودة: {date} الساعة {hour}:{minute}\n\n"
            "جاري العودة لقائمة الحقول...",
            parse_mode="Markdown"
        )
        
        # إعادة عرض قائمة الحقول
        return await handle_back_to_edit_fields_direct(update, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في اختيار الدقائق لتعديل المسودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_time_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي الوقت وحفظ التاريخ فقط"""
    query = update.callback_query
    await query.answer()
    
    try:
        date = context.user_data["report_tmp"].get("_pending_draft_edit_date")
        
        # حفظ التاريخ بدون وقت
        context.user_data["report_tmp"]["followup_date"] = date
        context.user_data["report_tmp"]["followup_time"] = None
        
        # تنظيف البيانات المؤقتة
        context.user_data["report_tmp"].pop("_pending_draft_edit_date", None)
        context.user_data["report_tmp"].pop("_pending_draft_edit_hour", None)
        context.user_data.pop("editing_draft_date", None)
        context.user_data.pop("editing_field", None)
        
        # العودة لقائمة الحقول
        flow_type = context.user_data.get('draft_flow_type', 'unknown')
        await query.edit_message_text(
            f"✅ تم تحديث تاريخ العودة: {date}\n\n"
            "جاري العودة لقائمة الحقول...",
            parse_mode="Markdown"
        )
        
        return await handle_back_to_edit_fields_direct(update, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في تخطي الوقت: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_cal_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي تاريخ العودة بالكامل"""
    query = update.callback_query
    await query.answer()
    
    try:
        # إزالة تاريخ العودة
        context.user_data["report_tmp"]["followup_date"] = None
        context.user_data["report_tmp"]["followup_time"] = None
        
        # تنظيف البيانات المؤقتة
        context.user_data.pop("editing_draft_date", None)
        context.user_data.pop("editing_field", None)
        
        # العودة لقائمة الحقول
        flow_type = context.user_data.get('draft_flow_type', 'unknown')
        await query.edit_message_text(
            "✅ تم إزالة تاريخ العودة\n\n"
            "جاري العودة لقائمة الحقول...",
            parse_mode="Markdown"
        )
        
        return await handle_back_to_edit_fields_direct(update, context, flow_type)
    except Exception as e:
        logger.error(f"خطأ في تخطي تاريخ العودة: {e}")
        return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_back_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع للتقويم من اختيار الوقت"""
    query = update.callback_query
    await query.answer()
    
    await _render_draft_edit_followup_calendar(query, context)
    return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_draft_edit_back_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع لاختيار الساعة"""
    query = update.callback_query
    await query.answer()
    
    await _show_draft_edit_hour_selection(query, context)
    return "EDIT_DRAFT_FOLLOWUP_CALENDAR"


async def handle_back_to_edit_fields_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, flow_type: str):
    """العودة مباشرة لقائمة الحقول"""
    query = update.callback_query
    
    try:
        medical_action = context.user_data.get('draft_medical_action', '')
        
        from bot.handlers.user.user_reports_edit import get_editable_fields_by_action_type
        editable_fields = get_editable_fields_by_action_type(medical_action)
        await show_draft_edit_fields(query.message, context, editable_fields, flow_type)
        
        # إرجاع state التأكيد
        confirm_state = get_confirm_state(flow_type)
        return confirm_state
    except Exception as e:
        logger.error(f"خطأ في العودة لقائمة الحقول: {e}")
        await query.edit_message_text("❌ حدث خطأ في العودة لقائمة الحقول")
        return


async def handle_draft_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة إدخال القيمة الجديدة للحقل
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # تحقق من أن النص ليس أمر بدء تقرير جديد
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            # المستخدم يريد بدء تقرير جديد - أعد توجيهه
            return await start_report(update, context)
        
        field_key = context.user_data.get('editing_field')
        if not field_key:
            # لا يوجد حقل للتعديل - تجاهل الرسالة
            return

        new_value = update.message.text.strip()

        # حفظ القيمة الجديدة في report_tmp
        context.user_data.setdefault("report_tmp", {})[field_key] = new_value

        # رسالة تأكيد
        field_names = {
            'complaint': 'الشكوى',
            'diagnosis': 'التشخيص',
            'decision': 'قرار الطبيب',
            'notes': 'الملاحظات',
            'treatment_plan': 'خطة العلاج',
            'medications': 'الأدوية',
            'followup_date': 'تاريخ العودة',
            'followup_reason': 'سبب العودة',
            'status': 'حالة الطوارئ',
            'admission_reason': 'سبب الرقود',
            'room_number': 'رقم الغرفة',
            'operation_details': 'تفاصيل العملية',
            'operation_name_en': 'اسم العملية بالإنجليزي',
            'tests': 'الفحوصات المطلوبة',
        }

        field_display_name = field_names.get(field_key, field_key)

        # مسح حقل التعديل
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)

        # العودة لقائمة الحقول
        flow_type = context.user_data.get('draft_flow_type', 'new_consult')
        medical_action = context.user_data.get('draft_medical_action', '')

        try:
            from bot.handlers.user.user_reports_edit import get_editable_fields_by_action_type
            editable_fields = get_editable_fields_by_action_type(medical_action)
            
            # بناء قائمة الحقول مع تأكيد التحديث
            text = f"✅ تم تحديث **{field_display_name}** بنجاح!\n\n"
            text += "📝 اختر حقلاً آخر للتعديل أو اضغط انتهيت:\n"
            
            await update.message.reply_text(text, parse_mode="Markdown")
            
            # عرض قائمة الحقول
            await _show_edit_fields_menu(update.message, context, editable_fields, flow_type)
            
            # إرجاع state التأكيد
            confirm_state = get_confirm_state(flow_type)
            return confirm_state
        except Exception as e:
            logger.error(f"خطأ في العودة لقائمة الحقول: {e}")
            await update.message.reply_text("❌ حدث خطأ في العودة لقائمة التعديل")
            return

    except Exception as e:
        logger.error(f"خطأ في handle_draft_field_input: {e}")
        await update.message.reply_text("❌ حدث خطأ في حفظ القيمة الجديدة")
        return


async def _show_edit_fields_menu(message, context, editable_fields, flow_type):
    """
    عرض قائمة الحقول القابلة للتعديل - فقط الحقول المدخلة
    """
    # ربط المفاتيح
    field_key_mapping = {
        'complaint_text': 'complaint',
        'doctor_decision': 'decision',
        'diagnosis': 'diagnosis',
        'notes': 'notes',
        'treatment_plan': 'treatment_plan',
        'followup_date': 'followup_date',
        'followup_reason': 'followup_reason',
        'medications': 'medications',
        'case_status': 'status',
        'admission_reason': 'admission_reason',
        'room_number': 'room_number',
        'operation_details': 'operation_details',
        'operation_name_en': 'operation_name_en',
        'tests': 'tests',
    }

    data = context.user_data.get("report_tmp", {})

    keyboard_buttons = []
    for edit_field_key, field_name in editable_fields:
        report_key = field_key_mapping.get(edit_field_key, edit_field_key)
        current_value = data.get(report_key, "")
        
        # ✅ عرض فقط الحقول التي لها قيم
        if not current_value or str(current_value).strip() == "":
            continue
        
        if len(str(current_value)) > 20:
            display_value = str(current_value)[:17] + "..."
        else:
            display_value = str(current_value)

        button_text = f"{field_name}: {display_value}"
        keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"edit_field_draft:{edit_field_key}")])

    keyboard_buttons.extend([
        [InlineKeyboardButton("✅ انتهيت من التعديل", callback_data=f"finish_edit_draft:{flow_type}")],
        [InlineKeyboardButton("🔙 رجوع للملخص", callback_data=f"back_to_summary:{flow_type}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await message.reply_text(
        "📝 **قائمة الحقول:**",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_finish_edit_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة انتهاء التعديل والعودة للملخص
    """
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        flow_type = callback_data.split(":", 1)[1] if ":" in callback_data else context.user_data.get('draft_flow_type', 'new_consult')

        # مسح بيانات التعديل المؤقت
        context.user_data.pop('editing_draft', None)
        context.user_data.pop('draft_flow_type', None)
        context.user_data.pop('draft_medical_action', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)

        # الحصول على البيانات
        data = context.user_data.get("report_tmp", {})
        
        # بناء الملخص
        report_date = data.get("report_date")
        if report_date and hasattr(report_date, 'strftime'):
            days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 
                       4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
            day_name = days_ar.get(report_date.weekday(), '')
            date_str = f"{report_date.strftime('%Y-%m-%d')} ({day_name})"
        else:
            date_str = str(report_date) if report_date else 'غير محدد'

        patient_name = data.get('patient_name') or 'غير محدد'
        hospital_name = data.get('hospital_name') or 'غير محدد'
        department_name = data.get('department_name') or 'غير محدد'
        doctor_name = data.get('doctor_name') or 'غير محدد'
        medical_action = data.get('medical_action') or 'غير محدد'

        summary = f"📋 **ملخص التقرير (بعد التعديل)**\n\n"
        summary += f"📅 **التاريخ:** {date_str}\n"
        summary += f"👤 **المريض:** {patient_name}\n"
        summary += f"🏥 **المستشفى:** {hospital_name}\n"
        summary += f"🏷️ **القسم:** {department_name}\n"
        summary += f"👨‍⚕️ **الطبيب:** {doctor_name}\n"
        summary += f"⚕️ **نوع الإجراء:** {medical_action}\n\n"

        # تفاصيل إضافية
        if data.get('complaint'):
            summary += f"💬 **الشكوى:** {data.get('complaint')}\n"
        if data.get('diagnosis'):
            summary += f"🔬 **التشخيص:** {data.get('diagnosis')}\n"
        if data.get('decision'):
            summary += f"📝 **قرار الطبيب:** {data.get('decision')}\n"
        if data.get('notes'):
            summary += f"📋 **ملاحظات:** {data.get('notes')}\n"
        if data.get('tests'):
            summary += f"🧪 **الفحوصات:** {data.get('tests')}\n"

        summary += "\n✅ **هل تريد حفظ التقرير؟**"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 حفظ التقرير", callback_data=f"save:{flow_type}")],
            [InlineKeyboardButton("✏️ تعديل آخر", callback_data=f"edit_draft:{flow_type}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])

        await query.edit_message_text(
            summary,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        # إرجاع state التأكيد
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        logger.error(f"خطأ في handle_finish_edit_draft: {e}")
        try:
            await query.edit_message_text("❌ حدث خطأ في إنهاء التعديل. اضغط /start للبدء من جديد.")
        except:
            pass
        return

async def handle_back_to_edit_fields(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة الرجوع لقائمة الحقول المعدلة
    """
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()

    try:
        # استخراج flow_type من callback_data أو context
        callback_data = query.data
        if ":" in callback_data:
            flow_type = callback_data.split(":", 1)[1]
        else:
            flow_type = context.user_data.get('draft_flow_type', 'new_consult')
        
        medical_action = context.user_data.get('draft_medical_action', '')

        try:
            from bot.handlers.user.user_reports_edit import get_editable_fields_by_action_type
            editable_fields = get_editable_fields_by_action_type(medical_action)
            await show_draft_edit_fields(query.message, context, editable_fields, flow_type)
            
            # إرجاع state التأكيد
            confirm_state = get_confirm_state(flow_type)
            return confirm_state
        except Exception as e:
            logger.error(f"خطأ في العودة لقائمة الحقول: {e}")
            await query.edit_message_text("❌ حدث خطأ في العودة لقائمة الحقول")
            return

    except Exception as e:
        logger.error(f"خطأ في handle_back_to_edit_fields: {e}")
        await query.edit_message_text("❌ حدث خطأ في الرجوع")
        return

async def handle_back_to_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة الرجوع للملخص دون حفظ التعديلات
    """
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        flow_type = callback_data.split(":", 1)[1] if ":" in callback_data else context.user_data.get('draft_flow_type', 'new_consult')

        # مسح بيانات التعديل المؤقت
        context.user_data.pop('editing_draft', None)
        context.user_data.pop('draft_flow_type', None)
        context.user_data.pop('draft_medical_action', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)

        # الحصول على البيانات
        data = context.user_data.get("report_tmp", {})
        
        # بناء الملخص مباشرة بدلاً من استدعاء show_final_summary
        report_date = data.get("report_date")
        if report_date and hasattr(report_date, 'strftime'):
            days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 
                       4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
            day_name = days_ar.get(report_date.weekday(), '')
            date_str = f"{report_date.strftime('%Y-%m-%d')} ({day_name})"
        else:
            date_str = str(report_date) if report_date else 'غير محدد'

        patient_name = data.get('patient_name') or 'غير محدد'
        hospital_name = data.get('hospital_name') or 'غير محدد'
        department_name = data.get('department_name') or 'غير محدد'
        doctor_name = data.get('doctor_name') or 'غير محدد'
        medical_action = data.get('medical_action') or 'غير محدد'

        summary = f"📋 **ملخص التقرير**\n\n"
        summary += f"📅 **التاريخ:** {date_str}\n"
        summary += f"👤 **المريض:** {patient_name}\n"
        summary += f"🏥 **المستشفى:** {hospital_name}\n"
        summary += f"🏷️ **القسم:** {department_name}\n"
        summary += f"👨‍⚕️ **الطبيب:** {doctor_name}\n"
        summary += f"⚕️ **نوع الإجراء:** {medical_action}\n\n"

        # تفاصيل إضافية
        if data.get('complaint'):
            summary += f"💬 **الشكوى:** {data.get('complaint')}\n"
        if data.get('diagnosis'):
            summary += f"🔬 **التشخيص:** {data.get('diagnosis')}\n"
        if data.get('decision'):
            summary += f"📝 **قرار الطبيب:** {data.get('decision')}\n"

        summary += "\n✅ **هل تريد حفظ التقرير؟**"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 حفظ التقرير", callback_data=f"save:{flow_type}")],
            [InlineKeyboardButton("✏️ تعديل التقرير", callback_data=f"edit_draft:{flow_type}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])

        await query.edit_message_text(
            summary,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        # إرجاع state التأكيد
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        logger.error(f"خطأ في handle_back_to_summary: {e}")
        try:
            await query.edit_message_text("❌ حدث خطأ في الرجوع للملخص. اضغط /start للبدء من جديد.")
        except:
            pass
        return

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
    logger.info("💾 SAVE REPORT BUTTON CLICKED!")
    logger.info(f"💾 Callback data: {query.data}")
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

    if action == "save":
        logger.info(f"💾 Starting save process for flow_type: {flow_type}")
        try:
            await save_report_to_database(query, context, flow_type)
            logger.info(f"Save completed successfully for flow_type: {flow_type}")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"❌ Error in save_report_to_database: {e}", exc_info=True)
            await query.answer(f"خطأ في الحفظ: {str(e)[:50]}", show_alert=True)
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
            decision_text = f"سبب الرقود: {admission_reason}\n\nرقم الغرفة: {room}\n\nملاحظات: {notes}"
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
        elif flow_type == "appointment_reschedule":
            # ✅ معالجة تأجيل المواعيد
            app_reschedule_reason = data.get("app_reschedule_reason", "")
            app_reschedule_return_reason = data.get("app_reschedule_return_reason", "") or data.get("followup_reason", "")
            return_date = data.get("app_reschedule_return_date") or data.get("followup_date")
            complaint_text = ""
            decision_text = f"سبب تأجيل الموعد: {app_reschedule_reason}"
            if return_date:
                if hasattr(return_date, 'strftime'):
                    date_str = return_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(return_date)
                decision_text += f"\n\nتاريخ العودة الجديد: {date_str}"
            if app_reschedule_return_reason:
                decision_text += f"\n\nسبب العودة: {app_reschedule_return_reason}"

        # ✅ الحصول على معرف المستخدم الذي أنشأ التقرير (Telegram User ID)
        user_id = None
        if query and hasattr(query, 'from_user') and query.from_user:
            user_id = query.from_user.id
            logger.info(f"✅ User ID from query.from_user: {user_id}")
        elif context.user_data.get('_user_id'):
            user_id = context.user_data.get('_user_id')
            logger.info(f"✅ User ID from context._user_id: {user_id}")
        else:
            logger.warning("⚠️ No user_id found! Report will have NULL submitted_by_user_id")
        
        logger.info(f"💾 Final submitted_by_user_id to save: {user_id}")
        
        # ✅ الحصول على translator_id من جدول Translator إذا كان المستخدم مسجلاً
        # هذا يضمن إمكانية البحث عن التقارير حتى لو كان اسم المترجم مختلفاً
        actual_translator_id = data.get("translator_id")
        if not actual_translator_id and user_id:
            translator_record = session.query(Translator).filter_by(tg_user_id=user_id).first()
            if translator_record:
                actual_translator_id = translator_record.id
                logger.info(f"✅ Found translator_id from Translator table: {actual_translator_id} ({translator_record.full_name})")
            else:
                logger.info(f"ℹ️ User {user_id} not found in Translator table")
        
        # ✅ تحويل التواريخ إلى naive datetime (SQLite لا يقبل tzinfo)
        def to_naive_datetime(dt):
            """تحويل datetime مع tzinfo إلى naive datetime"""
            if dt is None:
                return None
            # إذا كان string، حاول تحويله
            if isinstance(dt, str):
                try:
                    from dateutil import parser
                    dt = parser.parse(dt)
                except:
                    return None
            # إذا كان date فقط (بدون time)، حوله إلى datetime
            if hasattr(dt, 'year') and not hasattr(dt, 'hour'):
                from datetime import datetime as dt_module
                dt = dt_module.combine(dt, dt_module.min.time())
            # إزالة tzinfo إذا موجود
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                try:
                    from zoneinfo import ZoneInfo
                    return dt.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
                except:
                    return dt.replace(tzinfo=None)
            return dt
        
        # معالجة التواريخ
        followup_date = to_naive_datetime(data.get("followup_date"))
        report_date = to_naive_datetime(data.get("report_date")) or datetime.now()
        created_at = datetime.utcnow()
        
        # ✅ معالجة حقول تأجيل الموعد
        app_reschedule_reason_val = None
        app_reschedule_return_date_val = None
        app_reschedule_return_reason_val = None
        
        if flow_type == "appointment_reschedule":
            app_reschedule_reason_val = data.get("app_reschedule_reason", "")
            app_reschedule_return_reason_val = data.get("app_reschedule_return_reason") or data.get("followup_reason", "")
            return_date_raw = data.get("app_reschedule_return_date") or data.get("followup_date")
            if return_date_raw:
                app_reschedule_return_date_val = to_naive_datetime(return_date_raw)
            logger.info(f"💾 حفظ حقول تأجيل الموعد: reason={app_reschedule_reason_val}, return_date={app_reschedule_return_date_val}")
        
        # إنشاء التقرير
        new_report = Report(
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id if department else None,
            doctor_id=doctor.id if doctor else None,
            translator_id=actual_translator_id,  # ✅ استخدام translator_id الفعلي
            complaint_text=complaint_text,
            doctor_decision=decision_text,
            medical_action=final_medical_action,
            followup_date=followup_date,
            followup_reason=data.get("followup_reason", "لا يوجد"),
            report_date=report_date,
            created_at=created_at,
            submitted_by_user_id=user_id,  # ✅ حفظ معرف المستخدم الذي أنشأ التقرير
            # ✅ حفظ حقول تأجيل الموعد
            app_reschedule_reason=app_reschedule_reason_val,
            app_reschedule_return_date=app_reschedule_return_date_val,
            app_reschedule_return_reason=app_reschedule_return_reason_val
        )

        session.add(new_report)
        session.commit()
        session.refresh(new_report)

        report_id = new_report.id

        # الحصول على اسم المترجم (من data أولاً، ثم من translator_id)
        translator_name = data.get("translator_name", "غير محدد")
        if (not translator_name or translator_name == "غير محدد") and data.get("translator_id"):
            translator = session.query(Translator).filter_by(id=data["translator_id"]).first()
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

        # 📢 بث التقرير لجميع المستخدمين والإدارة

        try:
            from services.broadcast_service import broadcast_new_report

            # تجهيز بيانات البث
            followup_display = 'لا يوجد'
            if data.get('followup_date'):
                followup_display = data['followup_date'].strftime('%Y-%m-%d')
                if data.get('followup_time'):
                    followup_display += f" الساعة {data['followup_time']}"

            broadcast_data = {
                'report_id': report_id,  # ✅ إضافة معرف التقرير
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
                'translator_name': translator_name
            }
            
            # إضافة الحقول الفردية لـ surgery_consult لعرضها بشكل منفصل
            if flow_type == "surgery_consult":
                broadcast_data['diagnosis'] = data.get('diagnosis', '')
                broadcast_data['decision'] = data.get('decision', '')
                broadcast_data['operation_name_en'] = data.get('operation_name_en', '')
                broadcast_data['success_rate'] = data.get('success_rate', '')
                broadcast_data['benefit_rate'] = data.get('benefit_rate', '')
                broadcast_data['tests'] = data.get('tests', 'لا يوجد')
            
            # ✅ إضافة الحقول الخاصة لمسار تأجيل موعد
            if flow_type == "appointment_reschedule":
                logger.info(f"📅 save_report_to_database: معالجة مسار appointment_reschedule")
                
                # إضافة سبب تأجيل الموعد
                app_reschedule_reason = data.get('app_reschedule_reason', '')
                if app_reschedule_reason and str(app_reschedule_reason).strip():
                    broadcast_data['app_reschedule_reason'] = str(app_reschedule_reason).strip()
                    logger.info(f"✅ تم إضافة app_reschedule_reason إلى broadcast_data")
                else:
                    # محاولة الحصول عليه من report_tmp مباشرة
                    report_tmp = context.user_data.get("report_tmp", {})
                    app_reschedule_reason_from_tmp = report_tmp.get('app_reschedule_reason', '')
                    if app_reschedule_reason_from_tmp:
                        broadcast_data['app_reschedule_reason'] = str(app_reschedule_reason_from_tmp).strip()
                        logger.info(f"✅ تم الحصول على app_reschedule_reason من report_tmp")
                    else:
                        broadcast_data['app_reschedule_reason'] = ''
                        logger.warning(f"⚠️ app_reschedule_reason غير موجود")
                
                # استخدام app_reschedule_return_date إذا كان موجوداً
                return_date = data.get('app_reschedule_return_date') or data.get('followup_date')
                if return_date:
                    broadcast_data['app_reschedule_return_date'] = return_date
                    broadcast_data['followup_date'] = return_date
                
                # استخدام app_reschedule_return_reason إذا كان موجوداً
                return_reason = data.get('app_reschedule_return_reason') or data.get('followup_reason', 'لا يوجد')
                broadcast_data['app_reschedule_return_reason'] = return_reason
                broadcast_data['followup_reason'] = return_reason
                
                # إضافة followup_time إذا كان موجوداً
                if data.get('followup_time'):
                    broadcast_data['followup_time'] = data.get('followup_time')
            
            # ✅ إضافة الحقول الخاصة لمسار أشعة وفحوصات
            if flow_type == "radiology":
                logger.info(f"🔬 save_report_to_database: معالجة مسار radiology")
                
                # إضافة نوع الأشعة والفحوصات
                radiology_type = data.get('radiology_type', '')
                if radiology_type and str(radiology_type).strip():
                    broadcast_data['radiology_type'] = str(radiology_type).strip()
                    logger.info(f"✅ تم إضافة radiology_type إلى broadcast_data")
                
                # إضافة تاريخ تسليم النتائج
                delivery_date = data.get('radiology_delivery_date') or data.get('followup_date')
                if delivery_date:
                    if hasattr(delivery_date, 'strftime'):
                        broadcast_data['radiology_delivery_date'] = delivery_date.strftime('%Y-%m-%d')
                    else:
                        broadcast_data['radiology_delivery_date'] = str(delivery_date)
                    logger.info(f"✅ تم إضافة radiology_delivery_date إلى broadcast_data")

            await broadcast_new_report(context.bot, broadcast_data)
            logger.info(f"تم بث التقرير #{report_id} لجميع المستخدمين")
        except Exception as e:
            logger.error(f"خطأ في بث التقرير: {e}", exc_info=True)

        # الرد للمستخدم
        success_message = (
            f"✅ **تم حفظ التقرير بنجاح!**\n\n"
            f"📋 رقم التقرير: {report_id}\n"
            f"👤 المريض: {patient_name}\n"
            f"⚕️ نوع الإجراء: {action_names.get(flow_type, 'غير محدد')}\n"
        )
        
        # إضافة اسم العملية بالإنجليزية لمسار "استشارة مع قرار عملية"
        if flow_type == "surgery_consult" and data.get("operation_name_en"):
            success_message += f"🏥 **اسم العملية:** {data.get('operation_name_en')}\n"
        
        success_message += f"\nتم إرسال التقرير لجميع المستخدمين."
        
        await query.edit_message_text(
            success_message,
            parse_mode="Markdown"
        )

        # مسح البيانات المؤقتة
        context.user_data.pop("report_tmp", None)

        logger.info(f"تم حفظ التقرير #{report_id} - نوع: {flow_type}")


    except Exception as e:
        logger.error(f"خطأ في حفظ التقرير: {e}", exc_info=True)

        try:
            session.rollback()
            session.close()
        except Exception:
            pass

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
    
    try:
        msg_text = update.message.text if update.message else 'N/A'
    except UnicodeEncodeError:
        msg_text = '[Unicode Error]'
    
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
    
    # محاولة تحديد الحالة بناءً على البيانات
    # استشارة جديدة
    if medical_action == "استشارة جديدة" or current_flow == "new_consult":
        if not complaint:
            return await handle_new_consult_complaint(update, context)
        elif not diagnosis:
            return await handle_new_consult_diagnosis(update, context)
        elif not decision:
            return await handle_new_consult_decision(update, context)
        elif not tests:
            return await handle_new_consult_tests(update, context)
        elif not followup_reason:
            return await handle_new_consult_followup_reason(update, context)
        elif not translator_name:
            await show_translator_selection(update.message, context, "new_consult")
            return NEW_CONSULT_TRANSLATOR
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
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == SURGERY_CONSULT_DIAGNOSIS or not diagnosis:
            return await handle_surgery_consult_diagnosis(update, context)
        elif current_state == SURGERY_CONSULT_DECISION or not decision:
            return await handle_surgery_consult_decision(update, context)
        elif current_state == SURGERY_CONSULT_NAME_EN or not name_en:
            return await handle_surgery_consult_name_en(update, context)
        elif current_state == SURGERY_CONSULT_SUCCESS_RATE or not success_rate:
            return await handle_surgery_consult_success_rate(update, context)
        elif current_state == SURGERY_CONSULT_BENEFIT_RATE or not report_tmp.get("benefit_rate"):
            return await handle_surgery_consult_benefit_rate(update, context)
        elif current_state == SURGERY_CONSULT_TESTS or not tests:
            return await handle_surgery_consult_tests(update, context)
        elif current_state == SURGERY_CONSULT_FOLLOWUP_REASON or not followup_reason:
            return await handle_surgery_consult_followup_reason(update, context)
    # استشارة أخيرة
    elif medical_action == "استشارة أخيرة" or current_flow == "final_consult":
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        recommendations = report_tmp.get("recommendations")
        
        logger.debug(f"DEBUG: final_consult flow - diagnosis={repr(diagnosis)}, decision={repr(decision)}, recommendations={repr(recommendations)}")
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == FINAL_CONSULT_DIAGNOSIS or not diagnosis:
            return await handle_final_consult_diagnosis(update, context)
        elif current_state == FINAL_CONSULT_DECISION or not decision:
            return await handle_final_consult_decision(update, context)
        elif current_state == FINAL_CONSULT_RECOMMENDATIONS or not recommendations:
            return await handle_final_consult_recommendations(update, context)
    # طوارئ
    elif medical_action == "طوارئ" or current_flow == "emergency":
        complaint = report_tmp.get("complaint")
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        status = report_tmp.get("status")
        followup_reason = report_tmp.get("followup_reason")
        
        logger.debug(f"DEBUG: emergency flow - complaint={repr(complaint)}, diagnosis={repr(diagnosis)}, decision={repr(decision)}, status={repr(status)}, followup_reason={repr(followup_reason)}")
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == EMERGENCY_COMPLAINT or not complaint:
            return await handle_emergency_complaint(update, context)
        elif current_state == EMERGENCY_DIAGNOSIS or not diagnosis:
            return await handle_emergency_diagnosis(update, context)
        elif current_state == EMERGENCY_DECISION or not decision:
            return await handle_emergency_decision(update, context)
        elif current_state == EMERGENCY_STATUS or not status:
            return await handle_emergency_status_text(update, context)
        elif current_state == EMERGENCY_REASON or not followup_reason:
            return await handle_emergency_reason(update, context)
    # متابعة في الرقود
    elif medical_action == "متابعة في الرقود" or current_flow == "followup":
        complaint = report_tmp.get("complaint")
        diagnosis = report_tmp.get("diagnosis")
        decision = report_tmp.get("decision")
        followup_reason = report_tmp.get("followup_reason")
        
        logger.debug(f"DEBUG: followup flow - complaint={repr(complaint)}, diagnosis={repr(diagnosis)}, decision={repr(decision)}, followup_reason={repr(followup_reason)}")
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == FOLLOWUP_COMPLAINT or not complaint:
            return await handle_followup_complaint(update, context)
        elif current_state == FOLLOWUP_DIAGNOSIS or not diagnosis:
            return await handle_followup_diagnosis(update, context)
        elif current_state == FOLLOWUP_DECISION or not decision:
            return await handle_followup_decision(update, context)
        elif current_state == FOLLOWUP_REASON or not followup_reason:
            return await handle_followup_reason(update, context)
    # عملية
    elif medical_action == "عملية" or current_flow == "operation":
        operation_details = report_tmp.get("operation_details")
        operation_name_en = report_tmp.get("operation_name_en")
        notes = report_tmp.get("notes")
        followup_reason = report_tmp.get("followup_reason")
        
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == OPERATION_DETAILS_AR or not operation_details:
            return await handle_operation_details_ar(update, context)
        elif current_state == OPERATION_NAME_EN or not operation_name_en:
            return await handle_operation_name_en(update, context)
        elif current_state == OPERATION_NOTES or not notes:
            return await handle_operation_notes(update, context)
        elif current_state == OPERATION_FOLLOWUP_REASON or not followup_reason:
            return await handle_operation_followup_reason(update, context)
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
    
    # Return current state to stay in conversation
    return current_state if current_state != 'NOT SET' else None

# =============================
# Helper Functions - استيراد handlers من flows/new_consult.py
# =============================

# =============================
# دوال مساعدة للحصول على handlers المحلية
# =============================

def _get_new_consult_handler(handler_name):
    """الحصول على handler من التعريفات المحلية في هذا الملف"""
    # استخدام globals() للحصول على handler مباشرة من هذا الملف
    handler = globals().get(handler_name)
    return handler

def _get_followup_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_emergency_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_admission_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_surgery_consult_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_operation_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_final_consult_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_discharge_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_rehab_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_radiology_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

def _get_app_reschedule_handler(handler_name):
    """الحصول على handler من التعريفات المحلية"""
    return globals().get(handler_name)

# =============================
# تسجيل الـ ConversationHandler
# =============================

def register(app):
    """تسجيل جميع handlers للمرحلة 1"""

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
                    patients = s.query(Patient).filter(
                        Patient.full_name.ilike(f"%{query_text}%")
                    ).limit(20).all()
                else:
                    patients = s.query(Patient).order_by(Patient.created_at.desc()).limit(20).all()

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
            logger.error(f"❌ خطأ في البحث عن المرضى من قاعدة البيانات: {db_error}")
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

                    # إنشاء نتائج من الملف
                    for idx, name in enumerate(names[:20]):
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
            results.append(InlineQueryResultArticle(
                id="no_patients",
                title="⚠️ لا توجد أسماء مرضى",
                description="جرب البحث باسم مريض محدد",
                input_message_content=InputTextMessageContent(
                    message_text="__PATIENT_SELECTED__:0:لا يوجد"
                )
            ))

        await update.inline_query.answer(results, cache_time=1)

        async def handle_view_reschedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            """عرض سبب تأجيل الموعد عند الضغط على الزر في مجموعة البث"""
            try:
                query = update.callback_query
                if not query or not query.data:
                    return
                await query.answer()
                parts = query.data.split(':', 1)
                if len(parts) < 2:
                    await query.message.reply_text("⚠️ لم يتم تحديد التقرير.")
                    return
                try:
                    report_id = int(parts[1])
                except:
                    await query.message.reply_text("⚠️ معرف تقرير غير صالح.")
                    return

                # جلب التقرير من قاعدة البيانات
                from db.session import SessionLocal
                from db.models import Report

                with SessionLocal() as s:
                    report = s.query(Report).filter_by(id=report_id).first()
                    if not report:
                        await query.message.reply_text("⚠️ لم يتم العثور على التقرير.")
                        return

                    # محاولة استخراج معلومات التأجيل من الحقول المتاحة
                    # الحقل الأساسي هو app_reschedule_reason
                    reason = None
                    
                    # أولاً: التحقق من الحقل الصحيح app_reschedule_reason
                    if getattr(report, 'app_reschedule_reason', None):
                        reason = report.app_reschedule_reason
                    # ثانياً: fallback إلى followup_reason
                    elif getattr(report, 'followup_reason', None):
                        reason = report.followup_reason
                    # ثالثاً: fallback إلى doctor_decision إذا كان يحتوي على سبب التأجيل
                    elif getattr(report, 'doctor_decision', None) and 'سبب تأجيل' in str(report.doctor_decision):
                        reason = report.doctor_decision

                    # إذا لم نوجد سبباً واضحاً، عرض رسالة ملائمة
                    if not reason or not str(reason).strip():
                        await query.message.reply_text("ℹ️ لا يوجد سبب تأجيل مسجل لهذا التقرير.")
                        return

                    # بناء رسالة شاملة
                    text = f"📅 **سبب تأجيل الموعد للتقرير #{report_id}:**\n\n{reason}"
                    
                    # إضافة تاريخ العودة إذا كان موجوداً
                    return_date = getattr(report, 'app_reschedule_return_date', None) or getattr(report, 'followup_date', None)
                    if return_date:
                        if hasattr(return_date, 'strftime'):
                            text += f"\n\n📅 **موعد العودة:** {return_date.strftime('%Y-%m-%d')}"
                        else:
                            text += f"\n\n📅 **موعد العودة:** {return_date}"
                    
                    # إضافة سبب العودة إذا كان موجوداً
                    return_reason = getattr(report, 'app_reschedule_return_reason', None)
                    if return_reason and str(return_reason).strip():
                        text += f"\n\n✍️ **سبب العودة:** {return_reason}"
                    
                    await query.message.reply_text(text, parse_mode="Markdown")

            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(f"خطأ في handle_view_reschedule_callback: {e}")
                try:
                    await update.callback_query.message.reply_text("⚠️ حدث خطأ أثناء جلب بيانات التأجيل.")
                except:
                    pass

        # تسجيل معالج global للزر view_reschedule (يجب أن يكون خارج ConversationHandler)
        try:
            from telegram.ext import CallbackQueryHandler
            app.add_handler(CallbackQueryHandler(handle_view_reschedule_callback, pattern="^view_reschedule:"))
        except Exception:
            pass

    async def doctor_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler بسيط للبحث عن الأطباء مع فلترة حسب المستشفى والقسم"""
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


            # البحث عن الأطباء مع الفلترة
            doctors_results = search_doctors(
                query=query_text if query_text else "",
                hospital=search_hospital if search_hospital else None,
                department=department_name if department_name else None,
                limit=20  # زيادة العدد للحصول على نتائج أكثر
            )


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

        except Exception as e:
            import traceback
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
            # دعم الأزرار (CallbackQuery) - مهم للعمل بعد الإلغاء
            CallbackQueryHandler(start_report, pattern="^start_report$"),
            # دعم النص
            MessageHandler(filters.Regex(r"^📝\s*إضافة\s*تقرير\s*جديد\s*$"), start_report),
            MessageHandler(filters.Regex(r"^📝\s*إضافة تقرير جديد\s*$"), start_report),
            MessageHandler(filters.Regex(r"^📝 إضافة تقرير جديد$"), start_report),
            MessageHandler(filters.Regex(r"إضافة تقرير جديد"), start_report),
            MessageHandler(filters.TEXT & filters.Regex(r"📝.*إضافة.*تقرير.*جديد"), start_report),
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
            ],
            STATE_SELECT_PATIENT: [
                CallbackQueryHandler(handle_patient_selection, pattern="^patient_idx:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            R_PATIENT: [
                CallbackQueryHandler(handle_patient_selection, pattern="^patient_idx:"),
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
                CallbackQueryHandler(handle_doctor_btn_selection, pattern="^doctor_idx:"),
                CallbackQueryHandler(handle_doctor_page, pattern="^doctor_page:"),
                CallbackQueryHandler(handle_doctor_selection, pattern="^doctor_manual$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            R_DOCTOR: [
                CallbackQueryHandler(handle_doctor_btn_selection, pattern="^doctor_idx:"),
                CallbackQueryHandler(handle_doctor_page, pattern="^doctor_page:"),
                CallbackQueryHandler(handle_doctor_selection, pattern="^doctor_manual$"),
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
            # ✅ استخدام handlers من flows/new_consult.py
            NEW_CONSULT_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_complaint')),
            ],
            NEW_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_diagnosis')),
            ],
            NEW_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_decision')),
            ],
            NEW_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_tests')),
            ],
            NEW_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_calendar_nav'), pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_calendar_day'), pattern="^followup_cal_day:"),
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_date_skip'), pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
            ],
            NEW_CONSULT_FOLLOWUP_TIME: [
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_time_hour'), pattern="^followup_time_hour:"),
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_time_skip'), pattern="^followup_time_skip"),
            ],
            NEW_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_followup_reason')),
            ],
            NEW_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            NEW_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # حالة تعديل حقل مفرد
            "EDIT_DRAFT_FIELD": [
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # حالة تعديل تاريخ العودة بالتقويم (للمسودة)
            "EDIT_DRAFT_FOLLOWUP_CALENDAR": [
                CallbackQueryHandler(handle_draft_edit_calendar_nav, pattern="^draft_edit_cal_nav:"),
                CallbackQueryHandler(handle_draft_edit_calendar_day, pattern="^draft_edit_cal_day:"),
                CallbackQueryHandler(handle_draft_edit_cal_skip, pattern="^draft_edit_cal_skip$"),
                CallbackQueryHandler(handle_draft_edit_time_hour, pattern="^draft_edit_time_hour:"),
                CallbackQueryHandler(handle_draft_edit_time_minute, pattern="^draft_edit_time_minute:"),
                CallbackQueryHandler(handle_draft_edit_time_skip, pattern="^draft_edit_time_skip$"),
                CallbackQueryHandler(handle_draft_edit_back_calendar, pattern="^draft_edit_back_calendar$"),
                CallbackQueryHandler(handle_draft_edit_back_hour, pattern="^draft_edit_back_hour$"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
            ],
            # مسار استشارة مع قرار عملية (handlers من flows/surgery_consult.py)
            SURGERY_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_diagnosis')),
            ],
            SURGERY_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_decision')),
            ],
            SURGERY_CONSULT_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_name_en')),
            ],
            SURGERY_CONSULT_SUCCESS_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_success_rate')),
            ],
            SURGERY_CONSULT_BENEFIT_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_benefit_rate')),
            ],
            SURGERY_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_tests')),
            ],
            SURGERY_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
            ],
            SURGERY_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_followup_reason')),
            ],
            SURGERY_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            SURGERY_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار استشارة أخيرة (handlers من flows/final_consult.py)
            FINAL_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_final_consult_handler('handle_final_consult_diagnosis')),
            ],
            FINAL_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_final_consult_handler('handle_final_consult_decision')),
            ],
            FINAL_CONSULT_RECOMMENDATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_final_consult_handler('handle_final_consult_recommendations')),
            ],
            FINAL_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            FINAL_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار متابعة في الرقود (handlers من flows/followup.py)
            FOLLOWUP_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_complaint')),
            ],
            FOLLOWUP_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_diagnosis')),
            ],
            FOLLOWUP_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_decision')),
            ],
            # تم حذف FOLLOWUP_ROOM_FLOOR - لم يعد مستخدماً
            FOLLOWUP_DATE_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_reason')),
            ],
            FOLLOWUP_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            FOLLOWUP_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار طوارئ (handlers من flows/emergency.py)
            EMERGENCY_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_complaint')),
            ],
            EMERGENCY_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_diagnosis')),
            ],
            EMERGENCY_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_decision')),
            ],
            EMERGENCY_STATUS: [
                CallbackQueryHandler(_get_emergency_handler('handle_emergency_status_choice'), pattern="^emerg_status:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_status_text')),
            ],
            EMERGENCY_ADMISSION_TYPE: [
                CallbackQueryHandler(_get_emergency_handler('handle_emergency_admission_type_choice'), pattern="^emerg_admission:"),
            ],
            EMERGENCY_ROOM_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_room_number')),
            ],
            EMERGENCY_DATE_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_date_time_text')),
            ],
            EMERGENCY_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_reason')),
            ],
            EMERGENCY_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            EMERGENCY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار عملية (handlers من flows/operation.py)
            OPERATION_DETAILS_AR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_details_ar')),
            ],
            OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_name_en')),
            ],
            OPERATION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_notes')),
            ],
            OPERATION_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
            ],
            OPERATION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_followup_reason')),
            ],
            OPERATION_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            OPERATION_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار علاج طبيعي / أجهزة تعويضية (handlers من flows/rehab.py)
            REHAB_TYPE: [
                CallbackQueryHandler(_get_rehab_handler('handle_rehab_type'), pattern="^rehab_type:"),
            ],
            PHYSICAL_THERAPY_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_physical_therapy_details')),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_physical_therapy_followup_reason')),
            ],
            PHYSICAL_THERAPY_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            PHYSICAL_THERAPY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            DEVICE_NAME_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_device_name_details')),
            ],
            DEVICE_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
            ],
            DEVICE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_device_followup_reason')),
            ],
            DEVICE_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            DEVICE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار أشعة وفحوصات
            RADIOLOGY_TYPE: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiology_type),
            ],
            RADIOLOGY_DELIVERY_DATE: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_radiology_calendar_nav, pattern="^radiology_cal_(prev|next):"),
                CallbackQueryHandler(handle_radiology_calendar_day, pattern="^radiology_cal_day:"),
            ],
            RADIOLOGY_TRANSLATOR: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            RADIOLOGY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار ترقيد (handlers من flows/admission.py)
            ADMISSION_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_reason')),
            ],
            ADMISSION_ROOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_room')),
            ],
            ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_notes')),
            ],
            ADMISSION_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
            ],
            ADMISSION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_followup_reason')),
            ],
            ADMISSION_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            ADMISSION_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار خروج من المستشفى (handlers من flows/discharge.py)
            DISCHARGE_TYPE: [
                CallbackQueryHandler(_get_discharge_handler('handle_discharge_type'), pattern="^discharge_type:"),
            ],
            DISCHARGE_ADMISSION_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_admission_summary')),
            ],
            DISCHARGE_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_operation_details')),
            ],
            DISCHARGE_OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_operation_name_en')),
            ],
            DISCHARGE_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
            ],
            DISCHARGE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_followup_reason')),
            ],
            DISCHARGE_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            DISCHARGE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # مسار تأجيل موعد
            APP_RESCHEDULE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_app_reschedule_reason),
            ],
            APP_RESCHEDULE_RETURN_DATE: [
                CallbackQueryHandler(handle_reschedule_calendar_nav, pattern="^reschedule_cal_nav:"),
                CallbackQueryHandler(handle_reschedule_calendar_day, pattern="^reschedule_cal_day:"),
            ],
            APP_RESCHEDULE_RETURN_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_app_reschedule_return_reason),
            ],
            APP_RESCHEDULE_TRANSLATOR: [
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            APP_RESCHEDULE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^save:"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_draft_field_input),
            ],
            # State عام لمعالجة التعديل
            "EDIT_FIELD": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_field_input),
            ],
            # أضف هنا باقي المسارات بنفس الطريقة (FOLLOWUP_COMPLAINT، ADMISSION_COMPLAINT، ...)
        },
        fallbacks=[
            # معالجات للمرضى (أزرار اختيار المريض والتنقل بين الصفحات)
            CallbackQueryHandler(handle_patient_btn_selection, pattern="^patient_idx:"),
            CallbackQueryHandler(handle_patient_page, pattern="^user_patient_page:"),
            
            # معالجات للمستشفيات
            CallbackQueryHandler(handle_hospital_page, pattern="^hosp_page:"),
            CallbackQueryHandler(handle_hospital_selection, pattern="^select_hospital:"),

            CallbackQueryHandler(handle_cancel_navigation, pattern="^nav:cancel"),
            CommandHandler("cancel", handle_cancel_navigation),
            # معالج للرسائل التي تحتوي على "إضافة تقرير جديد" (للتعامل مع الأزرار)
            MessageHandler(filters.TEXT & filters.Regex(r".*إضافة.*تقرير.*جديد.*"), start_report),
            # معالج زر الرجوع - يعمل في جميع الـ states
            CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            # معالج زر الإلغاء - يعمل في جميع الـ states
            CallbackQueryHandler(handle_cancel_navigation, pattern="^nav:cancel$"),
            # DEBUG: إضافة fallback لالتقاط جميع callbacks غير متطابقة في حالة R_ACTION_TYPE
            CallbackQueryHandler(debug_all_callbacks, pattern=".*"),
        ],
        per_message=False,
        per_chat=True,
        per_user=True,
    )
    # ❌ تم إزالة unified_inline_query_handler - نستخدم user_patient_search_inline.py بدلاً منه
    # ✅ user_patient_search_inline.py مسجل في handlers_registry.py قبل هذا الملف
    # ✅ يعمل بشكل مستقل ولا يتطلب report_tmp

    # ❌ تم إزالة unified_inline_query_handler - نستخدم user_patient_search_inline.py بدلاً منه
    # ✅ user_patient_search_inline.py مسجل في handlers_registry.py قبل هذا الملف
    # ✅ ثم تسجيل ConversationHandler
    app.add_handler(conv_handler)


# ================================================
# 🆕 نظام المترجمين الجديد - مبسط وسريع
# ================================================

def load_translator_names():
    """
    قراءة أسماء المترجمين من الخدمة الموحدة
    """
    try:
        from services.translators_service import get_all_translator_names
        names = get_all_translator_names()
        if names:
            return names
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ فشل تحميل المترجمين: {e}")
    
    # قائمة احتياطية في حالة فشل التحميل
    return ["مصطفى", "واصل", "نجم الدين", "محمد علي", "سعيد", "مهدي", "صبري", "عزي", "معتز", "ادريس", "هاشم", "ادم", "زيد", "عصام", "عزالدين", "حسن", "زين العابدين", "عبدالسلام", "ياسر", "يحيى"]

async def show_translator_selection(message, context, flow_type):
    """
    عرض قائمة المترجمين للاختيار
    """
    translator_names = load_translator_names()

    if not translator_names:
        await message.reply_text("❌ خطأ: لا توجد أسماء مترجمين متاحة")
        # المتابعة بدون مترجم
        await show_final_summary(message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    # تقسيم الأسماء إلى صفوف (3 أسماء لكل صف)
    keyboard_buttons = []
    row = []

    for i, name in enumerate(translator_names):
        row.append(InlineKeyboardButton(name, callback_data=f"simple_translator:{flow_type}:{i}"))
        if len(row) == 3 or i == len(translator_names) - 1:
            keyboard_buttons.append(row)
            row = []

    # إضافة زر الرجوع وإلغاء
    keyboard_buttons.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await message.reply_text(
        f"👤 **اختر اسم المترجم**\n\n"
        f"المترجم مسؤول عن ترجمة التقرير إلى اللغة المطلوبة.\n"
        f"اختر من القائمة أدناه:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_simple_translator_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة اختيار المترجم البسيط
    """
    query = update.callback_query
    await query.answer()

    try:
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return

        flow_type = parts[1]
        choice = parts[2]

        if choice == "skip":
            # تخطي المترجم
            translator_name = "غير محدد"
            translator_id = None
        else:
            # اختيار مترجم من القائمة
            translator_names = load_translator_names()
            try:
                index = int(choice)
                translator_name = translator_names[index]
                translator_id = None  # لا نحتاج id للمترجمين الثابتين
            except (IndexError, ValueError):
                await query.edit_message_text("❌ اختيار غير صحيح")
                return

        # حفظ اسم المترجم
        context.user_data.setdefault("report_tmp", {})
        context.user_data["report_tmp"]["translator_name"] = translator_name
        context.user_data["report_tmp"]["translator_id"] = translator_id

        # المتابعة للتأكيد النهائي
        await query.edit_message_text(f"✅ تم اختيار المترجم: **{translator_name}**")
        await show_final_summary(query.message, context, flow_type)

        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        await query.edit_message_text("❌ حدث خطأ في معالجة الاختيار")
        return
