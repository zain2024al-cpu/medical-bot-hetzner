# =============================
# Final Consult - Edit Before Publish Handlers
# =============================
# handlers منفصلة تماماً لمسار "استشارة أخيرة"
# كل حقل له handler منفصل للتعديل قبل النشر
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# استيراد imports مطلوبة
try:
    from bot.handlers.user.user_reports_add_new_system.flows.shared import (
        get_confirm_state,
        show_final_summary,
        FINAL_CONSULT_CONFIRM
    )
except ImportError:
    logger.error("❌ Cannot import required modules for final_consult_edit")
    FINAL_CONSULT_CONFIRM = None
    get_confirm_state = lambda x: None
    show_final_summary = None


# =============================
# Field Selection Handler
# =============================

async def handle_final_consult_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة اختيار حقل للتعديل - مسار استشارة أخيرة
    كل حقل له معالجة منفصلة تماماً
    """
    try:
        query = update.callback_query
        await query.answer()
        
        # استخراج field_key من callback_data
        # Format: "edit_field:final_consult:field_key"
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        field_key = parts[2]
        flow_type = "final_consult"
        
        logger.info(f"✏️ [FINAL_CONSULT] handle_edit_field_selection: field_key={field_key}")
        
        data = context.user_data.get("report_tmp", {})
        current_value = data.get(field_key, "غير محدد")
        
        # حفظ معلومات التعديل
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        
        # أسماء الحقول للعرض - فقط الحقول المدخلة يدوياً
        field_names = {
            "diagnosis": "🔬 التشخيص النهائي",
            "decision": "📝 قرار الطبيب",
            "recommendations": "💡 التوصيات الطبية",
        }
        
        field_display_name = field_names.get(field_key, field_key)
        
        # تنظيف القيمة الحالية للعرض
        if isinstance(current_value, str) and len(current_value) > 200:
            current_value_display = current_value[:200] + "..."
        else:
            current_value_display = str(current_value) if current_value else "غير محدد"
        
        # عرض واجهة التعديل - للحقول النصية
        await query.edit_message_text(
            f"✏️ **تعديل {field_display_name}**\n\n"
            f"**القيمة الحالية:**\n{current_value_display}\n\n"
            f"📝 أرسل القيمة الجديدة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_edit_fields:{flow_type}")],
            ]),
            parse_mode="Markdown"
        )
        
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        logger.info(f"✅ [FINAL_CONSULT] تم طلب تعديل حقل: {field_key}, state: {confirm_state}")
        return confirm_state
        
    except Exception as e:
        logger.error(f"❌ [FINAL_CONSULT] خطأ في handle_edit_field_selection: {e}", exc_info=True)
        try:
            query = update.callback_query
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء اختيار الحقل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END


# =============================
# Field Input Handler
# =============================

async def handle_final_consult_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة إدخال القيمة الجديدة - مسار استشارة أخيرة
    منطق منفصل تماماً
    """
    try:
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            from bot.handlers.user.user_reports_add_new_system import start_report
            return await start_report(update, context)
        
        field_key = context.user_data.get("edit_field_key")
        flow_type = context.user_data.get("edit_flow_type")
        
        # ✅ التحقق من أن هذا handler مخصص لمسار final_consult فقط
        if flow_type != "final_consult":
            logger.warning(f"⚠️ [FINAL_CONSULT] handle_edit_field_input: flow_type={flow_type} ليس final_consult - تجاهل")
            return
        
        if not field_key:
            logger.warning("⚠️ [FINAL_CONSULT] handle_edit_field_input: لا يوجد حقل للتعديل - تجاهل")
            return
        
        logger.info(f"✏️ [FINAL_CONSULT] handle_edit_field_input: field_key={field_key}, text={text[:50]}")
        
        if not text or len(text) < 1:
            await update.message.reply_text(
                "⚠️ **خطأ:** النص فارغ\n\n"
                "يرجى إرسال قيمة صحيحة.",
                parse_mode="Markdown"
            )
            confirm_state = get_confirm_state(flow_type)
            return confirm_state
        
        # حفظ القيمة الجديدة في report_tmp
        data = context.user_data.setdefault("report_tmp", {})
        
        # ✅ منطق خاص لكل حقل - منفصل تماماً
        if field_key == "decision":
            data["decision"] = text
            data["doctor_decision"] = text  # نسخة للتوافق
        elif field_key == "recommendations":
            data["recommendations"] = text
            data["treatment_plan"] = text  # نسخة للتوافق
        else:
            # للحقول الأخرى (diagnosis, report_date, patient_name, hospital_name, department_name, doctor_name)
            data[field_key] = text
        
        # مسح معلومات التعديل
        context.user_data.pop("edit_field_key", None)
        
        # ✅ التأكد من حفظ current_flow في report_tmp للاستخدام في النشر
        data["current_flow"] = flow_type
        logger.info(f"✅ [FINAL_CONSULT] تم حفظ current_flow={flow_type} في report_tmp")
        
        logger.info(f"✅ [FINAL_CONSULT] تم حفظ التعديل: {field_key} = {text[:50]}")
        
        # ✅ إعادة عرض الملخص الكامل
        try:
            await show_final_summary(update.message, context, flow_type)
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            logger.info(f"✅ [FINAL_CONSULT] تم عرض الملخص بعد التعديل، flow_type={flow_type}, confirm_state={confirm_state}")
            return confirm_state
        except Exception as e:
            logger.error(f"❌ [FINAL_CONSULT] خطأ في عرض الملخص بعد التعديل: {e}", exc_info=True)
            await update.message.reply_text(
                "✅ **تم حفظ التعديل بنجاح**\n\n"
                "يرجى استخدام زر '🔙 رجوع' للرجوع إلى الملخص.",
                parse_mode="Markdown"
            )
            confirm_state = get_confirm_state(flow_type)
            return confirm_state
            
    except Exception as e:
        logger.error(f"❌ [FINAL_CONSULT] خطأ في handle_edit_field_input: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء حفظ التعديل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END




