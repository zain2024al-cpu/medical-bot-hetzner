# =============================
# Treatment Sessions + Endoscopy - Edit Before Publish Handlers
# =============================
# handler مشترك لكل مسارات جلسات العلاج (كيماوي/موجّه/مناعي/غسيل الكلى/
# المدمج) ومسار المناظير — كلها حقول نصية بسيطة بلا استخلاص مركّب
# (بخلاف new_consult/emergency وغيرها)، فيكفي معالج واحد عام بدل تكرار
# ملف منفصل لكل نوع.
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

try:
    from bot.handlers.user.user_reports_add_new_system.flows.shared import (
        get_confirm_state,
        show_final_summary,
    )
    from bot.handlers.user.user_reports_add_new_system.edit_handlers.draft.handlers import (
        _render_draft_edit_followup_calendar,
    )
except ImportError:
    logger.error("❌ Cannot import required modules for treatment_and_endoscopy_edit")
    get_confirm_state = lambda x: None
    show_final_summary = None
    _render_draft_edit_followup_calendar = None

TREATMENT_AND_ENDOSCOPY_FLOWS = {
    "treatment_chemo", "treatment_targeted", "treatment_immuno",
    "treatment_dialysis", "treatment_combined", "endoscopy",
}

_FIELD_NAMES = {
    "complaint":         "💬 شكوى المريض",
    "complaint_text":    "💬 شكوى المريض",
    "notes":             "📝 ملاحظات",
    "endoscopy_type":    "🔬 نوع المنظار",
    "endoscopy_result":  "📋 نتيجة المنظار / خطة الطبيب",
    "followup_date":     "📅 موعد العودة",
    "followup_time":     "⏰ وقت العودة",
    "followup_reason":   "✍️ سبب العودة",
}


async def handle_treatment_endoscopy_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار حقل للتعديل — مشتركة لجلسات العلاج/الأورام والمناظير."""
    query = update.callback_query
    try:
        await query.answer()
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END

        flow_type = parts[1]
        field_key = parts[2]

        data = context.user_data.get("report_tmp", {})
        current_value = data.get(field_key, "غير محدد")

        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type

        field_display_name = _FIELD_NAMES.get(field_key, field_key)
        if isinstance(current_value, str) and len(current_value) > 200:
            current_value_display = current_value[:200] + "..."
        else:
            current_value_display = str(current_value) if current_value else "غير محدد"

        confirm_state = get_confirm_state(flow_type)

        if field_key == "followup_date":
            context.user_data['editing_draft_date'] = True
            if _render_draft_edit_followup_calendar:
                await _render_draft_edit_followup_calendar(query, context)
                context.user_data['_conversation_state'] = "EDIT_DRAFT_FOLLOWUP_CALENDAR"
                return "EDIT_DRAFT_FOLLOWUP_CALENDAR"

        await query.edit_message_text(
            f"✏️ **تعديل {field_display_name}**\n\n"
            f"**القيمة الحالية:**\n{current_value_display}\n\n"
            f"📝 أرسل القيمة الجديدة:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_to_edit_fields:{flow_type}")],
            ]),
            parse_mode="Markdown"
        )
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        logger.error(f"❌ [TREATMENT/ENDOSCOPY] خطأ في handle_edit_field_selection: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء اختيار الحقل**\n\nيرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return ConversationHandler.END


async def handle_treatment_endoscopy_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال القيمة الجديدة — مشتركة لجلسات العلاج/الأورام والمناظير."""
    try:
        text = update.message.text.strip() if update.message else ""
        field_key = context.user_data.get("edit_field_key")
        flow_type = context.user_data.get("edit_flow_type")

        if flow_type not in TREATMENT_AND_ENDOSCOPY_FLOWS:
            logger.warning(f"⚠️ [TREATMENT/ENDOSCOPY] flow_type={flow_type} ليس ضمن النطاق - تجاهل")
            return

        if not field_key:
            logger.warning("⚠️ [TREATMENT/ENDOSCOPY] لا يوجد حقل للتعديل - تجاهل الرسالة")
            return

        if not text:
            await update.message.reply_text(
                "⚠️ **خطأ:** النص فارغ\n\nيرجى إدخال القيمة:",
                parse_mode="Markdown"
            )
            return get_confirm_state(flow_type)

        data = context.user_data.setdefault("report_tmp", {})

        # ✅ شكوى المريض: المسارات المدمجة/العلاجية تخزّنها في "complaint"،
        # المناظير في "complaint_text" مباشرة — نكتب في كليهما للتوافق.
        if field_key in ("complaint", "complaint_text"):
            data["complaint"] = text
            data["complaint_text"] = text
        else:
            data[field_key] = text

        context.user_data.pop("edit_field_key", None)
        data["current_flow"] = flow_type

        try:
            await show_final_summary(update.message, context, flow_type)
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state
        except Exception as e:
            logger.error(f"❌ [TREATMENT/ENDOSCOPY] خطأ في عرض الملخص بعد التعديل: {e}", exc_info=True)
            await update.message.reply_text(
                "✅ **تم حفظ التعديل بنجاح**\n\nيرجى استخدام زر '🔙 رجوع' للرجوع إلى الملخص.",
                parse_mode="Markdown"
            )
            return get_confirm_state(flow_type)

    except Exception as e:
        logger.error(f"❌ [TREATMENT/ENDOSCOPY] خطأ في handle_edit_field_input: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء حفظ التعديل**\n\nيرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        return ConversationHandler.END
