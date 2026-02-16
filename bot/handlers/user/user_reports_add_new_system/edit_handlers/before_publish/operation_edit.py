# =============================
# Operation - Edit Before Publish Handlers
# =============================
# handlers منفصلة تماماً لمسار "عملية"
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
        OPERATION_CONFIRM
    )
    from bot.handlers.user.user_reports_add_new_system.flows.new_consult import (
        _render_followup_calendar
    )
except ImportError:
    logger.error("❌ Cannot import required modules for operation_edit")
    OPERATION_CONFIRM = None
    get_confirm_state = lambda x: None
    show_final_summary = None
    _render_followup_calendar = None


# =============================
# Field Selection Handler
# =============================

async def handle_operation_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة اختيار حقل للتعديل - مسار عملية
    كل حقل له معالجة منفصلة تماماً
    """
    try:
        query = update.callback_query
        await query.answer()
        
        # استخراج field_key من callback_data
        # Format: "edit_field:operation:field_key"
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        field_key = parts[2]
        flow_type = "operation"
        
        logger.info(f"✏️ [OPERATION] handle_edit_field_selection: field_key={field_key}")
        
        data = context.user_data.get("report_tmp", {})
        current_value = data.get(field_key, "غير محدد")
        
        # حفظ معلومات التعديل
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        
        # أسماء الحقول للعرض - فقط الحقول المدخلة يدوياً
        field_names = {
            "operation_details": "⚕️ تفاصيل العملية بالعربي",
            "operation_name_en": "🔤 اسم العملية بالإنجليزي",
            "notes": "📝 ملاحظات",
            "followup_date": "📅 موعد العودة",
            "followup_time": "⏰ وقت العودة",
            "followup_reason": "✍️ سبب العودة",
        }
        
        field_display_name = field_names.get(field_key, field_key)
        
        # تنظيف القيمة الحالية للعرض
        if isinstance(current_value, str) and len(current_value) > 200:
            current_value_display = current_value[:200] + "..."
        else:
            current_value_display = str(current_value) if current_value else "غير محدد"
        
        # عرض واجهة التعديل - منطق خاص لكل حقل
        if field_key == "followup_date":
            # ✅ استخدام التقويم التفاعلي بدلاً من إدخال نصي
            if _render_followup_calendar:
                # حفظ معلومات التعديل في context للاستخدام في معالجة callbacks التقويم
                context.user_data["edit_field_key"] = field_key
                context.user_data["edit_flow_type"] = flow_type
                # عرض التقويم
                await _render_followup_calendar(query, context)
            else:
                # Fallback إلى إدخال نصي إذا لم يكن التقويم متاحاً
                await query.edit_message_text(
                    f"📅 **تعديل {field_display_name}**\n\n"
                    f"**القيمة الحالية:** {current_value_display}\n\n"
                    f"📝 أرسل التاريخ الجديد (مثال: 2025-01-15):",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")],
                        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                    ]),
                    parse_mode="Markdown"
                )
        else:
            # للحقول النصية
            await query.edit_message_text(
                f"✏️ **تعديل {field_display_name}**\n\n"
                f"**القيمة الحالية:**\n{current_value_display}\n\n"
                f"📝 أرسل القيمة الجديدة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"save:{flow_type}")],
                    [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
                ]),
                parse_mode="Markdown"
            )
        
        confirm_state = get_confirm_state(flow_type)
        context.user_data['_conversation_state'] = confirm_state
        logger.info(f"✅ [OPERATION] تم طلب تعديل حقل: {field_key}, state: {confirm_state}")
        return confirm_state
        
    except Exception as e:
        logger.error(f"❌ [OPERATION] خطأ في handle_edit_field_selection: {e}", exc_info=True)
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

async def handle_operation_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة إدخال القيمة الجديدة - مسار عملية
    منطق منفصل تماماً
    """
    try:
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            from bot.handlers.user.user_reports_add_new_system import start_report
            return await start_report(update, context)
        
        field_key = context.user_data.get("edit_field_key")
        flow_type = context.user_data.get("edit_flow_type")
        
        # ✅ التحقق من أن هذا handler مخصص لمسار operation فقط
        if flow_type != "operation":
            logger.warning(f"⚠️ [OPERATION] handle_edit_field_input: flow_type={flow_type} ليس operation - تجاهل")
            return
        
        if not field_key:
            logger.warning("⚠️ [OPERATION] handle_edit_field_input: لا يوجد حقل للتعديل - تجاهل")
            return
        
        logger.info(f"✏️ [OPERATION] handle_edit_field_input: field_key={field_key}, text={text[:50]}")
        
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
        if field_key == "followup_date":
            # تحليل التاريخ والوقت إذا كان موجوداً
            if " " in text:
                parts = text.split(" ", 1)
                data["followup_date"] = parts[0]
                if len(parts) > 1:
                    data["followup_time"] = parts[1]
            else:
                data["followup_date"] = text
                if "followup_time" not in data:
                    data["followup_time"] = ""
        else:
            # للحقول النصية الأخرى (operation_details, operation_name_en, notes, followup_reason)
            data[field_key] = text
        
        # مسح معلومات التعديل
        context.user_data.pop("edit_field_key", None)
        
        # ✅ التأكد من حفظ current_flow في report_tmp للاستخدام في النشر
        data["current_flow"] = flow_type
        logger.info(f"✅ [OPERATION] تم حفظ current_flow={flow_type} في report_tmp")
        
        logger.info(f"✅ [OPERATION] تم حفظ التعديل: {field_key} = {text[:50]}")
        
        # ✅ إعادة عرض الملخص الكامل
        try:
            await show_final_summary(update.message, context, flow_type)
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            logger.info(f"✅ [OPERATION] تم عرض الملخص بعد التعديل، flow_type={flow_type}, confirm_state={confirm_state}")
            return confirm_state
        except Exception as e:
            logger.error(f"❌ [OPERATION] خطأ في عرض الملخص بعد التعديل: {e}", exc_info=True)
            await update.message.reply_text(
                "✅ **تم حفظ التعديل بنجاح**\n\n"
                "يرجى استخدام زر '🔙 رجوع' للرجوع إلى الملخص.",
                parse_mode="Markdown"
            )
            confirm_state = get_confirm_state(flow_type)
            return confirm_state
            
    except Exception as e:
        logger.error(f"❌ [OPERATION] خطأ في handle_edit_field_input: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء حفظ التعديل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END

