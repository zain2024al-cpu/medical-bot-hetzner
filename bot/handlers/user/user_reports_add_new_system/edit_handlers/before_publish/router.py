# =============================
# Edit Router - قبل النشر
# =============================
# هذا الملف يوجه الطلبات إلى handlers المناسبة حسب flow_type
# كل flow type له handlers منفصلة تماماً
# =============================

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# استيراد handlers منفصلة
try:
    from .new_consult_edit import (
        handle_new_consult_edit_field_selection,
        handle_new_consult_edit_field_input,
    )
    from .followup_edit import (
        handle_followup_edit_field_selection,
        handle_followup_edit_field_input,
    )
    from .periodic_followup_edit import (
        handle_periodic_followup_edit_field_selection,
        handle_periodic_followup_edit_field_input,
    )
    from .inpatient_followup_edit import (
        handle_inpatient_followup_edit_field_selection,
        handle_inpatient_followup_edit_field_input,
    )
    from .emergency_edit import (
        handle_emergency_edit_field_selection,
        handle_emergency_edit_field_input,
    )
    from .surgery_consult_edit import (
        handle_surgery_consult_edit_field_selection,
        handle_surgery_consult_edit_field_input,
    )
    from .operation_edit import (
        handle_operation_edit_field_selection,
        handle_operation_edit_field_input,
    )
    from .final_consult_edit import (
        handle_final_consult_edit_field_selection,
        handle_final_consult_edit_field_input,
    )
    from .admission_edit import (
        handle_admission_edit_field_selection,
        handle_admission_edit_field_input,
    )
    from .discharge_edit import (
        handle_discharge_edit_field_selection,
        handle_discharge_edit_field_input,
    )
    from .radiology_edit import (
        handle_radiology_edit_field_selection,
        handle_radiology_edit_field_input,
    )
    from .appointment_reschedule_edit import (
        handle_appointment_reschedule_edit_field_selection,
        handle_appointment_reschedule_edit_field_input,
    )
    from .rehab_physical_edit import (
        handle_rehab_physical_edit_field_selection,
        handle_rehab_physical_edit_field_input,
    )
    from .rehab_device_edit import (
        handle_rehab_device_edit_field_selection,
        handle_rehab_device_edit_field_input,
    )
    from .radiation_therapy_edit import (
        handle_radiation_therapy_edit_field_selection,
        handle_radiation_therapy_edit_field_input,
    )
except ImportError as e:
    logger.error(f"❌ Cannot import edit handlers: {e}")
    handle_new_consult_edit_field_selection = None
    handle_new_consult_edit_field_input = None
    handle_followup_edit_field_selection = None
    handle_followup_edit_field_input = None
    handle_periodic_followup_edit_field_selection = None
    handle_periodic_followup_edit_field_input = None
    handle_inpatient_followup_edit_field_selection = None
    handle_inpatient_followup_edit_field_input = None
    handle_emergency_edit_field_selection = None
    handle_emergency_edit_field_input = None
    handle_surgery_consult_edit_field_selection = None
    handle_surgery_consult_edit_field_input = None
    handle_operation_edit_field_selection = None
    handle_operation_edit_field_input = None
    handle_final_consult_edit_field_selection = None
    handle_final_consult_edit_field_input = None
    handle_admission_edit_field_selection = None
    handle_admission_edit_field_input = None
    handle_discharge_edit_field_selection = None
    handle_discharge_edit_field_input = None
    handle_radiology_edit_field_selection = None
    handle_radiology_edit_field_input = None
    handle_appointment_reschedule_edit_field_selection = None
    handle_appointment_reschedule_edit_field_input = None
    handle_rehab_physical_edit_field_selection = None
    handle_rehab_physical_edit_field_input = None
    handle_rehab_device_edit_field_selection = None
    handle_rehab_device_edit_field_input = None
    handle_radiation_therapy_edit_field_selection = None
    handle_radiation_therapy_edit_field_input = None


# =============================
# Field Selection Router
# =============================

async def route_edit_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ Router لتوجيه اختيار الحقل للتعديل إلى handler المناسب
    كل flow type له handler منفصل تماماً
    """
    try:
        query = update.callback_query
        if not query:
            return ConversationHandler.END
        
        # استخراج flow_type من callback_data
        # Format: "edit_field:flow_type:field_key"
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        flow_type = parts[1]
        
        logger.info(f"🔀 [ROUTER] route_edit_field_selection: flow_type={flow_type}")
        
        # ✅ التوجيه حسب flow_type - كل flow type له handler منفصل
        if flow_type == "new_consult":
            if handle_new_consult_edit_field_selection:
                return await handle_new_consult_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_new_consult_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "periodic_followup":
            # ✅ مسار "مراجعة / عودة دورية" - handler منفصل
            logger.info("🔀 [ROUTER] التوجيه إلى periodic_followup مباشرة")
            if handle_periodic_followup_edit_field_selection:
                return await handle_periodic_followup_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_periodic_followup_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "inpatient_followup":
            # ✅ مسار "متابعة في الرقود" - handler منفصل
            logger.info("🔀 [ROUTER] التوجيه إلى inpatient_followup مباشرة")
            if handle_inpatient_followup_edit_field_selection:
                return await handle_inpatient_followup_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_inpatient_followup_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "followup":
            # ✅ التمييز بين "عودة دورية" و "متابعة في الرقود" بناءً على medical_action
            data = context.user_data.get("report_tmp", {})
            medical_action = data.get("medical_action", "")
            
            if medical_action == "متابعة في الرقود":
                # ✅ مسار "متابعة في الرقود" - يستخدم inpatient_followup handler
                logger.info("🔀 [ROUTER] التوجيه إلى inpatient_followup (متابعة في الرقود)")
                if handle_inpatient_followup_edit_field_selection:
                    return await handle_inpatient_followup_edit_field_selection(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_inpatient_followup_edit_field_selection غير متوفر")
                    await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                    return ConversationHandler.END
            elif medical_action == "مراجعة / عودة دورية":
                # ✅ مسار "مراجعة / عودة دورية" - يستخدم periodic_followup handler
                logger.info("🔀 [ROUTER] التوجيه إلى periodic_followup (عودة دورية)")
                if handle_periodic_followup_edit_field_selection:
                    return await handle_periodic_followup_edit_field_selection(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_periodic_followup_edit_field_selection غير متوفر")
                    await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                    return ConversationHandler.END
            else:
                # ✅ fallback إلى handler القديم للتوافق مع الكود القديم
                logger.warning(f"⚠️ [ROUTER] medical_action={medical_action} غير معروف - استخدام followup_edit القديم")
                if handle_followup_edit_field_selection:
                    return await handle_followup_edit_field_selection(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_followup_edit_field_selection غير متوفر")
                    await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                    return ConversationHandler.END
        elif flow_type == "emergency":
            # ✅ Handlers منفصلة لـ emergency
            if handle_emergency_edit_field_selection:
                return await handle_emergency_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_emergency_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "surgery_consult":
            # ✅ Handlers منفصلة لـ surgery_consult
            if handle_surgery_consult_edit_field_selection:
                return await handle_surgery_consult_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_surgery_consult_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "operation":
            # ✅ Handlers منفصلة لـ operation
            if handle_operation_edit_field_selection:
                return await handle_operation_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_operation_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "final_consult":
            # ✅ Handlers منفصلة لـ final_consult
            if handle_final_consult_edit_field_selection:
                return await handle_final_consult_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_final_consult_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "admission":
            # ✅ Handlers منفصلة لـ admission
            if handle_admission_edit_field_selection:
                return await handle_admission_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_admission_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "discharge":
            # ✅ Handlers منفصلة لـ discharge
            if handle_discharge_edit_field_selection:
                return await handle_discharge_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_discharge_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "radiology":
            # ✅ Handlers منفصلة لـ radiology
            if handle_radiology_edit_field_selection:
                return await handle_radiology_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_radiology_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "appointment_reschedule":
            # ✅ Handlers منفصلة لـ appointment_reschedule
            if handle_appointment_reschedule_edit_field_selection:
                return await handle_appointment_reschedule_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_appointment_reschedule_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "rehab_physical":
            # ✅ Handlers منفصلة لـ rehab_physical
            if handle_rehab_physical_edit_field_selection:
                return await handle_rehab_physical_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_rehab_physical_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type in ["rehab_device", "device"]:
            # ✅ Handlers منفصلة لـ rehab_device/device
            if handle_rehab_device_edit_field_selection:
                return await handle_rehab_device_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_rehab_device_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        elif flow_type == "radiation_therapy":
            # ✅ Handlers منفصلة لـ radiation_therapy (جلسة إشعاعي)
            if handle_radiation_therapy_edit_field_selection:
                return await handle_radiation_therapy_edit_field_selection(update, context)
            else:
                logger.error("❌ [ROUTER] handle_radiation_therapy_edit_field_selection غير متوفر")
                await query.edit_message_text("❌ **خطأ**\n\nمعالج التعديل غير متوفر.")
                return ConversationHandler.END
        else:
            logger.warning(f"⚠️ [ROUTER] flow_type={flow_type} - handlers غير متوفرة بعد")
            await query.edit_message_text("⚠️ **قيد التطوير**\n\nمعالجة التعديل لهذا المسار قيد التطوير.")
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"❌ [ROUTER] خطأ في route_edit_field_selection: {e}", exc_info=True)
        try:
            query = update.callback_query
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء التوجيه**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode="Markdown"
            )
        except:
            pass
        return ConversationHandler.END


# =============================
# Field Input Router
# =============================

async def route_edit_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    ✅ Router لتوجيه إدخال القيمة الجديدة إلى handler المناسب
    كل flow type له handler منفصل تماماً
    """
    try:
        # محاولة الحصول على flow_type من عدة مصادر
        flow_type = (
            context.user_data.get("edit_flow_type") or 
            context.user_data.get("report_tmp", {}).get("current_flow") or
            context.user_data.get("report_tmp", {}).get("flow_type")
        )
        
        if not flow_type:
            logger.warning("⚠️ [ROUTER] route_edit_field_input: لا يوجد flow_type - محاولة استعادة من السياق")
            
            # محاولة استعادة flow_type من medical_action
            data = context.user_data.get("report_tmp", {})
            medical_action = data.get("medical_action", "")
            
            # محاولة تحديد flow_type من medical_action
            if medical_action:
                action_to_flow = {
                    "استشارة جديدة": "new_consult",
                    "متابعة في الرقود": "inpatient_followup",
                    "مراجعة / عودة دورية": "periodic_followup",
                    "طوارئ": "emergency",
                    "عملية": "operation",
                    "ترقيد": "admission",
                    "خروج من المستشفى": "discharge",
                    "استشارة نهائية": "final_consult",
                    "أشعة وفحوصات": "radiology",
                    "تأجيل موعد": "appointment_reschedule",
                    "علاج طبيعي": "rehab_physical",
                    "أجهزة تعويضية": "rehab_device",
                    "جلسة إشعاعي": "radiation_therapy"
                }
                flow_type = action_to_flow.get(medical_action)
                if flow_type:
                    logger.info(f"✅ [ROUTER] تم استعادة flow_type={flow_type} من medical_action={medical_action}")
                    context.user_data["edit_flow_type"] = flow_type
                    data["current_flow"] = flow_type
        
        if not flow_type:
            logger.error("❌ [ROUTER] route_edit_field_input: لا يمكن تحديد flow_type - إنهاء المحادثة")
            if update.message:
                await update.message.reply_text(
                    "⚠️ **حدث خطأ**\n\n"
                    "لم يتم العثور على نوع التقرير.\n\n"
                    "يرجى البدء من جديد باستخدام زر '➕ إضافة تقرير جديد'.",
                    parse_mode="Markdown"
                )
            return ConversationHandler.END
        
        logger.info(f"🔀 [ROUTER] route_edit_field_input: flow_type={flow_type}")
        
        # ✅ التوجيه حسب flow_type - كل flow type له handler منفصل
        if flow_type == "new_consult":
            if handle_new_consult_edit_field_input:
                return await handle_new_consult_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_new_consult_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type in ["followup", "periodic_followup", "inpatient_followup"]:
            # ✅ التمييز بين "عودة دورية" و "متابعة في الرقود" بناءً على edit_flow_type أولاً، ثم medical_action
            edit_flow_type = context.user_data.get("edit_flow_type")
            data = context.user_data.get("report_tmp", {})
            medical_action = data.get("medical_action", "")
            
            logger.info(f"🔀 [ROUTER] route_edit_field_input: flow_type={flow_type}, edit_flow_type={edit_flow_type}, medical_action={medical_action}")
            
            # ✅ التحقق من edit_flow_type إذا كان محدداً (من handle_field_selection)
            if edit_flow_type == "periodic_followup" or flow_type == "periodic_followup":
                logger.info("🔀 [ROUTER] التوجيه إلى periodic_followup")
                # ✅ تعيين edit_flow_type بشكل صريح للتأكد
                context.user_data["edit_flow_type"] = "periodic_followup"
                if handle_periodic_followup_edit_field_input:
                    return await handle_periodic_followup_edit_field_input(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_periodic_followup_edit_field_input غير متوفر")
                    return ConversationHandler.END
            elif edit_flow_type == "inpatient_followup" or flow_type == "inpatient_followup":
                logger.info("🔀 [ROUTER] التوجيه إلى inpatient_followup")
                # ✅ تعيين edit_flow_type بشكل صريح للتأكد
                context.user_data["edit_flow_type"] = "inpatient_followup"
                if handle_inpatient_followup_edit_field_input:
                    return await handle_inpatient_followup_edit_field_input(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_inpatient_followup_edit_field_input غير متوفر")
                    return ConversationHandler.END
            elif medical_action == "متابعة في الرقود":
                # ✅ مسار "متابعة في الرقود" - يستخدم inpatient_followup handler
                logger.info("🔀 [ROUTER] التوجيه إلى inpatient_followup (متابعة في الرقود)")
                # ✅ تعيين edit_flow_type بشكل صريح
                context.user_data["edit_flow_type"] = "inpatient_followup"
                if handle_inpatient_followup_edit_field_input:
                    return await handle_inpatient_followup_edit_field_input(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_inpatient_followup_edit_field_input غير متوفر")
                    return ConversationHandler.END
            elif medical_action == "مراجعة / عودة دورية":
                # ✅ مسار "مراجعة / عودة دورية" - يستخدم periodic_followup handler
                logger.info("🔀 [ROUTER] التوجيه إلى periodic_followup (عودة دورية)")
                # ✅ تعيين edit_flow_type بشكل صريح
                context.user_data["edit_flow_type"] = "periodic_followup"
                if handle_periodic_followup_edit_field_input:
                    return await handle_periodic_followup_edit_field_input(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_periodic_followup_edit_field_input غير متوفر")
                    return ConversationHandler.END
            else:
                # ✅ fallback إلى handler القديم للتوافق مع الكود القديم
                logger.warning(f"⚠️ [ROUTER] medical_action={medical_action} غير معروف - استخدام followup_edit القديم")
                if handle_followup_edit_field_input:
                    return await handle_followup_edit_field_input(update, context)
                else:
                    logger.error("❌ [ROUTER] handle_followup_edit_field_input غير متوفر")
                    return ConversationHandler.END
        elif flow_type == "emergency":
            # ✅ Handlers منفصلة لـ emergency
            if handle_emergency_edit_field_input:
                return await handle_emergency_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_emergency_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "surgery_consult":
            # ✅ Handlers منفصلة لـ surgery_consult
            if handle_surgery_consult_edit_field_input:
                return await handle_surgery_consult_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_surgery_consult_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "operation":
            # ✅ Handlers منفصلة لـ operation
            if handle_operation_edit_field_input:
                return await handle_operation_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_operation_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "final_consult":
            # ✅ Handlers منفصلة لـ final_consult
            if handle_final_consult_edit_field_input:
                return await handle_final_consult_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_final_consult_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "admission":
            # ✅ Handlers منفصلة لـ admission
            if handle_admission_edit_field_input:
                return await handle_admission_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_admission_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "discharge":
            # ✅ Handlers منفصلة لـ discharge
            if handle_discharge_edit_field_input:
                return await handle_discharge_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_discharge_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "radiology":
            # ✅ Handlers منفصلة لـ radiology
            if handle_radiology_edit_field_input:
                return await handle_radiology_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_radiology_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "appointment_reschedule":
            # ✅ Handlers منفصلة لـ appointment_reschedule
            if handle_appointment_reschedule_edit_field_input:
                return await handle_appointment_reschedule_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_appointment_reschedule_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "rehab_physical":
            # ✅ Handlers منفصلة لـ rehab_physical
            if handle_rehab_physical_edit_field_input:
                return await handle_rehab_physical_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_rehab_physical_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type in ["rehab_device", "device"]:
            # ✅ Handlers منفصلة لـ rehab_device/device
            if handle_rehab_device_edit_field_input:
                return await handle_rehab_device_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_rehab_device_edit_field_input غير متوفر")
                return ConversationHandler.END
        elif flow_type == "radiation_therapy":
            # ✅ Handlers منفصلة لـ radiation_therapy (جلسة إشعاعي)
            if handle_radiation_therapy_edit_field_input:
                return await handle_radiation_therapy_edit_field_input(update, context)
            else:
                logger.error("❌ [ROUTER] handle_radiation_therapy_edit_field_input غير متوفر")
                return ConversationHandler.END
        else:
            logger.warning(f"⚠️ [ROUTER] flow_type={flow_type} غير معروف - تجاهل")
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"❌ [ROUTER] خطأ في route_edit_field_input: {e}", exc_info=True)
        return ConversationHandler.END

