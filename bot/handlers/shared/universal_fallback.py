# ================================================
# bot/handlers/shared/universal_fallback.py
# 🛡️ معالج شامل لجميع الرسائل والأزرار غير المعالجة
# ================================================

import logging
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.error import TimedOut, NetworkError, BadRequest
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# قائمة الـ callbacks المعروفة التي يتم معالجتها بواسطة handlers أخرى
KNOWN_CALLBACKS = [
    # ===========================
    # نظام إضافة التقارير (ConversationHandler)
    # ===========================
    r"^patient_idx:",     # اختيار المريض
    r"^user_patient_page:", # صفحات المرضى
    r"^hospital_idx:",    # اختيار المستشفى
    r"^dept_idx:",        # اختيار القسم
    r"^subdept_idx:",     # اختيار القسم الفرعي
    r"^doctor_idx:",      # اختيار الطبيب
    r"^doctor_page:",     # صفحات الأطباء
    r"^action_idx:",      # اختيار نوع الإجراء
    r"^hospital_page:",   # صفحات المستشفيات
    r"^hosp_page:",       # صفحات المستشفيات (بديل)
    r"^dept_page:",       # صفحات الأقسام
    r"^subdept_page:",    # صفحات الأقسام الفرعية
    r"^date:",            # اختيار التاريخ
    r"^main_cal_",        # التقويم الرئيسي
    r"^time_hour:",       # اختيار الساعة
    r"^time_minute:",     # اختيار الدقائق
    r"^time_skip",        # تخطي الوقت
    r"^doctor_manual",    # إدخال الطبيب يدوياً
    r"^simple_translator:", # اختيار المترجم البسيط
    r"^nav:",             # أزرار التنقل
    r"^noop$",            # زر لا يفعل شيء
    r"^abort$",           # إلغاء
    r"^skip",             # تخطي
    
    # التدفقات (flows) - نظام التقارير
    r"^new_consult",
    r"^followup",
    r"^emergency",
    r"^admission",
    r"^surgery",
    r"^operation",
    r"^final_consult",
    r"^discharge",
    r"^rehab",
    r"^radiology",
    r"^app_reschedule",
    r"^flow_",
    r"^save_report",
    r"^edit_before_save",
    r"^edit_draft:",
    r"^edit_field:",
    r"^draft_field:",
    r"^confirm_save",
    
    # ===========================
    # Admin
    # ===========================
    r"^admin:",
    r"^aa:",               # إدارة الأدمنين
    r"^remove_admin:",     # حذف أدمن
    r"^confirm_remove:",   # تأكيد حذف أدمن
    r"^um:",               # إدارة المستخدمين
    r"^suspend_reason:",   # أسباب التجميد
    r"^confirm_delete:",   # تأكيد الحذف
    r"^back_to_admin$",
    r"^back_to_main$",
    r"^back_to_schedule$",
    
    # إدارة الجدول (Admin)
    r"^upload_schedule$",
    r"^view_schedule$",
    r"^track_reports$",
    r"^send_notifications$",
    r"^confirm_schedule$",
    r"^cancel_upload$",
    
    # إدارة المرضى (Admin)
    r"^manage_patients$",
    r"^view_patient_names$",
    r"^add_patient_name$",
    r"^edit_patient_name$",
    r"^delete_patient_name$",
    r"^confirm_delete:\d+$",
    r"^select_edit:\d+$",
    r"^sched_patient_page:",
    r"^delete_patient_page:",
    r"^edit_patient_page:",
    r"^view_patients_page:",
    
    # إدارة المستشفيات (Admin)
    r"^manage_hospitals$",
    r"^view_hospitals$",
    r"^add_hospital$",
    r"^edit_hospital$",
    r"^delete_hospital$",
    r"^sync_hospitals$",
    r"^confirm_delete_hosp:\d+$",
    r"^select_edit_hosp:\d+$",
    r"^delete_hosp_page:",
    r"^edit_hosp_page:",
    r"^view_hospitals_page:",
    
    # إدارة المترجمين (Admin)
    r"^manage_translators$",
    r"^view_translators$",
    r"^add_translator$",
    r"^edit_translator$",
    r"^delete_translator$",
    r"^sync_translators$",
    r"^confirm_delete_trans:\d+$",
    r"^select_edit_trans:\d+$",
    r"^delete_trans_page:",
    r"^edit_trans_page:",
    r"^view_translators_page:",
    r"^cancel_translator_input$",
    r"^cancel_hospital_input$",

    # ===========================
    # نظام تعديل وحذف التقارير للمستخدمين
    # ===========================
    r"^edit_report:",        # تعديل تقرير محدد
    r"^edit_field:",         # تعديل حقل محدد (مكرر لكن للتوضيح)
    r"^edit_republish$",     # إعادة نشر التقرير
    r"^edit_back",           # رجوع في نظام التعديل
    r"^edit_cancel$",        # إلغاء التعديل
    r"^edit_confirm_save$",  # تأكيد حفظ التعديل
    r"^edit_save_and_publish$",  # حفظ ونشر التقرير بعد التعديل
    r"^edit_followup:",      # تعديل موعد المتابعة
    r"^edit_time:",          # تعديل الوقت
    r"^edit_translator:",    # تعديل المترجم
    r"^edit_back_to_fields$", # رجوع لقائمة الحقول
    r"^delete_report:",      # حذف تقرير محدد
    r"^delete_confirm$",     # تأكيد الحذف
    r"^delete_back$",        # رجوع في نظام الحذف
    r"^delete_cancel$",      # إلغاء الحذف
    
    # ===========================
    # واجهة المستخدم الأخرى
    # ===========================
    r"^start_report$",
    r"^user_action:add_report$",
    r"^add_report$",
    r"^edit_reports$",
    r"^start_main_menu$",
    
    # الجدول
    r"^upload_schedule$",
    r"^view_schedule$",
    r"^track_reports$",
    r"^send_notifications$",
    r"^daily_patients$",
    
    # أخرى
    r"^cancel",
    r"^save:",
    r"^publish:",
    r"^edit:",
    r"^um:",
    r"^back_",
    r"^approve:",
    r"^reject:",
]

# ================================================
# Safe Keyboard Builder
# ================================================

def get_back_keyboard(callback_data="back_to_main"):
    """إنشاء لوحة مفاتيح رجوع آمنة"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data=callback_data)]
    ])

# ================================================
# Universal Fallback Handler for Callbacks
# ================================================

def is_known_callback(callback_data: str) -> bool:
    """التحقق مما إذا كان الـ callback معروفاً ومعالجاً بواسطة handler آخر"""
    for pattern in KNOWN_CALLBACKS:
        if re.match(pattern, callback_data):
            return True
    return False

async def handle_any_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج شامل لأي callback query - يضمن عدم تعليق البوت أبداً
    هذا الـ handler يعمل فقط على الـ callbacks غير المعروفة
    """
    query = update.callback_query
    
    if not query:
        return
    
    callback_data = query.data or ""
    
    # تجاهل الـ callbacks المعروفة - ستتم معالجتها بواسطة handlers أخرى
    if is_known_callback(callback_data):
        # لا نفعل شيء - الـ handler المناسب سيتعامل معها
        return
    
    try:
        # الرد على الـ callback لمنع التعليق (loading indicator)
        try:
            await query.answer()
        except Exception:
            pass
        
        logger.warning(f"⚠️ Unhandled callback received: {callback_data}")
        
        # للـ callbacks غير المعروفة، نرسل رسالة بسيطة فقط
        # بدون محاولة تخمين نوع الـ callback
        try:
            await query.answer("⚠️ هذا الزر غير متاح حالياً", show_alert=False)
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"❌ Error in handle_any_callback: {e}")

async def _safe_edit_message(query, text, keyboard=None):
    """تعديل الرسالة بشكل آمن مع معالجة جميع الأخطاء"""
    try:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except BadRequest as e:
        error_msg = str(e).lower()
        # تجاهل أخطاء "message is not modified" و "message to edit not found"
        if "not modified" in error_msg or "not found" in error_msg:
            pass
        else:
            logger.warning(f"⚠️ BadRequest in _safe_edit_message: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Error in _safe_edit_message: {e}")

# ================================================
# Universal Fallback Handler for Messages
# ================================================

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج شامل لأي رسالة غير معالجة
    """
    try:
        if not update.message:
            return
        
        message_text = update.message.text or ""
        user = update.effective_user
        
        # ✅ السماح لأزرار ConversationHandlers بالمرور
        # هذه الأزرار يجب أن تصل إلى handlers المخصصة لها
        CONVERSATION_BUTTONS = [
            "✏️ تعديل التقارير",
            "🗑️ حذف التقارير",
            "📝 إضافة تقرير جديد",
            "❌ إلغاء العملية الحالية"
        ]
        
        if message_text in CONVERSATION_BUTTONS:
            # دع ConversationHandler يتعامل مع هذا
            return
        
        # التحقق من وجود conversation نشط - لا نتدخل
        conversation_keys = [
            'waiting_for_', 'edit_', 'add_', '_state', 'report_tmp',
            'admin_', '_conversation_state'
        ]
        if any(key in str(context.user_data.keys()) for key in conversation_keys):
            # محادثة نشطة - لا نتدخل
            return
        
        # رسائل مساعدة
        if any(word in message_text.lower() for word in ["مساعدة", "help", "مساعده"]):
            await update.message.reply_text(
                "ℹ️ **مساعدة**\n\n"
                "استخدم /start للوصول للقائمة الرئيسية\n"
                "استخدم /cancel لإلغاء أي عملية جارية",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # رسائل إلغاء
        if any(word in message_text.lower() for word in ["إلغاء", "الغاء", "cancel"]):
            context.user_data.clear()
            await update.message.reply_text(
                "✅ **تم الإلغاء**\n\n"
                "استخدم /start للبدء من جديد",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # تجاهل الرسائل الأخرى بصمت
        logger.debug(f"📝 Ignoring message: {message_text[:50]}")
        
    except Exception as e:
        logger.error(f"❌ Error in handle_any_message: {e}")

# ================================================
# Registration
# ================================================

def register(app):
    """تسجيل معالجات الـ fallback الشاملة"""
    logger.info("📋 تسجيل universal fallback handlers...")
    
    # 1. معالج لجميع callback queries غير المعالجة (أولوية منخفضة جداً)
    app.add_handler(
        CallbackQueryHandler(handle_any_callback),
        group=999  # آخر شيء يتم تنفيذه
    )
    
    # 2. ❌ تم تعطيل معالج الرسائل النصية لأنه يتداخل مع ConversationHandlers
    # ConversationHandlers تحتاج أن تلتقط الرسائل النصية للأزرار
    # app.add_handler(
    #     MessageHandler(
    #         filters.TEXT & ~filters.COMMAND,
    #         handle_any_message
    #     ),
    #     group=999
    # )
    
    logger.info("✅ تم تسجيل universal fallback handlers (callbacks فقط) في group 999")

