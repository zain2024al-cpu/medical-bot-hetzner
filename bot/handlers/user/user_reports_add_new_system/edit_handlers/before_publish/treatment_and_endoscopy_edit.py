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
    "session_number":    "🔢 رقم الجلسة الحالية",
}

# ✅ رقم الجلسة الحالية — نفس منطق التعديل بعد النشر تماماً (انظر
# _current_session_number_display/_apply_session_number_edit في
# user_reports_edit.py)، لكن على report_tmp الحي بدل صف Report منشور.
# chemo/targeted/immuno لها TreatmentPlan فعلية فيُقرأ/يُحدَّث الرقم منها
# مباشرة عبر get_active_plan/edit_plan، أما dialysis فالرقم مضمَّن فقط
# داخل نص treatment_plan_summary فيُستبدَل بالنص مباشرة.
_TREATMENT_KEY_BY_FLOW = {
    "treatment_chemo": "chemo",
    "treatment_targeted": "targeted",
    "treatment_immuno": "immuno",
    "treatment_dialysis": "dialysis",
}
_DIALYSIS_SESSION_PATTERN = r'رقم الجلسة الحالية:\s*(\d+)'


def _current_session_number_display(data: dict, flow_type: str) -> str:
    import re
    treatment_key = _TREATMENT_KEY_BY_FLOW.get(flow_type)
    if not treatment_key:
        return "غير محدد"
    if treatment_key == "dialysis":
        m = re.search(_DIALYSIS_SESSION_PATTERN, data.get("treatment_plan_summary") or "")
        return m.group(1) if m else "غير محدد"
    patient_id = data.get("patient_id")
    if not patient_id:
        return "غير محدد"
    from services.treatment_plan_service import get_active_plan
    plan = get_active_plan(patient_id, treatment_key)
    if plan and plan.get("current_session") is not None:
        return str(plan["current_session"])
    return "غير محدد"


def _apply_session_number_edit(data: dict, flow_type: str, new_value: str) -> None:
    import re
    treatment_key = _TREATMENT_KEY_BY_FLOW.get(flow_type)
    if treatment_key == "dialysis":
        summary = data.get("treatment_plan_summary") or ""
        if re.search(_DIALYSIS_SESSION_PATTERN, summary):
            data["treatment_plan_summary"] = re.sub(
                _DIALYSIS_SESSION_PATTERN, f"رقم الجلسة الحالية: {new_value}", summary,
            )
        else:
            data["treatment_plan_summary"] = f"🩸 **جلسات غسيل الكلى**\n\nرقم الجلسة الحالية: {new_value}"
        return
    if treatment_key:
        patient_id = data.get("patient_id")
        if patient_id:
            from services.treatment_plan_service import get_active_plan, edit_plan, format_progress_text
            plan = get_active_plan(patient_id, treatment_key)
            if plan:
                updated_plan = edit_plan(
                    plan["id"], {"current_session": int(new_value)},
                    changed_by=None, changed_by_name="تعديل قبل النشر",
                    reason="تصحيح رقم الجلسة قبل نشر التقرير",
                )
                data["treatment_plan_summary"] = format_progress_text(updated_plan)
                data["_tp_plan_id"] = plan["id"]


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
        if field_key == "session_number":
            current_value = _current_session_number_display(data, flow_type)
        else:
            current_value = data.get(field_key, "غير محدد")

        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type

        field_display_name = _FIELD_NAMES.get(field_key, field_key)
        if isinstance(current_value, str) and len(current_value) > 200:
            current_value_display = current_value[:200] + "..."
        else:
            current_value_display = str(current_value) if current_value else "غير محدد"

        # ✅ تهريب محارف Markdown من القيمة الحرة قبل حشرها في رسالة
        # parse_mode="Markdown" — انظر شرح السبب في escape_md_v1 (utils.py).
        from ...utils import escape_md_v1
        current_value_display = escape_md_v1(current_value_display)

        confirm_state = get_confirm_state(flow_type)

        if field_key == "followup_date":
            context.user_data['editing_draft_date'] = True
            if _render_draft_edit_followup_calendar:
                await _render_draft_edit_followup_calendar(query, context)
                context.user_data['_conversation_state'] = "EDIT_DRAFT_FOLLOWUP_CALENDAR"
                return "EDIT_DRAFT_FOLLOWUP_CALENDAR"

        # ✅ نوع المنظار: نفس قائمة الفورمه الأصلية بدل كتابة القيمة يدوياً.
        # القائمة تُقرأ من flows/endoscopy.py مباشرةً — لا نسخة ثانية تنحرف
        # عن الأصل عند إضافة نوع جديد.
        if field_key == "endoscopy_type":
            from bot.handlers.user.user_reports_add_new_system.flows.endoscopy import (
                ENDOSCOPY_TYPES,
            )
            rows = [
                [InlineKeyboardButton(
                    f"{'✅ ' if label == current_value else ''}{label}",
                    callback_data=f"edit_endo_type:{code}",
                )]
                for code, label in ENDOSCOPY_TYPES
            ]
            rows.append([InlineKeyboardButton(
                "🔙 رجوع", callback_data=f"back_to_edit_fields:{flow_type}")])
            await query.edit_message_text(
                f"✏️ **تعديل {field_display_name}**\n\n"
                f"**القيمة الحالية:** {current_value_display}\n\n"
                f"اختر نوع المنظار:",
                reply_markup=InlineKeyboardMarkup(rows),
                parse_mode="Markdown",
            )
            context.user_data['_conversation_state'] = confirm_state
            return confirm_state

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
            logger.debug("تم تجاهل استثناء في handle_treatment_endoscopy_edit_field_selection", exc_info=True)
        return ConversationHandler.END


async def handle_treatment_endoscopy_type_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار نوع المنظار من القائمة أثناء التعديل قبل النشر.

    يقابل handle_treatment_endoscopy_edit_field_input لكن بضغطة زر بدل نص،
    وينتهي بنفس نهايته تماماً (حفظ + إعادة عرض الملخص) حتى لا يختلف مسارا
    التعديل في سلوكهما بعد الحفظ.
    """
    query = update.callback_query
    try:
        await query.answer()
        from bot.handlers.user.user_reports_add_new_system.flows.endoscopy import (
            ENDOSCOPY_TYPES,
        )
        code = query.data.split(":", 1)[1]
        label = dict(ENDOSCOPY_TYPES).get(code)
        flow_type = context.user_data.get("edit_flow_type") or "endoscopy"

        if not label:
            await query.answer("نوع غير صحيح", show_alert=True)
            return get_confirm_state(flow_type)

        data = context.user_data.setdefault("report_tmp", {})
        data["endoscopy_type"] = label
        data["current_flow"] = flow_type
        context.user_data.pop("edit_field_key", None)

        await query.edit_message_text(
            f"✅ **تم حفظ التعديل**\n\n🔬 نوع المنظار: {label}",
            parse_mode="Markdown",
        )
        confirm_state = get_confirm_state(flow_type)
        try:
            await show_final_summary(query.message, context, flow_type)
        except Exception as e:
            logger.error(f"❌ [ENDOSCOPY] خطأ في عرض الملخص بعد اختيار النوع: {e}", exc_info=True)
        context.user_data['_conversation_state'] = confirm_state
        return confirm_state

    except Exception as e:
        logger.error(f"❌ [ENDOSCOPY] خطأ في handle_treatment_endoscopy_type_pick: {e}", exc_info=True)
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

        if field_key == "session_number" and (not text.isdigit() or int(text) <= 0):
            await update.message.reply_text(
                "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (رقم الجلسة الحالية):",
            )
            return get_confirm_state(flow_type)

        data = context.user_data.setdefault("report_tmp", {})

        # ✅ شكوى المريض: المسارات المدمجة/العلاجية تخزّنها في "complaint"،
        # المناظير في "complaint_text" مباشرة — نكتب في كليهما للتوافق.
        if field_key in ("complaint", "complaint_text"):
            data["complaint"] = text
            data["complaint_text"] = text
        elif field_key == "session_number":
            # ✅ يُحدِّث TreatmentPlan الفعلية (chemo/targeted/immuno) أو نص
            # treatment_plan_summary مباشرة (dialysis، بلا خطة) — وليس مجرد
            # مفتاح جديد في report_tmp لا يقرأه شيء.
            _apply_session_number_edit(data, flow_type, text)
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
            logger.debug("تم تجاهل استثناء في handle_treatment_endoscopy_edit_field_input", exc_info=True)
        return ConversationHandler.END
