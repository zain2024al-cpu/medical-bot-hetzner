# =============================
# Inpatient Followup - Edit Before Publish Handlers
# =============================
# handlers منفصلة تماماً لمسار "متابعة في الرقود"
# يحتوي على حقل room_number (رقم الغرفة والطابق)
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
    logger.error("❌ Cannot import required modules for inpatient_followup_edit")
    FOLLOWUP_CONFIRM = None
    get_confirm_state = lambda x: None
    show_final_summary = None
    _render_draft_edit_followup_calendar = None


# =============================
# Field Selection Handler
# =============================

async def handle_inpatient_followup_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة اختيار حقل للتعديل - مسار "متابعة في الرقود"
    يحتوي على حقل room_number
    """
    try:
        query = update.callback_query
        await query.answer()
        
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        field_key = parts[2]
        flow_type = "inpatient_followup"  # ✅ flow_type منفصل
        
        logger.info(f"✏️ [INPATIENT_FOLLOWUP] handle_edit_field_selection: field_key={field_key}")
        
        data = context.user_data.get("report_tmp", {})
        current_value = data.get(field_key, "غير محدد")
        
        # حفظ معلومات التعديل
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        
        # أسماء الحقول للعرض - فقط الحقول المدخلة يدوياً
        field_names = {
            "complaint": "💬 شكوى المريض",
            "diagnosis": "🔬 التشخيص الطبي",
            "decision": "📝 قرار الطبيب",
            "room_number": "🏥 رقم الغرفة والطابق",
            "followup_date": "📅 موعد العودة",
            "followup_time": "⏰ وقت العودة",
            "followup_reason": "✍️ سبب العودة",
        }
        
        field_display_name = field_names.get(field_key, field_key)
        
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
        confirm_state = get_confirm_state("followup")
        return confirm_state
        
    except Exception as e:
        logger.error(f"❌ [INPATIENT_FOLLOWUP] خطأ في handle_edit_field_selection: {e}", exc_info=True)
        try:
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

async def handle_inpatient_followup_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ معالجة إدخال القيمة الجديدة - مسار "متابعة في الرقود"
    منطق منفصل تماماً - يتضمن room_number
    """
    try:
        text = update.message.text.strip() if update.message else ""
        if "إضافة" in text and "تقرير" in text and "جديد" in text:
            from bot.handlers.user.user_reports_add_new_system import start_report
            return await start_report(update, context)
        
        field_key = context.user_data.get("edit_field_key")
        edit_flow_type = context.user_data.get("edit_flow_type")
        data = context.user_data.get("report_tmp", {})
        medical_action = data.get("medical_action", "")
        
        # ✅ التحقق من edit_flow_type أو medical_action للتمييز بين المسارين
        if edit_flow_type != "inpatient_followup" and medical_action != "متابعة في الرقود":
            # ✅ إذا كان medical_action "مراجعة / عودة دورية"، تجاهل (يجب أن يذهب إلى periodic_followup)
            if medical_action == "مراجعة / عودة دورية":
                logger.warning(f"⚠️ [INPATIENT_FOLLOWUP] handle_edit_field_input: medical_action='مراجعة / عودة دورية' - يجب أن يذهب إلى periodic_followup - تجاهل")
                return
            # ✅ إذا كان edit_flow_type "periodic_followup"، تجاهل
            if edit_flow_type == "periodic_followup":
                logger.warning(f"⚠️ [INPATIENT_FOLLOWUP] handle_edit_field_input: edit_flow_type='periodic_followup' - يجب أن يذهب إلى periodic_followup - تجاهل")
                return
            # ✅ إذا لم يكن inpatient_followup ولا "متابعة في الرقود"، تجاهل
            logger.warning(f"⚠️ [INPATIENT_FOLLOWUP] handle_edit_field_input: edit_flow_type={edit_flow_type}, medical_action={medical_action} ليس inpatient_followup - تجاهل")
            return
        
        if not field_key:
            logger.warning("⚠️ [INPATIENT_FOLLOWUP] handle_edit_field_input: لا يوجد حقل للتعديل - تجاهل")
            return
        
        logger.info(f"✏️ [INPATIENT_FOLLOWUP] handle_edit_field_input: field_key={field_key}, text={text[:50]}")
        
        if not text or len(text) < 1:
            await update.message.reply_text(
                "⚠️ **خطأ:** النص فارغ\n\n"
                "يرجى إرسال قيمة صحيحة.",
                parse_mode="Markdown"
            )
            return
        
        # ✅ حفظ القيمة - منطق منفصل لمتابعة في الرقود
        data = context.user_data.setdefault("report_tmp", {})
        
        # ✅ التأكد من medical_action
        if data.get("medical_action") != "متابعة في الرقود":
            data["medical_action"] = "متابعة في الرقود"
            logger.info("✅ تم تعيين medical_action إلى 'متابعة في الرقود'")
        
        # ✅ معالجة خاصة لكل حقل
        if field_key == "complaint":
            data["complaint"] = text
            data["complaint_text"] = text
        elif field_key == "decision":
            data["decision"] = text
            data["doctor_decision"] = text
        elif field_key == "room_number":
            # ✅ حفظ room_number (متاح في هذا المسار)
            data["room_number"] = text
            data["room_floor"] = text  # للتوافق
        elif field_key == "followup_date":
            # تحليل التاريخ والوقت إذا كان موجوداً
            if " " in text:
                parts = text.split(" ", 1)
                data["followup_date"] = parts[0]
                if len(parts) > 1:
                    data["followup_time"] = parts[1]
            else:
                data["followup_date"] = text
                data["followup_time"] = ""
        else:
            data[field_key] = text
        
        # مسح معلومات التعديل
        context.user_data.pop("edit_field_key", None)

        # ✅ التأكد من حفظ current_flow في report_tmp للاستخدام في النشر
        data = context.user_data.setdefault("report_tmp", {})
        data["current_flow"] = "inpatient_followup"  # ✅ تصحيح: استخدام "inpatient_followup"
        data["medical_action"] = "متابعة في الرقود"  # ✅ التأكد من medical_action الصحيح
        logger.info(f"✅ [INPATIENT_FOLLOWUP] تم حفظ current_flow=inpatient_followup في report_tmp")

        logger.info(f"✅ [INPATIENT_FOLLOWUP] تم حفظ التعديل: {field_key} = {text[:50]}")

        # ✅ إعادة عرض الملخص مع flow_type الصحيح
        await show_final_summary(update.message, context, "inpatient_followup")

        confirm_state = get_confirm_state("followup")  # ✅ استخدام FOLLOWUP_CONFIRM
        context.user_data['_conversation_state'] = confirm_state
        logger.info(f"✅ [INPATIENT_FOLLOWUP] تم عرض الملخص بعد التعديل، flow_type=inpatient_followup, confirm_state={confirm_state}")
        return confirm_state
        
    except Exception as e:
        logger.error(f"❌ [INPATIENT_FOLLOWUP] خطأ في handle_edit_field_input: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء حفظ التعديل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END

