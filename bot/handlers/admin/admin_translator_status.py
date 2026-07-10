#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
👥 لوحة متابعة المترجمين
Translators Status Dashboard
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
from bot.shared_auth import is_admin
from services.translator_reminders import get_translator_status
from db.session import SessionLocal
from db.models import Translator
from datetime import datetime
from bot.handlers.admin.decorators import require_admin

async def show_translators_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة جميع المترجمين"""
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.callback_query:
            await update.callback_query.answer("🚫 للأدمن فقط.", show_alert=True)
        return ConversationHandler.END
    
    try:
        # الحصول على الإحصائيات
        stats = get_translator_status()
        
        # بناء الرسالة
        message = f"""
📊 **حالة المترجمين - {datetime.now().strftime('%Y-%m-%d')}**

👥 الإجمالي: {stats['total']} مترجم
✅ أنزلوا تقارير: {stats['submitted']} ({stats['submitted']*100//stats['total'] if stats['total'] > 0 else 0}%)
⏳ لم ينزلوا: {stats['pending']} ({stats['pending']*100//stats['total'] if stats['total'] > 0 else 0}%)

"""
        
        if stats['late']:
            message += "⚠️ **المتأخرون:**\n\n"
            for i, translator in enumerate(stats['late'][:15], 1):
                message += f"{i}. {translator['name']}\n"
            
            if len(stats['late']) > 15:
                message += f"\n... و {len(stats['late']) - 15} آخرون"
        else:
            message += "✅ **جميع المترجمين أنزلوا تقاريرهم!** 🎉"
        
        # لوحة المفاتيح
        keyboard = [
            [InlineKeyboardButton("🔔 إرسال تنبيه للمتأخرين", callback_data="translator:remind_late")],
            [InlineKeyboardButton("📊 تفاصيل كل مترجم", callback_data="translator:details")],
            [InlineKeyboardButton("🔄 تحديث", callback_data="translator:refresh")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back_to_admin")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    except Exception as e:
        error_msg = f"❌ خطأ في عرض حالة المترجمين: {e}"
        if update.callback_query:
            await update.callback_query.answer(error_msg, show_alert=True)
        else:
            await update.message.reply_text(error_msg)


@require_admin
async def send_reminder_to_late_translators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال تنبيه للمترجمين المتأخرين"""
    query = update.callback_query
    await query.answer()
    
    try:
        from services.translator_reminders import check_and_send_reminders
        
        # إرسال التنبيهات
        await check_and_send_reminders(context.bot)
        
        await query.answer("✅ تم إرسال التنبيهات للمترجمين المتأخرين", show_alert=True)
        
        # إعادة عرض الحالة
        await show_translators_status(update, context)
    
    except Exception as e:
        await query.answer(f"❌ خطأ: {e}", show_alert=True)


@require_admin
async def show_translator_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاصيل كل مترجم"""
    query = update.callback_query
    await query.answer()
    
    try:
        today = datetime.now().date()
        db = SessionLocal()
        
        try:
            from db.models import Report
            
            translators = db.query(Translator).filter_by(is_active=True).all()
            
            message = f"📊 **تفاصيل المترجمين - {today}**\n\n"
            
            for translator in translators:
                reports_count = db.query(Report).filter(
                    Report.translator_id == translator.id,
                    Report.report_date == today
                ).count()
                
                status_icon = "✅" if reports_count > 0 else "⏳"
                
                message += f"{status_icon} **{translator.full_name}**\n"
                message += f"   📋 التقارير اليوم: {reports_count}\n\n"
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="translator:status")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        
        finally:
            db.close()
    
    except Exception as e:
        await query.answer(f"❌ خطأ: {e}", show_alert=True)


def register(application):
    """تسجيل handlers"""
    from telegram.ext import CommandHandler
    
    # أمر عرض حالة المترجمين
    application.add_handler(
        CommandHandler("translators_status", show_translators_status)
    )
    
    # Callback handlers
    application.add_handler(
        CallbackQueryHandler(show_translators_status, pattern="^translator:status$")
    )
    application.add_handler(
        CallbackQueryHandler(show_translators_status, pattern="^translator:refresh$")
    )
    application.add_handler(
        CallbackQueryHandler(send_reminder_to_late_translators, pattern="^translator:remind_late$")
    )
    application.add_handler(
        CallbackQueryHandler(show_translator_details, pattern="^translator:details$")
    )
























