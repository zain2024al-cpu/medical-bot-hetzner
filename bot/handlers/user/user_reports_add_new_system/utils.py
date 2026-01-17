# =============================
# utils.py
# دوال مساعدة عامة
# =============================

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import states for _nav_buttons
from .states import (
    STATE_SELECT_DATE, STATE_SELECT_DATE_TIME, STATE_SELECT_PATIENT,
    STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT, STATE_SELECT_SUBDEPARTMENT,
    STATE_SELECT_DOCTOR, STATE_SELECT_ACTION_TYPE
)

# ثوابت
MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

WEEKDAYS_AR = ["س", "أ", "ث", "ر", "خ", "ج", "س"]

# Step Indexing System
FLOW_QUESTIONS = {
    "new_consult": [
        {
            "question": "شكوى المريض",
            "field": "complaint",
            "prompt": "يرجى إدخال شكوى المريض:",
            "validation": {"min_length": 3, "max_length": 500}
        },
        {
            "question": "قرار الطبيب",
            "field": "decision",
            "prompt": "يرجى إدخال قرار الطبيب:",
            "validation": {"min_length": 3, "max_length": 500}
        },
        {
            "question": "الفحوصات المطلوبة",
            "field": "tests",
            "prompt": "يرجى إدخال الفحوصات المطلوبة قبل العملية:\n(أو اكتب 'لا يوجد' إذا لم تكن هناك فحوصات)",
            "validation": {"min_length": 3, "max_length": 500, "allow_empty": True}
        }
    ],
}

def get_step_back_button():
    """إنشاء زر الرجوع للخطوة السابقة"""
    return InlineKeyboardButton("🔙 تراجع عن هذا السؤال", callback_data="step:back")

def get_current_step(context: ContextTypes.DEFAULT_TYPE):
    """الحصول على الخطوة الحالية من user_data"""
    return context.user_data.get("current_step", 0)

def set_current_step(context: ContextTypes.DEFAULT_TYPE, step: int):
    """تعيين الخطوة الحالية"""
    context.user_data["current_step"] = step

def get_current_flow(context: ContextTypes.DEFAULT_TYPE):
    """الحصول على نوع الإجراء الحالي"""
    return context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")

def get_questions_for_flow(flow_type: str):
    """الحصول على قائمة الأسئلة لنوع إجراء معين"""
    return FLOW_QUESTIONS.get(flow_type, FLOW_QUESTIONS["new_consult"])

def get_current_question(context: ContextTypes.DEFAULT_TYPE):
    """الحصول على السؤال الحالي"""
    flow_type = get_current_flow(context)
    questions = get_questions_for_flow(flow_type)
    current_step = get_current_step(context)
    
    if 0 <= current_step < len(questions):
        return questions[current_step]
    return None

def get_previous_question(context: ContextTypes.DEFAULT_TYPE):
    """الحصول على السؤال السابق"""
    flow_type = get_current_flow(context)
    questions = get_questions_for_flow(flow_type)
    current_step = get_current_step(context)
    
    if current_step > 0:
        return questions[current_step - 1]
    return None


def _chunked(seq, size):
    """تقسيم القائمة إلى أجزاء"""
    return [seq[i: i + size] for i in range(0, len(seq), size)]


def _cancel_kb():
    """إنشاء زر الإلغاء"""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء العملية", callback_data="nav:cancel")]])


# ✅ تم نقل format_time_12h إلى flows/shared.py - النسخة الموحدة تدعم datetime و strings
# ⚠️ لا نستورد من flows/shared.py هنا لتجنب circular import
# flows/shared.py يستورد من utils.py، لذلك لا يمكننا استيراد منه هنا
# الدالة موجودة محلياً كـ fallback
try:
    # محاولة الاستيراد فقط إذا لم يكن هناك circular import
    import sys
    if 'bot.handlers.user.user_reports_add_new_system.flows.shared' not in sys.modules:
        from .flows.shared import format_time_12h
    else:
        raise ImportError("Circular import detected")
except (ImportError, AttributeError):
    # fallback للتوافق
    def format_time_12h(dt):
        """تحويل الوقت إلى صيغة 12 ساعة مع التمييز بين صباح/مساء"""
        if hasattr(dt, 'hour'):
            hour = dt.hour
            minute = dt.minute
        else:
            return str(dt)
        if hour == 0:
            return f"12:{minute:02d} صباحاً"
        elif hour < 12:
            return f"{hour}:{minute:02d} صباحاً"
        else:
            return f"{hour-12}:{minute:02d} مساءً"


# ✅ تم نقل _build_hour_keyboard و _build_minute_keyboard إلى flows/shared.py
# ⚠️ لا نستورد من flows/shared.py هنا لتجنب circular import
# flows/shared.py يستورد من utils.py، لذلك لا يمكننا استيراد منه هنا
# الدوال موجودة محلياً كـ fallback
try:
    # محاولة الاستيراد فقط إذا لم يكن هناك circular import
    import sys
    if 'bot.handlers.user.user_reports_add_new_system.flows.shared' not in sys.modules:
        from .flows.shared import _build_hour_keyboard, _build_minute_keyboard, _chunked
    else:
        raise ImportError("Circular import detected")
except (ImportError, AttributeError):
    # fallback للتوافق
    def _chunked(lst, n):
        """تقسيم قائمة إلى أجزاء بحجم n"""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    
    def _build_hour_keyboard():
        """بناء لوحة اختيار الساعات بصيغة 12 ساعة"""
        keyboard = []
        common_morning = [
            ("🌅 8:00 صباحاً", "08"), ("🌅 9:00 صباحاً", "09"),
            ("🌅 10:00 صباحاً", "10"), ("🌅 11:00 صباحاً", "11"),
        ]
        keyboard.append([InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in common_morning])
        keyboard.append([InlineKeyboardButton("☀️ 12:00 ظهراً", callback_data="time_hour:12")])
        common_afternoon = [
            ("🌆 1:00 مساءً", "13"), ("🌆 2:00 مساءً", "14"),
            ("🌆 3:00 مساءً", "15"), ("🌆 4:00 مساءً", "16"),
        ]
        keyboard.append([InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in common_afternoon])
        common_evening = [
            ("🌃 5:00 مساءً", "17"), ("🌃 6:00 مساءً", "18"),
            ("🌃 7:00 مساءً", "19"), ("🌃 8:00 مساءً", "20"),
        ]
        keyboard.append([InlineKeyboardButton(label, callback_data=f"time_hour:{val}") for label, val in common_evening])
        keyboard.append([InlineKeyboardButton("🕐 أوقات أخرى", callback_data="time_hour:more")])
        keyboard.append([InlineKeyboardButton("⏭️ بدون وقت", callback_data="time_skip")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"), InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
        return InlineKeyboardMarkup(keyboard)

    def _build_minute_keyboard(hour: str):
        """بناء لوحة اختيار الدقائق مع عرض الوقت بصيغة 12 ساعة"""
        minute_options = ["00", "15", "30", "45"]
        keyboard = []
        hour_int = int(hour)
        if hour_int == 0:
            hour_display, period = "12", "صباحاً"
        elif hour_int < 12:
            hour_display, period = str(hour_int), "صباحاً"
        elif hour_int == 12:
            hour_display, period = "12", "ظهراً"
        else:
            hour_display, period = str(hour_int - 12), "مساءً"
        for chunk in _chunked(minute_options, 2):
            row = [InlineKeyboardButton(f"{hour_display}:{m} {period}", callback_data=f"time_minute:{hour}:{m}") for m in chunk]
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⏭️ بدون وقت", callback_data="time_skip")])
        keyboard.append([InlineKeyboardButton("🔙 تغيير الساعة", callback_data="time_back_hour"), InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
        return InlineKeyboardMarkup(keyboard)


def get_back_button(previous_state_name):
    """إنشاء زر الرجوع بناءً على اسم الحالة السابقة"""
    return [InlineKeyboardButton("🔙 رجوع", callback_data=f"go_to_{previous_state_name}")]


def _nav_buttons(show_back=True, previous_state_name=None, current_state=None, context=None):
    """
    أزرار التنقل الأساسية - نظام ذكي للرجوع/التعديل
    
    Args:
        show_back: إذا True، يعرض زر الرجوع أو التعديل
        previous_state_name: اسم الحالة السابقة (مثل "hospital_selection")
        current_state: الحالة الحالية (للتحقق من نوع الزر)
        context: context للتحقق من الحالة الحالية إذا لم يتم تمرير current_state
    """
    buttons = []

    if show_back:
        # تحديد نوع الزر حسب الحالة الحالية
        # إذا لم يتم تمرير current_state، نحاول استخراجه من context
        if current_state is None and context:
            current_state = context.user_data.get('_conversation_state')
        
        # الحالات التي تستخدم زر الرجوع العادي (من المستشفى إلى الطبيب)
        states_with_back_button = [
            STATE_SELECT_DATE,
            STATE_SELECT_DATE_TIME,
            STATE_SELECT_PATIENT,
            STATE_SELECT_HOSPITAL,
            STATE_SELECT_DEPARTMENT,
            STATE_SELECT_SUBDEPARTMENT,
            STATE_SELECT_DOCTOR,
        ]
        
        # التحقق من الحالة الحالية
        use_edit_button = True  # افتراضي: زر التعديل
        
        if current_state is not None:
            # إذا كانت الحالة من المستشفى إلى الطبيب، استخدم زر الرجوع العادي
            if current_state in states_with_back_button:
                use_edit_button = False
        
        if use_edit_button:
            # ✅ استخدام زر الرجوع العادي (نفس منطق بقية المسارات)
            buttons.append([InlineKeyboardButton(
                "🔙 رجوع", callback_data="nav:back")])
        else:
            # ✅ استخدام زر الرجوع العادي (من المستشفى إلى الطبيب)
            if previous_state_name:
                buttons.append(get_back_button(previous_state_name))
            else:
                buttons.append([InlineKeyboardButton(
                    "🔙 رجوع", callback_data="nav:back")])

    buttons.append([InlineKeyboardButton(
        "❌ إلغاء العملية", callback_data="nav:cancel")])

    return InlineKeyboardMarkup(buttons)


# =============================
# تصدير الدوال
# =============================
__all__ = [
    '_chunked',
    '_cancel_kb',
    '_nav_buttons',
    '_build_hour_keyboard',
    '_build_minute_keyboard',
    'format_time_12h',
    'MONTH_NAMES_AR',
    'WEEKDAYS_AR',
    'FLOW_QUESTIONS',
    'get_step_question',
]

