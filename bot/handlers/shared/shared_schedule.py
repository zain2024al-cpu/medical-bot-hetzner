# ================================================
# bot/handlers/shared/shared_schedule.py
# 📅 زر جدول اليوم المشترك (للجميع)
# - للأدمن: يسمح برفع جدول جديد
# - للمستخدمين: يعرض الجدول المرفوع
# ================================================

from bot.handlers.admin.decorators import require_admin
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from bot.shared_auth import is_admin
from db.session import SessionLocal
from db.models import DailySchedule
from datetime import datetime, timedelta, date
from sqlalchemy import func
import os


async def handle_schedule_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة زر "📅 جدول اليوم"
    - للأدمن: خيارات رفع أو عرض الجدول
    - للمستخدمين: عرض الجدول المرفوع مباشرة
    """
    user = update.effective_user
    tg_id = user.id
    
    if is_admin(tg_id):
        # للأدمن: عرض خيارات
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 رفع جدول جديد", callback_data="schedule_admin:upload")],
            [InlineKeyboardButton("👁️ عرض الجدول الحالي", callback_data="schedule_admin:view")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="schedule_admin:cancel")]
        ])
        
        await update.message.reply_text(
            "📅 **إدارة جدول اليوم**\n\n"
            "اختر الإجراء المطلوب:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    else:
        # للمستخدمين العاديين: عرض الجدول مباشرة
        await show_schedule_to_user(update, context)


async def show_schedule_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE, allow_latest: bool = False):
    """عرض جدول اليوم للمستخدمين"""
    today = date.today()
    with SessionLocal() as s:
        if allow_latest:
            ds = s.query(DailySchedule).order_by(DailySchedule.date.desc()).first()
        else:
            ds = (
                s.query(DailySchedule)
                .filter(func.date(DailySchedule.date) == today.isoformat())
                .order_by(DailySchedule.date.desc())
                .first()
            )

    if not ds:
        if allow_latest:
            await update.message.reply_text(
                "⚠️ **لا يوجد جدول متاح**\n\n"
                "لم يقم الأدمن برفع أي جدول بعد.\n"
                "يرجى المحاولة لاحقاً أو التواصل مع الإدارة.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "⚠️ **لا يوجد جدول اليوم**\n\n"
                "لم ترفع الإدارة جدول اليوم.\n"
                "يرجى المحاولة لاحقاً.",
                parse_mode="Markdown"
            )
        return

    # إضافة معلومات عن تاريخ الجدول
    days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
    day_name = days_ar.get(ds.date.weekday(), '')
    date_str = ds.date.strftime('%Y-%m-%d')
    
    # محاولة إرسال الصورة
    if ds.photo_path and os.path.exists(ds.photo_path):
        try:
            with open(ds.photo_path, "rb") as photo_file:
                await update.message.reply_photo(
                    photo=photo_file,
                    caption=f"📅 **جدول اليوم**\n\n"
                            f"📆 التاريخ: {date_str} ({day_name})\n"
                            f"🕐 آخر تحديث: {ds.created_at.strftime('%H:%M')}\n\n"
                            f"✅ تم رفعه بواسطة الإدارة",
                    parse_mode="Markdown"
                )
            return
        except Exception as e:
            print(f"خطأ في إرسال صورة الجدول: {e}")

    # إذا فشل إرسال الصورة
    await update.message.reply_text(
        "⚠️ **تعذر عرض صورة الجدول**\n\n"
        "حدث خطأ أثناء تحميل الصورة.\n"
        "يرجى المحاولة لاحقاً أو التواصل مع الإدارة.",
        parse_mode="Markdown"
    )


@require_admin
async def handle_schedule_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة خيارات الأدمن لجدول اليوم"""
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    
    if action == "view":
        # عرض الجدول للأدمن
        await query.edit_message_text("🔄 جاري جلب الجدول...")
        # نستخدم نفس دالة عرض المستخدمين
        update.message = query.message
        await show_schedule_to_user(update, context, allow_latest=True)
        
    elif action == "upload":
        # بدء عملية رفع جدول جديد
        await query.edit_message_text(
            "📤 **رفع جدول جديد**\n\n"
            "يرجى الانتقال إلى:\n"
            "👉 **📅 إدارة الجدول** من القائمة الرئيسية\n\n"
            "لرفع جدول جديد بشكل صحيح.",
            parse_mode="Markdown"
        )
        
    elif action == "cancel":
        await query.edit_message_text("❌ تم الإلغاء.")


def register(app):
    """تسجيل handler زر جدول اليوم المشترك"""
    app.add_handler(MessageHandler(filters.Regex("^📅 جدول اليوم$"), handle_schedule_button))
    app.add_handler(CallbackQueryHandler(handle_schedule_admin_callback, pattern="^schedule_admin:"))
