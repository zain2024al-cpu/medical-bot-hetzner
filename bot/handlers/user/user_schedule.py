# =============================
# bot/handlers/user/user_schedule.py
# - عرض "جدول اليوم" الذي رفعه الأدمن (كصورة)
# - إن لم يوجد جدول حالياً، يرسل رسالة مناسبة
# =============================

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from db.session import SessionLocal
from db.models import DailySchedule
from datetime import datetime
import os

async def send_todays_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جدول اليوم للمستخدمين - الذي رفعه الأدمن"""
    
    # جلب آخر جدول تم رفعه
    with SessionLocal() as s:
        ds = s.query(DailySchedule).order_by(DailySchedule.date.desc()).first()

    if not ds:
        await update.message.reply_text(
            "⚠️ **لا يوجد جدول متاح حالياً**\n\n"
            "لم يقم الأدمن برفع أي جدول بعد.\n"
            "يرجى المحاولة لاحقاً أو التواصل مع الإدارة.",
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

def register(app):
    # نفس النص "📅 جدول اليوم" المستخدم في الأدمن — ترتيب التسجيل في app.py يحدد أي handler يُفعل أولاً
    app.add_handler(MessageHandler(filters.Regex("^📅 جدول اليوم$"), send_todays_schedule))
