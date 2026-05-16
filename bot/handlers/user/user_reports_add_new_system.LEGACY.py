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

# استيراد handle_final_confirm و show_final_summary من flows/shared.py
# Two-step import used because relative '.' resolves differently when this file is
# loaded via importlib as user_reports_add_new_system_original.
try:
    import bot.handlers.user.user_reports_add_new_system.flows.shared as _shared_mod
    handle_final_confirm = _shared_mod.handle_final_confirm
    show_final_summary = _shared_mod.show_final_summary
    get_confirm_state = _shared_mod.get_confirm_state
except (ImportError, AttributeError) as _e:
    logger.warning(f"⚠️ Cannot import from flows/shared.py: {_e}")
    handle_final_confirm = None
    show_final_summary = None
    get_confirm_state = None
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

# === State Data Managers — imported from package managers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.managers import (
        PatientDataManager,
        DoctorDataManager,
        DepartmentDataManager,
    )
except ImportError as _e:
    logger.error(f"Cannot import Data Managers from package: {_e}")

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



def _nav_buttons(show_back=True):
    """أزرار التنقل الأساسية"""
    buttons = []

    if show_back:
        buttons.append([InlineKeyboardButton(
            "🔙 رجوع", callback_data="nav:back")])

    buttons.append([InlineKeyboardButton(
        "❌ إلغاء العملية", callback_data="nav:cancel")])

    return InlineKeyboardMarkup(buttons)

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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'NEW_CONSULT_COMPLAINT': STATE_SELECT_ACTION_TYPE,
                'NEW_CONSULT_DIAGNOSIS': 'NEW_CONSULT_COMPLAINT',
                'NEW_CONSULT_DECISION': 'NEW_CONSULT_DIAGNOSIS',
                'NEW_CONSULT_TESTS': 'NEW_CONSULT_DECISION',
                'NEW_CONSULT_FOLLOWUP_DATE': 'NEW_CONSULT_TESTS',
                'NEW_CONSULT_FOLLOWUP_REASON': 'NEW_CONSULT_FOLLOWUP_DATE',
                'MEDICAL_REPORT_ASK': 'NEW_CONSULT_FOLLOWUP_REASON',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'SURGERY_CONSULT_DIAGNOSIS': STATE_SELECT_ACTION_TYPE,
                'SURGERY_CONSULT_DECISION': 'SURGERY_CONSULT_DIAGNOSIS',
                'SURGERY_CONSULT_OPERATION_NAME': 'SURGERY_CONSULT_DECISION',
                'SURGERY_CONSULT_SUCCESS_RATE': 'SURGERY_CONSULT_OPERATION_NAME',
                'SURGERY_CONSULT_TESTS': 'SURGERY_CONSULT_SUCCESS_RATE',
                'SURGERY_CONSULT_FOLLOWUP_DATE': 'SURGERY_CONSULT_TESTS',
                'SURGERY_CONSULT_FOLLOWUP_REASON': 'SURGERY_CONSULT_FOLLOWUP_DATE',
                'MEDICAL_REPORT_ASK': 'SURGERY_CONSULT_FOLLOWUP_REASON',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'FINAL_CONSULT_DIAGNOSIS': STATE_SELECT_ACTION_TYPE,
                'FINAL_CONSULT_DECISION': 'FINAL_CONSULT_DIAGNOSIS',
                'FINAL_CONSULT_RECOMMENDATIONS': 'FINAL_CONSULT_DECISION',
                'MEDICAL_REPORT_ASK': 'FINAL_CONSULT_RECOMMENDATIONS',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
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
                'MEDICAL_REPORT_ASK': 'EMERGENCY_REASON',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,   # ✅ رجوع لنوع الإجراء (تدفق طبيعي)
                FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,
                FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,
                FOLLOWUP_ROOM_FLOOR: FOLLOWUP_DECISION,
                FOLLOWUP_DATE_TIME: FOLLOWUP_ROOM_FLOOR,
                FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,
                'MEDICAL_REPORT_ASK': FOLLOWUP_REASON,
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                FOLLOWUP_COMPLAINT: STATE_SELECT_ACTION_TYPE,         # خطوة واحدة: شكوى ← نوع الإجراء
                FOLLOWUP_DIAGNOSIS: FOLLOWUP_COMPLAINT,               # خطوة واحدة: تشخيص ← شكوى المريض
                FOLLOWUP_DECISION: FOLLOWUP_DIAGNOSIS,                # خطوة واحدة: قرار ← تشخيص
                # تخطي رقم الغرفة
                FOLLOWUP_DATE_TIME: FOLLOWUP_DECISION,                # خطوة واحدة: تاريخ ← قرار
                FOLLOWUP_REASON: FOLLOWUP_DATE_TIME,                  # خطوة واحدة: سبب ← تاريخ
                'MEDICAL_REPORT_ASK': FOLLOWUP_REASON,
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'OPERATION_DETAILS_AR': STATE_SELECT_ACTION_TYPE,
                'OPERATION_NAME_EN': 'OPERATION_DETAILS_AR',
                'OPERATION_NOTES': 'OPERATION_NAME_EN',
                'OPERATION_FOLLOWUP_DATE': 'OPERATION_NOTES',
                'OPERATION_FOLLOWUP_REASON': 'OPERATION_FOLLOWUP_DATE',
                'MEDICAL_REPORT_ASK': 'OPERATION_FOLLOWUP_REASON',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'REHAB_TYPE': STATE_SELECT_ACTION_TYPE,
                'PHYSICAL_THERAPY_DETAILS': 'REHAB_TYPE',
                'PHYSICAL_THERAPY_DEVICES': 'PHYSICAL_THERAPY_DETAILS',
                'PHYSICAL_THERAPY_NOTES': 'PHYSICAL_THERAPY_DEVICES',
                'PHYSICAL_THERAPY_FOLLOWUP_DATE': 'PHYSICAL_THERAPY_NOTES',
                'PHYSICAL_THERAPY_FOLLOWUP_REASON': 'PHYSICAL_THERAPY_FOLLOWUP_DATE',
                'MEDICAL_REPORT_ASK': 'PHYSICAL_THERAPY_FOLLOWUP_REASON',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'RADIOLOGY_TYPE': STATE_SELECT_ACTION_TYPE,
                'RADIOLOGY_DELIVERY_DATE': 'RADIOLOGY_TYPE',
                'MEDICAL_REPORT_ASK': 'RADIOLOGY_DELIVERY_DATE',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
                'ADMISSION_REASON': STATE_SELECT_ACTION_TYPE,
                'ADMISSION_ROOM': 'ADMISSION_REASON',
                'ADMISSION_NOTES': 'ADMISSION_ROOM',
                'ADMISSION_FOLLOWUP_DATE': 'ADMISSION_NOTES',
                'ADMISSION_FOLLOWUP_REASON': 'ADMISSION_FOLLOWUP_DATE',
                'MEDICAL_REPORT_ASK': 'ADMISSION_FOLLOWUP_REASON',
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
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
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
                'MEDICAL_REPORT_ASK': 'DISCHARGE_FOLLOWUP_REASON',
                'DISCHARGE_TRANSLATOR': 'DISCHARGE_FOLLOWUP_REASON',
                'DISCHARGE_CONFIRM': 'DISCHARGE_TRANSLATOR',
            },

            # تدفق تأجيل موعد
            # ملاحظة: app_reschedule لا يمر بـ medrep gate (موجود في flows_without_gate)
            'app_reschedule': {
                STATE_SELECT_DATE: None,
                STATE_SELECT_PATIENT: STATE_SELECT_DATE,
                STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
                STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
                STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
                STATE_SELECT_DOCTOR: STATE_SELECT_DEPARTMENT,
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

        # medrep branch states always go back to the gate, regardless of flow
        if current_step in ("MEDICAL_REPORT_IMAGE", "MEDICAL_REPORT_NO_REASON"):
            logger.info(f"✅ medrep branch Back: {current_step} → MEDICAL_REPORT_ASK")
            return "MEDICAL_REPORT_ASK"

        if flow_type not in self.step_flows:
            logger.warning(f"⚠️ Flow type '{flow_type}' not found in step_flows")
            return STATE_SELECT_ACTION_TYPE

        flow_map = self.step_flows[flow_type]
        logger.info(f"🗺️ Using flow_map for '{flow_type}': {flow_map}")

        # ── Collision guard ─────────────────────────────────────────────────
        # STATE_SELECT_ACTION_TYPE == NEW_CONSULT_COMPLAINT == R_ACTION_TYPE == 7.
        # All flow maps include an integer key 7 meaning STATE_SELECT_ACTION_TYPE
        # (its predecessor is STATE_SELECT_DOCTOR).  But when the user is actually
        # at the *first step of a post-action flow* (e.g. NEW_CONSULT_COMPLAINT),
        # current_step is also 7 and the direct int lookup would incorrectly return
        # STATE_SELECT_DOCTOR instead of STATE_SELECT_ACTION_TYPE.
        #
        # We distinguish the two meanings by checking whether a flow has already
        # been entered (current_flow is set in report_tmp).  If it has, the user
        # is at the flow's first step and Back should show the action-type menu.
        if (isinstance(current_step, int)
                and current_step == STATE_SELECT_ACTION_TYPE
                and flow_type not in (None, 'new_consult')  # new_consult first step IS 7
                and context is not None
                and context.user_data.get('report_tmp', {}).get('current_flow')):
            logger.info(f"✅ Collision guard: int 7 inside active flow '{flow_type}' → STATE_SELECT_ACTION_TYPE")
            return STATE_SELECT_ACTION_TYPE

        # For new_consult the first step (NEW_CONSULT_COMPLAINT=7) also collides.
        # Detect it via the string key path instead of the int key path.
        _flow_first_step_strings = {
            'new_consult':      'NEW_CONSULT_COMPLAINT',
            'surgery_consult':  'SURGERY_CONSULT_DIAGNOSIS',
            'final_consult':    'FINAL_CONSULT_DIAGNOSIS',
            'emergency':        'EMERGENCY_COMPLAINT',
            'followup':         None,   # FOLLOWUP_COMPLAINT int key is unique (16)
            'periodic_followup': None,
            'operation':        'OPERATION_DETAILS_AR',
            'rehab':            'REHAB_TYPE',
            'radiology':        'RADIOLOGY_TYPE',
            'admission':        'ADMISSION_REASON',
            'discharge':        'DISCHARGE_TYPE',
            'app_reschedule':   'APP_RESCHEDULE_REASON',
        }
        first_step_str = _flow_first_step_strings.get(flow_type)
        if (first_step_str
                and isinstance(current_step, int)
                and context is not None
                and context.user_data.get('report_tmp', {}).get('current_flow') == flow_type):
            # Resolve the first-step string's integer value
            import importlib
            try:
                _states_mod = importlib.import_module('bot.handlers.user.user_reports_add_new_system.states')
                first_step_int = getattr(_states_mod, first_step_str, None)
            except Exception:
                first_step_int = None
            if first_step_int is not None and current_step == first_step_int:
                logger.info(f"✅ First-step guard: int {current_step} == {first_step_str} in '{flow_type}' → STATE_SELECT_ACTION_TYPE")
                return STATE_SELECT_ACTION_TYPE
        # ── End collision guard ─────────────────────────────────────────────

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
            # ── medrep gate (string-keyed, shared across flows) ──────────────
            # MEDICAL_REPORT_ASK is a string key — not a numeric PTB state.
            # It maps to itself so that the elif branch at line ~1401 can find it
            # in flow_map when current_step is the string "MEDICAL_REPORT_ASK".
            'MEDICAL_REPORT_ASK': 'MEDICAL_REPORT_ASK',
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
        # flow_map keys are integer constants (FOLLOWUP_REASON=17 etc.) — look up directly
        if flow_type in ['followup', 'periodic_followup'] and isinstance(current_step, int):
            if current_step in flow_map:
                prev_step = flow_map[current_step]
                logger.debug(f"✅ [FOLLOWUP] Direct int lookup: {current_step} -> {prev_step} (type: {type(prev_step).__name__})")
                if isinstance(prev_step, str):
                    if prev_step in state_name_to_value:
                        result = state_name_to_value[prev_step]
                        logger.debug(f"✅ [FOLLOWUP] Converted '{prev_step}' to int: {result}")
                        return result
                    else:
                        logger.warning(f"⚠️ [FOLLOWUP] '{prev_step}' not found in state_name_to_value")
                        return prev_step
                elif isinstance(prev_step, int):
                    logger.debug(f"✅ [FOLLOWUP] prev_step is already int: {prev_step}")
                    return prev_step
                else:
                    logger.warning(f"⚠️ [FOLLOWUP] prev_step is None for current_step={current_step}")
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

# === stub: SmartStateRenderer delegated to smart_state_renderer.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.smart_state_renderer import SmartStateRenderer
except ImportError as _e:
    logger.error(f"Cannot import SmartStateRenderer from package: {_e}")
# === stub: execute_smart_state_action delegated to execute_smart_state_action.py ===
try:
    import bot.handlers.user.user_reports_add_new_system.execute_smart_state_action as _essa_mod
    execute_smart_state_action = _essa_mod.execute_smart_state_action
except (ImportError, AttributeError) as _e:
    logger.error(f"Cannot import execute_smart_state_action from package: {_e}")

async def handle_save_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wrapper for save: callback — re-shows the summary screen."""
    from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary, get_confirm_state
    query = update.callback_query
    await query.answer()
    if query.data.startswith("save:"):
        flow_type = query.data.split(":")[1]
        await show_final_summary(query.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    return ConversationHandler.END


async def handle_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار حقل للتعديل قبل النشر — يعرض طلب إدخال القيمة الجديدة."""
    from bot.handlers.user.user_reports_add_new_system.flows.shared import get_confirm_state
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        flow_type = parts[1]
        field_key = parts[2]
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        context.user_data["editing_field"] = field_key
        confirm_state = get_confirm_state(flow_type)
        current_value = context.user_data.get("report_tmp", {}).get(field_key, "غير محدد")
        if current_value and len(str(current_value)) > 200:
            current_value = str(current_value)[:200] + "..."
        await query.edit_message_text(
            f"✏️ **تعديل الحقل**\n\n"
            f"**القيمة الحالية:**\n{current_value}\n\n"
            f"📝 أرسل القيمة الجديدة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
            ]),
            parse_mode="Markdown"
        )
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    except Exception as e:
        logger.error(f"handle_edit_field_selection error: {e}", exc_info=True)
        return ConversationHandler.END


async def handle_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال القيمة الجديدة بعد اختيار حقل للتعديل."""
    from bot.handlers.user.user_reports_add_new_system.flows.shared import show_final_summary, get_confirm_state
    try:
        text = update.message.text.strip() if update.message else ""
        field_key = context.user_data.get("edit_field_key") or context.user_data.get("editing_field")
        flow_type = (context.user_data.get("edit_flow_type")
                     or context.user_data.get("draft_flow_type")
                     or context.user_data.get("report_tmp", {}).get("current_flow"))
        if not field_key or not flow_type:
            return ConversationHandler.END
        data = context.user_data.setdefault("report_tmp", {})
        if field_key == "complaint":
            data["complaint_text"] = text
        elif field_key == "decision":
            data["doctor_decision"] = text
        data[field_key] = text
        context.user_data.pop("edit_field_key", None)
        context.user_data.pop("edit_flow_type", None)
        context.user_data.pop("editing_field", None)
        await show_final_summary(update.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    except Exception as e:
        logger.error(f"handle_edit_field_input error: {e}", exc_info=True)
        return ConversationHandler.END


async def debug_all_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch-all fallback handler — logs unmatched callbacks for debugging."""
    query = update.callback_query
    if not query:
        return None
    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    logger.warning(f"debug_all_callbacks: unmatched callback data={query.data!r} state={current_state}")
    if query.data and query.data.startswith('action_idx:'):
        try:
            return await handle_action_type_choice(update, context)
        except Exception as e:
            logger.error(f"debug_all_callbacks fallthrough error: {e}")
    return None


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
        report_tmp = context.user_data.get('report_tmp', {})
        flow_type = report_tmp.get('current_flow', 'new_consult')

        # Pop the step the user was just on from the navigation stack.
        # The stack is filled by _tracked() wrappers in conversation_handler.py —
        # every registered handler pushes its own state before executing, so the
        # stack always contains the exact sequence of states the user visited.
        stack = context.user_data.get('_nav_stack', [])
        logger.info(f"🔙 BACK: stack before pop = {stack}, flow = {flow_type}")

        previous_step = None
        if stack:
            previous_step = stack.pop()
            context.user_data['_nav_stack'] = stack
            logger.info(f"🔙 BACK: popped {previous_step}, stack now = {stack}")
        else:
            # Stack is empty — fall back to flow-map logic for robustness
            logger.warning("🔙 BACK: nav stack empty, using flow-map fallback")
            # Read PTB real state as current position
            current_state = None
            try:
                key = (update.effective_chat.id, update.effective_user.id)
                for handler_group in context.application.handlers.values():
                    for handler in handler_group:
                        if isinstance(handler, ConversationHandler):
                            current_state = handler._conversations.get(key)
                            break
                    if current_state is not None:
                        break
            except Exception:
                current_state = context.user_data.get('_conversation_state')
            if current_state is not None:
                previous_step = smart_nav_manager.get_previous_step(flow_type, current_state, context)

        if previous_step is None:
            # Stack empty and no flow-map result — return to action type menu
            # (user is at the first step of a flow, one step before action type selection)
            logger.info("🔙 BACK: no previous step — returning to action type menu")
            try:
                from bot.handlers.user.user_reports_add_new_system.action_type_handlers import show_action_type_menu
                context.user_data['_conversation_state'] = STATE_SELECT_ACTION_TYPE
                msg = query.message or (update.effective_message)
                await show_action_type_menu(msg, context, query=query if query.message else None)
            except Exception as e:
                logger.error(f"Error showing action type menu: {e}", exc_info=True)
            return STATE_SELECT_ACTION_TYPE

        context.user_data['_conversation_state'] = previous_step
        logger.info(f"🔙 BACK: rendering previous_step = {previous_step}")

        try:
            await execute_smart_state_action(previous_step, flow_type, update, context)
        except Exception as e:
            logger.error(f"Error in execute_smart_state_action: {e}", exc_info=True)
            try:
                await query.edit_message_text(
                    "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
                    ]])
                )
            except Exception:
                pass
            return previous_step

        return previous_step

    except Exception as e:
        logger.error(f"❌ Error in handle_smart_back_navigation: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
                ]])
            )
        except Exception:
            pass
        return ConversationHandler.END

# الدوال القديمة تم استبدالها بـ Smart Navigation System

# === stubs: date_time handlers delegated to date_time_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.date_time_handlers import (
        render_date_selection,
        handle_calendar_cancel,
        handle_date_choice,
        handle_main_calendar_nav,
        handle_main_calendar_day,
        handle_date_time_hour,
        handle_date_time_minute,
        handle_date_time_skip,
    )
except ImportError as _e:
    logger.error(f"Cannot import date_time_handlers: {_e}")
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


async def render_patient_selection(message, context, page=0, search_query="", query=None):
    """عرض شاشة اختيار المريض - rendering فقط مع قائمة أزرار"""
    text, keyboard, _ = _build_patients_keyboard(page, search_query, context)
    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return
        except Exception:
            pass
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def render_hospital_selection(message, context, query=None,
                                    page: int = 0, search: str = ""):
    """Forward to modular hospital selector authority."""
    try:
        from bot.handlers.user.user_reports_add_new_system.hospital_handlers import (
            render_hospital_selection as _modular_render
        )
        await _modular_render(message, context, query=query, page=page, search=search)
    except Exception:
        # fallback: render at page 0
        text, keyboard, _s = _build_hospitals_keyboard(page, search, context)
        context.user_data.setdefault("report_tmp", {})["hospitals_search"] = _s
        if query:
            try:
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
                return
            except Exception:
                pass
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def render_department_selection(message, context, query=None,
                                      page: int = 0, search: str = ""):
    """Forward to modular department selector authority."""
    try:
        from bot.handlers.user.user_reports_add_new_system.department_handlers import (
            render_department_selection as _modular_render
        )
        await _modular_render(message, context, query=query, page=page, search=search)
    except Exception:
        text, keyboard, _s = _build_departments_keyboard(page, search, context)
        context.user_data.setdefault("report_tmp", {})["departments_search"] = _s
        if query:
            try:
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
                return
            except Exception:
                pass
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
    
    # حفظ قائمة الأطباء في report_tmp (IDX snapshot doctrine)
    context.user_data.setdefault("report_tmp", {})["_doctors_list"] = doctors
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


async def render_doctor_selection(message, context, page=0, query=None):
    """Forward to modular doctor selector authority."""
    try:
        from bot.handlers.user.user_reports_add_new_system.doctor_handlers import (
            render_doctor_selection as _modular_render,
        )
        await _modular_render(message, context, query=query)
        return
    except Exception:
        pass

    import logging
    logger = logging.getLogger(__name__)
    # fallback inline
    DoctorDataManager.clear_doctor_data(context)
    report_tmp = context.user_data.get("report_tmp", {})
    hospital_name = report_tmp.get("hospital_name", "")
    department_name = report_tmp.get("department_name", "")
    doctors = _get_doctors_from_database(hospital_name, department_name)
    keyboard, total_doctors = _build_doctors_keyboard(page, doctors, context)
    # _build_doctors_keyboard stores a dict-list in _doctors_list.  Overwrite with a
    # string-list so the modular handle_doctor_selection resolver (which expects strings)
    # works correctly regardless of which render path was used.
    context.user_data.setdefault("report_tmp", {})["_doctors_list"] = [
        d["name"] for d in doctors if d.get("name")
    ]
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
        if query:
            try:
                await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
                return
            except Exception:
                pass
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة اختيار الطبيب: {e}", exc_info=True)
        try:
            await message.reply_text(text.replace("**", ""), reply_markup=keyboard)
        except Exception as e2:
            logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")

# =============================
# الخطوات الأساسية المشتركة
# =============================


async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تفويض لـ start_report الموحد في الحزمة"""
    try:
        from bot.handlers.user.user_reports_add_new_system.date_time_handlers import (
            start_report as _pkg_start_report
        )
        return await _pkg_start_report(update, context)
    except Exception as e:
        logger.error(f"Error delegating start_report to package: {e}", exc_info=True)
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if message:
            try:
                await message.reply_text("❌ حدث خطأ في بدء العملية، يرجى المحاولة مرة أخرى.")
            except:
                pass
        return ConversationHandler.END


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
# === stubs: handle_patient delegated to patient_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.patient_handlers import (
        handle_patient,
    )
except ImportError as _e:
    logger.error(f"Cannot import handle_patient: {_e}")
# === stubs: hospital handlers delegated to hospital_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.hospital_handlers import (
        show_hospitals_menu,
        handle_hospital_selection,
        handle_hospital_page,
        handle_hospital_search,
    )
except ImportError as _e:
    logger.error(f"Cannot import hospital_handlers: {_e}")
# === stubs: department handlers delegated to department_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.department_handlers import (
        show_departments_menu,
        handle_department_selection,
        handle_department_page,
        handle_department_search,
        show_subdepartment_options,
        handle_subdepartment_choice,
        handle_subdepartment_page,
    )
except ImportError as _e:
    logger.error(f"Cannot import department_handlers: {_e}")
# === stubs: doctor display handlers delegated to doctor_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.doctor_handlers import (
        show_doctor_selection,
        show_doctor_input,
    )
except ImportError as _e:
    logger.error(f"Cannot import doctor_handlers top: {_e}")
async def handle_doctor_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التنقل بين صفحات الأطباء"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = int(query.data.split(":")[1])
    
    # جلب قائمة الأطباء المحفوظة
    doctors = context.user_data.get("report_tmp", {}).get('_doctors_list', [])

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
    doctors = context.user_data.get("report_tmp", {}).get('_doctors_list', [])
    
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


# === stubs: doctor selection handlers delegated to doctor_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.doctor_handlers import (
        handle_doctor_selection,
        handle_doctor,
    )
except ImportError as _e:
    logger.error(f"Cannot import doctor_handlers bottom: {_e}")
# === stubs: action_type handlers delegated to action_type_handlers.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.action_type_handlers import (
        show_action_type_menu,
        handle_action_page,
        handle_noop,
        handle_stale_callback,
        handle_action_type_choice,
    )
except ImportError as _e:
    logger.error(f"Cannot import action_type_handlers: {_e}")
# === stubs: new_consult delegated to flows/new_consult.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.new_consult import (
        start_new_consultation_flow,
        handle_new_consult_complaint,
        handle_new_consult_diagnosis,
        handle_new_consult_decision,
        handle_new_consult_tests,
        handle_new_consult_followup_date_skip,
        handle_new_consult_followup_date_text as handle_followup_date_text_input,
        handle_new_consult_followup_calendar_nav,
        handle_new_consult_followup_calendar_day,
        handle_new_consult_followup_time_hour,
        handle_new_consult_followup_time_minute,
        handle_new_consult_followup_time_skip,
        handle_new_consult_followup_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import new_consult flows: {_e}")

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

# === stubs: emergency delegated to flows/emergency.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.emergency import (
        start_emergency_flow,
        handle_emergency_complaint,
        handle_emergency_diagnosis,
        handle_emergency_decision,
        handle_emergency_status_choice,
        handle_emergency_status_text,
        handle_emergency_admission_notes,
        handle_emergency_operation_details,
        handle_emergency_admission_type_choice,
        handle_emergency_room_number,
        handle_emergency_date_time_text,
        handle_emergency_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import emergency flows: {_e}")

# === stubs: admission delegated to flows/admission.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.admission import (
        start_admission_flow,
        handle_admission_reason,
        handle_admission_room,
        handle_admission_notes,
        handle_admission_followup_date_text,
        handle_admission_followup_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import admission flows: {_e}")

# === stubs: surgery_consult delegated to flows/surgery_consult.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.surgery_consult import (
        start_surgery_consult_flow,
        handle_surgery_consult_diagnosis,
        handle_surgery_consult_decision,
        handle_surgery_consult_name_en,
        handle_surgery_consult_success_rate,
        handle_surgery_consult_benefit_rate,
        handle_surgery_consult_tests,
        handle_surgery_consult_followup_date_text,
        handle_surgery_consult_followup_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import surgery_consult flows: {_e}")

# === stubs: operation delegated to flows/operation.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.operation import (
        start_operation_flow,
        handle_operation_details_ar,
        handle_operation_name_en,
        handle_operation_notes,
        handle_operation_followup_date_text,
        handle_operation_followup_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import operation flows: {_e}")

# === stubs: final_consult delegated to flows/final_consult.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.final_consult import (
        start_final_consult_flow,
        handle_final_consult_diagnosis,
        handle_final_consult_decision,
        handle_final_consult_recommendations,
    )
except ImportError as _e:
    logger.error(f"Cannot import final_consult flows: {_e}")

# === stubs: discharge delegated to flows/discharge.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.discharge import (
        start_discharge_flow,
        handle_discharge_type,
        handle_discharge_admission_summary,
        handle_discharge_operation_details,
        handle_discharge_operation_name_en,
        handle_discharge_followup_date_text,
        handle_discharge_followup_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import discharge flows: {_e}")

# === stubs: rehab delegated to flows/rehab.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.rehab import (
        start_rehab_flow,
        handle_rehab_type,
        handle_physical_therapy_details,
        handle_physical_therapy_followup_date_choice,
        handle_physical_therapy_followup_date_text,
        handle_physical_therapy_followup_reason,
        handle_device_name_details,
        handle_device_followup_date_text,
        handle_device_followup_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import rehab flows: {_e}")

# === stubs: radiology delegated to flows/radiology.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.radiology import (
        start_radiology_flow,
        handle_radiology_type,
        handle_radiology_calendar_nav,
        handle_radiology_calendar_day,
        _render_radiology_calendar,
        _build_radiology_calendar_markup,
    )
except ImportError as _e:
    logger.error(f"Cannot import radiology flows: {_e}")

# === stubs: app_reschedule delegated to flows/app_reschedule.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.app_reschedule import (
        start_appointment_reschedule_flow,
        handle_app_reschedule_reason,
        _show_reschedule_calendar,
        handle_reschedule_calendar_nav,
        handle_reschedule_calendar_day,
        handle_app_reschedule_return_reason,
    )
except ImportError as _e:
    logger.error(f"Cannot import app_reschedule flows: {_e}")

# === stubs: translator handlers delegated to flows/shared.py ===
try:
    from bot.handlers.user.user_reports_add_new_system.flows.shared import (
        ask_translator_name,
        handle_translator_choice,
        handle_translator_text,
    )
except ImportError as _e:
    logger.error(f"Cannot import translator handlers from flows/shared: {_e}")

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
    """تفويض للقائمة الموحدة في shared.py — المصدر الوحيد للحقيقة."""
    try:
        from bot.handlers.user.user_reports_add_new_system.flows.shared import (
            get_editable_fields_by_flow_type as _shared_get,
        )
        return _shared_get(flow_type)
    except Exception:
        return []

try:
    from bot.handlers.user.user_reports_add_new_system.edit_handlers.draft.handlers import (
        show_edit_fields_menu,
        handle_edit_before_save,
        handle_edit_draft_report,
        show_draft_edit_fields,
        handle_edit_draft_field,
        handle_draft_field_input,
        handle_finish_edit_draft,
        handle_back_to_edit_fields,
        handle_back_to_summary,
        handle_draft_edit_calendar_nav,
        handle_draft_edit_calendar_day,
        handle_draft_edit_time_hour,
        handle_draft_edit_time_minute,
        handle_draft_edit_time_skip,
        handle_draft_edit_cal_skip,
        handle_draft_edit_back_calendar,
        handle_draft_edit_back_hour,
        handle_draft_edit_translator,
        _render_draft_edit_translator_selection,
        _render_draft_edit_followup_calendar,
    )
    logger.info("✅ draft handlers loaded from package")
except ImportError as _e:
    logger.error(f"❌ Cannot import draft handlers from package: {_e} — draft editing will not work")


# handle_final_confirm is imported from flows/shared.py at the top of this file (line 62-67)


# =============================
# Helper Functions - استيراد handlers من flows/new_consult.py
# =============================

# =============================
# دوال مساعدة للحصول على handlers المحلية
# =============================
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

# =============================
# Module-level inline query handlers (extracted from register() for importability)
# =============================

async def patient_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler منفصل للبحث عن المرضى فقط - لا يتداخل مع الأطباء"""
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

                if query_text:
                    names = [n for n in names if query_text.lower() in n.lower()]

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
        except Exception:
            await query.message.reply_text("⚠️ معرف تقرير غير صالح.")
            return

        from db.session import SessionLocal as _SL
        from db.models import Report as _Report

        with _SL() as s:
            report = s.query(_Report).filter_by(id=report_id).first()
            if not report:
                await query.message.reply_text("⚠️ لم يتم العثور على التقرير.")
                return

            reason = None
            if getattr(report, 'app_reschedule_reason', None):
                reason = report.app_reschedule_reason
            elif getattr(report, 'followup_reason', None):
                reason = report.followup_reason
            elif getattr(report, 'doctor_decision', None) and 'سبب تأجيل' in str(report.doctor_decision):
                reason = report.doctor_decision

            if not reason or not str(reason).strip():
                await query.message.reply_text("ℹ️ لا يوجد سبب تأجيل مسجل لهذا التقرير.")
                return

            text = f"📅 **سبب تأجيل الموعد للتقرير #{report_id}:**\n\n{reason}"

            return_date = getattr(report, 'app_reschedule_return_date', None) or getattr(report, 'followup_date', None)
            if return_date:
                if hasattr(return_date, 'strftime'):
                    text += f"\n\n📅 **موعد العودة:** {return_date.strftime('%Y-%m-%d')}"
                else:
                    text += f"\n\n📅 **موعد العودة:** {return_date}"

            return_reason = getattr(report, 'app_reschedule_return_reason', None)
            if return_reason and str(return_reason).strip():
                text += f"\n\n✍️ **سبب العودة:** {return_reason}"

            await query.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.exception(f"خطأ في handle_view_reschedule_callback: {e}")
        try:
            await update.callback_query.message.reply_text("⚠️ حدث خطأ أثناء جلب بيانات التأجيل.")
        except Exception:
            pass


async def doctor_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler بسيط للبحث عن الأطباء مع فلترة حسب المستشفى والقسم"""
    try:
        query_text = update.inline_query.query.strip() if update.inline_query.query else ""

        report_tmp = context.user_data.get("report_tmp", {})
        hospital_name = report_tmp.get("hospital_name", "").strip()
        department_name = report_tmp.get("department_name", "").strip()

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

        search_hospital = hospital_mapping.get(hospital_name, hospital_name)

        doctors_results = search_doctors(
            query=query_text if query_text else "",
            hospital=search_hospital if search_hospital else None,
            department=department_name if department_name else None,
            limit=20,
        )

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

        await update.inline_query.answer(results, cache_time=1)

    except Exception:
        await update.inline_query.answer([], cache_time=1)


async def handle_chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار من inline query"""
    result_id = update.chosen_inline_result.result_id

    if result_id.startswith("patient_"):
        patient_id = int(result_id.split("_")[1])
        report_tmp = context.user_data.setdefault("report_tmp", {})
        with SessionLocal() as s:
            patient = s.query(Patient).filter_by(id=patient_id).first()
            if patient:
                report_tmp["patient_name"] = patient.full_name
                report_tmp["patient_id"] = patient_id
    elif result_id.startswith("doctor_"):
        context.user_data.setdefault("report_tmp", {})

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
            "واصل", "عزالدين", "عبدالسلام", "يحيى", "ياسر"]

async def show_translator_selection(message, context, flow_type, page=1):
    """
    عرض قائمة المترجمين للاختيار مع صفحات
    """
    # Forward to modular authority on page=1 so the medical-report gate is applied.
    # The modular show_translator_selection in flows/shared.py owns that gate.
    # On page>1 (pagination callbacks) we fall through to the paginated list below.
    if page == 1:
        try:
            from bot.handlers.user.user_reports_add_new_system.flows.shared import (
                show_translator_selection as _modular_show,
            )
            result = await _modular_show(message, context, flow_type)
            # If gate was triggered it returns "MEDICAL_REPORT_ASK"; if translator
            # list was shown it returns None. Either way we are done for page 1.
            return result
        except Exception:
            pass  # fall through to inline implementation on import failure

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
        row.append(InlineKeyboardButton(name, callback_data=f"simple_translator:{flow_type}:{name}"))
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
            row.append(InlineKeyboardButton(name, callback_data=f"simple_translator:{flow_type}:{name}"))
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
            translator_name = "غير محدد"
            translator_id = None
            logger.debug("translator callback: skip")
        elif choice.lstrip('-').isdigit():
            # ── IDX-format (legacy, draining) ──────────────────────────────
            logger.debug("translator callback: IDX-format  idx=%s  flow=%s", choice, flow_type)
            translator_names = load_translator_names()
            try:
                index = int(choice)
                translator_name = translator_names[index]
                translator_id = None
                logger.debug("translator IDX resolved: idx=%d → name=[%s]", index, translator_name)
            except (IndexError, ValueError) as exc:
                logger.warning(
                    "translator callback: invalid IDX payload  choice=%r  flow=%s  error=%s",
                    choice, flow_type, exc
                )
                await query.edit_message_text("❌ اختيار غير صحيح")
                return
        else:
            # ── NAME-format (current protocol post-migration) ───────────────
            logger.debug("translator callback: NAME-format  name=[%s]  flow=%s", choice, flow_type)
            translator_name = choice
            translator_id = None

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
            logger.error(f"❌ خطأ في get_confirm_state: {e}", exc_info=True)
            # إرجاع state افتراضي
            context.user_data['_conversation_state'] = NEW_CONSULT_CONFIRM
            return NEW_CONSULT_CONFIRM

    except Exception as e:
        logger.error(f"❌ خطأ في handle_simple_translator_choice: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ حدث خطأ في معالجة الاختيار")
        except:
            pass
        return
