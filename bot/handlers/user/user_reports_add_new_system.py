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

# ✅ استيراد router للتعديل قبل النشر - يتم بعد تعريف logger
route_edit_field_selection = None
route_edit_field_input = None

def _import_edit_routers():
    """استيراد routers للتعديل - يتم استدعاؤها بعد تعريف logger"""
    global route_edit_field_selection, route_edit_field_input
    try:
        from bot.handlers.user.user_reports_add_new_system.edit_handlers.before_publish.router import (
            route_edit_field_selection as _route_selection,
            route_edit_field_input as _route_input,
        )
        route_edit_field_selection = _route_selection
        route_edit_field_input = _route_input
        logger.info("✅ تم استيراد edit routers بنجاح")
    except ImportError as e:
        logger.warning(f"⚠️ Cannot import edit handlers router: {e} - edit before publish may not work")

# استيراد routers بعد تعريف logger
_import_edit_routers()

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
    TIMEZONE = 'Asia/Kolkata'  # توقيت الهند (IST = UTC+5:30)
from datetime import datetime, timedelta, date
import calendar
import hashlib
import os
from .user_reports_add_helpers import (
    PREDEFINED_HOSPITALS, PREDEFINED_DEPARTMENTS, DIRECT_DEPARTMENTS,
    PREDEFINED_ACTIONS, validate_text_input, validate_english_only, save_report_to_db,
    broadcast_report, create_evaluation
)

# استيراد handle_final_confirm من flows/shared.py
try:
    from .flows.shared import handle_final_confirm
except ImportError:
    logger.warning("⚠️ Cannot import handle_final_confirm from flows/shared.py")
    handle_final_confirm = None
from services.error_monitoring import error_monitor
from services.doctors_smart_search import search_doctors
from services.smart_cancel_manager import SmartCancelManager

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

# مسار 2: مراجعة/عودة دورية ومتابعة في الرقود (16-23) - 8 حقول
# ✅ FOLLOWUP_ROOM_FLOOR يُستخدم فقط لمسار "متابعة في الرقود" وليس "مراجعة / عودة دورية"
(
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,  # FOLLOWUP_ROOM_FLOOR فقط لـ "متابعة في الرقود"
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM
) = range(16, 24)

# مسار 3: طوارئ (24-35) - مدمج بالفعل ✓ (تم تصحيح التداخل)
(
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION,
    EMERGENCY_STATUS, EMERGENCY_ADMISSION_NOTES, EMERGENCY_OPERATION_DETAILS,
    EMERGENCY_ADMISSION_TYPE, EMERGENCY_ROOM_NUMBER,
    EMERGENCY_DATE_TIME, EMERGENCY_REASON,
    EMERGENCY_TRANSLATOR, EMERGENCY_CONFIRM
) = range(24, 36)

# مسار 4: ترقيد (36-42) - سيصبح مدمج (تم تصحيح التداخل)
(
    ADMISSION_REASON, ADMISSION_ROOM, ADMISSION_NOTES,
    ADMISSION_FOLLOWUP_DATE, ADMISSION_FOLLOWUP_REASON,
    ADMISSION_TRANSLATOR, ADMISSION_CONFIRM
) = range(36, 43)

# مسار 5: استشارة مع قرار عملية (43-52) - سيصبح مدمج (تم تصحيح التداخل)
(
    SURGERY_CONSULT_DIAGNOSIS, SURGERY_CONSULT_DECISION, SURGERY_CONSULT_NAME_EN,
    SURGERY_CONSULT_SUCCESS_RATE, SURGERY_CONSULT_BENEFIT_RATE, SURGERY_CONSULT_TESTS, SURGERY_CONSULT_FOLLOWUP_DATE,
    SURGERY_CONSULT_FOLLOWUP_REASON,
    SURGERY_CONSULT_TRANSLATOR, SURGERY_CONSULT_CONFIRM
) = range(43, 53)

# مسار 6: عملية (53-59) - سيصبح مدمج (تم تصحيح التداخل)
(
    OPERATION_DETAILS_AR, OPERATION_NAME_EN, OPERATION_NOTES,
    OPERATION_FOLLOWUP_DATE, OPERATION_FOLLOWUP_REASON,
    OPERATION_TRANSLATOR, OPERATION_CONFIRM
) = range(53, 60)

# مسار 7: استشارة أخيرة (60-64) (تم تصحيح التداخل)
(
    FINAL_CONSULT_DIAGNOSIS, FINAL_CONSULT_DECISION, FINAL_CONSULT_RECOMMENDATIONS,
    FINAL_CONSULT_TRANSLATOR, FINAL_CONSULT_CONFIRM
) = range(60, 65)

# مسار 8: خروج من المستشفى (65-72) - سيصبح مدمج (تم تصحيح التداخل)
(
    DISCHARGE_TYPE, DISCHARGE_ADMISSION_SUMMARY, DISCHARGE_OPERATION_DETAILS,
    DISCHARGE_OPERATION_NAME_EN, DISCHARGE_FOLLOWUP_DATE, DISCHARGE_FOLLOWUP_REASON,
    DISCHARGE_TRANSLATOR, DISCHARGE_CONFIRM
) = range(65, 73)

# مسار 9: علاج طبيعي / أجهزة تعويضية (73-83) - سيصبح مدمج (تم تصحيح التداخل)
(
    REHAB_TYPE, PHYSICAL_THERAPY_DETAILS, PHYSICAL_THERAPY_FOLLOWUP_DATE,
    PHYSICAL_THERAPY_FOLLOWUP_REASON,
    PHYSICAL_THERAPY_TRANSLATOR, PHYSICAL_THERAPY_CONFIRM,
    DEVICE_NAME_DETAILS, DEVICE_FOLLOWUP_DATE,
    DEVICE_FOLLOWUP_REASON, DEVICE_TRANSLATOR, DEVICE_CONFIRM
) = range(73, 84)

# مسار 10: أشعة وفحوصات (82-85) (تم تصحيح التداخل)
(
    RADIOLOGY_TYPE, RADIOLOGY_DELIVERY_DATE, RADIOLOGY_TRANSLATOR, RADIOLOGY_CONFIRM
) = range(84, 88)

# مسار 11: تأجيل موعد (88-93)
(
    APP_RESCHEDULE_REASON, APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON,
    APP_RESCHEDULE_TRANSLATOR, APP_RESCHEDULE_CONFIRM
) = range(88, 93)

# مسار 12: جلسة إشعاعي (93-101)
(
    RADIATION_THERAPY_TYPE,           # نوع الإشعاعي
    RADIATION_THERAPY_SESSION_NUMBER, # رقم الجلسة
    RADIATION_THERAPY_REMAINING,      # الجلسات المتبقية
    RADIATION_THERAPY_NOTES,          # ملاحظات أو توصيات
    RADIATION_THERAPY_RETURN_DATE,    # تاريخ العودة والوقت
    RADIATION_THERAPY_RETURN_REASON,  # سبب العودة
    RADIATION_THERAPY_TRANSLATOR,     # اسم المترجم
    RADIATION_THERAPY_CONFIRM         # تأكيد
) = range(93, 101)

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

# ✅ تهيئة المتغيرات المشتركة لتجنب NameError
_chunked = None
_cancel_kb = None
_nav_buttons = None

# ✅ محاولة استيراد الأدوات المشتركة من utils.py أولاً
try:
    from .utils import _chunked as _chunked_utils, _cancel_kb, _nav_buttons
    if _chunked_utils is not None:
        _chunked = _chunked_utils
    logger.info("✅ تم استيراد utils.py بنجاح")
except ImportError as e:
    logger.warning(f"⚠️ Cannot import utilities from utils.py: {e} - using local definitions")
    _chunked_utils = None

# ✅ تعريف محلي إذا فشل الاستيراد أو كان None
if _chunked is None:
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
        # إرجاع END دائمًا بعد الإلغاء لأي حالة
        return ConversationHandler.END

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
    flow_type = context.user_data.get('report_tmp', {}).get('current_flow')
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

    previous_step = smart_nav_manager.get_previous_step(flow_type, current_state, context)

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
                'EMERGENCY_ADMISSION_NOTES': 'EMERGENCY_STATUS',
                'EMERGENCY_OPERATION_DETAILS': 'EMERGENCY_STATUS',
                'EMERGENCY_ADMISSION_TYPE': 'EMERGENCY_ADMISSION_NOTES',
                'EMERGENCY_ROOM_NUMBER': 'EMERGENCY_ADMISSION_TYPE',
                'EMERGENCY_DATE_TIME': 'EMERGENCY_STATUS',  # للخروج أو العملية
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
                FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,   # ✅ رجوع لنوع الإجراء (تدفق طبيعي)
                FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,
                FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,
                FOLLOWUP_ROOM_FLOOR: FOLLOWUP_DECISION,
                FOLLOWUP_DATE_TIME: FOLLOWUP_ROOM_FLOOR,
                FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,
                FOLLOWUP_TRANSLATOR: FOLLOWUP_REASON,
                FOLLOWUP_CONFIRM: FOLLOWUP_TRANSLATOR,
            },

            # تدفق مراجعة / عودة دورية
            'periodic_followup': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,         # خطوة واحدة: شكوى ← نوع الإجراء
                FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,               # خطوة واحدة: تشخيص ← شكوى المريض
                FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,                # خطوة واحدة: قرار ← تشخيص
                # تخطي رقم الغرفة
                FOLLOWUP_DATE_TIME: FOLLOWUP_DECISION,                # خطوة واحدة: تاريخ ← قرار
                FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,                  # خطوة واحدة: سبب ← تاريخ
                FOLLOWUP_TRANSLATOR: FOLLOWUP_REASON,                 # خطوة واحدة: مترجم ← سبب
                FOLLOWUP_CONFIRM: FOLLOWUP_TRANSLATOR,
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
            # ✅ خريطة الرجوع تعتمد على discharge_type (يتم حلها ديناميكياً في get_previous_step)
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
                'DISCHARGE_OPERATION_DETAILS': 'DISCHARGE_TYPE',
                'DISCHARGE_OPERATION_NAME_EN': 'DISCHARGE_OPERATION_DETAILS',
                # DISCHARGE_FOLLOWUP_DATE: يتم حله ديناميكياً حسب discharge_type
                # admission → DISCHARGE_ADMISSION_SUMMARY
                # operation → DISCHARGE_OPERATION_NAME_EN
                'DISCHARGE_FOLLOWUP_DATE': '_DYNAMIC_DISCHARGE_BACK_',
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

    def get_previous_step(self, flow_type, current_step, context=None):
        """
        الحصول على الخطوة السابقة بدقة لنوع التدفق المحدد
        context: اختياري - يُستخدم لتحديد المسار الديناميكي (مثل discharge_type)
        """
        import logging
        logger = logging.getLogger(__name__)

        # ✅ تسجيل تفصيلي للتشخيص
        logger.info(f"🔍 GET_PREVIOUS_STEP: flow_type='{flow_type}', current_step={current_step}")

        if flow_type not in self.step_flows:
            logger.warning(f"⚠️ Flow type '{flow_type}' not found in step_flows")
            return STATE_SELECT_ACTION_TYPE

        flow_map = self.step_flows[flow_type]
        logger.info(f"🗺️ Using flow_map for '{flow_type}': {flow_map}")
        
        # ✅ أولاً: تحقق إذا كان current_step موجود مباشرة في flow_map (كرقم)
        if current_step in flow_map:
            prev_step = flow_map[current_step]
            prev_step = self._resolve_dynamic_back(prev_step, flow_type, context, logger)
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
            'FOLLOWUP_ROOM_FLOOR': FOLLOWUP_ROOM_FLOOR,
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
        # ✅ معالجة خاصة: إذا كانت هناك قيم مكررة، نأخذ أول قيمة
        value_to_state_name = {}
        for k, v in state_name_to_value.items():
            if v not in value_to_state_name:  # فقط إذا لم يكن موجوداً
                value_to_state_name[v] = k
        
        # ✅ تقليل logging لتجنب التأخير
        logger.debug(f"🔍 Looking for previous step: current_step={current_step}, flow_type={flow_type}")
        
        # ✅ معالجة خاصة لمسار followup و periodic_followup - أولوية عالية
        if flow_type in ['followup', 'periodic_followup'] and isinstance(current_step, int):
            # تحويل مباشر للأرقام إلى أسماء FOLLOWUP
            followup_state_map = {
                FOLLOWUP_COMPLAINT: 'FOLLOWUP_COMPLAINT',
                FOLLOWUP_DIAGNOSIS: 'FOLLOWUP_DIAGNOSIS',
                FOLLOWUP_DECISION: 'FOLLOWUP_DECISION',
                FOLLOWUP_ROOM_FLOOR: 'FOLLOWUP_ROOM_FLOOR',
                FOLLOWUP_DATE_TIME: 'FOLLOWUP_DATE_TIME',
                FOLLOWUP_REASON: 'FOLLOWUP_REASON',
                FOLLOWUP_TRANSLATOR: 'FOLLOWUP_TRANSLATOR',
                FOLLOWUP_CONFIRM: 'FOLLOWUP_CONFIRM',
            }
            current_step_name = followup_state_map.get(current_step)
            if current_step_name and current_step_name in flow_map:
                prev_step = flow_map[current_step_name]
                logger.debug(f"✅ [FOLLOWUP] Found: {current_step_name} -> {prev_step} (type: {type(prev_step).__name__})")
                # ✅ معالجة الخطوة السابقة - قد تكون رقم أو string
                if isinstance(prev_step, str):
                    # إذا كانت string، نحولها إلى رقم
                    if prev_step in state_name_to_value:
                        result = state_name_to_value[prev_step]
                        logger.debug(f"✅ [FOLLOWUP] Converted '{prev_step}' to int: {result}")
                        return result
                    else:
                        logger.warning(f"⚠️ [FOLLOWUP] '{prev_step}' not found in state_name_to_value")
                        return prev_step
                elif isinstance(prev_step, int):
                    # إذا كانت رقم، نعيدها مباشرة
                    logger.debug(f"✅ [FOLLOWUP] prev_step is already int: {prev_step}")
                    return prev_step
                else:
                    # إذا كانت None، نعيد None
                    logger.warning(f"⚠️ [FOLLOWUP] prev_step is None for {current_step_name}")
                    return prev_step
        
        # تحويل current_step إلى اسم إذا كان رقماً
        if isinstance(current_step, int):
            current_step_name = value_to_state_name.get(current_step)
            
            if current_step_name and current_step_name in flow_map:
                prev_step = flow_map[current_step_name]
                prev_step = self._resolve_dynamic_back(prev_step, flow_type, context, logger)
                logger.debug(f"✅ Found in flow_map: {current_step_name} -> {prev_step} (type: {type(prev_step).__name__})")
                # ✅ معالجة الخطوة السابقة - قد تكون رقم أو string
                if isinstance(prev_step, str):
                    if prev_step in state_name_to_value:
                        return state_name_to_value[prev_step]
                    return prev_step
                elif isinstance(prev_step, int):
                    return prev_step
                return prev_step
            else:
                # ✅ محاولة استخدام current_step مباشرة كرقم
                if current_step in flow_map:
                    prev_step = flow_map[current_step]
                    prev_step = self._resolve_dynamic_back(prev_step, flow_type, context, logger)
                    logger.debug(f"✅ Found current_step as int: {current_step} -> {prev_step} (type: {type(prev_step).__name__})")
                    if isinstance(prev_step, str) and prev_step in state_name_to_value:
                        return state_name_to_value[prev_step]
                    elif isinstance(prev_step, int):
                        return prev_step
                    return prev_step
        elif isinstance(current_step, str) and current_step in flow_map:
            prev_step = flow_map[current_step]
            prev_step = self._resolve_dynamic_back(prev_step, flow_type, context, logger)
            logger.debug(f"✅ Found string key: {current_step} -> {prev_step} (type: {type(prev_step).__name__})")
            if isinstance(prev_step, str) and prev_step in state_name_to_value:
                return state_name_to_value[prev_step]
            elif isinstance(prev_step, int):
                return prev_step
            return prev_step

        # ✅ محاولة أخيرة: البحث في flow_map باستخدام current_step كرقم
        if isinstance(current_step, int) and current_step in flow_map:
            prev_step = flow_map[current_step]
            prev_step = self._resolve_dynamic_back(prev_step, flow_type, context, logger)
            logger.debug(f"✅ Found as int (fallback): {current_step} -> {prev_step} (type: {type(prev_step).__name__})")
            if isinstance(prev_step, str) and prev_step in state_name_to_value:
                return state_name_to_value[prev_step]
            elif isinstance(prev_step, int):
                return prev_step
            return prev_step
        
        logger.warning(f"⚠️ Could not find previous step for current_step={current_step}, flow_type={flow_type}")
        return STATE_SELECT_ACTION_TYPE  # الرجوع لقائمة نوع الإجراء

    def _resolve_dynamic_back(self, prev_step, flow_type, context, logger):
        """
        حل القيم الديناميكية لزر الرجوع.
        يُستخدم عندما تعتمد الخطوة السابقة على بيانات المستخدم (مثل discharge_type).
        """
        if prev_step != '_DYNAMIC_DISCHARGE_BACK_':
            return prev_step

        # ✅ خروج من المستشفى: الخطوة السابقة لـ FOLLOWUP_DATE تعتمد على نوع الخروج
        if context is not None:
            discharge_type = context.user_data.get('report_tmp', {}).get('discharge_type', '')
        else:
            discharge_type = ''

        if discharge_type == 'admission':
            logger.info("🔙 DYNAMIC_BACK: discharge admission → DISCHARGE_ADMISSION_SUMMARY")
            return 'DISCHARGE_ADMISSION_SUMMARY'
        else:
            # operation أو أي نوع آخر
            logger.info("🔙 DYNAMIC_BACK: discharge operation → DISCHARGE_OPERATION_NAME_EN")
            return 'DISCHARGE_OPERATION_NAME_EN'

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
        'periodic_followup': 'FOLLOWUP_TRANSLATOR',
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

    # ✅ تقليل logging لتجنب التأخير
    logger.debug(f"🎯 Executing SMART action for step: {target_step}, flow: {flow_type}")

    # حماية تلقائية لمسار متابعة في الرقود: إذا كانت الخطوة المطلوبة هي FOLLOWUP_ROOM_FLOOR (19)، اجبر flow_type ليكون 'followup'
    FOLLOWUP_ROOM_FLOOR = 19
    if target_step == FOLLOWUP_ROOM_FLOOR and flow_type != 'followup':
        logger.warning(f"⚠️ Auto-fixing flow_type to 'followup' for FOLLOWUP_ROOM_FLOOR step (was: {flow_type})")
        flow_type = 'followup'
    
    # ✅ حماية إضافية لمسار مراجعة / عودة دورية: إذا كانت medical_action تدل على مراجعة دورية، فرض flow_type إلى 'periodic_followup'
    report_tmp = context.user_data.get("report_tmp", {})
    medical_action = report_tmp.get("medical_action", "")
    if medical_action == "مراجعة / عودة دورية" and flow_type != 'periodic_followup':
        logger.info(f"✅ Auto-setting flow_type to 'periodic_followup' based on medical_action (was: {flow_type})")
        flow_type = 'periodic_followup'

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
        FOLLOWUP_COMPLAINT: 'FOLLOWUP_COMPLAINT',
        FOLLOWUP_DIAGNOSIS: 'FOLLOWUP_DIAGNOSIS',
        FOLLOWUP_DECISION: 'FOLLOWUP_DECISION',
        FOLLOWUP_ROOM_FLOOR: 'FOLLOWUP_ROOM_FLOOR',
        FOLLOWUP_DATE_TIME: 'FOLLOWUP_DATE_TIME',
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
        elif step_name == 'FOLLOWUP_DATE_TIME' or 'FOLLOWUP_DATE' in step_name or 'DELIVERY_DATE' in step_name or 'RETURN_DATE' in step_name:
            # تحديد نوع التقويم المناسب
            if 'DELIVERY_DATE' in step_name and flow_type == 'radiology':
                # تقويم خاص بالأشعة
                await _render_radiology_calendar(update.callback_query.message, context)
            elif 'RETURN_DATE' in step_name and flow_type == 'app_reschedule':
                # تقويم خاص بتأجيل المواعيد
                await _show_reschedule_calendar(update.callback_query.message, context)
            else:
                # تقويم المتابعة العادي - للرجوع من سبب العودة
                await _render_followup_calendar(update.callback_query.message, context)
            return target_step

        # ============================================
        # خطوات سبب العودة
        # ============================================
        elif 'FOLLOWUP_REASON' in step_name or 'RETURN_REASON' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("followup_reason", "")
            message_text = "✍️ **سبب موعد المتابعة**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            if current_value:
                message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل سبب موعد المتابعة\n"
            message_text += "• مثال: فحص الجرح، استلام نتائج"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات الشكوى
        # ============================================
        elif 'COMPLAINT' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("complaint", "")
            message_text = "💬 **شكوى المريض**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            if current_value:
                message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل شكوى المريض الجديدة\n"
            message_text += "أو اضغط **التالي** للمتابعة"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات التشخيص
        # ============================================
        elif 'DIAGNOSIS' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("diagnosis", "")
            message_text = "🔬 **التشخيص الطبي**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            if current_value:
                message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل التشخيص الجديد\n"
            message_text += "أو اضغط **التالي** للمتابعة"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات القرار
        # ============================================
        elif 'DECISION' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("decision", "")
            message_text = "📝 **قرار الطبيب**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            if current_value:
                message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل القرار الجديد\n"
            message_text += "أو اضغط **التالي** للمتابعة"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات الفحوصات
        # ============================================
        elif 'TESTS' in step_name:
            current_value = context.user_data.get("report_tmp", {}).get("tests", "")
            message_text = "🔬 **الفحوصات المطلوبة**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            if current_value:
                message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل الفحوصات الجديدة\n"
            message_text += "أو اضغط **التالي** للمتابعة"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات نوع العملية
        # ============================================
        elif 'NAME_EN' in step_name:
            message_text = "🏥 **اسم العملية بالإنجليزية**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل اسم العملية بالإنجليزية\n"
            message_text += "• مثال: Appendectomy"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات تفاصيل العملية
        # ============================================
        elif 'DETAILS_AR' in step_name or 'OPERATION_DETAILS' in step_name:
            message_text = "📝 **تفاصيل العملية**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل تفاصيل العملية بالعربي\n"
            message_text += "• اذكر التفاصيل المهمة"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات الملاحظات
        # ============================================
        elif 'NOTES' in step_name:
            message_text = "📝 **الملاحظات**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل الملاحظات الإضافية\n"
            message_text += "• أي معلومات أخرى مهمة"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
            )
            return target_step

        # ============================================
        # خطوات الغرفة
        # ============================================
        elif step_name == 'FOLLOWUP_ROOM_FLOOR':
            # ✅ تحقق من نوع المسار: إذا كان مراجعة دورية، تخطي رقم الغرفة
            if flow_type == 'periodic_followup':
                logger.info("🔄 FOLLOWUP_ROOM_FLOOR in periodic_followup flow - skipping to previous step")
                # الرجوع إلى قرار الطبيب مباشرة
                previous_step = smart_nav_manager.get_previous_step(flow_type, target_step, context)
                if previous_step is not None:
                    context.user_data['_conversation_state'] = previous_step
                    return await execute_smart_state_action(previous_step, flow_type, update, context)
                else:
                    # عرض قرار الطبيب مباشرة
                    current_value = context.user_data.get("report_tmp", {}).get("decision", "")
                    message_text = "📝 **قرار الطبيب**\n"
                    message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
                    if current_value:
                        message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                        message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
                    message_text += "✍️ أدخل القرار الجديد\n"
                    message_text += "أو اضغط **التالي** للمتابعة"
                    await update.callback_query.edit_message_text(
                        message_text,
                        reply_markup=_nav_buttons(),
                        parse_mode="Markdown"
                    )
                    return FOLLOWUP_DECISION
            else:
                # المسار العادي للمتابعة في الرقود
                current_value = context.user_data.get("report_tmp", {}).get("room_number", "")
                from telegram import ReplyKeyboardMarkup
                message_text = "🚪 **رقم الغرفة والطابق**\n"
                message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
                if current_value:
                    message_text += f"📋 **القيمة الحالية:**\n```\n{current_value}\n```\n\n"
                    message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
                message_text += "✍️ أدخل رقم الغرفة والطابق\n"
                message_text += "• مثال: غرفة 205 - الطابق الثاني"
                skip_keyboard = ReplyKeyboardMarkup([["تخطي"]], resize_keyboard=True)
                await update.callback_query.edit_message_text(
                    message_text + "\n\nإذا لم يكن هذا الحقل مطلوبًا يمكنك الضغط على تخطي.",
                    reply_markup=skip_keyboard,
                    parse_mode="Markdown"
                )
            return target_step
        elif 'ROOM' in step_name:
            message_text = "🏥 **رقم الغرفة**\n"
            message_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            message_text += "✍️ أدخل رقم الغرفة\n"
            message_text += "• مثال: 205"
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=_nav_buttons(),
                parse_mode="Markdown"
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
                    "🏠 **خروج من المستشفى**\n\n"
                    "اختر نوع الخروج:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛏️ خروج بعد رقود طبي", callback_data="discharge_type:admission")],
                        [InlineKeyboardButton("⚕️ خروج بعد عملية", callback_data="discharge_type:operation")],
                        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
                        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                    ]),
                    parse_mode="Markdown"
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

    # ✅ الإجابة على callback فوراً لتجنب timeout - بدون أي معالجة
    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"⚠️ Failed to answer callback: {e}")
        # حتى لو فشل answer، نستمر في المعالجة

    # ✅ تقليل logging لتجنب التأخير
    logger.debug("🔙 SMART BACK NAVIGATION TRIGGERED")

    try:
        # ✅ الحصول على البيانات بسرعة - بدون عمليات ثقيلة
        current_state = context.user_data.get('_conversation_state')
        report_tmp = context.user_data.get('report_tmp', {})
        flow_type = report_tmp.get('current_flow')
        
        # ✅ تحديد flow_type بسرعة مع إعطاء أولوية عالية لـ medical_action
        medical_action = report_tmp.get('medical_action', '')
        
        # ✅ فحص أولي مباشر من medical_action (أولوية عالية)
        if medical_action == "متابعة في الرقود":
            flow_type = "followup"
            logger.debug(f"🎯 FLOW_TYPE: Direct detection 'followup' from medical_action")
        elif medical_action == "مراجعة / عودة دورية":
            flow_type = "periodic_followup"
            logger.debug(f"🎯 FLOW_TYPE: Direct detection 'periodic_followup' from medical_action")
        elif medical_action == "استشارة جديدة":
            flow_type = "new_consult"
        elif medical_action == "طوارئ":
            flow_type = "emergency"
        elif not flow_type and current_state:
            # ✅ تحديد من current_state فقط إذا لم نجد medical_action
            followup_states = [FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR, FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR]
            if current_state in followup_states:
                # ✅ اكتشاف ذكي بناءً على رقم الغرفة
                room_number = report_tmp.get('room_number')
                if room_number:
                    flow_type = "followup"  # لديه رقم غرفة = متابعة في الرقود
                    logger.debug(f"🎯 FLOW_TYPE: Smart detection 'followup' (has room_number)")
                else:
                    flow_type = "periodic_followup"  # لا يوجد رقم غرفة = مراجعة دورية
                    logger.debug(f"🎯 FLOW_TYPE: Smart detection 'periodic_followup' (no room_number)")
            else:
                flow_type = 'new_consult'
        elif not flow_type:
            # ✅ افتراضي آمن
            flow_type = 'periodic_followup'
            logger.debug(f"🎯 FLOW_TYPE: Safe fallback to 'periodic_followup'")
        
        # ✅ تأكيد نهائي من medical_action (حماية إضافية)
        if medical_action == "مراجعة / عودة دورية" and flow_type != 'periodic_followup':
            logger.warning(f"🔧 FLOW_TYPE: Overriding {flow_type} → periodic_followup based on medical_action")
            flow_type = 'periodic_followup'
        elif medical_action == "متابعة في الرقود" and flow_type != 'followup':
            logger.warning(f"🔧 FLOW_TYPE: Overriding {flow_type} → followup based on medical_action")
            flow_type = 'followup'

        logger.debug(f"🔙 Current state: {current_state}, Flow type: {flow_type}")

        # ✅ تسجيل إضافي مفصل للتشخيص
        logger.info(f"🔍 NAVIGATION_DEBUG: medical_action='{medical_action}', current_flow='{report_tmp.get('current_flow')}', detected_flow_type='{flow_type}', current_state={current_state}")
        
        # ✅ فحص إضافي للتأكد من استخدام خريطة periodic_followup
        if medical_action == "مراجعة / عودة دورية":
            logger.info(f"🎯 PERIODIC_FOLLOWUP_FLOW: Using periodic_followup navigation map for medical_action='{medical_action}'")
            if flow_type != 'periodic_followup':
                logger.error(f"❌ FLOW_TYPE_MISMATCH: medical_action indicates periodic_followup but flow_type='{flow_type}'!")
        
        # ✅ الحصول على الخطوة السابقة - مع تسجيل مفصل
        logger.debug(f"🔍 Getting previous step for flow_type='{flow_type}', current_state={current_state}")
        previous_step = smart_nav_manager.get_previous_step(flow_type, current_state, context)
        logger.info(f"🔙 NAVIGATION_RESULT: {current_state} → {previous_step} (flow_type={flow_type})")

        if previous_step is None:
            # الرجوع للبداية
            logger.debug("🔙 No previous step, going to start")
            try:
                await start_report(update, context)
            except Exception as e:
                logger.error(f"❌ Error in start_report: {e}", exc_info=True)
                try:
                    await query.edit_message_text(
                        "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                        ]])
                    )
                except:
                    pass
            return STATE_SELECT_DATE

        # ✅ تحديث الـ conversation state
        context.user_data['_conversation_state'] = previous_step

        # ✅ تنفيذ الإجراء - مع timeout handling
        try:
            await execute_smart_state_action(previous_step, flow_type, update, context)
        except Exception as e:
            logger.error(f"❌ Error in execute_smart_state_action: {e}", exc_info=True)
            # محاولة إظهار رسالة خطأ للمستخدم
            try:
                await query.edit_message_text(
                    "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                    ]])
                )
            except:
                pass
            return previous_step

        logger.debug(f"🔙 Successfully went back to {previous_step}")
        return previous_step

    except Exception as e:
        logger.error(f"❌ Error in handle_smart_back_navigation: {e}", exc_info=True)
        # في حالة الخطأ، محاولة إظهار رسالة خطأ
        try:
            await query.edit_message_text(
                "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
                ]])
            )
        except:
            pass
        return ConversationHandler.END

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
    # زر البحث في صف منفصل واضح ومميز مع رموز ذهبية
    keyboard.append([
        InlineKeyboardButton(
            "⭐ 🔍 اضغط للبحث عن مريض 🔍 ⭐",
            switch_inline_query_current_chat=""
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
    if page == 0 and not search_query:
        text += "💡 **جديد!** اضغط زر البحث الذهبي ⭐🔍 للبحث السريع عن المريض!\n\n"
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

        text = (
            "📅 **إضافة تقرير جديد**\n\n"
            "🎉 **الميزات الجديدة:**\n"
            "✅ 🔍 **البحث السريع عن المرضى** - استخدم زر البحث في قائمة المرضى!\n"
            "✅ 🏥 **قسم جديد:** العلاج الإشعاعي\n"
            "✅ 💉 **إجراء جديد:** جلسة إشعاعي\n\n"
            "اختر طريقة إدخال التاريخ:"
        )

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


async def handle_calendar_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة إلغاء التقويم"""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass

    # استخدام SmartCancelManager للتعامل مع الإلغاء
    await SmartCancelManager.handle_contextual_cancel(update, context, 'report_creation')
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

    # إذا لم يكن في وضع البحث - لا نقبل إدخال نصي
    # يجب على المستخدم اختيار المريض من القائمة أو استخدام البحث
    try:
        await update.message.delete()
    except:
        pass
    
    await update.message.reply_text(
        "⚠️ **يرجى اختيار المريض من القائمة أعلاه**\n\n"
        "💡 أو اضغط على 🔍 للبحث عن مريض",
        parse_mode="Markdown"
    )
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
    """
    جلب المستشفيات من قاعدة البيانات (Hospital table) كمصدر الحقيقة.
    Fallback إلى doctors_unified.json فقط إذا كانت قاعدة البيانات فارغة/غير متاحة.
    """
    try:
        from db.session import SessionLocal
        from db.models import Hospital

        with SessionLocal() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
            db_names = [
                h.name for h in hospitals
                if h.name and not any('\u0600' <= char <= '\u06FF' for char in h.name)
            ]
            if db_names:
                return db_names
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ فشل تحميل المستشفيات من قاعدة البيانات: {e}")

    # Fallback: JSON unified file (قد يتم استبداله أثناء النشر)
    try:
        from services.hospitals_service import get_all_hospitals
        hospitals = get_all_hospitals()
        if hospitals:
            return hospitals
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ فشل تحميل المستشفيات من ملف JSON: {e}")

    # آخر حل: القائمة القديمة المحملة وقت التشغيل
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
            # إذا لم يكن في وضع البحث، نعرض رسالة تنبيه
            try:
                await update.message.delete()
            except:
                pass
            await update.message.reply_text(
                "⚠️ **يرجى اختيار المستشفى من القائمة أعلاه**\n\n"
                "💡 أو اضغط على 🔍 للبحث عن مستشفى",
                parse_mode="Markdown"
            )
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
    text += f"\n📄 **الصفحة:** {page + 1} من {total_pages}\n"
    if page == 0 and not search_query:
        text += "\n💡 **جديد!** تم إضافة قسم: **العلاج الإشعاعي** 🏥\n"
    text += "\nاختر القسم:"

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
            # إذا لم يكن في وضع البحث، نعرض رسالة تنبيه
            try:
                await update.message.delete()
            except:
                pass
            await update.message.reply_text(
                "⚠️ **يرجى اختيار القسم من القائمة أعلاه**\n\n"
                "💡 أو اضغط على 🔍 للبحث عن قسم",
                parse_mode="Markdown"
            )
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
    # استيراد start_radiation_therapy_flow من flows/radiation_therapy.py
    try:
        from bot.handlers.user.user_reports_add_new_system.flows.radiation_therapy import start_radiation_therapy_flow
    except ImportError as e:
        logger.error(f"Error importing start_radiation_therapy_flow: {e}")
        start_radiation_therapy_flow = None

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
        "جلسة إشعاعي": {  # ✅ مسار العلاج الإشعاعي
            "state": RADIATION_THERAPY_TYPE,
            "flow": start_radiation_therapy_flow,
            "pre_process": None
        },
    }

    # Logging للتحقق من المفاتيح
    for action in PREDEFINED_ACTIONS:
        in_routing = action in routing_dict

    return routing_dict


def _build_action_type_keyboard(page=0):
    """بناء لوحة مفاتيح أنواع الإجراءات - عرض النص الكامل"""
    total = len(PREDEFINED_ACTIONS)
    keyboard = []

    # إضافة جميع أزرار أنواع الإجراءات - كل زر في صف منفصل
    for i in range(total):
        action_name = PREDEFINED_ACTIONS[i]
        callback_data = f"action_idx:{i}"
        
        # عرض النص الكامل بدون اختصار
        display = f"⚕️ {action_name}"
        
        keyboard.append([InlineKeyboardButton(display, callback_data=callback_data)])

    # أزرار التنقل الرئيسية
    keyboard.append([
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = (
        "⚕️ **نوع الإجراء الطبي** (الخطوة 6 من 6)\n\n"
        "💡 **جديد!** إضافة إجراء: **جلسة إشعاعي** 💉\n\n"
        "📋 اختر نوع الإجراء المناسب من القائمة أدناه:\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

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
            "مراجعة / عودة دورية": "periodic_followup",  # مسار منفصل لتجنب طلب رقم الغرفة
            "استشارة مع قرار عملية": "surgery_consult",
            "طوارئ": "emergency",
            "عملية": "operation",
            "استشارة أخيرة": "final_consult",
            "علاج طبيعي وإعادة تأهيل": "rehab_physical",
            "أشعة وفحوصات": "radiology",  # ✅ تم إضافتها بعد نقلها من الأقسام
            "تأجيل موعد": "appointment_reschedule",  # ✅ تم إضافتها
            "ترقيد": "admission",  # ✅ تم إضافتها
            "خروج من المستشفى": "discharge",  # ✅ تم إضافتها
            "جلسة إشعاعي": "radiation_therapy",  # ✅ مسار العلاج الإشعاعي
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
    medical_action = context.user_data.get('report_tmp', {}).get('medical_action')
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
    """
    معالجة إدخال نص بدلاً من اختيار التاريخ من التقويم
    ✅ يرفض النص ويعيد عرض التقويم للاختيار منه
    """
    text = update.message.text.strip()

    logger.info(f"⚠️ [FOLLOWUP_DATE_TEXT] المستخدم أدخل نص '{text}' بدلاً من اختيار التاريخ من التقويم")

    # ✅ رفض إدخال النص وإعادة عرض التقويم
    await update.message.reply_text(
        "⚠️ **يرجى اختيار التاريخ من التقويم أعلاه**\n\n"
        "لا يمكن إدخال التاريخ يدوياً، يجب الضغط على التاريخ المطلوب من التقويم.",
        parse_mode="Markdown"
    )

    # ✅ إعادة عرض التقويم
    await _render_followup_calendar(update.message, context)

    # ✅ البقاء في نفس الحالة
    current_state = context.user_data.get('_conversation_state')
    return current_state


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
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_DATE
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
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_REASON
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
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_REASON
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
        elif current_flow == "appointment_reschedule":
            next_state = APP_RESCHEDULE_RETURN_REASON
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


# =============================
# مسار 2: مراجعة الطبيب / عودة دورية (6 حقول)
# شكوى، تشخيص، قرار، تاريخ ووقت عودة، سبب عودة، مترجم
# =============================

# استيراد الدوال من ملف flows/followup.py
try:
    from bot.handlers.user.user_reports_add_new_system.flows.followup import (
        start_followup_flow,
        start_periodic_followup_flow,
        handle_followup_complaint,
        handle_followup_diagnosis,
        handle_followup_decision,
        handle_followup_room_floor,
        handle_followup_reason
    )
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"⚠️ Cannot import followup flows: {e}")

# =============================
# مسار 3: طوارئ (7 حقول)

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

    # أزرار سريعة لوضع الحالة 
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 تم الخروج من الطوارئ", callback_data="emerg_status:discharged")],
        [InlineKeyboardButton("🛏️ تم الترقيد", callback_data="emerg_status:admitted")],
        [InlineKeyboardButton("⚕️ تم إجراء عملية", callback_data="emerg_status:operation")],
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

    # تحديد النص بناءً على الاختيار
    status_text = {
        "discharged": "تم الخروج من الطوارئ",
        "admitted": "تم الترقيد",
        "operation": "تم إجراء عملية"
    }.get(data, "غير محدد")

    context.user_data["report_tmp"]["status"] = status_text

    # إذا اختار "تم الترقيد"، نطلب ملاحظات الرقود أولاً
    if data == "admitted":
        await query.edit_message_text(
            f"✅ تم اختيار: {status_text}\n\n"
            "📝 **ملاحظات الرقود**\n\n"
            "يرجى توضيح ماذا تم وما هي خطة الرقود:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ADMISSION_NOTES
    
    # إذا اختار "تم إجراء عملية"، نطلب تفاصيل العملية
    elif data == "operation":
        await query.edit_message_text(
            f"✅ تم اختيار: {status_text}\n\n"
            "⚕️ **تفاصيل العملية**\n\n"
            "يرجى إدخال ماهي العملية التي تمت للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_OPERATION_DETAILS
    
    # للخروج من الطوارئ، نكمل مباشرة للتاريخ
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


async def handle_emergency_admission_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة ملاحظات الرقود"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى توضيح ماذا تم وما هي خطة الرقود:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_ADMISSION_NOTES

    context.user_data["report_tmp"]["admission_notes"] = text

    # خيار نوع الترقيد
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏥 العناية المركزة", callback_data="emerg_admission:icu")],
        [InlineKeyboardButton("🛏️ الرقود", callback_data="emerg_admission:ward")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])

    await update.message.reply_text(
        "✅ تم حفظ الملاحظات\n\n"
        "أين تم الترقيد؟",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    return EMERGENCY_ADMISSION_TYPE


async def handle_emergency_operation_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تفاصيل العملية"""
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال ماهي العملية التي تمت للحالة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown"
        )
        return EMERGENCY_OPERATION_DETAILS

    context.user_data["report_tmp"]["operation_details"] = text

    await update.message.reply_text("✅ تم الحفظ")

    # عرض تقويم تاريخ العودة (اختياري)
    await _render_followup_calendar(update.message, context)

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
    """معالج اختيار تاريخ العودة - يعرض اختيار الوقت بعد التاريخ"""
    query = update.callback_query
    await query.answer()

    date_str = query.data.split(":", 1)[1]
    try:
        return_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data["report_tmp"]["app_reschedule_return_date"] = return_date
        context.user_data["report_tmp"]["followup_date"] = return_date
        context.user_data["report_tmp"]["_pending_followup_date"] = return_date

        # عرض اختيار الوقت (نفس نظام باقي المسارات)
        keyboard = []
        common_morning = [
            ("🌅 8:00 صباحاً", "08"),
            ("🌅 9:00 صباحاً", "09"),
            ("🌅 10:00 صباحاً", "10"),
            ("🌅 11:00 صباحاً", "11"),
        ]
        keyboard.append([InlineKeyboardButton(label,
            callback_data=f"followup_time_hour:{val}") for label, val in common_morning])

        keyboard.append([InlineKeyboardButton("☀️ 12:00 ظهراً", callback_data="followup_time_hour:12")])

        common_afternoon = [
            ("🌆 1:00 مساءً", "13"),
            ("🌆 2:00 مساءً", "14"),
            ("🌆 3:00 مساءً", "15"),
            ("🌆 4:00 مساءً", "16"),
        ]
        keyboard.append([InlineKeyboardButton(label,
            callback_data=f"followup_time_hour:{val}") for label, val in common_afternoon])

        keyboard.append([InlineKeyboardButton("🕐 أوقات أخرى", callback_data="followup_time_hour:more")])
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ])

        await query.edit_message_text(
            f"✅ **تم اختيار التاريخ**\n\n"
            f"📅 **التاريخ:**\n"
            f"{date_str}\n\n"
            f"🕐 **الوقت** (اختياري)\n\n"
            f"اختر الساعة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

        context.user_data['_conversation_state'] = APP_RESCHEDULE_RETURN_DATE
        return APP_RESCHEDULE_RETURN_DATE

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
    """الحصول على الحقول القابلة للتعديل حسب نوع التدفق - فقط حقول التقرير (بدون البيانات الأساسية)"""
    fields_map = {
        "new_consult": [
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("tests", "🧪 الفحوصات والأشعة"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "followup": [
            ("complaint", "💬 حالة المريض اليومية"),
            ("diagnosis", "🔬 التشخيص"),
            ("decision", "📝 قرار الطبيب اليومي"),
            ("room_number", "🚪 رقم الغرفة والطابق"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "periodic_followup": [
            # ✅ مسار "مراجعة / عودة دورية" - بدون room_number
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص"),
            ("decision", "📝 قرار الطبيب"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "inpatient_followup": [
            # ✅ مسار "متابعة في الرقود" - مع room_number
            ("complaint", "💬 حالة المريض اليومية"),
            ("diagnosis", "🔬 التشخيص"),
            ("decision", "📝 قرار الطبيب اليومي"),
            ("room_number", "🚪 رقم الغرفة والطابق"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "emergency": [
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص"),
            ("decision", "📝 قرار الطبيب وماذا تم"),
            ("status", "🏥 وضع الحالة"),
            ("admission_type", "🛏️ نوع الترقيد"),
            # لا تضف room_number هنا إلا إذا كان flow_type == 'followup' أو 'inpatient_followup'
            # (يتم التحكم في ذلك عبر منطق بناء الأزرار)
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "admission": [
            ("admission_reason", "🛏️ سبب الرقود"),
            ("room_number", "🚪 رقم الغرفة"),
            ("notes", "📝 ملاحظات"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "surgery_consult": [
            ("diagnosis", "🔬 التشخيص"),
            ("decision", "📝 قرار الطبيب وتفاصيل العملية"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("success_rate", "📊 نسبة نجاح العملية"),
            ("benefit_rate", "💡 نسبة الاستفادة"),
            ("tests", "🧪 الفحوصات والأشعة"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "operation": [
            ("operation_details", "⚕️ تفاصيل العملية بالعربي"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("notes", "📝 ملاحظات"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "final_consult": [
            ("diagnosis", "🔬 التشخيص النهائي"),
            ("decision", "📝 قرار الطبيب"),
            ("recommendations", "💡 التوصيات الطبية"),
            ("translator_name", "👤 المترجم"),
        ],
        "discharge": [
            ("discharge_type", "🚪 نوع الخروج"),
            ("admission_summary", "📋 ملخص الرقود"),
            ("operation_details", "⚕️ تفاصيل العملية"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "rehab_physical": [
            ("therapy_details", "🏃 تفاصيل جلسة العلاج الطبيعي"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "rehab_device": [
            ("device_name", "🦾 اسم الجهاز والتفاصيل"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
        "radiology": [
            ("radiology_type", "🔬 نوع الأشعة/الفحص"),
            ("delivery_date", "📅 تاريخ الاستلام"),
            ("translator_name", "👤 المترجم"),
        ],
        "app_reschedule": [
            ("app_reschedule_reason", "📅 سبب التأجيل"),
            ("app_reschedule_return_date", "📅 موعد العودة الجديد"),
            ("app_reschedule_return_reason", "✍️ سبب العودة"),
            ("translator_name", "👤 المترجم"),
        ],
    }
    return fields_map.get(flow_type, [])

async def show_edit_fields_menu(query, context, flow_type):
    """عرض قائمة الحقول القابلة للتعديل - حقول نوع الإجراء فقط"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        data = context.user_data.get("report_tmp", {})
        medical_action = data.get("medical_action", "غير محدد")

        # ✅ الحصول على الحقول المحددة لهذا النوع من التدفق
        editable_fields = get_editable_fields_by_flow_type(flow_type)

        # ✅ منع ظهور room_number إلا إذا كان flow_type == 'followup' أو 'inpatient_followup'
        if flow_type not in ["followup", "inpatient_followup"]:
            editable_fields = [(fk, fd) for fk, fd in editable_fields if fk != "room_number"]
            logger.info(f"✅ [EDIT_MENU] تم إزالة room_number من القائمة لمسار: {flow_type}")

        logger.info(f"🔍 show_edit_fields_menu: flow_type={flow_type}, medical_action={medical_action}")
        logger.info(f"🔍 show_edit_fields_menu: editable_fields count={len(editable_fields)}")
        logger.info(f"🔍 show_edit_fields_menu: data keys={list(data.keys())}")
        
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
        buttons_created = 0
        
        # ✅ عرض جميع حقول هذا النوع من الإجراء (حتى الفارغة)
        for field_key, field_display in editable_fields:
            # الحصول على القيمة الحالية
            current_value = data.get(field_key, "")
            
            # ✅ تنسيق القيمة للعرض
            if not current_value or str(current_value).strip() == "" or current_value == "غير محدد":
                display_value = "⚠️ فارغ"
            elif isinstance(current_value, datetime):
                display_value = current_value.strftime('%Y-%m-%d')
            elif len(str(current_value)) > 15:
                display_value = str(current_value)[:12] + "..."
            else:
                display_value = str(current_value)
            
            # ✅ تقصير اسم الحقل إذا كان طويلاً
            field_display_short = field_display[:20] if len(field_display) > 20 else field_display
            button_text = f"{field_display_short}: {display_value}"
            
            # ✅ كل زر في صف منفصل
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"draft_field:{flow_type}:{field_key}"
                )
            ])
            buttons_created += 1
        
        logger.info(f"✅ تم إنشاء {buttons_created} زر للتعديل")
        
        # ✅ استخدام back_to_summary بدلاً من save لتجنب النشر التلقائي
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_summary:{flow_type}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ تم عرض قائمة الحقول القابلة للتعديل ({len(editable_fields)} حقل)")
        
        # ✅ إرجاع نفس CONFIRM state لهذا النوع من التدفق (حتى تعمل الأزرار)
        confirm_state = get_confirm_state(flow_type)
        return confirm_state
        
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
        data = context.user_data.setdefault("report_tmp", {})

        # ✅ استخدام current_flow من report_tmp إذا كان موجوداً (الأولوية له)
        stored_flow_type = data.get("current_flow")

        # إذا لم يتم تمرير flow_type، نحاول استخراجه من callback_data أو report_tmp
        if flow_type is None:
            if hasattr(query, 'data') and query.data:
                # استخراج من callback_data مثل "edit:admission"
                if query.data.startswith("edit:"):
                    flow_type = query.data.split(":")[1]
                else:
                    flow_type = stored_flow_type
            else:
                flow_type = stored_flow_type

        # ✅ إذا كان stored_flow_type موجوداً ويختلف عن flow_type، استخدم stored_flow_type
        # هذا لضمان احترام current_flow الأصلي (مثل periodic_followup)
        if stored_flow_type and stored_flow_type != flow_type:
            if flow_type == "followup" and stored_flow_type == "periodic_followup":
                flow_type = "periodic_followup"
                logger.info(f"✅ [EDIT_BEFORE_SAVE] استخدام current_flow المحفوظ: {flow_type}")
            elif flow_type == "followup" and stored_flow_type == "inpatient_followup":
                flow_type = "inpatient_followup"
                logger.info(f"✅ [EDIT_BEFORE_SAVE] استخدام current_flow المحفوظ: {flow_type}")

        if not flow_type:
            logger.error("❌ لم يتم العثور على flow_type")
            await query.edit_message_text(
                "❌ **حدث خطأ**\n\n"
                "لم يتم العثور على نوع التدفق.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

        medical_action = data.get("medical_action", "")

        # ✅ إذا كان flow_type == "followup" و medical_action مفقود، نحاول تحديده
        if flow_type == "followup" and not medical_action:
            if data.get("room_number"):
                data["medical_action"] = "متابعة في الرقود"
            else:
                data["medical_action"] = "مراجعة / عودة دورية"
                flow_type = "periodic_followup"
                logger.info(f"✅ [EDIT_BEFORE_SAVE] تم تعيين flow_type='periodic_followup'")

        logger.info(f"✏️ handle_edit_before_save: flow_type={flow_type}, medical_action={data.get('medical_action', '')}")

        # حفظ flow_type في report_tmp
        data["current_flow"] = flow_type

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

async def handle_edit_during_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callback edit_during_entry:show_menu - عرض قائمة التعديل أثناء الإدخال"""
    query = update.callback_query
    await query.answer()
    
    try:
        # استخراج flow_type من report_tmp
        data = context.user_data.get("report_tmp", {})
        flow_type = data.get("current_flow")
        
        # إذا لم يكن flow_type موجوداً، نحاول تحديده من medical_action أو الحالة الحالية
        if not flow_type:
            medical_action = data.get("medical_action", "")
            
            # تحديد flow_type من medical_action
            medical_action_to_flow = {
                "استشارة جديدة": "new_consult",
                "متابعة في الرقود": "followup",
                "مراجعة / عودة دورية": "periodic_followup",
                "طوارئ": "emergency",
                "استشارة مع قرار عملية": "surgery_consult",
                "عملية": "operation",
                "استشارة أخيرة": "final_consult",
                "ترقيد": "admission",
                "خروج من المستشفى": "discharge",
                "علاج طبيعي وإعادة تأهيل": "rehab_physical",
                "علاج طبيعي": "rehab_physical",
                "أجهزة تعويضية": "rehab_device",
                "أشعة وفحوصات": "radiology",
                "تأجيل موعد": "appointment_reschedule",
                "جلسة إشعاعي": "radiation_therapy",
            }
            
            if medical_action in medical_action_to_flow:
                flow_type = medical_action_to_flow[medical_action]
            else:
                # محاولة تحديد من الحالة الحالية
                current_state = context.user_data.get('_conversation_state')
                # استخدام الأرقام مباشرة لتجنب مشاكل الاستيراد
                state_to_flow = {
                    # NEW_CONSULT states (7-15)
                    7: "new_consult", 8: "new_consult", 9: "new_consult", 10: "new_consult", 11: "new_consult", 12: "new_consult", 13: "new_consult", 14: "new_consult", 15: "new_consult",
                    # FOLLOWUP states (16-23) - ✅ سنحدد النوع بناءً على medical_action وليس state فقط
                    # 16: "followup", 17: "followup", 18: "followup", 19: "followup", 20: "followup", 21: "followup", 22: "followup", 23: "followup",
                    # EMERGENCY states (24-35)
                    24: "emergency", 25: "emergency", 26: "emergency", 27: "emergency", 28: "emergency", 29: "emergency", 30: "emergency", 31: "emergency", 32: "emergency", 33: "emergency", 34: "emergency", 35: "emergency",
                    # ADMISSION states (36-42)
                    36: "admission", 37: "admission", 38: "admission", 39: "admission", 40: "admission", 41: "admission", 42: "admission",
                    # OPERATION states (53-59)
                    53: "operation", 54: "operation", 55: "operation", 56: "operation", 57: "operation", 58: "operation", 59: "operation",
                }
                
                # ✅ معالجة خاصة لـ FOLLOWUP states (16-23)
                followup_states = [16, 17, 18, 19, 20, 21, 22, 23]
                if current_state in followup_states:
                    # تحديد النوع بناءً على medical_action
                    if medical_action == "مراجعة / عودة دورية":
                        flow_type = "periodic_followup"
                    elif medical_action == "متابعة في الرقود":
                        flow_type = "followup"
                    else:
                        # افتراضي: periodic_followup للأمان (يضمن التنقل خطوة بخطوة)
                        flow_type = "periodic_followup"
                elif current_state in state_to_flow:
                    flow_type = state_to_flow[current_state]
        
        if not flow_type:
            await query.edit_message_text(
                "❌ **حدث خطأ**\n\n"
                "لم يتم العثور على نوع التدفق.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        # استدعاء handle_edit_before_save لعرض قائمة التعديل
        return await handle_edit_before_save(query, context, flow_type)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ خطأ في handle_edit_during_entry: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء التعديل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END

async def handle_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper لمعالجة callback save:"""
    query = update.callback_query
    await query.answer()
    if query.data.startswith("save:"):
        flow_type = query.data.split(":")[1]
        # إعادة عرض الملخص - استيراد show_final_summary
        from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary
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
        
        # ✅ حفظ معلومات التعديل في context (للنظام الجديد edit_field:)
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        # ✅ أيضاً حفظ في editing_field (للنظام القديم draft_field) للتوافق
        context.user_data["editing_field"] = field_key
        
        # الحصول على state التأكيد الصحيح
        confirm_state = get_confirm_state(flow_type)
        
        # ✅ تنظيف القيمة الحالية من نصوص التعليمات
        current_value_display = format_field_value(current_value)
        if current_value_display and len(str(current_value_display)) > 200:
            current_value_display = str(current_value_display)[:200] + "..."
        
        # عرض واجهة التعديل حسب نوع الحقل
        if field_key in ["report_date", "followup_date", "delivery_date"]:
            # للحقول التاريخية - طلب إدخال نصي
            await query.edit_message_text(
                f"📅 **تعديل {get_field_display_name(field_key)}**\n\n"
                f"**القيمة الحالية:** {current_value_display}\n\n"
                f"📝 أرسل التاريخ الجديد (مثال: 2025-01-15 أو 2025-01-15 14:30):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                ]),
                parse_mode="Markdown"
            )
            context.user_data['_conversation_state'] = confirm_state
            logger.info(f"✅ تم طلب تعديل حقل تاريخي: {field_key}, state: {confirm_state}")
            return confirm_state
        else:
            # للحقول النصية - طلب إدخال جديد
            await query.edit_message_text(
                f"✏️ **تعديل {get_field_display_name(field_key)}**\n\n"
                f"**القيمة الحالية:**\n{current_value_display}\n\n"
                f"📝 أرسل القيمة الجديدة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                ]),
                parse_mode="Markdown"
            )
            context.user_data['_conversation_state'] = confirm_state
            logger.info(f"✅ تم طلب تعديل حقل نصي: {field_key}, state: {confirm_state}")
            return confirm_state
        
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
    # استيراد الحقول الخاصة بكل مسار من الملفات المنفصلة
    from bot.handlers.user.user_reports_flows.followup_in_admission import FOLLOWUP_FIELDS
    from bot.handlers.user.user_reports_flows.periodic_review import PERIODIC_REVIEW_FIELDS
    fields_map = {
        "followup": FOLLOWUP_FIELDS,
        "periodic_followup": PERIODIC_REVIEW_FIELDS,
        # ... أضف بقية المسارات الأخرى إذا لزم ...
    }
    field_names = {
        "complaint": "💬 حالة المريض اليومية",
        "diagnosis": "🔬 التشخيص",
        "decision": "📝 قرار الطبيب اليومي",
        "room_number": "🚪 رقم الغرفة والطابق",
        "followup_date": "📅 موعد العودة",
        "followup_reason": "✍️ سبب العودة",
        "translator_name": "👤 المترجم",
        "delivery_date": "📅 تاريخ الاستلام",
        "discharge_type": "🚪 نوع الخروج",
        "admission_summary": "📋 ملخص الرقود",
        "app_reschedule_reason": "📅 سبب التأجيل",
        "app_reschedule_return_date": "📅 موعد العودة الجديد",
        "app_reschedule_return_reason": "✍️ سبب العودة",
    }
    return field_names.get(field_key, field_key)

def format_field_value(value):
    """تنسيق قيمة الحقل للعرض"""
    if value is None or value == "":
        return "غير محدد"
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)

async def handle_unified_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ دالة موحدة لمعالجة إدخال القيمة الجديدة بعد اختيار حقل للتعديل
    تعمل مع كلا النظامين: edit_field (قبل النشر) و draft_field (بعد النشر)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # ✅ التحقق من أن النص ليس أمر بدء تقرير جديد
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            from .user_reports_add_new_system import start_report
            return await start_report(update, context)
        
        # ✅ محاولة الحصول على معلومات التعديل من النظامين
        field_key = context.user_data.get("edit_field_key") or context.user_data.get("editing_field")
        flow_type = context.user_data.get("edit_flow_type") or context.user_data.get("draft_flow_type") or context.user_data.get("report_tmp", {}).get("current_flow")
        
        if not field_key:
            logger.warning("⚠️ handle_unified_edit_field_input: لا يوجد حقل للتعديل - تجاهل الرسالة")
            # ✅ إذا لم يكن هناك حقل للتعديل، تجاهل الرسالة (قد تكون رسالة عادية)
            return
        
        if not flow_type:
            logger.error("❌ لم يتم العثور على flow_type")
            await update.message.reply_text(
                "❌ **حدث خطأ**\n\n"
                "لم يتم العثور على نوع التدفق.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        logger.info(f"✏️ handle_unified_edit_field_input: field_key={field_key}, flow_type={flow_type}, text={text[:50]}")
        
        # ✅ التحقق من صحة الإدخال
        if not text or len(text) < 1:
            await update.message.reply_text(
                "⚠️ **خطأ:** النص فارغ\n\n"
                f"يرجى إدخال {get_field_display_name(field_key)}:",
                parse_mode="Markdown"
            )
            confirm_state = get_confirm_state(flow_type)
            return confirm_state
        
        # ✅ حفظ القيمة الجديدة في report_tmp مع تطبيق Rule-based Field Authorization
        data = context.user_data.setdefault("report_tmp", {})

        # السماح بتخزين room_number في جميع المسارات
        if field_key == "complaint":
            data["complaint_text"] = text  # ✅ حفظ في complaint_text أيضاً للتوافق
            data["complaint"] = text
        elif field_key == "decision":
            data["doctor_decision"] = text  # ✅ حفظ في doctor_decision أيضاً للتوافق
            data["decision"] = text
        else:
            data[field_key] = text
        
        # ✅ مسح معلومات التعديل
        context.user_data.pop("edit_field_key", None)
        context.user_data.pop("edit_flow_type", None)
        context.user_data.pop("editing_field", None)
        context.user_data.pop("editing_field_original", None)
        
        logger.info(f"✅ تم حفظ التعديل: {field_key} = {text[:50]}")
        
        # ✅ إعادة عرض الملخص الكامل
        from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary
        await show_final_summary(update.message, context, flow_type)
        
        # ✅ العودة إلى state التأكيد
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        logger.info(f"✅ تم حفظ التعديل والعودة إلى state: {confirm_state}")
        return confirm_state
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_unified_edit_field_input: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء حفظ التعديل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END

# ✅ دالة قديمة - تم استبدالها بـ handle_unified_edit_field_input
async def handle_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال النص بعد اختيار حقل للتعديل (قديم - يتم استدعاء handle_unified_edit_field_input)"""
    return await handle_unified_edit_field_input(update, context)

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

        # ✅ توحيد العناوين: "متابعة في الرقود" تستخدم مسميات مختلفة
        is_inpatient = (flow_type == "followup" and data.get("medical_action") == "متابعة في الرقود")

        if is_inpatient:
            summary += f"🛏️ **حالة المريض اليومية:** {data.get('complaint', 'غير محدد')}\n"
        else:
            summary += f"💬 **شكوى المريض:** {data.get('complaint', 'غير محدد')}\n"

        # ✅ التشخيص لا يظهر في "متابعة في الرقود"
        if not is_inpatient:
            summary += f"🔬 **التشخيص:** {data.get('diagnosis', 'غير محدد')}\n"

        if is_inpatient:
            summary += f"📝 **قرار الطبيب اليومي:** {data.get('decision', 'غير محدد')}\n"
        else:
            summary += f"📝 **قرار الطبيب:** {data.get('decision', 'غير محدد')}\n"

        if flow_type == "new_consult":
            summary += f"🔬 **الفحوصات المطلوبة:** {data.get('tests', 'لا يوجد')}\n"

        if flow_type == "emergency":
            summary += f"🏥 **وضع الحالة:** {data.get('status', 'غير محدد')}\n"

        # ✅ رقم الغرفة والطابق (فقط لمتابعة في الرقود)
        if is_inpatient:
            room_info = data.get('room_number') or data.get('room_floor') or data.get('room')
            if room_info and str(room_info).strip():
                summary += f"🏥 **رقم الغرفة والطابق:** {room_info}\n"

        # موعد العودة
        followup_date = data.get('followup_date')
        if followup_date:
            if hasattr(followup_date, 'strftime'):
                date_str = followup_date.strftime('%Y-%m-%d')
            else:
                date_str = str(followup_date)
            followup_time = data.get('followup_time', '')
            if followup_time:
                time_display = format_time_string_12h(followup_time)
                summary += f"📅 **موعد العودة:** {date_str} الساعة {time_display}\n"
            else:
                summary += f"📅 **موعد العودة:** {date_str}\n"
            summary += f"✍️ **سبب العودة:** {data.get('followup_reason', 'غير محدد')}\n"

        # حماية إضافية: لا تعرض رقم الغرفة في periodic_review/مراجعة دورية حتى لو كان موجودًا
        if flow_type == "periodic_followup" and "room_number" in data:
            data.pop("room_number", None)

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
        # إرسال الملخص النهائي كنص عادي بدون تنسيق لتجنب أخطاء الكيانات.
        # إذا كان النص طويلًا جدًا يتم تقسيمه لعدة رسائل وتوضع أزرار النشر في آخر جزء.
        summary_plain = summary.replace("**", "")
        max_message_len = 3500  # أقل من حد تيليجرام (4096) كهامش أمان

        chunks = []
        remaining = summary_plain.strip()
        while remaining:
            if len(remaining) <= max_message_len:
                chunks.append(remaining)
                break

            split_at = remaining.rfind("\n", 0, max_message_len)
            if split_at == -1 or split_at < int(max_message_len * 0.5):
                split_at = max_message_len

            chunk = remaining[:split_at].rstrip()
            if chunk:
                chunks.append(chunk)
            remaining = remaining[split_at:].lstrip("\n")

        for idx, chunk in enumerate(chunks):
            is_last_chunk = idx == (len(chunks) - 1)
            await message.reply_text(
                chunk,
                reply_markup=keyboard if is_last_chunk else None
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ خطأ في إرسال الملخص النهائي: {e}", exc_info=True)
        try:
            await message.reply_text(
                "⚠️ التقرير طويل جدًا للعرض الكامل.\n"
                "تم حفظ البيانات، حاول اختصار بعض الحقول أو أكمل من جديد."
            )
        except Exception:
            pass

# =============================
# معالجة التأكيد والحفظ
# =============================

async def handle_edit_draft_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة تعديل التقرير المؤقت قبل الحفظ - استخدام نظام التعديل الجديد
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
        
        logger.info(f"✏️ handle_edit_draft_report: flow_type={flow_type}")

        # حفظ flow_type في report_tmp
        context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type
        
        # ✅ استخدام نظام التعديل الجديد الذي يعرض جميع الحقول
        edit_state = await show_edit_fields_menu(query, context, flow_type)
        return edit_state

    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_draft_report: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ في بدء عملية التعديل")
        return ConversationHandler.END

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
        'translator_name': 'translator_name',  # ✅ المترجم
        # ✅ حقول تأجيل الموعد
        'app_reschedule_reason': 'app_reschedule_reason',
        'app_reschedule_return_date': 'app_reschedule_return_date',
        'app_reschedule_return_reason': 'app_reschedule_return_reason',
        # ✅ حقول الأشعة والفحوصات
        'radiology_type': 'radiology_type',
        'radiology_delivery_date': 'radiology_delivery_date',
        # ✅ حقول العلاج الطبيعي
        'therapy_details': 'therapy_details',
        # ✅ حقول الأجهزة التعويضية
        'device_details': 'device_details',
        # ✅ حقول الرقود
        'admission_summary': 'admission_summary',
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
        
        # ✅ تقصير القيمة للعرض
        if len(str(current_value)) > 15:
            display_value = str(current_value)[:12] + "..."
        else:
            display_value = str(current_value)
        
        # ✅ تقصير اسم الحقل أيضاً إذا كان طويلاً
        field_name_short = field_name[:20] if len(field_name) > 20 else field_name
        button_text = f"{field_name_short}: {display_value}"
        
        # ✅ كل زر في صف منفصل لضمان سهولة الاختيار
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
            'translator_name': 'translator_name',  # ✅ المترجم
            # ✅ حقول تأجيل الموعد
            'app_reschedule_reason': 'app_reschedule_reason',
            'app_reschedule_return_date': 'app_reschedule_return_date',
            'app_reschedule_return_reason': 'app_reschedule_return_reason',
            # ✅ حقول الأشعة والفحوصات
            'radiology_type': 'radiology_type',
            'radiology_delivery_date': 'radiology_delivery_date',
            # ✅ حقول العلاج الطبيعي
            'therapy_details': 'therapy_details',
            # ✅ حقول الأجهزة التعويضية
            'device_details': 'device_details',
            # ✅ حقول الرقود
            'admission_summary': 'admission_summary',
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
            'translator_name': 'المترجم',  # ✅ المترجم
            # ✅ حقول تأجيل الموعد
            'app_reschedule_reason': 'سبب تأجيل الموعد',
            'app_reschedule_return_date': 'موعد العودة الجديد',
            'app_reschedule_return_reason': 'سبب العودة',
            # ✅ حقول الأشعة والفحوصات
            'radiology_type': 'نوع الأشعة والفحوصات',
            'radiology_delivery_date': 'تاريخ التسليم',
            # ✅ حقول العلاج الطبيعي
            'therapy_details': 'تفاصيل الجلسة',
            # ✅ حقول الأجهزة التعويضية
            'device_details': 'تفاصيل الجهاز',
            # ✅ حقول الرقود
            'admission_summary': 'ملخص الرقود',
        }

        field_display_name = field_names.get(edit_field_key, edit_field_key)

        # الحقول التي تحتاج تقويم بدلاً من إدخال نصي
        date_fields = ['followup_date', 'app_reschedule_return_date', 'radiology_delivery_date']
        
        # حقل المترجم يحتاج عرض قائمة المترجمين
        if edit_field_key == 'translator_name':
            return await _render_draft_edit_translator_selection(query, context)
        
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


# =============================
# دوال تعديل المترجم (للمسودة)
# =============================

async def _render_draft_edit_translator_selection(query, context):
    """عرض قائمة المترجمين لتعديل المسودة"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        translator_names = load_translator_names()
        current_translator = context.user_data.get("report_tmp", {}).get('translator_name', 'غير محدد')
        
        text = "👤 **تعديل المترجم**\n\n"
        text += f"المترجم الحالي: {current_translator}\n\n"
        text += "اختر المترجم الجديد من القائمة:"
        
        # تقسيم الأسماء إلى صفوف (3 أسماء لكل صف)
        keyboard = []
        row = []
        
        for i, name in enumerate(translator_names):
            row.append(InlineKeyboardButton(name, callback_data=f"draft_edit_translator:{i}"))
            if len(row) == 3 or i == len(translator_names) - 1:
                keyboard.append(row)
                row = []
        
        flow_type = context.user_data.get('draft_flow_type', 'unknown')
        keyboard.append([InlineKeyboardButton("🔙 رجوع لقائمة الحقول", callback_data=f"back_to_edit_fields:{flow_type}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        return "EDIT_DRAFT_TRANSLATOR"
        
    except Exception as e:
        logger.error(f"خطأ في عرض قائمة المترجمين للتعديل: {e}")
        await query.edit_message_text("❌ حدث خطأ في تحميل قائمة المترجمين")
        return


async def handle_draft_edit_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المترجم الجديد للمسودة"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()
    
    try:
        # استخراج index المترجم
        translator_index = int(query.data.replace("draft_edit_translator:", ""))
        translator_names = load_translator_names()
        
        if translator_index < 0 or translator_index >= len(translator_names):
            await query.edit_message_text("❌ اختيار غير صحيح")
            return
        
        new_translator_name = translator_names[translator_index]
        
        # حفظ في report_tmp
        context.user_data.setdefault("report_tmp", {})["translator_name"] = new_translator_name
        
        # تنظيف
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)
        
        logger.info(f"✅ تم تحديث المترجم في المسودة: {new_translator_name}")
        
        # العودة لقائمة الحقول
        flow_type = context.user_data.get('draft_flow_type', 'unknown')
        
        await query.edit_message_text(
            f"✅ تم تحديث المترجم: {new_translator_name}\n\n"
            "جاري العودة لقائمة الحقول...",
            parse_mode="Markdown"
        )
        
        return await handle_back_to_edit_fields_direct(update, context, flow_type)
        
    except Exception as e:
        logger.error(f"خطأ في اختيار المترجم للمسودة: {e}")
        await query.edit_message_text("❌ حدث خطأ في تحديث المترجم")
        return


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
            'translator_name': 'المترجم',
            # ✅ حقول تأجيل الموعد
            'app_reschedule_reason': 'سبب تأجيل الموعد',
            'app_reschedule_return_date': 'موعد العودة الجديد',
            'app_reschedule_return_reason': 'سبب العودة',
            # ✅ حقول الأشعة والفحوصات
            'radiology_type': 'نوع الأشعة والفحوصات',
            'radiology_delivery_date': 'تاريخ التسليم',
            # ✅ حقول العلاج الطبيعي
            'therapy_details': 'تفاصيل الجلسة',
            # ✅ حقول الأجهزة التعويضية
            'device_details': 'تفاصيل الجهاز',
            # ✅ حقول الرقود
            'admission_summary': 'ملخص الرقود',
        }

        field_display_name = field_names.get(field_key, field_key)
        
        # تنظيف اسم الحقل من الأحرف الخاصة لتجنب أخطاء Markdown
        safe_field_name = field_display_name.replace('_', ' ').replace('*', '').replace('`', '')

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
            text = f"✅ تم تحديث {safe_field_name} بنجاح!\n\n"
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
        'translator_name': 'translator_name',
        # ✅ حقول تأجيل الموعد
        'app_reschedule_reason': 'app_reschedule_reason',
        'app_reschedule_return_date': 'app_reschedule_return_date',
        'app_reschedule_return_reason': 'app_reschedule_return_reason',
        # ✅ حقول الأشعة والفحوصات
        'radiology_type': 'radiology_type',
        'radiology_delivery_date': 'radiology_delivery_date',
        # ✅ حقول العلاج الطبيعي
        'therapy_details': 'therapy_details',
        # ✅ حقول الأجهزة التعويضية
        'device_details': 'device_details',
        # ✅ حقول الرقود
        'admission_summary': 'admission_summary',
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
    يستخدم show_final_summary من flows/shared.py لعرض الملخص الكامل بشكل صحيح
    """
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()

    try:
        callback_data = query.data
        flow_type = callback_data.split(":", 1)[1] if ":" in callback_data else context.user_data.get('draft_flow_type', 'new_consult')
        
        # ✅ الحصول على flow_type من report_tmp إذا لم يكن في callback_data
        data = context.user_data.get("report_tmp", {})
        current_flow = data.get("current_flow", "")
        valid_flow_types = ["new_consult", "followup", "periodic_followup", "inpatient_followup",
                            "emergency", "admission", "surgery_consult", "operation", "final_consult",
                            "discharge", "rehab_physical", "rehab_device", "device",
                            "radiology", "appointment_reschedule", "radiation_therapy"]
        if flow_type not in valid_flow_types:
            if current_flow:
                flow_type = current_flow
                logger.info(f"🔙 Using current_flow from report_tmp: {flow_type}")

        # مسح بيانات التعديل المؤقت
        context.user_data.pop('editing_draft', None)
        context.user_data.pop('draft_flow_type', None)
        context.user_data.pop('draft_medical_action', None)
        context.user_data.pop('editing_field', None)
        context.user_data.pop('editing_field_original', None)
        context.user_data.pop('edit_field_key', None)
        context.user_data.pop('edit_flow_type', None)

        logger.info(f"🔙 [BACK_TO_SUMMARY] Returning to summary for flow_type: {flow_type}")

        # ✅ استخدام show_final_summary من flows/shared.py لعرض الملخص الكامل
        from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary
        await show_final_summary(query.message, context, flow_type)

        # إرجاع state التأكيد
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        logger.info(f"🔙 [BACK_TO_SUMMARY] Returned to state: {confirm_state}")
        return confirm_state

    except Exception as e:
        logger.error(f"❌ خطأ في handle_back_to_summary: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ حدث خطأ في الرجوع للملخص.\n\n"
                "يرجى المحاولة مرة أخرى أو استخدام زر '❌ إلغاء' للبدء من جديد.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END

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
    logger.info("💾 [HANDLE_FINAL_CONFIRM] CALLED!")
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
    valid_flow_types = ["new_consult", "followup", "periodic_followup", "inpatient_followup",
                        "emergency", "admission", "surgery_consult", "operation", "final_consult",
                        "discharge", "rehab_physical", "rehab_device", "device",
                        "radiology", "appointment_reschedule", "radiation_therapy"]
    
    logger.info(f"🔍 [LOCAL_HANDLE_FINAL_CONFIRM] Raw callback_data: {query.data}")
    logger.info(f"🔍 [LOCAL_HANDLE_FINAL_CONFIRM] Parsed flow_type from callback: {flow_type}")
    logger.info(f"🔍 [LOCAL_HANDLE_FINAL_CONFIRM] current_flow from report_tmp: {current_flow}")
    logger.info(f"🔍 [LOCAL_HANDLE_FINAL_CONFIRM] medical_action from report_tmp: {data.get('medical_action', '')}")

    # ✅ إصلاح: إذا كان current_flow أكثر تحديداً (مثل periodic_followup بدلاً من followup أو new_consult)، استخدمه
    # المسارات الأكثر تحديداً لها الأولوية على المسارات العامة
    more_specific_flows = {
        "followup": ["periodic_followup", "inpatient_followup"],
        "new_consult": ["periodic_followup", "inpatient_followup"],  # ✅ إضافة new_consult أيضاً
    }

    if flow_type in more_specific_flows and current_flow in more_specific_flows.get(flow_type, []):
        logger.info(f"💾 ✅ [LOCAL_HANDLE_FINAL_CONFIRM] Overriding flow_type '{flow_type}' with more specific current_flow '{current_flow}'")
        flow_type = current_flow
    elif flow_type in valid_flow_types:
        logger.info(f"✅ [LOCAL_HANDLE_FINAL_CONFIRM] flow_type '{flow_type}' is valid, using it directly")
    elif flow_type not in valid_flow_types:
        if current_flow:
            flow_type = current_flow
            logger.info(f"💾 Using current_flow from report_tmp: {flow_type}")
    
    logger.info(f"💾 [LOCAL_HANDLE_FINAL_CONFIRM] Final flow_type to use: {flow_type}")
    
    # ✅ تحويل "rehab_device" إلى "device" للتوافق مع get_confirm_state و save_report_to_database
    if flow_type == "rehab_device":
        flow_type = "device"
        logger.info(f"💾 Converted flow_type from 'rehab_device' to 'device'")
    
    logger.info(f"💾 Action: {action}, Flow type: {flow_type}")
    logger.info(f"💾 Current flow from report_tmp: {current_flow}")

    if action == "publish":
        logger.info(f"💾 [PUBLISH] Starting publish process for flow_type: {flow_type}")
        logger.info(f"💾 [PUBLISH] Callback data: {query.data}")
        logger.info(f"💾 [PUBLISH] Current flow_type: {flow_type}")
        try:
            # استيراد save_report_to_database من flows/shared.py
            from bot.handlers.user.user_reports_add_new_system.flows.shared import save_report_to_database
            logger.info(f"💾 [PUBLISH] Calling save_report_to_database with flow_type: {flow_type}")
            await save_report_to_database(query, context, flow_type)
            logger.info(f"✅ [PUBLISH] Publish completed successfully for flow_type: {flow_type}")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"❌ [PUBLISH] Error in save_report_to_database: {e}", exc_info=True)
            logger.error(f"❌ [PUBLISH] Error type: {type(e).__name__}")
            logger.error(f"❌ [PUBLISH] Error details: {str(e)}")
            try:
                await query.answer(f"خطأ في النشر: {str(e)[:50]}", show_alert=True)
            except Exception as ans_err:
                logger.error(f"❌ [PUBLISH] Error answering query: {ans_err}")
            confirm_state = get_confirm_state(flow_type)
            logger.info(f"💾 [PUBLISH] Returning to confirm_state: {confirm_state}")
            return confirm_state
    elif action == "save":
        # ✅ Save action يجب أن يعيد إلى الملخص (show_final_summary)، وليس ينشر التقرير
        # النشر يتم فقط عند action == "publish"
        logger.info(f"📋 Save button clicked (returning to summary) for flow_type: {flow_type}")
        try:
            # استيراد show_final_summary من flows/shared.py
            from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary
            await show_final_summary(query.message, context, flow_type)
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            logger.info(f"✅ Returned to summary for flow_type: {flow_type}")
            return confirm_state
        except Exception as e:
            logger.error(f"❌ Error in show_final_summary: {e}", exc_info=True)
            await query.answer(f"خطأ في عرض الملخص: {str(e)[:50]}", show_alert=True)
            return get_confirm_state(flow_type)
    elif action == "edit":
        logger.info(f"✏️ Edit button clicked for flow_type: {flow_type}")
        # إعادة المستخدم إلى الخطوة الأولى من التدفق الحالي
        from bot.handlers.user.user_reports_add_new_system.flows.shared import handle_edit_before_save
        edit_state = await handle_edit_before_save(query, context, flow_type)
        # إرجاع state الذي تم إرجاعه من handle_edit_before_save (عادة FOLLOWUP_CONFIRM)
        if edit_state:
            return edit_state
        # إذا لم يتم إرجاع state، نرجع confirm_state الحالي
        return get_confirm_state(flow_type)

# =============================
# حفظ التقرير في قاعدة البيانات
# =============================

# ⚠️ ملاحظة: الدالة المحلية save_report_to_database أدناه (السطر 9648) غير مستخدمة
# يتم استخدام الدالة من flows/shared.py بدلاً منها (انظر handle_final_confirm السطر 9581)
# تم الاحتفاظ بها للتوافق مع الكود القديم فقط

def normalize_date_field(value):
    """تحويل قيمة التاريخ إلى date أو datetime أو None"""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        # إذا كان datetime، نعيد date فقط
        if isinstance(value, datetime):
            return value.date()
        return value
    if isinstance(value, str):
        # محاولة تحويل النص إلى date
        if not value.strip() or value.strip() == "لا يوجد":
            return None
        # محاولة صيغ مختلفة
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"]:
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt.date()
            except ValueError:
                continue
        # إذا فشل التحويل، نعيد None (لن نحفظ نصاً في حقل تاريخ)
        return None
    return None

def normalize_datetime_field(value):
    """تحويل قيمة التاريخ إلى datetime أو None (لحقول DateTime في قاعدة البيانات)"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        # تحويل date إلى datetime (في بداية اليوم)
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        # محاولة تحويل النص إلى datetime
        if not value.strip() or value.strip() == "لا يوجد":
            return None
        # محاولة صيغ مختلفة
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"]:
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        # إذا فشل التحويل، نعيد None
        return None
    return None

# ⚠️ DEPRECATED: هذه الدالة غير مستخدمة - يتم استخدام الدالة من flows/shared.py بدلاً منها
# تم الاحتفاظ بها للتوافق مع الكود القديم فقط
# TODO: حذف هذه الدالة بعد التأكد من عدم استخدامها في أي مكان
async def save_report_to_database_OLD_UNUSED(query, context, flow_type):
    """حفظ التقرير في قاعدة البيانات - DEPRECATED: غير مستخدمة"""
    import logging
    logger = logging.getLogger(__name__)
    
    # ⚠️ تحذير: هذه الدالة المحلية غير مستخدمة
    logger.error("❌ [ERROR] استخدام الدالة المحلية save_report_to_database_OLD_UNUSED - يجب استخدام الدالة من flows/shared.py")
    raise NotImplementedError("❌ هذه الدالة غير مستخدمة - يرجى استخدام الدالة من flows/shared.py")
    
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
                         "operation", "final_consult", "discharge", "rehab_physical", "rehab_device", "radiology",
                         "appointment_reschedule", "physical_therapy", "prosthetics"]
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

        # ✅ دالة مساعدة لتنظيف القيم من النصوص التعليمية
        def clean_field_value(value):
            """إزالة النصوص التعليمية من القيم"""
            if not value:
                return ""
            value_str = str(value)
            # إزالة النصوص التعليمية
            unwanted_patterns = [
                "✏️ تعديل:",
                "القيمة الحالية:",
                "📝 أدخل القيمة الجديدة:",
                "📌 القيمة الحالية:"
            ]
            for pattern in unwanted_patterns:
                if pattern in value_str:
                    # استخراج النص الفعلي بين "القيمة الحالية:" و "📝 أدخل"
                    if "القيمة الحالية:" in value_str:
                        parts = value_str.split("القيمة الحالية:", 1)
                        if len(parts) > 1:
                            actual_value = parts[1].split("📝 أدخل القيمة الجديدة:")[0].strip()
                            return actual_value
                    # إذا لم ينجح التنظيف، نزيل النص التعليمي فقط
                    value_str = value_str.replace(pattern, "").strip()
            return value_str

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
            # ✅ استخدام دالة التنظيف المعرفة أعلاه
            complaint_text = clean_field_value(data.get("complaint", ""))
            diagnosis = clean_field_value(data.get("diagnosis", ""))
            decision = clean_field_value(data.get("decision", ""))
            decision_text = f"التشخيص: {diagnosis}\n\nقرار الطبيب: {decision}"
            
            if flow_type == "new_consult":
                tests = clean_field_value(data.get("tests", "لا يوجد"))
                decision_text += f"\n\nالفحوصات المطلوبة: {tests}"
            elif flow_type == "emergency":
                status = clean_field_value(data.get("status", ""))
                decision_text += f"\n\nوضع الحالة: {status}"

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
        
        # ✅ تحضير followup_date قبل إنشاء Report
        # ✅ followup_date من نوع DateTime في النموذج، يجب تحويله إلى datetime
        followup_date_raw = data.get("followup_date")
        followup_datetime = None
        if followup_date_raw:
            followup_datetime = normalize_datetime_field(followup_date_raw)
            # إذا كان هناك وقت منفصل، نضيفه
            if followup_datetime and data.get("followup_time"):
                try:
                    time_str = data.get("followup_time")
                    if ':' in time_str:
                        hour, minute = map(int, time_str.split(':'))
                        followup_datetime = followup_datetime.replace(hour=hour, minute=minute)
                except:
                    pass
        
        # إنشاء التقرير
        new_report = Report(
            # IDs للربط
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id if department else None,
            doctor_id=doctor.id if doctor else None,
            translator_id=actual_translator_id,  # ✅ استخدام translator_id الفعلي
            submitted_by_user_id=user_id,  # ✅ حفظ معرف المستخدم الذي أنشأ التقرير
            
            # ✅ الأسماء المكررة للبحث والطباعة السريعة (مطلوبة في النموذج)
            patient_name=patient_name,
            hospital_name=hospital_name,
            department=dept_name_for_display or (department.name if department else None),
            doctor_name=doctor_name,
            translator_name=data.get("translator_name"),
            
            # محتوى التقرير
            complaint_text=complaint_text,
            doctor_decision=clean_field_value(data.get("decision", "")),  # ✅ حفظ قرار الطبيب فقط
            diagnosis=clean_field_value(data.get("diagnosis", "")),  # ✅ حفظ التشخيص كحقل منفصل
            notes=clean_field_value(data.get("tests", "") or data.get("notes", "")),  # ✅ حفظ الفحوصات/الملاحظات
            treatment_plan=clean_field_value(data.get("recommendations", "") or data.get("treatment_plan", "")),  # ✅ حفظ التوصيات
            case_status=clean_field_value(data.get("status", "")),  # ✅ حفظ وضع الحالة (للطوارئ)
            medical_action=final_medical_action,
            medications=clean_field_value(data.get("tests", "") or data.get("medications", "")),  # ✅ حفظ الفحوصات في medications لـ new_consult
            
            # ✅ حقول خاصة
            room_number=clean_field_value(data.get("room_number") or data.get("room_floor") or data.get("room") or ""),  # رقم الغرفة/الطابق (موحد من جميع المسارات)
            
            # ✅ ملاحظة: operation_name_en, success_rate, benefit_rate غير موجودة في نموذج Report
            # سيتم إرسالها من data مباشرة في broadcast_data عند البث
            
            # التواريخ
            followup_date=followup_datetime,  # ✅ تحويل التاريخ إلى datetime
            followup_time=data.get("followup_time"),  # ✅ حفظ وقت العودة
            followup_reason=data.get("followup_reason", "لا يوجد"),
            report_date=data.get("report_date", datetime.now()),
            created_at=datetime.now(),
            
            # ✅ حفظ حقول تأجيل الموعد
            app_reschedule_reason=clean_field_value(data.get("app_reschedule_reason", "")),  # سبب تأجيل الموعد
            app_reschedule_return_date=normalize_datetime_field(data.get("app_reschedule_return_date")),  # ✅ تحويل التاريخ إلى datetime
            app_reschedule_return_reason=clean_field_value(data.get("app_reschedule_return_reason", "")),  # سبب العودة
            
            # ✅ حقول الأشعة
            radiology_type=clean_field_value(data.get("radiology_type", "")),
            radiology_delivery_date=normalize_datetime_field(data.get("radiology_delivery_date")),  # ✅ تحويل التاريخ إلى datetime
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
            
            # ✅ إضافة رقم الغرفة للمسارات التي تحتاجه
            # إضافة room_number فقط إذا كان action_type == INPATIENT_FOLLOWUP أو flow_type == followup
            action_type = data.get('action_type', '')
            if (action_type == 'INPATIENT_FOLLOWUP' or flow_type == 'followup'):
                room_number = data.get('room_number') or data.get('room_floor') or data.get('room')
                if room_number and str(room_number).strip() and str(room_number).strip() != 'لم يتم التحديد':
                    broadcast_data['room_number'] = str(room_number).strip()
                    logger.info(f"✅ تم إضافة room_number إلى broadcast_data: {broadcast_data['room_number']}")
            
            # ✅ إضافة diagnosis و decision لجميع المسارات (مهم للعرض الصحيح)
            broadcast_data['diagnosis'] = data.get('diagnosis', '')
            broadcast_data['decision'] = data.get('decision', '')
            
            # إضافة الحقول الإضافية لـ surgery_consult
            if flow_type == "surgery_consult":
                broadcast_data['operation_name_en'] = data.get('operation_name_en', '')
                broadcast_data['success_rate'] = data.get('success_rate', '')
                broadcast_data['benefit_rate'] = data.get('benefit_rate', '')
                broadcast_data['tests'] = data.get('tests', 'لا يوجد')
            
            # ✅ إضافة tests لـ new_consult
            if flow_type == "new_consult":
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
                    data = context.user_data.get("report_tmp", {})
                    # --- منطق الفصل الصريح بين المسارات ---
                    # استيراد قوائم الحقول المصرح بها لكل مسار
                    from bot.handlers.user.user_reports_flows.followup_in_admission import FOLLOWUP_FIELDS
                    from bot.handlers.user.user_reports_flows.periodic_review import PERIODIC_REVIEW_FIELDS

                    # بناء dict من قائمة الحقول المصرح بها لهذا المسار
                    allowed_fields = []
                    if flow_type == "followup":
                        allowed_fields = [f[0] for f in FOLLOWUP_FIELDS]
                    elif flow_type == "periodic_followup":
                        allowed_fields = [f[0] for f in PERIODIC_REVIEW_FIELDS]

                    # فقط الحقول المصرح بها لهذا المسار
                    filtered_data = {k: v for k, v in data.items() if k in allowed_fields}

                    # تفاصيل حسب نوع المسار
                    if flow_type in ["new_consult", "followup", "emergency", "periodic_followup"]:
                        # استخدم filtered_data بدلاً من data
                        summary += f"💬 **الشكوى:** {filtered_data.get('complaint', 'غير محدد')}\n"
                        summary += f"🔬 **التشخيص:** {filtered_data.get('diagnosis', 'غير محدد')}\n"
                        summary += f"📝 **قرار الطبيب:** {filtered_data.get('decision', 'غير محدد')}\n"

                        if flow_type == "new_consult":
                            summary += f"🔬 **الفحوصات المطلوبة:** {filtered_data.get('tests', 'لا يوجد')}\n"

                        if flow_type == "emergency":
                            summary += f"🏥 **وضع الحالة:** {filtered_data.get('status', 'غير محدد')}\n"

                        # تاريخ العودة
                        followup_date = filtered_data.get('followup_date')
                        if followup_date:
                            if hasattr(followup_date, 'strftime'):
                                date_str = followup_date.strftime('%Y-%m-%d')
                            else:
                                date_str = str(followup_date)
                            followup_time = filtered_data.get('followup_time', '')
                            if followup_time:
                                time_display = format_time_string_12h(followup_time)
                                summary += f"📅 **تاريخ العودة:** {date_str} الساعة {time_display}\n"
                            else:
                                summary += f"📅 **تاريخ العودة:** {date_str}\n"
                            summary += f"✍️ **سبب العودة:** {filtered_data.get('followup_reason', 'غير محدد')}\n"
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

        # ✅ إصلاح رسالة الخطأ لتجنب مشاكل Markdown
        error_msg = str(e)
        # تنظيف رسالة الخطأ من الأحرف الخاصة التي قد تسبب مشاكل في Markdown
        error_msg_clean = error_msg.replace("*", "\\*").replace("_", "\\_").replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")
        
        await query.edit_message_text(
            f"❌ **حدث خطأ أثناء الحفظ**\n\n"
            f"الخطأ: `{error_msg_clean[:200]}`\n\n"
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
        room_number = report_tmp.get("room_number") or report_tmp.get("room_floor")
        followup_reason = report_tmp.get("followup_reason")
        
        logger.debug(f"DEBUG: followup flow - complaint={repr(complaint)}, diagnosis={repr(diagnosis)}, decision={repr(decision)}, room_number={repr(room_number)}, followup_reason={repr(followup_reason)}, medical_action={repr(medical_action)}")
        
        # التحقق من الحالة الحالية بناءً على البيانات
        if current_state == FOLLOWUP_COMPLAINT or not complaint:
            return await handle_followup_complaint(update, context)
        elif current_state == FOLLOWUP_DIAGNOSIS or not diagnosis:
            return await handle_followup_diagnosis(update, context)
        elif current_state == FOLLOWUP_DECISION or not decision:
            return await handle_followup_decision(update, context)
        # ✅ التحقق من رقم الغرفة فقط لمسار "متابعة في الرقود" (وليس "مراجعة / عودة دورية")
        elif medical_action == "متابعة في الرقود" and (current_state == FOLLOWUP_ROOM_FLOOR or not room_number):
            return await handle_followup_room_floor(update, context)
        elif medical_action == "مراجعة / عودة دورية" and (current_state == FOLLOWUP_ROOM_FLOOR or not room_number):
            # تجاوز خطوة رقم الغرفة في مسار مراجعة / عودة دورية
            return await handle_followup_reason(update, context)
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

def _get_radiation_therapy_handler(handler_name):
    """الحصول على handler من flows/radiation_therapy.py"""
    try:
        from bot.handlers.user.user_reports_add_new_system.flows.radiation_therapy import (
            handle_radiation_therapy_type,
            handle_radiation_therapy_session_number,
            handle_radiation_therapy_remaining,
            handle_radiation_therapy_notes,
            handle_radiation_therapy_return_date,
            handle_radiation_therapy_return_reason,
            handle_radiation_calendar_callback,
            handle_radiation_translator_callback,
        )
        handlers = {
            'handle_radiation_therapy_type': handle_radiation_therapy_type,
            'handle_radiation_therapy_session_number': handle_radiation_therapy_session_number,
            'handle_radiation_therapy_remaining': handle_radiation_therapy_remaining,
            'handle_radiation_therapy_notes': handle_radiation_therapy_notes,
            'handle_radiation_therapy_return_date': handle_radiation_therapy_return_date,
            'handle_radiation_therapy_return_reason': handle_radiation_therapy_return_reason,
            'handle_radiation_calendar_callback': handle_radiation_calendar_callback,
            'handle_radiation_translator_callback': handle_radiation_translator_callback,
        }
        return handlers.get(handler_name)
    except ImportError as e:
        logger.error(f"Error importing radiation_therapy handlers: {e}")
        return None

async def handle_restart_from_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()
    except Exception:
        pass
    try:
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
    except Exception:
        if update.message:
            await update.message.reply_text("✅ تم إعادة البدء. اختر العملية المطلوبة.")
    return ConversationHandler.END

async def handle_restart_from_start_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data.clear()
    except Exception:
        pass
    try:
        from bot.handlers.user.user_start import handle_start_main_menu
        await handle_start_main_menu(update, context)
    except Exception:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("✅ تم إعادة البدء. اختر العملية المطلوبة.")
    return ConversationHandler.END

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
            CallbackQueryHandler(start_report, pattern="^user_action:add_report$"),
            CallbackQueryHandler(start_report, pattern="^add_report$"),
            # دعم النص
            MessageHandler(filters.Regex(r"^📝\s*إضافة\s*تقرير\s*جديد\s*$"), start_report),
            MessageHandler(filters.Regex(r"^📝\s*إضافة تقرير جديد\s*$"), start_report),
            MessageHandler(filters.Regex(r"^📝 إضافة تقرير جديد$"), start_report),
            MessageHandler(filters.Regex(r"إضافة تقرير جديد"), start_report),
            MessageHandler(filters.TEXT & filters.Regex(r"📝.*إضافة.*تقرير.*جديد"), start_report),
        ],
        states={
            STATE_SELECT_DATE: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_date_choice, pattern="^(date:|nav:)"),
                CallbackQueryHandler(handle_main_calendar_nav, pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(handle_main_calendar_day, pattern="^main_cal_day:"),
            ],
            R_DATE: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_date_choice, pattern="^(date:|nav:)"),
                CallbackQueryHandler(handle_main_calendar_nav, pattern="^main_cal_(prev|next):"),
                CallbackQueryHandler(handle_main_calendar_day, pattern="^main_cal_day:"),
            ],
            R_DATE_TIME: [
                CallbackQueryHandler(handle_date_time_hour, pattern="^time_hour:"),
                CallbackQueryHandler(handle_date_time_minute, pattern="^time_minute:"),
                CallbackQueryHandler(handle_date_time_skip, pattern="^time_skip"),
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
            ],
            STATE_SELECT_PATIENT: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_patient_selection, pattern="^patient_idx:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            R_PATIENT: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_patient_selection, pattern="^patient_idx:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient),
            ],
            STATE_SELECT_HOSPITAL: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_hospital_selection, pattern="^hospital_idx:"),
                CallbackQueryHandler(handle_hospital_page, pattern="^(hospital_page|hosp_page):"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_search),
            ],
            STATE_SELECT_DEPARTMENT: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_department_selection, pattern="^dept_idx:"),
                CallbackQueryHandler(handle_department_page, pattern="^dept_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
            ],
            R_DEPARTMENT: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_department_selection, pattern="^dept_idx:"),
                CallbackQueryHandler(handle_department_page, pattern="^dept_page:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_department_search),
            ],
            R_SUBDEPARTMENT: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_subdepartment_choice, pattern="^subdept(?:_idx)?:"),
                CallbackQueryHandler(handle_subdepartment_page, pattern="^subdept_page:"),
            ],
            STATE_SELECT_DOCTOR: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_doctor_btn_selection, pattern="^doctor_idx:"),
                CallbackQueryHandler(handle_doctor_page, pattern="^doctor_page:"),
                CallbackQueryHandler(handle_doctor_selection, pattern="^doctor_manual$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            R_DOCTOR: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_doctor_btn_selection, pattern="^doctor_idx:"),
                CallbackQueryHandler(handle_doctor_page, pattern="^doctor_page:"),
                CallbackQueryHandler(handle_doctor_selection, pattern="^doctor_manual$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_doctor),
            ],
            R_ACTION_TYPE: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                # جميع الأزرار في صفحة واحدة - لا حاجة لـ handle_action_page
                CallbackQueryHandler(handle_action_type_choice, pattern="^action_idx:"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
                # معالجة callbacks القديمة (من حالات سابقة)
                CallbackQueryHandler(handle_stale_callback, pattern="^(hosp_page|hospital_page|dept_page|department_page|subdept_page|subdepartment_page|doctor_idx|hospital_idx|dept_idx|subdept|subdept_idx):"),
            ],
            STATE_SELECT_ACTION_TYPE: [
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
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
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_diagnosis')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_decision')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_tests')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_calendar_nav'), pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_calendar_day'), pattern="^followup_cal_day:"),
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_date_skip'), pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_TIME: [
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_time_hour'), pattern="^followup_time_hour:"),
                CallbackQueryHandler(_get_new_consult_handler('handle_new_consult_followup_time_skip'), pattern="^followup_time_skip"),
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_new_consult_handler('handle_new_consult_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            NEW_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            NEW_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_new_consult_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ new_consult
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
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
            # حالة تعديل المترجم (للمسودة)
            "EDIT_DRAFT_TRANSLATOR": [
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
            ],
            # مسار استشارة مع قرار عملية (handlers من flows/surgery_consult.py)
            SURGERY_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_diagnosis')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_decision')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_name_en')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_SUCCESS_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_success_rate')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_BENEFIT_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_benefit_rate')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_TESTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_tests')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_surgery_consult_handler('handle_surgery_consult_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            SURGERY_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            SURGERY_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_surgery_consult_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ surgery_consult
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار استشارة أخيرة (handlers من flows/final_consult.py)
            FINAL_CONSULT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_final_consult_handler('handle_final_consult_diagnosis')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FINAL_CONSULT_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_final_consult_handler('handle_final_consult_decision')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FINAL_CONSULT_RECOMMENDATIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_final_consult_handler('handle_final_consult_recommendations')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FINAL_CONSULT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            FINAL_CONSULT_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_final_consult_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ final_consult
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار متابعة في الرقود (handlers من flows/followup.py)
            FOLLOWUP_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_complaint')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FOLLOWUP_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_diagnosis')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FOLLOWUP_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_decision')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            # ✅ حالة FOLLOWUP_ROOM_FLOOR - فقط لمسار "متابعة في الرقود" (وليس "مراجعة / عودة دورية")
            FOLLOWUP_ROOM_FLOOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_room_floor')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FOLLOWUP_DATE_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                CallbackQueryHandler(handle_calendar_cancel, pattern="^nav:cancel$"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_followup_handler('handle_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            FOLLOWUP_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            FOLLOWUP_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_inpatient_followup_edit_field_selection أو handle_periodic_followup_edit_field_selection بناءً على medical_action
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ followup
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار طوارئ (handlers من flows/emergency.py)
            EMERGENCY_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_complaint')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_diagnosis')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_DECISION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_decision')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_STATUS: [
                CallbackQueryHandler(_get_emergency_handler('handle_emergency_status_choice'), pattern="^emerg_status:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_status_text')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            # ✅ إضافة handler لحالة ملاحظات الرقود (بعد اختيار "تم الترقيد")
            EMERGENCY_ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_admission_notes')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            # ✅ إضافة handler لحالة تفاصيل العملية (بعد اختيار "تم إجراء عملية")
            EMERGENCY_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_operation_details')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_ADMISSION_TYPE: [
                CallbackQueryHandler(_get_emergency_handler('handle_emergency_admission_type_choice'), pattern="^emerg_admission:"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_ROOM_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_room_number')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_DATE_TIME: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_date_time_text')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            EMERGENCY_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            EMERGENCY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_emergency_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ emergency
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار عملية (handlers من flows/operation.py)
            OPERATION_DETAILS_AR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_details_ar')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_name_en')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            OPERATION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_notes')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            OPERATION_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            OPERATION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_operation_handler('handle_operation_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            OPERATION_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            OPERATION_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_operation_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ operation
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار علاج طبيعي / أجهزة تعويضية (handlers من flows/rehab.py)
            REHAB_TYPE: [
                CallbackQueryHandler(_get_rehab_handler('handle_rehab_type'), pattern="^rehab_type:"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_physical_therapy_details')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_physical_therapy_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            PHYSICAL_THERAPY_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            PHYSICAL_THERAPY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_rehab_physical_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ rehab_physical
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            DEVICE_NAME_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_device_name_details')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DEVICE_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DEVICE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_rehab_handler('handle_device_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DEVICE_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            DEVICE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_rehab_device_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ rehab_device/device
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
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
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_radiology_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ radiology
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار ترقيد (handlers من flows/admission.py)
            ADMISSION_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            ADMISSION_ROOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_room')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            ADMISSION_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_notes')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            ADMISSION_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            ADMISSION_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_admission_handler('handle_admission_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            ADMISSION_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            ADMISSION_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_admission_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ admission
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار خروج من المستشفى (handlers من flows/discharge.py)
            DISCHARGE_TYPE: [
                CallbackQueryHandler(_get_discharge_handler('handle_discharge_type'), pattern="^discharge_type:"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DISCHARGE_ADMISSION_SUMMARY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_admission_summary')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DISCHARGE_OPERATION_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_operation_details')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DISCHARGE_OPERATION_NAME_EN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_operation_name_en')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DISCHARGE_FOLLOWUP_DATE: [
                CallbackQueryHandler(handle_new_consult_followup_calendar_nav, pattern="^followup_cal_(prev|next):"),
                CallbackQueryHandler(handle_new_consult_followup_calendar_day, pattern="^followup_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_date_skip, pattern="^followup_date_skip"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_new_consult_followup_time_skip, pattern="^followup_time_skip"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DISCHARGE_FOLLOWUP_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_discharge_handler('handle_discharge_followup_reason')),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            DISCHARGE_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            DISCHARGE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_discharge_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ discharge
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # مسار تأجيل موعد
            APP_RESCHEDULE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_app_reschedule_reason),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            APP_RESCHEDULE_RETURN_DATE: [
                CallbackQueryHandler(handle_reschedule_calendar_nav, pattern="^reschedule_cal_nav:"),
                CallbackQueryHandler(handle_reschedule_calendar_day, pattern="^reschedule_cal_day:"),
                CallbackQueryHandler(handle_new_consult_followup_time_hour, pattern="^followup_time_hour:"),
                CallbackQueryHandler(handle_new_consult_followup_time_minute, pattern="^followup_time_minute:"),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_cancel_navigation, pattern="^nav:cancel$"),
            ],
            APP_RESCHEDULE_RETURN_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_app_reschedule_return_reason),
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            ],
            APP_RESCHEDULE_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_page_navigation, pattern="^translator_page:"),
                CallbackQueryHandler(handle_simple_translator_choice, pattern="^simple_translator:"),
            ],
            APP_RESCHEDULE_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                # ✅ استخدام router للتعديل قبل النشر (edit_field:)
                # Router يوجه إلى handle_appointment_reschedule_edit_field_selection بناءً على flow_type في callback_data
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                # ✅ معالجة إدخال القيمة الجديدة - router يوجه إلى handler المناسب لـ appointment_reschedule
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
            ],
            # =============================
            # مسار جلسة إشعاعي (Radiation Therapy)
            # =============================
            RADIATION_THERAPY_TYPE: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_radiation_therapy_handler('handle_radiation_therapy_type')),
            ],
            RADIATION_THERAPY_SESSION_NUMBER: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_radiation_therapy_handler('handle_radiation_therapy_session_number')),
            ],
            RADIATION_THERAPY_REMAINING: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_radiation_therapy_handler('handle_radiation_therapy_remaining')),
            ],
            RADIATION_THERAPY_NOTES: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_radiation_therapy_handler('handle_radiation_therapy_notes')),
            ],
            RADIATION_THERAPY_RETURN_DATE: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                # callbacks التقويم
                CallbackQueryHandler(_get_radiation_therapy_handler('handle_radiation_calendar_callback'), pattern="^rad_cal_"),
                CallbackQueryHandler(_get_radiation_therapy_handler('handle_radiation_calendar_callback'), pattern="^rad_time_"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_radiation_therapy_handler('handle_radiation_therapy_return_date')),
            ],
            RADIATION_THERAPY_RETURN_REASON: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _get_radiation_therapy_handler('handle_radiation_therapy_return_reason')),
            ],
            RADIATION_THERAPY_TRANSLATOR: [
                CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
                CallbackQueryHandler(handle_smart_cancel_navigation, pattern="^nav:cancel$"),
                # callbacks المترجمين مع pagination
                CallbackQueryHandler(_get_radiation_therapy_handler('handle_radiation_translator_callback'), pattern="^rad_translator"),
                CallbackQueryHandler(handle_noop, pattern="^noop$"),
            ],
            RADIATION_THERAPY_CONFIRM: [
                CallbackQueryHandler(handle_final_confirm, pattern="^(save|publish|edit):"),
                CallbackQueryHandler(handle_save_callback, pattern="^save:"),
                CallbackQueryHandler(handle_edit_draft_report, pattern="^edit_draft:"),
                CallbackQueryHandler(handle_edit_field_selection, pattern="^draft_field:"),
                CallbackQueryHandler(
                    route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END),
                    pattern="^edit_field:"
                ),
                CallbackQueryHandler(handle_finish_edit_draft, pattern="^finish_edit_draft:"),
                CallbackQueryHandler(handle_back_to_summary, pattern="^back_to_summary:"),
                CallbackQueryHandler(handle_edit_draft_field, pattern="^edit_field_draft:"),
                CallbackQueryHandler(handle_draft_edit_translator, pattern="^draft_edit_translator:"),
                CallbackQueryHandler(handle_back_to_edit_fields, pattern="^back_to_edit_fields"),
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    route_edit_field_input if route_edit_field_input else handle_draft_field_input
                ),
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

            CallbackQueryHandler(handle_cancel_navigation, pattern="^nav:cancel$"),
            CommandHandler("cancel", handle_cancel_navigation),
            CommandHandler("start", handle_restart_from_start),
            MessageHandler(filters.Regex(r"^/start$"), handle_restart_from_start),
            MessageHandler(filters.Regex(r"^🚀\s*(ابدأ( الآن)?|أبدا استخدام النظام)\s*$"), handle_restart_from_start),
            CallbackQueryHandler(handle_restart_from_start_main_menu, pattern="^start_main_menu$"),
            # معالج للرسائل التي تحتوي على "إضافة تقرير جديد" (للتعامل مع الأزرار)
            MessageHandler(filters.TEXT & filters.Regex(r".*إضافة.*تقرير.*جديد.*"), start_report),
            # معالج زر الرجوع - يعمل في جميع الـ states
            CallbackQueryHandler(handle_smart_back_navigation, pattern="^nav:back$"),
            # DEBUG: إضافة fallback لالتقاط جميع callbacks غير متطابقة في حالة R_ACTION_TYPE
            CallbackQueryHandler(debug_all_callbacks, pattern=".*"),
        ],
        per_message=False,  # ✅ False لأن entry points مختلطة (CallbackQueryHandler و MessageHandler)
        per_chat=True,
        per_user=True,
        allow_reentry=True,  # ✅ السماح بإعادة الدخول عند الضغط على /start
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
    
    # قائمة احتياطية في حالة فشل التحميل - بنفس الترتيب المطلوب
    return ["معتز", "ادم", "هاشم", "مصطفى", "حسن", "نجم الدين", "محمد علي", 
            "صبري", "عزي", "سعيد", "عصام", "زيد", "مهدي", "ادريس", 
            "واصل", "عزالدين", "عبدالسلام", "يحيى العنسي", "ياسر"]

async def show_translator_selection(message, context, flow_type, page=1):
    """
    عرض قائمة المترجمين للاختيار مع صفحات
    """
    translator_names = load_translator_names()

    if not translator_names:
        await message.reply_text("❌ خطأ: لا توجد أسماء مترجمين متاحة")
        # المتابعة بدون مترجم
        await show_final_summary(message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    # تقسيم إلى صفحتين: الصفحة الأولى 19 مترجم، الباقي في الصفحة الثانية
    FIRST_PAGE_COUNT = 19
    
    if page == 1:
        # الصفحة الأولى - أول 19 مترجم
        page_names = translator_names[:FIRST_PAGE_COUNT]
    else:
        # الصفحة الثانية - الباقي
        page_names = translator_names[FIRST_PAGE_COUNT:]
    
    # تقسيم الأسماء إلى صفوف (3 أسماء لكل صف)
    keyboard_buttons = []
    row = []

    for name in page_names:
        # الحصول على الـ index الحقيقي من القائمة الأصلية
        real_index = translator_names.index(name)
        row.append(InlineKeyboardButton(name, callback_data=f"simple_translator:{flow_type}:{real_index}"))
        if len(row) == 3:
            keyboard_buttons.append(row)
            row = []
    
    # إضافة الصف الأخير إذا كان غير مكتمل
    if row:
        keyboard_buttons.append(row)

    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if page == 1 and len(translator_names) > FIRST_PAGE_COUNT:
        # الصفحة الأولى - إضافة زر "الصفحة التالية"
        nav_buttons.append(InlineKeyboardButton("⬅️ الصفحة التالية", callback_data=f"translator_page:{flow_type}:2"))
    elif page == 2:
        # الصفحة الثانية - إضافة زر "الصفحة السابقة"
        nav_buttons.append(InlineKeyboardButton("➡️ الصفحة السابقة", callback_data=f"translator_page:{flow_type}:1"))
    
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)

    # إضافة زر الرجوع وإلغاء
    keyboard_buttons.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    page_text = f"(الصفحة {page} من 2)" if len(translator_names) > FIRST_PAGE_COUNT else ""

    await message.reply_text(
        f"👤 **اختر اسم المترجم** {page_text}\n\n"
        f"المترجم مسؤول عن ترجمة التقرير إلى اللغة المطلوبة.\n"
        f"اختر من القائمة أدناه:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

async def handle_translator_page_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة التنقل بين صفحات المترجمين
    """
    query = update.callback_query
    await query.answer()
    
    try:
        parts = query.data.split(":")
        if len(parts) < 3:
            return
        
        flow_type = parts[1]
        page = int(parts[2])
        
        # ✅ التحقق من flow_type وتصحيحه إذا لزم الأمر
        valid_flow_types = ["new_consult", "followup", "periodic_followup", "inpatient_followup",
                            "emergency", "admission", "surgery_consult", "operation", "final_consult",
                            "discharge", "rehab_physical", "rehab_device", "device",
                            "radiology", "appointment_reschedule", "radiation_therapy"]

        # ✅ إصلاح: إذا كان current_flow أكثر تحديداً، استخدمه
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "")
        more_specific_flows = {
            "followup": ["periodic_followup", "inpatient_followup"],
            "new_consult": ["periodic_followup", "inpatient_followup"],
        }

        if flow_type in more_specific_flows and current_flow in more_specific_flows.get(flow_type, []):
            flow_type = current_flow
        elif flow_type not in valid_flow_types:
            # محاولة الحصول على flow_type من report_tmp
            if current_flow in valid_flow_types:
                flow_type = current_flow
            else:
                flow_type = "new_consult"  # القيمة الافتراضية
        
        translator_names = load_translator_names()
        FIRST_PAGE_COUNT = 19
        
        if page == 1:
            page_names = translator_names[:FIRST_PAGE_COUNT]
        else:
            page_names = translator_names[FIRST_PAGE_COUNT:]
        
        # تقسيم الأسماء إلى صفوف (3 أسماء لكل صف)
        keyboard_buttons = []
        row = []

        for name in page_names:
            real_index = translator_names.index(name)
            row.append(InlineKeyboardButton(name, callback_data=f"simple_translator:{flow_type}:{real_index}"))
            if len(row) == 3:
                keyboard_buttons.append(row)
                row = []
        
        if row:
            keyboard_buttons.append(row)

        # أزرار التنقل
        nav_buttons = []
        if page == 1 and len(translator_names) > FIRST_PAGE_COUNT:
            nav_buttons.append(InlineKeyboardButton("⬅️ الصفحة التالية", callback_data=f"translator_page:{flow_type}:2"))
        elif page == 2:
            nav_buttons.append(InlineKeyboardButton("➡️ الصفحة السابقة", callback_data=f"translator_page:{flow_type}:1"))
        
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)

        keyboard_buttons.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ])

        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        page_text = f"(الصفحة {page} من 2)" if len(translator_names) > FIRST_PAGE_COUNT else ""

        await query.edit_message_text(
            f"👤 **اختر اسم المترجم** {page_text}\n\n"
            f"المترجم مسؤول عن ترجمة التقرير إلى اللغة المطلوبة.\n"
            f"اختر من القائمة أدناه:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in handle_translator_page_navigation: {e}")

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

        # التحقق من flow_type
        valid_flow_types = ["new_consult", "followup", "periodic_followup", "inpatient_followup",
                            "emergency", "admission", "surgery_consult", "operation", "final_consult",
                            "discharge", "rehab_physical", "rehab_device", "device",
                            "radiology", "appointment_reschedule", "radiation_therapy"]

        # ✅ إصلاح: إذا كان current_flow أكثر تحديداً، استخدمه
        current_flow = context.user_data.get("report_tmp", {}).get("current_flow", "")
        more_specific_flows = {
            "followup": ["periodic_followup", "inpatient_followup"],
            "new_consult": ["periodic_followup", "inpatient_followup"],
        }

        if flow_type in more_specific_flows and current_flow in more_specific_flows.get(flow_type, []):
            flow_type = current_flow
        elif not flow_type or flow_type not in valid_flow_types:
            # محاولة الحصول على flow_type من report_tmp
            if current_flow in valid_flow_types:
                flow_type = current_flow
            else:
                flow_type = "new_consult"  # القيمة الافتراضية

        # المتابعة للتأكيد النهائي
        message_to_use = None
        
        # محاولة تعديل الرسالة أولاً
        try:
            await query.edit_message_text(f"✅ تم اختيار المترجم: **{translator_name}**", parse_mode="Markdown")
            # بعد تعديل الرسالة، query.message قد لا يكون متاحاً، لذا نحفظ chat_id
            message_to_use = query.message
        except Exception as e:
            # إذا فشل تعديل الرسالة، نستخدم query.message الأصلي
            message_to_use = query.message
        
        # محاولة إرسال الملخص
        try:
            if message_to_use:
                await show_final_summary(message_to_use, context, flow_type)
            elif update.effective_message:
                await show_final_summary(update.effective_message, context, flow_type)
            else:
                # كحل أخير، أرسل رسالة جديدة
                bot = context.bot
                new_message = await bot.send_message(
                    chat_id=query.from_user.id,
                    text="✅ تم اختيار المترجم"
                )
                await show_final_summary(new_message, context, flow_type)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ خطأ في show_final_summary: {e}", exc_info=True)
            # حتى لو فشل show_final_summary، نكمل العملية
            try:
                if not message_to_use and update.effective_message:
                    await update.effective_message.reply_text(
                        f"✅ تم اختيار المترجم: {translator_name}\n\n"
                        f"اضغط على زر '📢 نشر التقرير' للمتابعة."
                    )
            except:
                pass

        try:
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ خطأ في get_confirm_state: {e}", exc_info=True)
            # إرجاع state افتراضي
            context.user_data['_conversation_state'] = NEW_CONSULT_CONFIRM
            return NEW_CONSULT_CONFIRM

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ خطأ في handle_simple_translator_choice: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ حدث خطأ في معالجة الاختيار")
        except:
            pass
        return
