# =============================
# Followup - Edit Before Publish Handlers
# =============================
# handlers منفصلة تماماً لمسار "عودة دورية" و "متابعة في الرقود"
# كل حقل له handler منفصل للتعديل قبل النشر
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

try:
    from bot.handlers.user.user_reports_add_new_system.flows.shared import (
        get_confirm_state,
        show_final_summary,
        FOLLOWUP_CONFIRM
    )
    from bot.handlers.user.user_reports_add_new_system.edit_handlers.draft.handlers import (
        _render_draft_edit_followup_calendar
    )
except ImportError:
    logger.error("❌ Cannot import required modules for followup_edit")
    FOLLOWUP_CONFIRM = None
    get_confirm_state = lambda x: None
    show_final_summary = None
    _render_draft_edit_followup_calendar = None


async def handle_followup_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة اختيار حقل للتعديل - مسار followup
    """
    try:
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        field_key = parts[2]

        logger.info(f"✏️ [FOLLOWUP] handle_edit_field_selection: field_key={field_key}")

        data = context.user_data.get("report_tmp", {})
        current_value = data.get(field_key, "غير محدد")
        medical_action = data.get("medical_action", "")

        # تحديد flow_type الفعلي بناءً على medical_action
        if medical_action == "مراجعة / عودة دورية":
            flow_type = "periodic_followup"
        elif medical_action == "متابعة في الرقود":
            flow_type = "inpatient_followup"
        else:
            flow_type = "followup"

        # حفظ معلومات التعديل
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        
        # أسماء الحقول للعرض - فقط الحقول المدخلة يدوياً
        field_names = {
            "complaint": "💬 شكوى المريض",
            "diagnosis": "🔬 التشخيص الطبي",
            "decision": "📝 قرار الطبيب",
            "room_number": "🚪 رقم الغرفة والطابق",
            "followup_date": "📅 موعد العودة",
            "followup_time": "⏰ وقت العودة",
            "followup_reason": "✍️ سبب العودة",
        }
        
        field_display_name = field_names.get(field_key, field_key)
        
        # ✅ التحقق من room_number - فقط لـ "متابعة في الرقود"
        if field_key == "room_number" and medical_action != "متابعة في الرقود":
            await query.edit_message_text(
                "❌ **خطأ**\n\n"
                "حقل رقم الغرفة متاح فقط لمسار 'متابعة في الرقود'.",
                parse_mode="Markdown"
            )
            return FOLLOWUP_CONFIRM
        
        # تنظيف القيمة الحالية
        if isinstance(current_value, str) and len(current_value) > 200:
            current_value_display = current_value[:200] + "..."
        else:
            current_value_display = str(current_value) if current_value else "غير محدد"
        
        # عرض واجهة التعديل
        if field_key == "followup_date":
            # ✅ استخدام التقويم التفاعلي بدلاً من إدخال نصي
            context.user_data["edit_field_key"] = field_key
            context.user_data["edit_flow_type"] = flow_type
            context.user_data['editing_draft_date'] = True
            if _render_draft_edit_followup_calendar:
                await _render_draft_edit_followup_calendar(query, context)
                context.user_data['_conversation_state'] = "EDIT_DRAFT_FOLLOWUP_CALENDAR"
                return "EDIT_DRAFT_FOLLOWUP_CALENDAR"
            else:
                # Fallback إلى إدخال نصي إذا لم يكن التقويم متاحاً
                await query.edit_message_text(
                    f"📅 **تعديل {field_display_name}**\n\n"
                    f"**القيمة الحالية:** {current_value_display}\n\n"
                    f"📝 أرسل التاريخ الجديد (مثال: 2025-01-15):",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_edit_fields:{flow_type}")],
                    ]),
                    parse_mode="Markdown"
                )
        else:
            await query.edit_message_text(
                f"✏️ **تعديل {field_display_name}**\n\n"
                f"**القيمة الحالية:**\n{current_value_display}\n\n"
                f"📝 أرسل القيمة الجديدة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_edit_fields:{flow_type}")],
                ]),
                parse_mode="Markdown"
            )
        
        context.user_data['_conversation_state'] = FOLLOWUP_CONFIRM
        return FOLLOWUP_CONFIRM
        
    except Exception as e:
        logger.error(f"❌ [FOLLOWUP] خطأ في handle_edit_field_selection: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء اختيار الحقل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END


async def handle_followup_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة إدخال القيمة الجديدة - مسار followup
    منطق منفصل تماماً
    """
    try:
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            from bot.handlers.user.user_reports_add_new_system import start_report
            return await start_report(update, context)
        
        field_key = context.user_data.get("edit_field_key")
        flow_type = context.user_data.get("edit_flow_type")
        
        if flow_type not in ("followup", "periodic_followup", "inpatient_followup"):
            logger.warning(f"⚠️ [FOLLOWUP] handle_edit_field_input: flow_type={flow_type} ليس followup/periodic_followup/inpatient_followup - تجاهل")
            return
        
        if not field_key:
            logger.warning("⚠️ [FOLLOWUP] handle_edit_field_input: لا يوجد حقل للتعديل - تجاهل")
            return
        
        logger.info(f"✏️ [FOLLOWUP] handle_edit_field_input: field_key={field_key}, text={text[:50]}")
        
        if not text or len(text) < 1:
            await update.message.reply_text(
                "⚠️ **خطأ:** النص فارغ\n\n"
                f"يرجى إدخال القيمة:",
                parse_mode="Markdown"
            )
            return FOLLOWUP_CONFIRM
        
        # ✅ حفظ القيمة - منطق منفصل
        data = context.user_data.setdefault("report_tmp", {})
        medical_action = data.get("medical_action", "")
        
        # ✅ معالجة خاصة لكل حقل
        if field_key == "complaint":
            data["complaint"] = text
            data["complaint_text"] = text
        elif field_key == "decision":
            data["decision"] = text
            data["doctor_decision"] = text
        elif field_key == "room_number":
            # ✅ فقط لـ "متابعة في الرقود"
            if medical_action == "متابعة في الرقود":
                data["room_number"] = text
                data["room_floor"] = text  # للتوافق
            else:
                await update.message.reply_text(
                    "❌ **خطأ**\n\n"
                    "حقل رقم الغرفة متاح فقط لمسار 'متابعة في الرقود'.",
                    parse_mode="Markdown"
                )
                return FOLLOWUP_CONFIRM
        else:
            data[field_key] = text
        
        # مسح معلومات التعديل
        context.user_data.pop("edit_field_key", None)
        # ✅ لا نحذف edit_flow_type - قد نحتاجه لاحقاً

        logger.info(f"✅ [FOLLOWUP] تم حفظ التعديل: {field_key} = {text[:50]}")

        # ✅ تحديد flow_type الصحيح بناءً على medical_action
        actual_flow_type = "followup"
        if medical_action == "مراجعة / عودة دورية":
            actual_flow_type = "periodic_followup"
            data["current_flow"] = "periodic_followup"
        elif medical_action == "متابعة في الرقود":
            actual_flow_type = "inpatient_followup"
            data["current_flow"] = "inpatient_followup"
        else:
            data["current_flow"] = "followup"

        # ✅ إعادة عرض الملخص مع flow_type الصحيح
        await show_final_summary(update.message, context, actual_flow_type)

        context.user_data['_conversation_state'] = FOLLOWUP_CONFIRM
        return FOLLOWUP_CONFIRM
        
    except Exception as e:
        logger.error(f"❌ [FOLLOWUP] خطأ في handle_edit_field_input: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء حفظ التعديل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END

