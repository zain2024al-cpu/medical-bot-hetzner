# =============================
# flows/shared.py
# الدوال المشتركة بين جميع المسارات (flows)
# Translator, Confirm, Edit, Save
# =============================

import logging
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# Imports from parent modules
from ..states import (
    NEW_CONSULT_TRANSLATOR, FOLLOWUP_TRANSLATOR, EMERGENCY_TRANSLATOR,
    ADMISSION_TRANSLATOR, SURGERY_CONSULT_TRANSLATOR, OPERATION_TRANSLATOR,
    FINAL_CONSULT_TRANSLATOR, DISCHARGE_TRANSLATOR, PHYSICAL_THERAPY_TRANSLATOR,
    DEVICE_TRANSLATOR, RADIOLOGY_TRANSLATOR, APP_RESCHEDULE_TRANSLATOR,
    NEW_CONSULT_CONFIRM, FOLLOWUP_CONFIRM, EMERGENCY_CONFIRM,
    ADMISSION_CONFIRM, SURGERY_CONSULT_CONFIRM, OPERATION_CONFIRM,
    FINAL_CONSULT_CONFIRM, DISCHARGE_CONFIRM, PHYSICAL_THERAPY_CONFIRM,
    DEVICE_CONFIRM, RADIOLOGY_CONFIRM, APP_RESCHEDULE_CONFIRM,
    R_ACTION_TYPE
)
from ..utils import _nav_buttons
from ..navigation_helpers import handle_cancel_navigation

# External imports
try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None
try:
    from db.models import Translator, Report, Patient, Hospital, Department, Doctor
except ImportError:
    Translator = Report = Patient = Hospital = Department = Doctor = None
try:
    from bot.handlers.user.user_reports_add_helpers import validate_text_input, _build_action_type_keyboard
except ImportError:
    validate_text_input = None
    _build_action_type_keyboard = None

logger = logging.getLogger(__name__)


# =============================
# Helper Functions
# =============================

def load_translator_names():
    """
    قراءة أسماء المترجمين من الملف
    دالة ثابتة للقوائم - تقرأ من ملف translator_names.txt
    """
    try:
        # البحث عن الملف في عدة مسارات محتملة
        current_file = os.path.abspath(__file__)
        # flows/shared.py -> flows/ -> user_reports_add_new_system/ -> user/ -> handlers/ -> bot/ -> workspace root
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))))
        
        possible_paths = [
            os.path.join(workspace_root, 'data', 'translator_names.txt'),
            os.path.join(os.path.dirname(current_file), '..', '..', '..', 'data', 'translator_names.txt'),
            os.path.join(os.path.dirname(current_file), '..', '..', '..', '..', 'data', 'translator_names.txt'),
            'data/translator_names.txt',
            '../data/translator_names.txt',
            '../../data/translator_names.txt'
        ]

        translator_file = None
        for path in possible_paths:
            if os.path.exists(path):
                translator_file = path
                break

        if not translator_file:
            raise FileNotFoundError(f"لم يتم العثور على ملف translator_names.txt في أي من المسارات: {possible_paths}")

        logger.info(f"📁 تم العثور على ملف المترجمين: {translator_file}")

        # محاولة قراءة الملف بطرق مختلفة
        try:
            # محاولة أولى: utf-8 مع BOM
            with open(translator_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                lines = content.split('\n')
                names = [line.strip() for line in lines[1:] if line.strip()]
                if names and any('م' in name for name in names):
                    logger.info(f"✅ تم قراءة {len(names)} مترجم باستخدام utf-8-sig")
                    return names
        except Exception:
            pass

        # محاولة ثانية: قراءة كـ bytes ثم decode
        try:
            with open(translator_file, 'rb') as f:
                content = f.read()
                # محاولة decode بترميز مختلف
                for encoding in ['utf-8', 'cp1256', 'windows-1256']:
                    try:
                        text = content.decode(encoding)
                        lines = text.split('\n')
                        names = [line.strip() for line in lines[1:] if line.strip()]
                        if names and any('م' in name for name in names):
                            logger.info(f"✅ تم قراءة {len(names)} مترجم باستخدام {encoding} (binary)")
                            return names
                    except UnicodeDecodeError:
                        continue
        except Exception:
            pass

        # إذا فشل جميع encodings
        raise Exception("فشل في قراءة الملف بجميع encodings المحاولة")

    except Exception as e:
        logger.error(f"❌ خطأ في قراءة ملف المترجمين: {e}")
        # قائمة احتياطية في حالة فشل قراءة الملف
        fallback_names = ["مصطفى", "واصل", "نجم الدين", "محمد علي", "سعيد", "مهدي", "صبري", "عزي", "معتز", "ادريس", "هاشم", "ادم", "زيد", "عصام", "عزالدين", "حسن", "زين العابدين", "عبدالسلام", "ياسر", "يحيى"]
        logger.warning(f"⚠️ استخدام القائمة الاحتياطية: {len(fallback_names)} مترجم")
        return fallback_names


def ensure_default_translators():
    """
    إضافة المترجمين الافتراضيين إلى قاعدة البيانات إذا لم يكونوا موجودين
    دالة ثابتة للقوائم - تضمن وجود المترجمين الأساسيين في قاعدة البيانات
    """
    if not SessionLocal or not Translator:
        logger.warning("⚠️ SessionLocal or Translator not available - skipping ensure_default_translators")
        return
    
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
        "عبدالسلام",
        "ياسر",
        "يحيى"
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


def escape_markdown_v1(text: str) -> str:
    """تهريب الأحرف الخاصة في Markdown V1"""
    import re
    if not text:
        return ""
    escape_chars = r'_*[]()`'
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', text)


def format_field_value(value):
    """تنسيق قيمة الحقل للعرض"""
    if value is None or value == "":
        return "غير محدد"
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def format_time_12h(time_str):
    """تحويل الوقت لصيغة 12 ساعة مع صباحاً/ظهراً/مساءً"""
    if not time_str:
        return None
    try:
        if ':' in str(time_str):
            parts = str(time_str).split(':')
            hour = int(parts[0])
            minute = parts[1] if len(parts) > 1 else '00'
        else:
            hour = int(time_str)
            minute = '00'
        
        if hour == 0:
            return f"12:{minute} صباحاً"
        elif hour < 12:
            return f"{hour}:{minute} صباحاً"
        elif hour == 12:
            return f"12:{minute} ظهراً"
        else:
            return f"{hour-12}:{minute} مساءً"
    except:
        return str(time_str)


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
        "admission_reason": "🛏️ سبب الرقود",
        "room_number": "🚪 رقم الغرفة",
        "notes": "📝 ملاحظات",
        "status": "🏥 وضع الحالة",
        "admission_type": "🛏️ نوع الترقيد",
        "operation_details": "⚕️ تفاصيل العملية",
        "operation_name_en": "🔤 اسم العملية بالإنجليزي",
        "success_rate": "📊 نسبة نجاح العملية",
        "benefit_rate": "💡 نسبة الاستفادة",
        "recommendations": "💡 التوصيات الطبية",
        "discharge_type": "🚪 نوع الخروج",
        "admission_summary": "📋 ملخص الرقود",
        "therapy_details": "🏃 تفاصيل جلسة العلاج الطبيعي",
        "device_name": "🦾 اسم الجهاز والتفاصيل",
        "device_details": "🦾 اسم الجهاز والتفاصيل",
        "radiology_type": "🔬 نوع الأشعة/الفحص",
        "delivery_date": "📅 تاريخ الاستلام",
    }
    return names.get(field_key, field_key)


def _has_field_value(data, field_key):
    """
    التحقق من وجود قيمة فعلية للحقل في report_tmp
    يعيد True فقط إذا كان للحقل قيمة حقيقية (ليست فارغة، None، أو "غير محدد")
    
    منطق العمل:
    1. الحقول الأساسية (report_date, patient_name, hospital_name, department_name, doctor_name) 
       تكون موجودة عادة، لكن يتم التحقق منها أيضاً
    2. الحقول الأخرى يتم التحقق منها في الحقول المشتقة أولاً
    3. إذا لم توجد في الحقول المشتقة، يتم التحقق من الحقل نفسه
    """
    # ✅ التحقق من الحقول المشتقة أولاً
    field_aliases = {
        # الحقول الأساسية
        "report_date": ["report_date"],
        "patient_name": ["patient_name"],
        "hospital_name": ["hospital_name"],
        "department_name": ["department_name"],
        "doctor_name": ["doctor_name"],
        
        # الحقول المشتقة
        "complaint": ["complaint", "complaint_text"],
        "decision": ["decision", "doctor_decision"],
        "diagnosis": ["diagnosis"],
        "tests": ["tests", "notes"],  # في بعض المسارات، tests محفوظ في notes
        "operation_details": ["operation_details", "notes"],
        "operation_name_en": ["operation_name_en"],
        "success_rate": ["success_rate"],
        "benefit_rate": ["benefit_rate"],
        "room_number": ["room_number", "room_floor"],
        "followup_date": ["followup_date"],
        "followup_time": ["followup_time"],
        "followup_reason": ["followup_reason"],
        "delivery_date": ["delivery_date", "radiology_delivery_date"],
        "radiology_delivery_date": ["delivery_date", "radiology_delivery_date"],
        "radiology_type": ["radiology_type"],
        "admission_reason": ["admission_reason"],
        "discharge_type": ["discharge_type"],
        "admission_summary": ["admission_summary"],
        "therapy_details": ["therapy_details"],
        "device_name": ["device_name", "device_details"],
        "device_details": ["device_name", "device_details"],
        "app_reschedule_reason": ["app_reschedule_reason"],
        "app_reschedule_return_date": ["app_reschedule_return_date", "followup_date"],
        "app_reschedule_return_reason": ["app_reschedule_return_reason", "followup_reason"],
        "recommendations": ["recommendations"],
        "notes": ["notes"],
        "status": ["status"],
        "admission_type": ["admission_type"],
    }
    
    # ✅ البحث في الحقول المشتقة
    aliases = field_aliases.get(field_key, [field_key])
    for alias in aliases:
        alias_value = data.get(alias)
        if alias_value is not None:
            # ✅ التحقق من التواريخ
            if isinstance(alias_value, (date, datetime)):
                return True
            
            # ✅ التحقق من النصوص
            value_str = str(alias_value).strip()
            if value_str and value_str not in ["غير محدد", "لا يوجد", "None", "null", "", "⚠️ فارغ"]:
                return True
    
    # ✅ التحقق من الحقل نفسه (fallback)
    value = data.get(field_key)
    if value is not None:
        # ✅ التحقق من التواريخ
        if isinstance(value, (date, datetime)):
            return True
        
        # ✅ التحقق من النصوص
        value_str = str(value).strip()
        if value_str and value_str not in ["غير محدد", "لا يوجد", "None", "null", "", "⚠️ فارغ"]:
            return True
    
    return False


def get_editable_fields_by_flow_type(flow_type):
    """الحصول على الحقول القابلة للتعديل حسب نوع التدفق - دالة ثابتة للقوائم
    ✅ ملاحظة: تم إزالة الحقول الأساسية (report_date, patient_name, hospital_name, department_name, doctor_name)
    لأنها تُحدد قبل بدء المسار وليست جزءاً من الإدخال اليدوي
    """
    fields_map = {
        "new_consult": [
            # ✅ الحقول المدخلة فقط في مسار استشارة جديدة
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("tests", "🧪 الفحوصات والأشعة"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "followup": [
            # ✅ الحقول المدخلة فقط في مسار متابعة (متابعة في الرقود)
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("room_number", "🏥 رقم الغرفة والطابق"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "periodic_followup": [
            # ✅ مسار "مراجعة / عودة دورية" - بدون room_number
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "inpatient_followup": [
            # ✅ مسار "متابعة في الرقود" - مع room_number
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب"),
            ("room_number", "🏥 رقم الغرفة والطابق"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "emergency": [
            # ✅ الحقول المدخلة فقط في مسار طوارئ
            ("complaint", "💬 شكوى المريض"),
            ("diagnosis", "🔬 التشخيص الطبي"),
            ("decision", "📝 قرار الطبيب وماذا تم"),
            ("status", "🏥 وضع الحالة"),
            ("room_number", "🚪 رقم الغرفة"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "admission": [
            # ✅ الحقول المدخلة فقط في مسار ترقيد
            ("admission_reason", "🛏️ سبب الرقود"),
            ("room_number", "🚪 رقم الغرفة"),
            ("notes", "📝 ملاحظات"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "surgery_consult": [
            # ✅ الحقول المدخلة فقط في مسار استشارة مع قرار عملية
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
            # ✅ الحقول المدخلة فقط في مسار عملية
            ("operation_details", "⚕️ تفاصيل العملية بالعربي"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("notes", "📝 ملاحظات"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "final_consult": [
            # ✅ الحقول المدخلة فقط في مسار استشارة أخيرة
            ("diagnosis", "🔬 التشخيص النهائي"),
            ("decision", "📝 قرار الطبيب"),
            ("recommendations", "💡 التوصيات الطبية"),
        ],
        "discharge": [
            # ✅ الحقول المدخلة فقط في مسار خروج من المستشفى
            ("discharge_type", "🚪 نوع الخروج"),
            ("admission_summary", "📋 ملخص الرقود"),
            ("operation_details", "⚕️ تفاصيل العملية"),
            ("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "rehab_physical": [
            # ✅ الحقول المدخلة فقط في مسار علاج طبيعي
            ("therapy_details", "🏃 تفاصيل جلسة العلاج الطبيعي"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "rehab_device": [
            # ✅ الحقول المدخلة فقط في مسار أجهزة تعويضية
            ("device_name", "🦾 اسم الجهاز والتفاصيل"),
            ("followup_date", "📅 موعد العودة"),
            ("followup_time", "⏰ وقت العودة"),
            ("followup_reason", "✍️ سبب العودة"),
        ],
        "radiology": [
            # ✅ الحقول المدخلة فقط في مسار أشعة وفحوصات
            ("radiology_type", "🔬 نوع الأشعة/الفحص"),
            ("delivery_date", "📅 تاريخ الاستلام"),
        ],
        "appointment_reschedule": [
            # ✅ الحقول المدخلة فقط في مسار تأجيل موعد
            ("app_reschedule_reason", "📅 سبب تأجيل الموعد"),
            ("app_reschedule_return_date", "📅 تاريخ العودة الجديد"),
            ("app_reschedule_return_reason", "✍️ سبب العودة"),
        ],
    }
    return fields_map.get(flow_type, [])


def get_translator_state(flow_type):
    """الحصول على state المترجم المناسب"""
    states = {
        "new_consult": NEW_CONSULT_TRANSLATOR,
        "followup": FOLLOWUP_TRANSLATOR,
        "surgery_consult": SURGERY_CONSULT_TRANSLATOR,
        "appointment_reschedule": APP_RESCHEDULE_TRANSLATOR,
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
        "appointment_reschedule": APP_RESCHEDULE_CONFIRM,
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


# =============================
# Translator Functions
# =============================

async def show_translator_selection(message, context, flow_type):
    """
    عرض قائمة المترجمين للاختيار (من ملف translator_names.txt)
    دالة ثابتة للقوائم
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

    # إضافة زر تخطي (اختياري)
    keyboard_buttons.append([
        InlineKeyboardButton("⏭️ تخطي (بدون مترجم)", callback_data=f"simple_translator:{flow_type}:skip"),
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
    معالجة اختيار المترجم البسيط (من قائمة ثابتة)
    """
    query = update.callback_query
    await query.answer()

    try:
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END

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
                return ConversationHandler.END

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
        logger.error(f"❌ خطأ في معالجة اختيار المترجم: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ في معالجة الاختيار")
        return ConversationHandler.END


async def render_translator_selection(message, context, flow_type):
    """عرض شاشة اختيار المترجم - عرض قائمة المترجمين مباشرة (مثل اختيار الطبيب)"""
    keyboard = []
    
    # ✅ جلب المترجمين من قاعدة البيانات مباشرة
    translators_list = []
    
    try:
        if SessionLocal and Translator:
            with SessionLocal() as s:
                # جلب المترجمين المضافة يدوياً فقط (ليس لديهم tg_user_id)
                all_translators = s.query(Translator).filter(
                    Translator.is_approved == True,
                    Translator.is_active == True,
                    Translator.full_name.isnot(None),
                    Translator.full_name != "",
                    Translator.tg_user_id.is_(None)
                ).order_by(Translator.full_name).all()
                
                # استخراج الأسماء فقط (بدون تكرار)
                translator_names = []
                seen_names = set()
                for translator in all_translators:
                    name = translator.full_name or translator.name
                    if name and name not in seen_names:
                        translator_names.append(name)
                        seen_names.add(name)
                        translators_list.append({
                            'id': translator.id,
                            'name': name
                        })
                
                logger.info(f"✅ تم جلب {len(translators_list)} مترجم من قاعدة البيانات")
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المترجمين: {e}", exc_info=True)
    
    # ✅ إذا كان هناك مترجمين، عرضهم كأزرار مباشرة (10 أسماء في الصفحة الأولى)
    if translators_list:
        # حفظ قائمة المترجمين في context للاسترجاع لاحقاً
        context.user_data["_translators_list"] = translators_list
        
        # إضافة أزرار المترجمين (10 في الصفحة الأولى) - عرض اسمين في كل صف
        translators_first_page = translators_list[:10]
        for i in range(0, len(translators_first_page), 2):
            row = []
            for translator in translators_first_page[i:i+2]:
                button_text = f"👤 {translator['name']}"
                if len(button_text) > 32:  # تقليل الحد لأننا نضع اسمين في صف واحد
                    button_text = f"👤 {translator['name'][:28]}..."
                
                row.append(InlineKeyboardButton(
                    button_text,
                    callback_data=f"translator_idx:{flow_type}:{translator['id']}"
                ))
            keyboard.append(row)
        
        # ✅ إذا كان هناك أكثر من 10 مترجمين، إضافة زر "التالي"
        if len(translators_list) > 10:
            keyboard.append([InlineKeyboardButton(
                "التالي ➡️",
                callback_data=f"translator:show_list:{flow_type}:1"
            )])
        
        # ✅ إضافة زر "إدخال يدوي" دائماً
        keyboard.append([InlineKeyboardButton(
            "✏️ إدخال اسم المترجم يدوياً",
            callback_data=f"translator:{flow_type}:add_new"
        )])
        
        text = f"👤 **اسم المترجم**\n\n"
        text += f"📋 **عدد المترجمين:** {len(translators_list)}\n\n"
        text += "اختر المترجم من القائمة أو اضغط على **إدخال يدوي** لإضافة مترجم جديد:"
    else:
        # ✅ إذا لم يوجد مترجمين، عرض زر "إدخال يدوي" فقط
        keyboard.append([InlineKeyboardButton(
            "✏️ إدخال اسم المترجم يدوياً",
            callback_data=f"translator:{flow_type}:add_new"
        )])
        
        text = f"👤 **اسم المترجم**\n\n"
        text += "⚠️ **لم يتم العثور على مترجمين** في قاعدة البيانات.\n\n"
        text += "يرجى إدخال اسم المترجم يدوياً:"
    
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    try:
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة اختيار المترجم: {e}", exc_info=True)
        try:
            await message.reply_text(
                text.replace("**", ""),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")


async def ask_translator_name(message, context, flow_type):
    """طلب اسم المترجم - مشترك لجميع المسارات"""
    context.user_data['_current_search_type'] = 'translator'
    await render_translator_selection(message, context, flow_type)


async def show_translator_list(update: Update, context: ContextTypes.DEFAULT_TYPE, flow_type: str, page: int = 0):
    """عرض قائمة المترجمين مع pagination"""
    query = update.callback_query
    if query:
        await query.answer()
    
    items_per_page = 10
    
    # ✅ محاولة استخدام القائمة المحفوظة من render_translator_selection أولاً
    saved_translators_list = context.user_data.get("_translators_list", [])
    
    if saved_translators_list:
        # استخدام القائمة المحفوظة
        all_translators = saved_translators_list
    else:
        # ✅ إذا لم تكن هناك قائمة محفوظة، جلب من قاعدة البيانات
        if not SessionLocal or not Translator:
            logger.error("❌ SessionLocal or Translator not available")
            if query:
                await query.edit_message_text("❌ خطأ في الاتصال بقاعدة البيانات")
            return get_translator_state(flow_type)
        
        with SessionLocal() as s:
            all_translators_objects = s.query(Translator).filter(
                Translator.is_approved == True,
                Translator.is_active == True,
                Translator.full_name.isnot(None),
                Translator.full_name != "",
                Translator.tg_user_id.is_(None)
            ).order_by(Translator.full_name).all()
            
            # تحويل إلى نفس البنية (list of dicts)
            all_translators = [{'id': t.id, 'name': t.full_name} for t in all_translators_objects]
    
    # ✅ الكود المشترك لعرض المترجمين
    total = len(all_translators)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    translators_page = all_translators[start_idx:end_idx]
    
    keyboard = []
    
    # إضافة أزرار المترجمين - عرض اسمين في كل صف
    for i in range(0, len(translators_page), 2):
        row = []
        for translator in translators_page[i:i+2]:
            button_text = f"👤 {translator['name']}"
            if len(button_text) > 32:  # تقليل الحد لأننا نضع اسمين في صف واحد
                button_text = f"👤 {translator['name'][:28]}..."
            
            row.append(InlineKeyboardButton(
                button_text,
                callback_data=f"translator_idx:{flow_type}:{translator['id']}"
            ))
        keyboard.append(row)
    
    # أزرار التنقل بين الصفحات
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"translator:show_list:{flow_type}:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"translator:show_list:{flow_type}:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # ✅ إضافة زر "إدخال يدوي" دائماً
    keyboard.append([InlineKeyboardButton(
        "✏️ إدخال اسم المترجم يدوياً",
        callback_data=f"translator:{flow_type}:add_new"
    )])
    
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data=f"translator:back_to_menu:{flow_type}")
    ])
    
    text = f"👤 **قائمة المترجمين**\n\n"
    text += f"📊 **العدد الإجمالي:** {total} مترجم\n"
    text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
    text += "اختر المترجم من القائمة أو اضغط على **إدخال يدوي** لإضافة مترجم جديد:"
    
    if query:
        try:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
            try:
                await query.message.reply_text(
                    text.replace("**", ""),
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e2:
                logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
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
    try:
        query = update.callback_query
        if not query:
            logger.error("❌ handle_translator_choice: No query found")
            return ConversationHandler.END
        
        await query.answer()

        parts = query.data.split(":")
        if len(parts) < 2:
            logger.error(f"❌ Invalid callback_data format: {query.data}")
            await query.answer("⚠️ خطأ في البيانات", show_alert=True)
            flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
            return get_translator_state(flow_type)
        
        flow_type = parts[1]
        logger.info(f"✅ handle_translator_choice: flow_type={flow_type}, callback_data={query.data}")
        
        # Import show_final_summary (defined below in this file)
        pass  # show_final_summary is defined in this same file
        
        if query.data.startswith("translator_idx:"):
            try:
                if len(parts) < 3:
                    logger.error(f"❌ callback_data missing translator_id: {query.data}")
                    await query.answer("⚠️ خطأ في البيانات (لا يوجد رقم المترجم)", show_alert=True)
                    flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
                    return get_translator_state(flow_type)
                translator_id = int(parts[2])
                logger.info(f"✅ Selecting translator by ID: {translator_id}")
                found_translator = False
                if SessionLocal and Translator:
                    with SessionLocal() as s:
                        translator = s.query(Translator).filter_by(id=translator_id).first()
                        if translator:
                            context.user_data.setdefault("report_tmp", {})["translator_name"] = translator.full_name
                            context.user_data["report_tmp"]["translator_id"] = translator.id
                            logger.info(f"✅ Translator selected: {translator.full_name}")
                            found_translator = True
                        else:
                            context.user_data.setdefault("report_tmp", {})["translator_name"] = "غير محدد"
                            context.user_data["report_tmp"]["translator_id"] = None
                            logger.warning(f"⚠️ Translator ID {translator_id} not found in DB")
                if not found_translator:
                    await query.answer("⚠️ لم يتم العثور على المترجم المطلوب. يرجى المحاولة مرة أخرى أو تحديث القائمة.", show_alert=True)
                    return get_translator_state(flow_type)
                try:
                    await query.edit_message_text("✅ تم اختيار المترجم")
                except Exception as e:
                    logger.warning(f"⚠️ Could not edit message: {e}")
                    try:
                        await query.message.reply_text("✅ تم اختيار المترجم")
                    except:
                        pass
                try:
                    await show_final_summary(query.message, context, flow_type)
                except Exception as e:
                    logger.error(f"❌ Error in show_final_summary: {e}", exc_info=True)
                    await query.message.reply_text(
                        f"❌ **حدث خطأ أثناء عرض الملخص**\n\n"
                        f"يرجى المحاولة مرة أخرى.",
                        parse_mode="Markdown"
                    )
                    flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
                    return get_translator_state(flow_type)
                confirm_state = get_confirm_state(flow_type)
                context.user_data['_conversation_state'] = confirm_state
                logger.info(f"✅ Returning confirm_state: {confirm_state}")
                return confirm_state
            except (ValueError, IndexError) as e:
                logger.error(f"❌ Error parsing translator ID: {e}", exc_info=True)
                await query.answer("⚠️ خطأ في رقم المترجم. يرجى المحاولة مرة أخرى.", show_alert=True)
                flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
                return get_translator_state(flow_type)
            except Exception as e:
                logger.error(f"❌ Unexpected error in translator_idx handler: {e}", exc_info=True)
                await query.answer("⚠️ حدث خطأ غير متوقع أثناء اختيار المترجم", show_alert=True)
                flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
                return get_translator_state(flow_type)
        
        # Handle old format (auto, manual, add_new) - kept for backward compatibility
        if len(parts) > 2:
            choice = parts[2]
            
            if choice == "add_new":
                try:
                    await query.edit_message_text(
                        "➕ **إضافة مترجم جديد**\n\n"
                        "يرجى إدخال اسم المترجم الجديد:",
                        reply_markup=_nav_buttons(show_back=True, previous_state_name="new_consult_complaint", context=context),
                        parse_mode="Markdown"
                    )

                    context.user_data.setdefault("report_tmp", {})["current_flow"] = flow_type
                    context.user_data.setdefault("report_tmp", {})["translator_add_new"] = True
                    translator_state = get_translator_state(flow_type)
                    context.user_data['_conversation_state'] = translator_state
                    return translator_state
                except Exception as e:
                    logger.error(f"❌ Error in add_new translator: {e}", exc_info=True)
                    await query.answer("⚠️ حدث خطأ غير متوقع", show_alert=True)
                    flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
                    return get_translator_state(flow_type)
        
        logger.warning(f"⚠️ Unknown translator choice: {query.data}")
        await query.answer("⚠️ خيار غير معروف", show_alert=True)
        flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        return get_translator_state(flow_type)
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in handle_translator_choice: {e}", exc_info=True)
        try:
            if query:
                await query.answer("⚠️ حدث خطأ غير متوقع، يرجى المحاولة مرة أخرى", show_alert=True)
        except:
            pass
        flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
        return get_translator_state(flow_type)


async def handle_translator_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المترجم من inline query"""
    text = update.message.text.strip()
    
    if text.startswith("__TRANSLATOR_SELECTED__:"):
        try:
            parts = text.split(":")
            translator_id = int(parts[1])
            translator_name = parts[2] if len(parts) > 2 else ""
            
            flow_type = context.user_data.get("report_tmp", {}).get("current_flow", "new_consult")
            
            # show_final_summary is defined in this same file (below)
            
            if SessionLocal and Translator:
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
    
    return await handle_translator_text(update, context)


async def handle_translator_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المترجم يدوياً"""
    text = update.message.text.strip()
    
    if text.startswith("__TRANSLATOR_SELECTED__:"):
        return await handle_translator_inline_selection(update, context)
    
    if not validate_text_input:
        logger.error("❌ validate_text_input not available")
        await update.message.reply_text("❌ خطأ في النظام")
        flow_type = context.user_data["report_tmp"].get("current_flow", "new_consult")
        return get_translator_state(flow_type)
    
    valid, msg = validate_text_input(text, min_length=2, max_length=100)

    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال اسم المترجم:",
            reply_markup=_nav_buttons(show_back=True, previous_state_name="new_consult_complaint", context=context),
            parse_mode="Markdown"
        )
        flow_type = context.user_data["report_tmp"].get("current_flow", "new_consult")
        return get_translator_state(flow_type)

    flow_type = context.user_data["report_tmp"].get("current_flow", "new_consult")
    
    # show_final_summary is defined in this same file (below)
    
    if context.user_data.get("report_tmp", {}).get("translator_add_new"):
        try:
            if SessionLocal and Translator:
                with SessionLocal() as s:
                    existing_translator = s.query(Translator).filter(
                        Translator.full_name.ilike(text)
                    ).first()
                    
                    if existing_translator:
                        context.user_data.setdefault("report_tmp", {})["translator_name"] = existing_translator.full_name
                        context.user_data["report_tmp"]["translator_id"] = existing_translator.id
                        await update.message.reply_text(f"✅ تم استخدام المترجم الموجود: {existing_translator.full_name}")
                    else:
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
        context.user_data.setdefault("report_tmp", {})["translator_name"] = text
        context.user_data["report_tmp"]["translator_id"] = None

    await show_final_summary(update.message, context, flow_type)

    confirm_state = get_confirm_state(flow_type)
    context.user_data['_conversation_state'] = confirm_state
    return confirm_state


# =============================
# Summary and Confirm Functions
# =============================

async def show_final_summary(message, context, flow_type):
    """
    ✅ عرض ملخص التقرير النهائي قبل الحفظ
    - يستخدم نفس منطق format_report_message
    - يعرض فقط الحقول المدخلة فعلياً (بدون قيم افتراضية)
    - ما يظهر في الملخص = ما سيُنشر حرفيًا
    """
    try:
        data = context.user_data.get("report_tmp", {}).copy()  # نسخة لتجنب التعديل على البيانات الأصلية
        
        # ✅ استيراد format_report_message من broadcast_service
        try:
            from services.broadcast_service import format_report_message
        except ImportError:
            logger.error("❌ Cannot import format_report_message from broadcast_service")
            await message.reply_text("❌ حدث خطأ في عرض الملخص")
            return
        
        # ✅ استخدام format_report_message لبناء الملخص (نفس منطق النشر)
        report_message = format_report_message(data)
        
        # ✅ استبدال "🆕 تقرير جديد" بـ "📋 ملخص التقرير"
        if report_message.startswith("🆕 **تقرير جديد**"):
            report_message = report_message.replace("🆕 **تقرير جديد**", "📋 **ملخص التقرير**", 1)
        elif report_message.startswith("✏️ **تقرير معدل**"):
            report_message = report_message.replace("✏️ **تقرير معدل**", "📋 **ملخص التقرير (معدل)**", 1)
        
        # ✅ إرسال الملخص مع الأزرار
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ مراجعة وتعديل التقرير", callback_data=f"edit:{flow_type}"),
                InlineKeyboardButton("📤 نشر التقرير", callback_data=f"publish:{flow_type}")
            ],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        
        await message.reply_text(
            report_message,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"❌ Error in show_final_summary: {e}", exc_info=True)
        try:
            await message.reply_text("❌ حدث خطأ في عرض الملخص")
        except:
            pass


async def show_review_screen(query, context, flow_type):
    """عرض شاشة المراجعة مع خيارات التعديل والنشر"""
    try:
        review_text = "📋 **مراجعة التقرير**\n\n"
        review_text += "يمكنك الآن:\n"
        review_text += "• ✏️ تعديل أي حقل في التقرير\n\n"
        review_text += "اختر الحقل الذي تريد تعديله:"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ تعديل الحقول", callback_data=f"edit:{flow_type}")],
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


async def handle_final_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التأكيد النهائي"""
    query = update.callback_query
    if not query:
        logger.error("❌ handle_final_confirm: No query found")
        return ConversationHandler.END
    
    await query.answer()
    
    logger.info("=" * 80)
    logger.info(f"📋 CALLBACK RECEIVED: {query.data}")
    logger.info(f"💾 Current state: {context.user_data.get('_conversation_state', 'NOT SET')}")
    logger.info("=" * 80)

    parts = query.data.split(":")
    action = parts[0]
    flow_type = parts[1] if len(parts) > 1 else "new_consult"
    
    data = context.user_data.get("report_tmp", {})
    current_flow = data.get("current_flow", "")
    if flow_type not in ["new_consult", "followup", "emergency", "admission", "surgery_consult", 
                         "operation", "final_consult", "discharge", "rehab_physical", "rehab_device", "radiology", "appointment_reschedule"]:
        if current_flow:
            flow_type = current_flow
            logger.info(f"💾 Using current_flow from report_tmp: {flow_type}")
    
    logger.info(f"💾 Action: {action}, Flow type: {flow_type}")

    if action == "review":
        logger.info(f"📋 Review button clicked for flow_type: {flow_type}")
        await show_review_screen(query, context, flow_type)
        return get_confirm_state(flow_type)
    elif action == "back_to_summary":
        logger.info(f"🔙 Back to summary clicked for flow_type: {flow_type}")
        await show_final_summary(query.message, context, flow_type)
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state
    elif action == "publish":
        logger.info(f"💾 Starting publish process for flow_type: {flow_type}")
        try:
            # save_report_to_database is defined in this same file (below)
            await save_report_to_database(query, context, flow_type)
            logger.info(f"Publish completed successfully for flow_type: {flow_type}")
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"❌ Error in save_report_to_database: {e}", exc_info=True)
            await query.answer(f"خطأ في النشر: {str(e)[:50]}", show_alert=True)
            return get_confirm_state(flow_type)
    elif action == "save":
        logger.info(f"📋 Save button clicked (treating as review) for flow_type: {flow_type}")
        await show_review_screen(query, context, flow_type)
        return get_confirm_state(flow_type)
    elif action == "edit":
        logger.info(f"✏️ Edit button clicked for flow_type: {flow_type}")
        # handle_edit_before_save is defined in this same file (below)
        edit_state = await handle_edit_before_save(query, context, flow_type)
        # إرجاع state الذي تم إرجاعه من handle_edit_before_save (عادة FOLLOWUP_CONFIRM)
        if edit_state:
            return edit_state
        # إذا لم يتم إرجاع state، نرجع confirm_state الحالي
        return get_confirm_state(flow_type)


# =============================
# =============================
# Save Report Function - حفظ التقرير في قاعدة البيانات
# =============================

async def save_report_to_database(query, context, flow_type):
    """حفظ التقرير في قاعدة البيانات"""
    if not SessionLocal or not Report or not Patient or not Hospital or not Department or not Doctor:
        logger.error("❌ Database models not available")
        # ✅ محاولة تعديل الرسالة - مع fallback إذا فشل
        try:
            await query.edit_message_text(
                "❌ **خطأ:** لا يمكن حفظ التقرير - قاعدة البيانات غير متاحة.",
                parse_mode="Markdown"
            )
        except Exception as edit_err:
            logger.warning(f"⚠️ Cannot edit message: {edit_err}")
            try:
                if query.message:
                    await query.message.reply_text("❌ **خطأ:** لا يمكن حفظ التقرير - قاعدة البيانات غير متاحة.", parse_mode="Markdown")
                else:
                    await query.answer("❌ قاعدة البيانات غير متاحة", show_alert=True)
            except:
                await query.answer("❌ خطأ في قاعدة البيانات", show_alert=True)
        return
    
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
                         "operation", "final_consult", "discharge", "rehab_physical", "rehab_device", "radiology", "appointment_reschedule"]
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
            "followup": "متابعة في الرقود",
            "surgery_consult": "استشارة مع قرار عملية",
            "emergency": "طوارئ",
            "admission": "ترقيد",
            "operation": "عملية",
            "final_consult": "استشارة أخيرة",
            "discharge": "خروج من المستشفى",
            "rehab_physical": "علاج طبيعي",
            "rehab_device": "أجهزة تعويضية",
            "device": "أجهزة تعويضية",  # ✅ إضافة "device" للتوافق مع get_confirm_state
            "radiology": "أشعة وفحوصات",
            "appointment_reschedule": "تأجيل موعد"
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
            complaint_text = ""
            decision_text = f"تفاصيل العملية: {operation_details}\n\nاسم العملية بالإنجليزي: {operation_name}\n\nملاحظات: {notes}"
        elif flow_type == "surgery_consult":
            diagnosis = data.get("diagnosis", "")
            decision = data.get("decision", "")
            operation_name = data.get("operation_name_en", "")
            success_rate = data.get("success_rate", "")
            benefit_rate = data.get("benefit_rate", "")
            tests = data.get("tests", "لا يوجد")
            complaint_text = ""
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
            complaint_text = ""
            decision_text = f"سبب الرقود: {admission_reason}\n\nرقم الغرفة: {room}\n\nملاحظات: {notes}"
        elif flow_type == "discharge":
            discharge_type = data.get("discharge_type", "")
            if discharge_type == "admission":
                summary = data.get("admission_summary", "")
                complaint_text = ""
                decision_text = f"ملخص الرقود: {summary}"
            else:
                operation_details = data.get("operation_details", "")
                operation_name = data.get("operation_name_en", "")
                complaint_text = ""
                decision_text = f"تفاصيل العملية: {operation_details}\n\nاسم العملية بالإنجليزي: {operation_name}"
        elif flow_type == "rehab_physical":
            therapy_details = data.get("therapy_details", "")
            complaint_text = ""
            decision_text = f"تفاصيل الجلسة: {therapy_details}"
        elif flow_type in ["rehab_device", "device"]:
            # ✅ التعامل مع "rehab_device" و "device" بنفس الطريقة
            device_details = data.get("device_details") or data.get("device_name", "")
            complaint_text = ""
            decision_text = f"تفاصيل الجهاز: {device_details}"
        elif flow_type == "radiology":
            radiology_type = data.get("radiology_type", "")
            complaint_text = ""
            # ✅ لا نضيف radiology_type هنا لأنه يُعرض بشكل منفصل في البث
            decision_text = ""
        elif flow_type == "appointment_reschedule":
            app_reschedule_reason = data.get("app_reschedule_reason", "")
            app_reschedule_return_reason = data.get("app_reschedule_return_reason", "")
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

        # تحويل datetime مع tzinfo إلى naive datetime (SQLite لا يقبل tzinfo)
        def to_naive_datetime(dt):
            """تحويل datetime مع tzinfo إلى naive datetime"""
            if dt is None:
                return None
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                # تحويل إلى UTC ثم إزالة tzinfo
                return dt.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
            return dt
        
        # معالجة report_date
        report_date = data.get("report_date", datetime.now())
        report_date = to_naive_datetime(report_date)
        
        # معالجة followup_date
        followup_date = data.get("followup_date")
        followup_date = to_naive_datetime(followup_date)
        
        # معالجة created_at (استخدام datetime.utcnow() لضمان naive datetime)
        created_at = datetime.utcnow()
        
        # الحصول على معرف المستخدم الذي أنشأ التقرير
        user_id = None
        if query and hasattr(query, 'from_user') and query.from_user:
            user_id = query.from_user.id
            logger.info(f"✅ User ID from query.from_user: {user_id}")
        elif context.user_data.get('_user_id'):
            user_id = context.user_data.get('_user_id')
            logger.info(f"✅ User ID from context._user_id: {user_id}")
        else:
            logger.warning("⚠️ No user_id found! Report will have NULL submitted_by_user_id")
        
        # ✅ الحصول على translator_id من جدول Translator إذا كان المستخدم مسجلاً
        actual_translator_id = data.get("translator_id")
        if not actual_translator_id and user_id:
            translator_record = session.query(Translator).filter_by(tg_user_id=user_id).first()
            if translator_record:
                actual_translator_id = translator_record.id
                logger.info(f"✅ Found translator_id from Translator table: {actual_translator_id} ({translator_record.full_name})")
        
        # إعداد حقول تأجيل الموعد
        app_reschedule_reason = None
        app_reschedule_return_date = None
        app_reschedule_return_reason = None
        
        if flow_type == "appointment_reschedule":
            app_reschedule_reason = data.get("app_reschedule_reason", "")
            app_reschedule_return_reason = data.get("app_reschedule_return_reason") or data.get("followup_reason", "")
            app_reschedule_return_date = data.get("app_reschedule_return_date") or data.get("followup_date")
            if app_reschedule_return_date:
                app_reschedule_return_date = to_naive_datetime(app_reschedule_return_date)
            logger.info(f"💾 حفظ حقول تأجيل الموعد: reason={app_reschedule_reason}, return_date={app_reschedule_return_date}, return_reason={app_reschedule_return_reason}")
        
        # ✅ حفظ tests في medications لـ new_consult (للاسترجاع لاحقاً)
        medications_field = None
        if flow_type == "new_consult":
            medications_field = data.get("tests", "")
        elif flow_type in ["surgery_consult", "operation"]:
            medications_field = data.get("tests", "") or data.get("medications", "")
        
        # إنشاء التقرير مع جميع الحقول المطلوبة
        new_report = Report(
            # IDs للربط
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id if department else None,
            doctor_id=doctor.id if doctor else None,
            translator_id=actual_translator_id,
            submitted_by_user_id=user_id,
            
            # ✅ الأسماء المكررة للبحث والطباعة السريعة
            patient_name=patient_name,
            hospital_name=hospital_name,
            department=dept_name_for_display or (department.name if department else None),
            doctor_name=doctor_name,
            translator_name=data.get("translator_name"),
            
            # محتوى التقرير
            complaint_text=complaint_text,
            doctor_decision=decision_text,
            medical_action=final_medical_action,
            diagnosis=data.get("diagnosis", ""),  # ✅ حفظ التشخيص بشكل منفصل
            medications=medications_field,  # ✅ حفظ tests في medications لـ new_consult
            notes=data.get("notes", ""),  # ✅ حفظ notes
            treatment_plan=data.get("treatment_plan", ""),  # ✅ حفظ treatment_plan
            case_status=data.get("status", ""),  # ✅ حفظ حالة الطوارئ
            
            # ✅ حقول خاصة
            room_number=data.get("room_number", "") or None,  # ✅ حفظ room_number
            
            # ✅ ملاحظة: operation_name_en, success_rate, benefit_rate غير موجودة في نموذج Report
            # سيتم إرسالها من data مباشرة في broadcast_data عند البث (انظر السطر 1638-1640)
            
            # التواريخ
            followup_date=followup_date,
            followup_time=data.get("followup_time", ""),  # ✅ حفظ وقت العودة
            followup_reason=data.get("followup_reason", "لا يوجد"),
            report_date=report_date,
            created_at=created_at,
            
            # ✅ حفظ حقول تأجيل الموعد
            app_reschedule_reason=app_reschedule_reason,
            app_reschedule_return_date=app_reschedule_return_date,
            app_reschedule_return_reason=app_reschedule_return_reason,
            
            # ✅ حقول الأشعة
            radiology_type=data.get("radiology_type", "") or None,
            radiology_delivery_date=to_naive_datetime(data.get("radiology_delivery_date")) if data.get("radiology_delivery_date") else None,
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
        final_dept_name = dept_name_for_display if dept_name_for_display else 'غير محدد'
        if not final_dept_name or final_dept_name == 'غير محدد':
            if department:
                final_dept_name = department.name
                logger.info(f"💾 Using department.name as fallback: {final_dept_name}")
            else:
                logger.warning("💾 ⚠️ No department found, using default 'غير محدد'")
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
                    time_12h = format_time_12h(data['followup_time'])
                    followup_display += f" - {time_12h}"

            # الحصول على معرف المستخدم الذي أنشأ التقرير
            user_id = None
            if query and hasattr(query, 'from_user') and query.from_user:
                user_id = query.from_user.id
            elif context.user_data.get('_user_id'):
                user_id = context.user_data.get('_user_id')
            
            broadcast_data = {
                'report_id': report_id,  # إضافة معرف التقرير لحفظ معرف الرسالة
                'report_date': data.get('report_date', datetime.now()).strftime('%Y-%m-%d %H:%M'),
                'patient_name': patient_name,
                'hospital_name': hospital_name,
                'department_name': final_dept_name,
                'doctor_name': doctor_name or 'لم يتم التحديد',
                'medical_action': final_medical_action,
                'complaint_text': complaint_text,
                'doctor_decision': decision_text,
                'followup_date': followup_display,
                'followup_time': data.get('followup_time'),  # ✅ إضافة وقت العودة
                'followup_reason': data.get('followup_reason', 'لا يوجد'),
                'translator_name': translator_name,
                'user_id': user_id,  # إضافة معرف المستخدم
                'translator_id': data.get("translator_id")  # إضافة معرف المترجم أيضاً
            }
            
            # ✅ إضافة التشخيص لجميع المسارات التي تحتاجه
            if flow_type in ["new_consult", "followup", "emergency", "surgery_consult", "final_consult"]:
                broadcast_data['diagnosis'] = data.get('diagnosis', '')
            
            # ✅ إضافة decision مباشرة لمسار followup و new_consult و emergency
            if flow_type in ["new_consult", "followup", "emergency"]:
                broadcast_data['decision'] = data.get('decision', '')
            
            # ✅ إضافة tests لمسار new_consult
            if flow_type == "new_consult":
                broadcast_data['tests'] = data.get('tests', '')
            
            # إضافة الحقول الفردية لـ surgery_consult لعرضها بشكل منفصل
            if flow_type == "surgery_consult":
                broadcast_data['decision'] = data.get('decision', '')
                broadcast_data['operation_name_en'] = data.get('operation_name_en', '')
                broadcast_data['success_rate'] = data.get('success_rate', '')
                broadcast_data['benefit_rate'] = data.get('benefit_rate', '')
                broadcast_data['tests'] = data.get('tests', '')
            
            # ✅ إضافة decision لمسار final_consult (منع التكرار)
            if flow_type == "final_consult":
                broadcast_data['decision'] = data.get('decision', '')
                broadcast_data['recommendations'] = data.get('recommendations', '') or data.get('treatment_plan', '') or data.get('notes', '')
            
            # ✅ إضافة room_number لمسار "متابعة في الرقود" إذا كان موجوداً
            if data.get('room_number'):
                broadcast_data['room_number'] = data.get('room_number')
            
            # إضافة الحقول الخاصة لمسار تأجيل موعد
            if flow_type == "appointment_reschedule":
                logger.info(f"📅 save_report_to_database: معالجة مسار appointment_reschedule")
                logger.info(f"📅 save_report_to_database: data keys = {list(data.keys())}")
                
                # إضافة سبب تأجيل الموعد
                app_reschedule_reason = data.get('app_reschedule_reason', '')
                logger.info(f"📅 save_report_to_database: app_reschedule_reason من data = {repr(app_reschedule_reason)}")
                
                # ✅ إذا لم يكن موجوداً في data، محاولة الحصول عليه من report_tmp
                if not app_reschedule_reason or not str(app_reschedule_reason).strip():
                    logger.warning(f"⚠️ save_report_to_database: app_reschedule_reason فارغ في data، محاولة الحصول من report_tmp")
                    report_tmp = context.user_data.get("report_tmp", {})
                    app_reschedule_reason_from_tmp = report_tmp.get('app_reschedule_reason', '')
                    if app_reschedule_reason_from_tmp and str(app_reschedule_reason_from_tmp).strip():
                        app_reschedule_reason = str(app_reschedule_reason_from_tmp).strip()
                        logger.info(f"✅ save_report_to_database: تم الحصول على app_reschedule_reason من report_tmp = {repr(app_reschedule_reason)}")
                
                # ✅ إذا كان موجوداً، إضافته إلى broadcast_data
                if app_reschedule_reason and str(app_reschedule_reason).strip():
                    broadcast_data['app_reschedule_reason'] = str(app_reschedule_reason).strip()
                    logger.info(f"✅ save_report_to_database: تم إضافة app_reschedule_reason إلى broadcast_data = {repr(broadcast_data.get('app_reschedule_reason'))}")
                else:
                    # ✅ محاولة استخراجه من doctor_decision إذا كان موجوداً
                    doctor_decision = broadcast_data.get('doctor_decision', '')
                    if doctor_decision and 'سبب تأجيل الموعد:' in str(doctor_decision):
                        parts = str(doctor_decision).split('سبب تأجيل الموعد:', 1)
                        if len(parts) > 1:
                            extracted_reason = parts[1].strip()
                            if '\n' in extracted_reason:
                                extracted_reason = extracted_reason.split('\n')[0].strip()
                            if extracted_reason:
                                broadcast_data['app_reschedule_reason'] = extracted_reason
                                logger.info(f"✅ save_report_to_database: تم استخراج app_reschedule_reason من doctor_decision = {repr(extracted_reason)}")
                            else:
                                logger.warning(f"⚠️ save_report_to_database: لم يتم العثور على app_reschedule_reason في doctor_decision")
                    else:
                        logger.warning(f"⚠️ save_report_to_database: app_reschedule_reason غير موجود في data أو report_tmp أو doctor_decision")
                
                # استخدام app_reschedule_return_date إذا كان موجوداً
                return_date = data.get('app_reschedule_return_date') or data.get('followup_date')
                if return_date:
                    if hasattr(return_date, 'strftime'):
                        broadcast_data['app_reschedule_return_date'] = return_date
                        broadcast_data['followup_date'] = return_date
                    else:
                        broadcast_data['app_reschedule_return_date'] = return_date
                        broadcast_data['followup_date'] = return_date
                else:
                    broadcast_data['app_reschedule_return_date'] = None
                    broadcast_data['followup_date'] = None
                
                # استخدام app_reschedule_return_reason إذا كان موجوداً
                return_reason = data.get('app_reschedule_return_reason') or data.get('followup_reason', 'لا يوجد')
                broadcast_data['app_reschedule_return_reason'] = return_reason
                broadcast_data['followup_reason'] = return_reason
                
                # إضافة followup_time إذا كان موجوداً
                if data.get('followup_time'):
                    broadcast_data['followup_time'] = data.get('followup_time')
            
            # ✅ إضافة حقول الأشعة والفحوصات لمسار radiology
            if flow_type == "radiology":
                logger.info(f"🔬 save_report_to_database: معالجة مسار radiology")
                logger.info(f"🔬 save_report_to_database: data keys = {list(data.keys())}")
                
                # إضافة نوع الأشعة والفحوصات
                radiology_type = data.get("radiology_type", "")
                logger.info(f"🔬 save_report_to_database: radiology_type من data = {repr(radiology_type)}")
                
                # ✅ إذا لم يكن موجوداً في data، محاولة الحصول عليه من report_tmp
                if not radiology_type or not str(radiology_type).strip():
                    logger.warning(f"⚠️ save_report_to_database: radiology_type فارغ في data، محاولة الحصول من report_tmp")
                    report_tmp = context.user_data.get("report_tmp", {})
                    radiology_type_from_tmp = report_tmp.get('radiology_type', '')
                    if radiology_type_from_tmp and str(radiology_type_from_tmp).strip():
                        radiology_type = str(radiology_type_from_tmp).strip()
                        logger.info(f"✅ save_report_to_database: تم الحصول على radiology_type من report_tmp = {repr(radiology_type)}")
                
                # ✅ إضافة radiology_type إلى broadcast_data
                if radiology_type and str(radiology_type).strip():
                    broadcast_data['radiology_type'] = str(radiology_type).strip()
                    logger.info(f"✅ save_report_to_database: تم إضافة radiology_type إلى broadcast_data = {repr(broadcast_data.get('radiology_type'))}")
                else:
                    logger.warning(f"⚠️ save_report_to_database: radiology_type غير موجود في data أو report_tmp")
                
                # إضافة تاريخ التسليم (radiology_delivery_date)
                radiology_delivery_date = data.get("radiology_delivery_date") or data.get("delivery_date")
                logger.info(f"🔬 save_report_to_database: radiology_delivery_date من data = {repr(radiology_delivery_date)}")
                
                # ✅ إذا لم يكن موجوداً في data، محاولة الحصول عليه من report_tmp
                if not radiology_delivery_date:
                    logger.warning(f"⚠️ save_report_to_database: radiology_delivery_date فارغ في data، محاولة الحصول من report_tmp")
                    report_tmp = context.user_data.get("report_tmp", {})
                    delivery_date_from_tmp = report_tmp.get('radiology_delivery_date') or report_tmp.get('delivery_date')
                    if delivery_date_from_tmp:
                        radiology_delivery_date = delivery_date_from_tmp
                        logger.info(f"✅ save_report_to_database: تم الحصول على radiology_delivery_date من report_tmp = {repr(radiology_delivery_date)}")
                
                # ✅ إضافة radiology_delivery_date إلى broadcast_data
                if radiology_delivery_date:
                    # تحويل التاريخ إلى string إذا كان datetime/date object
                    if hasattr(radiology_delivery_date, 'strftime'):
                        broadcast_data['radiology_delivery_date'] = radiology_delivery_date.strftime('%Y-%m-%d')
                    else:
                        broadcast_data['radiology_delivery_date'] = str(radiology_delivery_date)
                    logger.info(f"✅ save_report_to_database: تم إضافة radiology_delivery_date إلى broadcast_data = {repr(broadcast_data.get('radiology_delivery_date'))}")
                else:
                    logger.warning(f"⚠️ save_report_to_database: radiology_delivery_date غير موجود في data أو report_tmp")

            # ✅ إضافة logging قبل البث
            logger.info(f"📤 save_report_to_database: جاهز للبث - report_id={report_id}, flow_type={flow_type}")
            logger.info(f"📤 save_report_to_database: broadcast_data keys = {list(broadcast_data.keys())}")
            logger.info(f"📤 save_report_to_database: medical_action = {broadcast_data.get('medical_action')}")
            if flow_type == "radiology":
                logger.info(f"🔬 save_report_to_database: radiology_type في broadcast_data = {repr(broadcast_data.get('radiology_type'))}")
                logger.info(f"🔬 save_report_to_database: radiology_delivery_date في broadcast_data = {repr(broadcast_data.get('radiology_delivery_date'))}")
            
            try:
                await broadcast_new_report(context.bot, broadcast_data)
                logger.info(f"✅ save_report_to_database: تم بث التقرير #{report_id} لجميع المستخدمين")
            except Exception as broadcast_error:
                logger.error(f"❌ save_report_to_database: خطأ في بث التقرير #{report_id}: {broadcast_error}", exc_info=True)
                # ✅ لا نوقف العملية - نكمل حتى لو فشل البث
        except Exception as e:
            logger.error(f"❌ save_report_to_database: خطأ عام في حفظ التقرير: {e}", exc_info=True)

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
        
        # ✅ محاولة تعديل الرسالة - مع fallback إذا فشل
        try:
            await query.edit_message_text(
                success_message,
                parse_mode="Markdown"
            )
        except Exception as edit_err:
            logger.warning(f"⚠️ Cannot edit message (may be from reply_text): {edit_err}")
            # ✅ Fallback: إرسال رسالة جديدة
            try:
                if query.message:
                    await query.message.reply_text(
                        success_message,
                        parse_mode="Markdown"
                    )
                else:
                    # ✅ Fallback: استخدام answer
                    await query.answer(success_message[:200], show_alert=True)
            except Exception as fallback_err:
                logger.error(f"❌ Error in fallback message: {fallback_err}")
                await query.answer("✅ تم حفظ التقرير بنجاح", show_alert=True)

        # مسح البيانات المؤقتة
        context.user_data.pop("report_tmp", None)

        logger.info(f"تم حفظ التقرير #{report_id} - نوع: {flow_type}")

    except Exception as e:
        logger.error(f"خطأ في حفظ التقرير: {e}", exc_info=True)

        try:
            if 'session' in locals():
                session.rollback()
                session.close()
        except Exception:
            pass

        # ✅ محاولة تعديل الرسالة - مع fallback إذا فشل
        try:
            await query.edit_message_text(
                f"❌ **حدث خطأ أثناء الحفظ**\n\n"
                f"الخطأ: {str(e)}\n\n"
                f"يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except Exception as edit_err:
            logger.warning(f"⚠️ Cannot edit message (may be from reply_text): {edit_err}")
            # ✅ Fallback: إرسال رسالة جديدة
            try:
                if query.message:
                    await query.message.reply_text(
                        f"❌ **حدث خطأ أثناء الحفظ**\n\n"
                        f"الخطأ: {str(e)}\n\n"
                        f"يرجى المحاولة مرة أخرى.",
                        parse_mode="Markdown"
                    )
                else:
                    # ✅ Fallback: استخدام answer
                    await query.answer(f"❌ خطأ: {str(e)[:100]}", show_alert=True)
            except Exception as fallback_err:
                logger.error(f"❌ Error in fallback error message: {fallback_err}")
                await query.answer("❌ حدث خطأ أثناء الحفظ", show_alert=True)


# =============================
# Edit Functions (simplified - will be expanded)
# =============================

# =============================
# Edit Functions - دوال التعديل قبل الحفظ
# =============================

async def show_edit_fields_menu(query, context, flow_type):
    """عرض قائمة الحقول القابلة للتعديل"""
    try:
        data = context.user_data.get("report_tmp", {})
        medical_action = data.get("medical_action", "")
        
        logger.info(f"🔍 [EDIT_MENU] show_edit_fields_menu: flow_type={flow_type}, medical_action={medical_action}")
        logger.info(f"🔍 [EDIT_MENU] report_tmp keys: {list(data.keys())}")
        
        editable_fields = get_editable_fields_by_flow_type(flow_type)
        logger.info(f"🔍 [EDIT_MENU] editable_fields before processing: {[fk for fk, _ in editable_fields]}")
        
        # ✅ إضافة room_number لمسار "متابعة في الرقود" ديناميكياً
        # استخدام strip() لضمان تطابق النص
        action_clean = medical_action.strip() if medical_action else ""
        # ✅ تحسين التحقق: استخدام in بدلاً من == للتعامل مع المسافات أو الاختلافات البسيطة
        is_inpatient_followup = (flow_type == "followup" and "متابعة في الرقود" in action_clean)
        
        # ✅ أو إذا كان room_number موجوداً بالفعل في البيانات (بغض النظر عن medical_action)
        has_room_data = _has_field_value(data, "room_number")
        
        if is_inpatient_followup or has_room_data:
            logger.info("✅ [EDIT_MENU] مسار 'متابعة في الرقود' أو يوجد بيانات - إضافة room_number")
            # ✅ التحقق من وجود room_number في القائمة
            has_room_number = any(fk == "room_number" for fk, _ in editable_fields)
            logger.info(f"🔍 [EDIT_MENU] has_room_number: {has_room_number}")
            
            if not has_room_number:
                # ✅ البحث عن موضع إدراج room_number (بعد decision وقبل followup_date)
                room_field = ("room_number", "🏥 رقم الغرفة والطابق")
                decision_index = None
                followup_date_index = None
                
                for i, (field_key, _) in enumerate(editable_fields):
                    if field_key == "decision":
                        decision_index = i
                        logger.info(f"🔍 [EDIT_MENU] Found decision at index: {decision_index}")
                    elif field_key == "followup_date" and followup_date_index is None:
                        followup_date_index = i
                        logger.info(f"🔍 [EDIT_MENU] Found followup_date at index: {followup_date_index}")
                
                # ✅ إدراج room_number بعد decision مباشرة، أو قبل followup_date، أو في النهاية
                if decision_index is not None:
                    editable_fields.insert(decision_index + 1, room_field)
                    logger.info(f"✅ [EDIT_MENU] تم إضافة room_number بعد decision (index: {decision_index + 1})")
                elif followup_date_index is not None:
                    editable_fields.insert(followup_date_index, room_field)
                    logger.info(f"✅ [EDIT_MENU] تم إضافة room_number قبل followup_date (index: {followup_date_index})")
                else:
                    editable_fields.append(room_field)
                    logger.info(f"✅ [EDIT_MENU] تم إضافة room_number في النهاية")
        else:
            logger.info(f"⚠️ [EDIT_MENU] لا يتم إضافة room_number: flow_type={flow_type}, medical_action={medical_action}")
        
        # ✅ إزالة room_number من مسار "مراجعة / عودة دورية" إذا كان موجوداً
        # تحسين التحقق ليشمل المسافات والاختلافات البسيطة
        # ✅ أيضاً إزالة room_number إذا كان flow_type == "periodic_followup"
        is_periodic_followup = (
            flow_type == "periodic_followup" or
            (flow_type == "followup" and "مراجعة / عودة دورية" in (medical_action or ""))
        )
        if is_periodic_followup:
            logger.info("✅ [EDIT_MENU] مسار 'عودة دورية' - إزالة room_number إذا كان موجوداً")
            editable_fields = [(fk, fd) for fk, fd in editable_fields if fk != "room_number"]
            logger.info(f"✅ [EDIT_MENU] تم إزالة room_number من القائمة")
        
        logger.info(f"🔍 [EDIT_MENU] editable_fields after processing: {[fk for fk, _ in editable_fields]}")
        
        # ✅ تصفية الحقول: عرض جميع الحقول (تم تعطيل التصفية بناءً على طلب المستخدم)
        fields_with_values = []
        for field_key, field_display in editable_fields:
            # عرض جميع الحقول سواء كانت فارغة أم لا
            fields_with_values.append((field_key, field_display))
            logger.info(f"✅ [EDIT_MENU] إضافة حقل '{field_key}' للقائمة")
        
        editable_fields = fields_with_values
        logger.info(f"✅ [EDIT_MENU] الحقول النهائية بعد التصفية: {[fk for fk, _ in editable_fields]}")
        
        if not editable_fields:
            await query.edit_message_text(
                "⚠️ **لا توجد حقول مدخلة للتعديل**\n\n"
                "لم يتم إدخال أي بيانات بعد.\n"
                "يرجى استخدام زر '🔙 رجوع' للرجوع إلى الخطوات السابقة.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        text = "✏️ **تعديل التقرير**\n\n"
        text += "اختر الحقل الذي تريد تعديله:\n\n"
        
        keyboard = []
        for field_key, field_display in editable_fields:
            # الحصول على القيمة الحالية (مع التحقق من الحقول المشتقة)
            current_value = data.get(field_key)
            
            # ✅ البحث في الحقول المشتقة إذا لم توجد قيمة مباشرة
            if not current_value:
                field_aliases = {
                    "complaint": ["complaint_text", "complaint"],
                    "decision": ["doctor_decision", "decision"],
                    "tests": ["notes", "tests"],
                    "operation_details": ["notes", "operation_details"],
                    "delivery_date": ["radiology_delivery_date", "delivery_date"],
                    "radiology_delivery_date": ["delivery_date", "radiology_delivery_date"],
                    "room_number": ["room_floor", "room_number"],
                    "device_name": ["device_details", "device_name"],
                    "device_details": ["device_name", "device_details"],
                    "app_reschedule_return_date": ["followup_date", "app_reschedule_return_date"],
                    "app_reschedule_return_reason": ["followup_reason", "app_reschedule_return_reason"],
                }
                aliases = field_aliases.get(field_key, [])
                for alias in aliases:
                    alias_value = data.get(alias)
                    if alias_value and str(alias_value).strip() and str(alias_value).strip() not in ["غير محدد", "لا يوجد", "None", "null", ""]:
                        current_value = alias_value
                        break
            
            # ✅ تنسيق القيمة للعرض
            if isinstance(current_value, datetime):
                current_value = current_value.strftime('%Y-%m-%d %H:%M')
            elif current_value:
                current_value_str = str(current_value).strip()
                if len(current_value_str) > 30:
                    current_value = current_value_str[:27] + "..."
                else:
                    current_value = current_value_str
            
            button_text = f"{field_display}"
            if current_value and current_value != "غير محدد":
                button_text += f" ({str(current_value)[:20]})"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"edit_field:{flow_type}:{field_key}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_summary:{flow_type}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        logger.info(f"✅ تم عرض قائمة الحقول القابلة للتعديل ({len(editable_fields)} حقل)")
        # ✅ إرجاع state التأكيد - سيتم التعامل مع edit_field callback عبر router
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
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
    try:
        # ✅ التأكد من حفظ medical_action في report_tmp إذا كان مفقوداً
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
            # ✅ إذا كان flow_type == "followup" و stored_flow_type == "periodic_followup"، استخدم periodic_followup
            if flow_type == "followup" and stored_flow_type == "periodic_followup":
                flow_type = "periodic_followup"
                logger.info(f"✅ [EDIT_BEFORE_SAVE] استخدام current_flow المحفوظ: {flow_type}")
            # ✅ إذا كان flow_type == "followup" و stored_flow_type == "inpatient_followup"، استخدم inpatient_followup
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

        # ✅ إذا كان flow_type == "followup" و medical_action مفقود، نحاول تحديده بناءً على الحقول الموجودة
        if flow_type == "followup" and not medical_action:
            # ✅ التحقق من وجود room_number في report_tmp لتحديد نوع المسار
            if data.get("room_number"):
                medical_action = "متابعة في الرقود"
                data["medical_action"] = medical_action
                logger.info(f"✅ [EDIT_BEFORE_SAVE] تم تعيين medical_action='متابعة في الرقود' بناءً على وجود room_number")
            else:
                # ✅ افتراض أنه "مراجعة / عودة دورية" إذا لم يكن room_number موجوداً
                medical_action = "مراجعة / عودة دورية"
                data["medical_action"] = medical_action
                # ✅ تحديث flow_type إلى periodic_followup
                flow_type = "periodic_followup"
                logger.info(f"✅ [EDIT_BEFORE_SAVE] تم تعيين medical_action='مراجعة / عودة دورية' و flow_type='periodic_followup'")

        logger.info(f"✏️ [EDIT_BEFORE_SAVE] handle_edit_before_save: flow_type={flow_type}, medical_action={medical_action}")
        logger.info(f"✏️ [EDIT_BEFORE_SAVE] report_tmp keys: {list(data.keys())}")

        # حفظ flow_type في report_tmp
        data["current_flow"] = flow_type

        # ✅ استخدام النظام الموحد للتعديل (مثل draft editing)
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

