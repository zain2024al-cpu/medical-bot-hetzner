# =============================
# navigation_helpers.py
# دوال مساعدة للتنقل والإلغاء
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
            context.user_data['_nav_stack'] = []
            context.user_data.pop("_current_search_type", None)
            
            # عرض التقويم مباشرة
            from .date_time_handlers import render_date_selection
            nav_push(context, STATE_SELECT_DATE)
            context.user_data['_conversation_state'] = STATE_SELECT_DATE
            context.user_data['last_valid_state'] = 'date_selection'
            
            if query:
                await render_date_selection(query.message, context, query=query)
            else:
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
        context.user_data['_nav_stack'] = []
        
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
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context, query=query)
            nav_push(context, STATE_SELECT_DATE)
            context.user_data['_conversation_state'] = STATE_SELECT_DATE
            return STATE_SELECT_DATE

        popped = nav_pop(context)
        previous_step = nav_peek(context)
        new_history = nav_get_history(context)

        logger.info(f"🔙 BACK: popped={popped}, previous_step={previous_step}, new_history={new_history}")

        if previous_step is None:
            logger.info("🔙 BACK: No previous step, going to start")
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context, query=query)
            nav_push(context, STATE_SELECT_DATE)
            context.user_data['_conversation_state'] = STATE_SELECT_DATE
            return STATE_SELECT_DATE

        context.user_data['_conversation_state'] = previous_step

        if previous_step == STATE_SELECT_DATE:
            from .date_time_handlers import render_date_selection
            await render_date_selection(query.message, context, query=query)
            return STATE_SELECT_DATE
        elif previous_step == STATE_SELECT_PATIENT:
            PatientDataManager.clear_patient_data(context)
            from .patient_handlers import show_patient_selection
            await show_patient_selection(query.message, context, query=query, restore=True, update=update)
            return STATE_SELECT_PATIENT
        elif previous_step == STATE_SELECT_HOSPITAL:
            from .hospital_handlers import show_hospitals_menu
            await show_hospitals_menu(query.message, context, query=query, restore=True)
            return STATE_SELECT_HOSPITAL
        elif previous_step == STATE_SELECT_DEPARTMENT:
            DepartmentDataManager.clear_department_data(context, full_clear=False)
            from .department_handlers import show_departments_menu
            await show_departments_menu(query.message, context, query=query, restore=True)
            return STATE_SELECT_DEPARTMENT
        elif previous_step == STATE_SELECT_SUBDEPARTMENT:
            DepartmentDataManager.clear_department_data(context, full_clear=False)
            from .department_handlers import show_departments_menu
            await show_departments_menu(query.message, context, query=query, restore=True)
            return STATE_SELECT_DEPARTMENT
        elif previous_step == STATE_SELECT_DOCTOR:
            DoctorDataManager.clear_doctor_data(context)
            from .doctor_handlers import show_doctor_input
            await show_doctor_input(query.message, context, query=query)
            return STATE_SELECT_DOCTOR
        elif previous_step == R_ACTION_TYPE:
            report_tmp = context.user_data.get("report_tmp", {})
            report_tmp.pop("medical_action", None)
            report_tmp.pop("action_type", None)
            report_tmp.pop("current_flow", None)
            from .action_type_handlers import show_action_type_menu
            await show_action_type_menu(query.message, context, query=query)
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
            await render_date_selection(query.message, context, query=query)
        elif target_state == STATE_SELECT_PATIENT:
            from .patient_handlers import show_patient_selection
            await show_patient_selection(query.message, context, query=query, restore=True, update=update)
        elif target_state == STATE_SELECT_HOSPITAL:
            from .hospital_handlers import show_hospitals_menu
            await show_hospitals_menu(query.message, context, query=query, restore=True)
        elif target_state == STATE_SELECT_DEPARTMENT:
            from .department_handlers import show_departments_menu
            await show_departments_menu(query.message, context, query=query, restore=True)
        elif target_state == STATE_SELECT_DOCTOR:
            from .doctor_handlers import show_doctor_input
            await show_doctor_input(query.message, context, query=query)
        elif target_state == R_ACTION_TYPE:
            from .action_type_handlers import show_action_type_menu
            await show_action_type_menu(query.message, context, query=query)
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



async def handle_smart_back_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج زر الرجوع الذكي — يعتمد على _nav_stack الذي تملؤه _tracked() wrappers.
    يرجع خطوة واحدة بدقة. إذا كان الـ stack فارغاً يعود لقائمة نوع الإجراء.
    """
    from .states import STATE_SELECT_ACTION_TYPE
    from .execute_smart_state_action import execute_smart_state_action

    query = update.callback_query
    if not query:
        logger.error("❌ handle_smart_back_navigation: No query found")
        return ConversationHandler.END

    try:
        await query.answer()
    except Exception as e:
        logger.warning(f"⚠️ Failed to answer callback: {e}")

    try:
        report_tmp = context.user_data.get('report_tmp', {})
        flow_type = report_tmp.get('current_flow', 'new_consult')
        current_conv_state = context.user_data.get('_conversation_state')

        stack = context.user_data.get('_nav_stack', [])
        logger.info(f"🔙 BACK: stack={stack}, flow={flow_type}, conv_state={current_conv_state}")

        # States between content steps and translator: back from any of these returns to the gate
        if current_conv_state in ("MEDICAL_REPORT_NO_REASON", "MEDICAL_REPORT_IMAGE", "TRANSLATOR_SELECTING"):
            logger.info(f"🔙 BACK: from {current_conv_state} → re-show MEDICAL_REPORT_ASK gate")
            # reset gate-related data so gate re-appears (not skipped)
            report_tmp.pop("_medical_report_step_done", None)
            report_tmp.pop("_medical_attachments", None)
            report_tmp.pop("no_report_reason", None)
            report_tmp.pop("_pending_translator_flow", None)
            report_tmp["_pending_translator_flow"] = flow_type
            first_row = [
                InlineKeyboardButton("✅ نعم", callback_data="medrep:yes"),
                InlineKeyboardButton("❌ لا", callback_data="medrep:no"),
            ]
            if flow_type == "radiology":
                first_row.append(InlineKeyboardButton("⏭️ تخطي", callback_data="medrep:skip"))
            gate_keyboard = InlineKeyboardMarkup([
                first_row,
                [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back")],
            ])
            if flow_type == "operation":
                gate_text = "📎 **هل يوجد تقرير طبي او صور للعملية؟**\n\nاختر (نعم) إذا يوجد تقرير أو صور، أو (لا) إذا لا يوجد."
            elif flow_type in ("rehab_physical", "rehab_device", "device"):
                gate_text = "📎 **هل يوجد صور او فيدوهات للتمارين؟**\n\nاختر (نعم) إذا يوجد صور أو فيديوهات، أو (لا) إذا لا يوجد."
            else:
                gate_text = "📎 **هل يوجد تقرير طبي؟**\n\nاختر (نعم) إذا يوجد تقرير طبي، أو (لا) إذا لا يوجد."
            try:
                await query.edit_message_text(gate_text, reply_markup=gate_keyboard, parse_mode="Markdown")
            except Exception:
                await query.message.reply_text(gate_text, reply_markup=gate_keyboard, parse_mode="Markdown")
            context.user_data["_conversation_state"] = "MEDICAL_REPORT_ASK"
            return "MEDICAL_REPORT_ASK"

        previous_step = None
        if stack:
            previous_step = stack.pop()
            context.user_data['_nav_stack'] = stack
            logger.info(f"🔙 BACK: popped {previous_step}, stack now={stack}")
        else:
            logger.warning("🔙 BACK: nav stack empty")

        if previous_step is None:
            logger.info("🔙 BACK: no previous step — returning to action type menu")
            try:
                from .action_type_handlers import show_action_type_menu
                context.user_data['_conversation_state'] = STATE_SELECT_ACTION_TYPE
                msg = query.message or update.effective_message
                await show_action_type_menu(msg, context, query=query if query.message else None)
            except Exception as e:
                logger.error(f"Error showing action type menu: {e}", exc_info=True)
            return STATE_SELECT_ACTION_TYPE

        context.user_data['_conversation_state'] = previous_step
        logger.info(f"🔙 BACK: rendering previous_step={previous_step}")

        try:
            await execute_smart_state_action(previous_step, flow_type, update, context)
        except Exception as e:
            logger.error(f"Error in execute_smart_state_action: {e}", exc_info=True)
            try:
                await query.edit_message_text(
                    "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
                    ]])
                )
            except Exception:
                pass
            return previous_step

        return previous_step

    except Exception as e:
        logger.error(f"❌ Error in handle_smart_back_navigation: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ حدث خطأ في الرجوع\n\nيرجى المحاولة مرة أخرى",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
                ]])
            )
        except Exception:
            pass
        return ConversationHandler.END
