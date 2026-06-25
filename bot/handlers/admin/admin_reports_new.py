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
from services.reporting_engine.report_engine import ReportEngine
from services.reporting_engine.filters import (
    CompositeFilter, DateRangeFilter, HospitalFilter,
    DepartmentFilter, MedicalActionFilter, PatientFilter
)
from services.export_handlers.export_factory import ExportFactory
from shared.report_constants import ExportFormat
from db.repositories.patient_repository import PatientRepository
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

async def show_patient_selection(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """طلب اسم المريض"""
    
    await query.edit_message_text(
        "👤 *ابحث عن المريض*\n\n"
        "اكتب اسم المريض أو جزءاً منه:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")],
        ]),
    )
    
    return States.PATIENT_SELECTION


async def handle_patient_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة البحث عن المريض"""
    
    search_text = (update.message.text or "").strip()
    
    if not search_text:
        await update.message.reply_text("⚠️ يرجى كتابة اسم المريض")
        return States.PATIENT_SELECTION
    
    # البحث عن المريض
    patient_repo = PatientRepository()
    patients = patient_repo.search_by_name(search_text, limit=20)
    
    if not patients:
        await update.message.reply_text(
            f"⚠️ لم يُعثر على مريض يطابق *{search_text}*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return States.PATIENT_SELECTION
    
    # عرض النتائج
    keyboard = []
    for p in patients:
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {p.full_name}",
                callback_data=f"patient:{p.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    
    await update.message.reply_text(
        f"🔍 نتائج البحث ({len(patients)} مريض):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    
    return States.PATIENT_SELECTION


async def handle_patient_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيار المريض"""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data or ""
    
    if data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية")
        return ConversationHandler.END
    
    # استخراج معرف المريض
    patient_id = int(data.split(":")[1])
    context.user_data["patient_id"] = patient_id
    
    # جلب بيانات المريض
    patient_repo = PatientRepository()
    patient = patient_repo.get_by_id(patient_id)
    
    if patient:
        context.user_data["patient_name"] = patient.full_name
    
    logger.info(f"👤 المريض المختار: {patient_id}")
    
    # عرض خيارات الأقسام
    return await show_department_selection(query, context)


async def show_department_selection(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض خيارات الأقسام"""
    
    # جلب قائمة الأقسام من قاعدة البيانات
    stats_repo = StatisticsRepository()
    filters = CompositeFilter()
    filters.add("patient", PatientFilter(patient_id=context.user_data.get("patient_id")))
    
    departments = stats_repo.get_department_statistics(filters)
    
    keyboard = [
        [InlineKeyboardButton("🏥 جميع الأقسام", callback_data="dept:all")],
    ]
    
    for dept in departments[:10]:  # أعلى 10 أقسام
        keyboard.append([
            InlineKeyboardButton(f"🏢 {dept['name']}", callback_data=f"dept:{dept['id']}")
        ])
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    
    await query.edit_message_text(
        "🏢 *اختر الأقسام*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    
    return States.DEPARTMENT_SELECTION


async def handle_department_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيار الأقسام"""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data or ""
    
    if data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية")
        return ConversationHandler.END
    
    # استخراج معرف القسم
    dept_id = data.split(":")[1]
    context.user_data["department_id"] = dept_id if dept_id != "all" else None
    
    logger.info(f"🏢 القسم المختار: {dept_id}")
    
    # عرض خيارات الإجراءات
    return await show_action_selection(query, context)


async def show_action_selection(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    """عرض خيارات الإجراءات"""
    
    keyboard = [
        [InlineKeyboardButton("💉 جميع الإجراءات", callback_data="action:all")],
    ]
    
    # جلب قائمة الإجراءات
    stats_repo = StatisticsRepository()
    filters = CompositeFilter()
    filters.add("patient", PatientFilter(patient_id=context.user_data.get("patient_id")))
    
    actions = stats_repo.get_action_statistics(filters)
    
    for action in actions[:10]:  # أعلى 10 إجراءات
        keyboard.append([
            InlineKeyboardButton(f"💉 {action['name']}", callback_data=f"action:{action['name']}")
        ])
    
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])
    
    await query.edit_message_text(
        "💉 *اختر الإجراءات*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    
    return States.ACTION_SELECTION


async def handle_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالجة اختيار الإجراءات"""
    
    query = update.callback_query
    await query.answer()
    
    data = query.data or ""
    
    if data == "cancel":
        await query.edit_message_text("✅ تم إلغاء العملية")
        return ConversationHandler.END
    
    # استخراج الإجراء
    action = data.split(":")[1]
    context.user_data["action"] = action if action != "all" else None
    
    logger.info(f"💉 الإجراء المختار: {action}")
    
    # عرض خيارات الفترة الزمنية
    return await show_date_selection(query, context)


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
