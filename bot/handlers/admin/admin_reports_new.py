# ================================================
# bot/handlers/admin/admin_reports_new.py
# 🖨️ نظام التقارير الجديد - معالج Telegram
# ================================================

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters

from bot.shared_auth import is_admin
from bot.decorators import admin_handler
from shared.report_constants import ReportType, DateRangePreset
from shared.selectors.patient_selector import selector as patient_selector
from shared.selectors.result_router import register as _register_route
from shared.multiselect import engine as multiselect
from shared.multiselect import Option
from services.reporting_engine.report_engine import ReportEngine
from services.reporting_engine.filters import (
    CompositeFilter, DateRangeFilter, HospitalFilter,
    DepartmentFilter, MedicalActionFilter, PatientFilter
)
from services.export_handlers.export_factory import ExportFactory
from shared.report_constants import ExportFormat
from db.repositories.statistics_repository import StatisticsRepository

logger = logging.getLogger(__name__)

# ========================================
# States
# ========================================

class States:
    REPORT_TYPE = 100
    DATE_SELECTION = 101
    PATIENT_SELECTION = 102
    DEPARTMENT_SELECTION = 103
    ACTION_SELECTION = 104
    GENERATING = 105

_RKEY_PATIENT = "admin.reports.patient"
_RKEY_DEPARTMENTS = "admin.reports.departments"
_RKEY_ACTIONS = "admin.reports.actions"


# ========================================
# Main Entry Point
# ========================================

async def start_reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    نقطة الدخول الرئيسية - عرض الزرين الرئيسيين
    """
    user = update.effective_user
    
    if not user or not is_admin(user.id):
        await update.message.reply_text("❌ أنت لست مشرفاً")
        return ConversationHandler.END
    
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("📊 تقرير شامل", callback_data="report_type:global")],
        [InlineKeyboardButton("👤 تقرير مريض", callback_data="report_type:patient")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")],
    ]
    
    await update.message.reply_text(
        "🖨️ *نظام التقارير الجديد*\n\n"
        "اختر نوع التقرير المطلوب:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    
    return States.REPORT_TYPE


# ========================================
# Report Type Selection
# ========================================

async def handle_report_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيار نوع التقرير"""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data or ""
    
    if data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية")
        return ConversationHandler.END
    
    # استخراج نوع التقرير
    report_type = data.split(":")[1]  # "global" أو "patient"
    context.user_data["report_type"] = report_type
    
    logger.info(f"📊 نوع التقرير المختار: {report_type}")
    
    # الخطوة التالية حسب نوع التقرير
    if report_type == "global":
        return await show_date_selection(query, context)
    elif report_type == "patient":
        return await show_patient_selection(query, context)
    
    return ConversationHandler.END


# ========================================
# Global Report - Date Selection
# ========================================

async def show_date_selection(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض خيارات تحديد الفترة الزمنية"""
    
    keyboard = [
        [InlineKeyboardButton("📅 آخر شهر", callback_data="date:last_month")],
        [InlineKeyboardButton("📅 آخر 3 أشهر", callback_data="date:last_3_months")],
        [InlineKeyboardButton("📅 هذه السنة", callback_data="date:this_year")],
        [InlineKeyboardButton("📅 كل الفترات", callback_data="date:all_time")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="back_to_type")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")],
    ]
    
    await query.edit_message_text(
        "📅 *اختر الفترة الزمنية*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    
    return States.DATE_SELECTION


async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيار الفترة الزمنية"""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data or ""
    
    if data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية")
        return ConversationHandler.END
    
    if data == "back_to_type":
        return await start_reports_menu(update, context)
    
    # استخراج نوع الفترة
    date_preset = data.split(":")[1]
    context.user_data["date_preset"] = date_preset
    
    logger.info(f"📅 الفترة الزمنية المختارة: {date_preset}")
    
    # بدء إنشاء التقرير
    await query.edit_message_text(
        "⏳ جاري إنشاء التقرير...\n\n"
        "الرجاء الانتظار..."
    )
    
    return await generate_global_report(update, context)


# ========================================
# Patient Report - Patient Selection
# ========================================

async def show_patient_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فتح محدد المرضى المشترك في نظام المترجمين"""
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)
    return States.PATIENT_SELECTION


async def _on_patient_selected(result, update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة نتيجة اختيار المريض من patient_selector"""
    if result.cancelled:
        await update.effective_chat.send_message("✅ تم إلغاء العملية")
        return

    patient = result.patient
    if patient is None:
        await update.effective_chat.send_message("⚠️ حدث خطأ في اختيار المريض. يرجى المحاولة مرة أخرى.")
        return

    context.user_data["patient_id"] = patient.id
    context.user_data["patient_name"] = patient.name
    logger.info(f"👤 المريض المختار: {patient.id} ({patient.name})")

    await show_department_selection(update, context)


async def show_department_selection(update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فتح قائمة اختيار الأقسام المتعددة"""
    stats_repo = StatisticsRepository()
    filters = CompositeFilter()
    filters.add("patient", PatientFilter(patient_id=context.user_data.get("patient_id")))
    departments = stats_repo.get_department_statistics(filters)

    options = [
        Option(id="all_departments", label="كل الأقسام", icon="🏥"),
    ]
    options.extend(
        Option(id=str(dept["id"]), label=dept["name"], icon="🏥")
        for dept in departments
    )

    await multiselect.open(
        update,
        context,
        title="🏢 اختر الأقسام",
        options=options,
        return_to=_RKEY_DEPARTMENTS,
        icon="🏥",
        min_select=0,
    )

    return States.DEPARTMENT_SELECTION


async def _on_departments_selected(result, update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة نتيجة اختيار الأقسام من multiselect"""
    if result.cancelled:
        await update.effective_chat.send_message("✅ تم إلغاء العملية")
        return

    ids = result.ids
    if not ids or "all_departments" in ids:
        context.user_data["department_ids"] = None
        logger.info("🏢 الأقسام المختارة: الكل")
    else:
        context.user_data["department_ids"] = [int(dept_id) for dept_id in ids]
        logger.info(f"🏢 الأقسام المختارة: {context.user_data['department_ids']}")

    await show_action_selection(update, context)


async def show_action_selection(update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فتح قائمة اختيار الإجراءات المتعددة"""
    stats_repo = StatisticsRepository()
    filters = CompositeFilter()
    filters.add("patient", PatientFilter(patient_id=context.user_data.get("patient_id")))
    actions = stats_repo.get_action_statistics(filters)

    options = [
        Option(id="all_actions", label="كل الإجراءات", icon="💉"),
    ]
    options.extend(
        Option(id=action["name"], label=action["name"], icon="💉")
        for action in actions
    )

    await multiselect.open(
        update,
        context,
        title="💉 اختر الإجراءات",
        options=options,
        return_to=_RKEY_ACTIONS,
        icon="💉",
        min_select=0,
    )

    return States.ACTION_SELECTION


async def _on_actions_selected(result, update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة نتيجة اختيار الإجراءات من multiselect"""
    if result.cancelled:
        await update.effective_chat.send_message("✅ تم إلغاء العملية")
        return

    ids = result.ids
    if not ids or "all_actions" in ids:
        context.user_data["action_names"] = None
        logger.info("💉 الإجراءات المختارة: الكل")
    else:
        context.user_data["action_names"] = ids
        logger.info(f"💉 الإجراءات المختارة: {context.user_data['action_names']}")

    query = update.callback_query
    if query:
        await show_date_selection(query, context)
    else:
        await show_date_selection(update, context)


# ========================================
# Report Generation
# ========================================

async def generate_global_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إنشاء التقرير الشامل"""
    
    try:
        # إعداد الفلاتر
        filters = CompositeFilter()
        
        # إضافة فلتر الفترة الزمنية
        date_preset = context.user_data.get("date_preset")
        if date_preset:
            preset_enum = DateRangePreset[date_preset.upper()]
            date_filter = DateRangeFilter(preset=preset_enum)
            filters.add("date_range", date_filter)
        
        logger.info(f"🔨 بناء التقرير الشامل")
        
        # بناء التقرير
        engine = ReportEngine()
        report_data = engine.build_report(
            report_type=ReportType.GLOBAL,
            filters=filters,
            title="تقرير شامل",
            subtitle=f"الفترة: {date_preset}" if date_preset else "كل الفترات",
        )
        
        # تصدير إلى PDF
        logger.info("📤 تصدير إلى PDF")
        pdf_buffer = ExportFactory.export(
            report_data=report_data,
            format=ExportFormat.PDF,
            filename=f"تقرير_شامل_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        
        # إرسال الملف
        if pdf_buffer:
            await update.effective_chat.send_document(
                document=pdf_buffer,
                filename=f"تقرير_شامل_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                caption="✅ تم إنشاء التقرير الشامل بنجاح"
            )
            logger.info("✅ تم إرسال التقرير بنجاح")
        
        return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء التقرير: {e}", exc_info=True)
        await update.effective_chat.send_message(f"❌ حدث خطأ: {e}")
        return ConversationHandler.END


# ========================================
# Cancel Handler
# ========================================

async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء العملية"""
    
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ تم إلغاء العملية")
    
    return ConversationHandler.END


# ========================================
# Registration (يتم استدعاؤها من main app)
# ========================================

def register_new_reports_handlers(dispatcher):
    """تسجيل معالجات التقارير الجديدة"""
    
    logger.info("📊 تسجيل معالجات التقارير الجديدة")
    
    # ConversationHandler الرئيسي
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.COMMAND & filters.Regex("^/reports_new$"),
                start_reports_menu
            ),
            MessageHandler(
                filters.Regex("^🖨️ طباعة التقارير$"),
                start_reports_menu
            ),
        ],
        states={
            States.REPORT_TYPE: [
                CallbackQueryHandler(handle_report_type, pattern="^report_type:|cancel"),
            ],
            States.DATE_SELECTION: [
                CallbackQueryHandler(handle_date_selection, pattern="^date:|back_to_type|cancel"),
            ],
            States.PATIENT_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient_search),
                CallbackQueryHandler(handle_patient_selected, pattern="^patient:|cancel"),
            ],
            States.DEPARTMENT_SELECTION: [
                CallbackQueryHandler(handle_department_selection, pattern="^dept:|cancel"),
            ],
            States.ACTION_SELECTION: [
                CallbackQueryHandler(handle_action_selection, pattern="^action:|cancel"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_operation, pattern="^cancel$"),
        ],
    )
    
    dispatcher.add_handler(conv_handler)
    logger.info("✅ تم تسجيل معالجات التقارير بنجاح")
