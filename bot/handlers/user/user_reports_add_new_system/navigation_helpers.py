# =============================
# navigation_helpers.py
# دوال مساعدة للتنقل والإلغاء
# =============================

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)


async def handle_cancel_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إلغاء العملية - تنظيف شامل لجميع البيانات"""
    from .states import STATE_SELECT_DATE
    from .navigation import nav_clear, nav_push
    
    query = update.callback_query
    if query:
        await query.answer()
    
    # ✅ التحقق من last_valid_state - إذا كان التاريخ، عرض التقويم مباشرة
    last_valid_state = context.user_data.get('last_valid_state')
    logger.info(f"🔙 CANCEL: last_valid_state={last_valid_state}")
    
    # إذا كان last_valid_state هو date_selection أو STATE_SELECT_DATE
    if last_valid_state in ['date_selection', STATE_SELECT_DATE]:
        try:
            if query:
                try:
                    await query.message.delete()
                except:
                    pass
            
            # تنظيف البيانات
            report_tmp = context.user_data.get("report_tmp", {})
            if report_tmp:
                keys_to_remove = [
                    "report_date", "patient_name", "patient_id", "hospital_name",
                    "department_name", "doctor_name", "doctor_id", "action_type",
                    "medical_action", "current_flow", "complaint", "diagnosis",
                    "decision", "tests", "followup_date", "followup_time",
                    "followup_reason", "translator_name", "translator_id",
                    "patient_search_mode", "doctor_search_mode", "hospitals_search",
                    "departments_search", "doctor_manual_mode", "step_history"
                ]
                for key in keys_to_remove:
                    report_tmp.pop(key, None)
            
            # تنظيف navigation stack
            nav_clear(context)
            context.user_data.pop("_current_search_type", None)
            
            # عرض التقويم مباشرة
            from .date_time_handlers import render_date_selection
            nav_push(context, STATE_SELECT_DATE)
            context.user_data['_conversation_state'] = STATE_SELECT_DATE
            context.user_data['last_valid_state'] = 'date_selection'
            
            if query:
                await render_date_selection(query.message, context)
            else:
                await update.message.reply_text("✅ تم الإلغاء - اختر التاريخ:")
                await render_date_selection(update.message, context)
            
            logger.info("✅ CANCEL: Redirected to date selection")
            return STATE_SELECT_DATE
        except Exception as e:
            logger.error(f"❌ خطأ في إعادة توجيه إلى التقويم: {e}", exc_info=True)
    
    # ✅ إذا لم يكن التاريخ، تنظيف شامل وإنهاء المحادثة
    if query:
        try:
            await query.edit_message_text(
                "❌ **تم إلغاء العملية**\n\n"
                "✅ تم تنظيف جميع البيانات.",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث رسالة الإلغاء: {e}")
    
    try:
        # تنظيف شامل لجميع البيانات
        report_tmp = context.user_data.get("report_tmp", {})
        if report_tmp:
            # قائمة المفاتيح التي يجب حذفها
            keys_to_remove = [
                "report_date", "patient_name", "patient_id", "hospital_name",
                "department_name", "doctor_name", "doctor_id", "action_type",
                "medical_action", "current_flow", "complaint", "diagnosis",
                "decision", "tests", "followup_date", "followup_time",
                "followup_reason", "translator_name", "translator_id",
                "patient_search_mode", "doctor_search_mode", "hospitals_search",
                "departments_search", "doctor_manual_mode",
                "step_history"
            ]
            for key in keys_to_remove:
                context.user_data.pop(key, None)
        
        # حذف report_tmp نفسه
        context.user_data.pop("report_tmp", None)
        context.user_data.pop("_conversation_state", None)
        context.user_data.pop("_current_search_type", None)
        context.user_data.pop("history", None)
        context.user_data.pop("last_valid_state", None)
        
        logger.info("✅ تم تنظيف جميع البيانات المتعلقة بالتقرير")
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف البيانات عند الإلغاء: {e}", exc_info=True)
        # حتى في حالة الخطأ، نحاول حذف report_tmp على الأقل
        context.user_data.pop("report_tmp", None)
        context.user_data.pop("_conversation_state", None)
        context.user_data.pop("_current_search_type", None)
        context.user_data.pop("history", None)
        context.user_data.pop("last_valid_state", None)
    
    return ConversationHandler.END


async def handle_back_navigation(update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرجوع للخطوة السابقة - نظام Navigation Stack"""
    from .navigation import nav_get_history, nav_pop, nav_peek, nav_push
    from .states import (
        STATE_SELECT_DATE, STATE_SELECT_PATIENT, STATE_SELECT_HOSPITAL,
        STATE_SELECT_DEPARTMENT, STATE_SELECT_SUBDEPARTMENT, STATE_SELECT_DOCTOR,
        R_ACTION_TYPE
    )
    from .managers import PatientDataManager, DoctorDataManager, DepartmentDataManager
    
    query = update.callback_query
    if not query:
        logger.error("❌ handle_back_navigation: No callback query found")
        return ConversationHandler.END
    
    await query.answer()

    try:
        history = nav_get_history(context)
        current_state = context.user_data.get('_conversation_state')

        logger.info(f"🔙 BACK: current_state={current_state}, history={history}")

        if not history:
            logger.warning("🔙 BACK: No history, going to start")
            try:
                await query.message.delete()
            except:
                pass
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context)
            nav_push(context, STATE_SELECT_DATE)
            context.user_data['_conversation_state'] = STATE_SELECT_DATE
            return STATE_SELECT_DATE

        popped = nav_pop(context)
        previous_step = nav_peek(context)
        new_history = nav_get_history(context)
        
        logger.info(f"🔙 BACK: popped={popped}, previous_step={previous_step}, new_history={new_history}")

        if previous_step is None:
            logger.info("🔙 BACK: No previous step, going to start")
            try:
                await query.message.delete()
            except:
                pass
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context)
            nav_push(context, STATE_SELECT_DATE)
            context.user_data['_conversation_state'] = STATE_SELECT_DATE
            return STATE_SELECT_DATE

        context.user_data['_conversation_state'] = previous_step

        if previous_step == STATE_SELECT_DATE:
            try:
                await query.message.delete()
            except:
                pass
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context)
            return STATE_SELECT_DATE
        elif previous_step == STATE_SELECT_PATIENT:
            PatientDataManager.clear_patient_data(context)
            try:
                await query.message.delete()
            except:
                pass
            from .patient_handlers import show_patient_selection
            await show_patient_selection(query.message, context)
            return STATE_SELECT_PATIENT
        elif previous_step == STATE_SELECT_HOSPITAL:
            try:
                await query.message.delete()
            except:
                pass
            from .hospital_handlers import render_hospital_selection
            await render_hospital_selection(query.message, context)
            return STATE_SELECT_HOSPITAL
        elif previous_step == STATE_SELECT_DEPARTMENT:
            DepartmentDataManager.clear_department_data(context, full_clear=False)
            try:
                await query.message.delete()
            except:
                pass
            from .department_handlers import render_department_selection
            await render_department_selection(query.message, context)
            return STATE_SELECT_DEPARTMENT
        elif previous_step == STATE_SELECT_SUBDEPARTMENT:
            DepartmentDataManager.clear_department_data(context, full_clear=False)
            try:
                await query.message.delete()
            except:
                pass
            from .department_handlers import render_department_selection
            await render_department_selection(query.message, context)
            return STATE_SELECT_DEPARTMENT
        elif previous_step == STATE_SELECT_DOCTOR:
            DoctorDataManager.clear_doctor_data(context)
            try:
                await query.message.delete()
            except:
                pass
            from .doctor_handlers import render_doctor_selection
            await render_doctor_selection(query.message, context)
            return STATE_SELECT_DOCTOR
        elif previous_step == R_ACTION_TYPE:
            report_tmp = context.user_data.get("report_tmp", {})
            report_tmp.pop("medical_action", None)
            report_tmp.pop("action_type", None)
            report_tmp.pop("current_flow", None)
            try:
                await query.message.delete()
            except:
                pass
            from .action_type_handlers import show_action_type_menu
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE
        else:
            logger.warning(f"🔙 BACK: Unknown state {previous_step}, using fallback")
            try:
                await query.message.delete()
            except:
                pass
            return previous_step

    except Exception as e:
        logger.error(f"❌ Error in handle_back_navigation: {e}", exc_info=True)
        return ConversationHandler.END


async def handle_go_to_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الانتقال إلى state محدد - نظام State Dictionary System"""
    from .states import (
        STATE_SELECT_DATE, STATE_SELECT_PATIENT, STATE_SELECT_HOSPITAL,
        STATE_SELECT_DEPARTMENT, STATE_SELECT_SUBDEPARTMENT, STATE_SELECT_DOCTOR,
        R_ACTION_TYPE
    )
    
    query = update.callback_query
    if not query:
        logger.error("❌ handle_go_to_state: No callback query found")
        return ConversationHandler.END
    
    await query.answer()
    
    try:
        callback_data = query.data
        if not callback_data.startswith("go_to_"):
            logger.error(f"❌ handle_go_to_state: Invalid callback_data format: {callback_data}")
            return ConversationHandler.END
        
        state_name = callback_data.replace("go_to_", "")
        
        # Mapping بسيط للأسماء
        state_mapping = {
            "date_selection": STATE_SELECT_DATE,
            "patient_selection": STATE_SELECT_PATIENT,
            "hospital_selection": STATE_SELECT_HOSPITAL,
            "department_selection": STATE_SELECT_DEPARTMENT,
            "search_doctor_screen": STATE_SELECT_DOCTOR,
            "action_type_selection": R_ACTION_TYPE,
        }
        
        target_state = state_mapping.get(state_name)
        
        if target_state is None:
            logger.error(f"❌ handle_go_to_state: Unknown state name: {state_name}")
            await query.answer("⚠️ خطأ: حالة غير معروفة", show_alert=True)
            return ConversationHandler.END
        
        logger.info(f"🔙 GO_TO_STATE: Navigating to {state_name} (state={target_state})")
        
        context.user_data['_conversation_state'] = target_state
        
        # عرض الشاشة المناسبة
        if target_state == STATE_SELECT_DATE:
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context)
        elif target_state == STATE_SELECT_PATIENT:
            from .patient_handlers import render_patient_selection
            await render_patient_selection(query.message, context)
        elif target_state == STATE_SELECT_HOSPITAL:
            from .hospital_handlers import render_hospital_selection
            await render_hospital_selection(query.message, context)
        elif target_state == STATE_SELECT_DEPARTMENT:
            from .department_handlers import render_department_selection
            await render_department_selection(query.message, context)
        elif target_state == STATE_SELECT_DOCTOR:
            from .doctor_handlers import render_doctor_selection
            await render_doctor_selection(query.message, context)
        elif target_state == R_ACTION_TYPE:
            from .action_type_handlers import show_action_type_menu
            await show_action_type_menu(query.message, context)
        else:
            await query.edit_message_text(
                f"✅ **تم الرجوع إلى:** {state_name}\n\n"
                "يرجى المتابعة.",
                parse_mode="Markdown"
            )
        
        return target_state
    except Exception as e:
        logger.error(f"❌ خطأ في handle_go_to_state: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ**\n\n"
            "يرجى المحاولة مرة أخرى.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

