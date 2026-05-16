# ================================================
# bot/handlers/user/user_schedule_view.py
# 🔹 عرض الجدول للمستخدمين
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from datetime import date, datetime
from db.session import SessionLocal
from db.models import ScheduleImage, DailyReportTracking, Translator
from bot.shared_auth import is_admin

try:
    from bot.handlers.user.user_reports_add_new_system.date_time_handlers import start_report as _start_report
except ImportError:
    _start_report = None

async def view_daily_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الجدول اليومي للمستخدم"""
    user = update.effective_user
    
    # التحقق من أن المستخدم أدمن أولاً
    if is_admin(user.id):
        # إذا كان أدمن، أرسله إلى لوحة الأدمن
        from bot.handlers.admin.admin_start import admin_start
        await admin_start(update, context)
        return
    
    today = date.today()
    
    with SessionLocal() as s:
        # البحث عن الجدول اليوم
        schedule_image = s.query(ScheduleImage).filter(
            ScheduleImage.uploaded_at >= today
        ).order_by(ScheduleImage.uploaded_at.desc()).first()
        
        if schedule_image:
            # إرسال صورة الجدول
            await update.message.reply_text("📅 **جدول اليوم:**")
            
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=schedule_image.file_id,
                caption=f"📅 تاريخ الجدول: {schedule_image.uploaded_at.strftime('%Y-%m-%d %H:%M')}"
            )
            
            # عرض حالة التقرير للمستخدم إذا كان مترجم
            translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
            if translator:
                tracking_record = s.query(DailyReportTracking).filter_by(
                    date=today,
                    translator_name=translator.full_name
                ).first()
                
                if tracking_record:
                    status_text = f"📊 **حالة تقاريرك اليومية:**\n\n"
                    status_text += f"👤 **الاسم:** {translator.full_name}\n"
                    status_text += f"📝 **التقارير المطلوبة:** {tracking_record.expected_reports}\n"
                    status_text += f"📊 **التقارير المرفوعة:** {tracking_record.actual_reports}\n"
                    
                    if tracking_record.is_completed:
                        status_text += f"✅ **الحالة:** مكتمل"
                    else:
                        remaining = tracking_record.expected_reports - tracking_record.actual_reports
                        status_text += f"⏳ **الحالة:** متبقي {remaining} تقرير"
                    
                    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(
                "⚠️ **لا يوجد جدول مرفوع لهذا اليوم**\n\n"
                "يرجى التواصل مع الإدارة لرفع الجدول.",
                parse_mode=ParseMode.MARKDOWN
            )


async def handle_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة استدعاءات الجدول"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_report":
        if _start_report:
            return await _start_report(update, context)
        await query.edit_message_text(
            "📝 **إضافة تقرير جديد**\n\nاضغط على زر '📝 إضافة تقرير جديد' في القائمة الرئيسية.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    elif query.data == "view_my_reports":
        # توجيه لعرض التقارير
        await query.edit_message_text("📋 **عرض تقاريري**\n\nاضغط على زر '📋 عرض تقاريري' في القائمة الرئيسية.")
    
    elif query.data == "view_schedule":
        # عرض الجدول
        await query.edit_message_text("📅 **عرض الجدول**\n\nاضغط على زر '📅 جدول اليوم' في القائمة الرئيسية.")

def register(app):
    """تسجيل الهاندلرز"""
    # معالج عرض الجدول
    app.add_handler(MessageHandler(filters.Regex("^📅 جدول اليوم$"), view_daily_schedule))
    
    # معالج الاستدعاءات
    app.add_handler(CallbackQueryHandler(handle_schedule_callback, pattern="^add_report$|^view_my_reports$|^view_schedule$"))



