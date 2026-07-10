# =============================
# bot/handlers/admin/admin_schedule.py
# - رفع "جدول اليوم" (صورة) من قبل الأدمن
# - يحفظ سجلًا في DB (ScheduleImage & DailySchedule)
# - يسمح بالإلغاء أثناء المحادثة
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import os
from datetime import datetime
from db.session import SessionLocal
from db.models import ScheduleImage, DailySchedule, Translator
from bot.shared_auth import is_admin
from bot.handlers.admin.decorators import require_admin

UPLOAD_IMAGE, CONFIRM_SAVE = range(2)

def _confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 حفظ الجدول", callback_data="save:yes"),
         InlineKeyboardButton("❌ إلغاء", callback_data="save:no")]
    ])

async def start_upload_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # يتأكد أن المستخدم أدمن
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END

    await update.message.reply_text("📤 أرسل صورة *جدول اليوم* الآن (كصورة أو كملف صورة).", parse_mode="HTML")
    return UPLOAD_IMAGE

@require_admin
async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    # الصورة قد تكون photo (list) أو document
    file_id = None
    filename = None
    if msg.photo:
        # أخذ أفضل دقة
        file_id = msg.photo[-1].file_id
        filename = f"schedule_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    elif msg.document and msg.document.mime_type.startswith("image"):
        file_id = msg.document.file_id
        filename = msg.document.file_name or f"schedule_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jpg"
    else:
        await update.message.reply_text("⚠️ لم يتم التعرف على الملف. أرسل صورة أو ملف صورة.")
        return UPLOAD_IMAGE

    context.user_data["schedule_file_id"] = file_id
    context.user_data["schedule_filename"] = filename

    await update.message.reply_text("✅ تم استلام الصورة. هل تريد حفظها كـ 'جدول اليوم'؟", reply_markup=_confirm_kb())
    return CONFIRM_SAVE

@require_admin
async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "save:no":
        context.user_data.pop("schedule_file_id", None)
        context.user_data.pop("schedule_filename", None)
        await q.edit_message_text("❌ تم إلغاء حفظ الجدول.")
        return ConversationHandler.END

    # حفظ الملف فعليًا (تنزيل من تلغرام) ثم تخزين السجل في DB
    file_id = context.user_data.get("schedule_file_id")
    filename = context.user_data.get("schedule_filename")
    if not file_id:
        await q.edit_message_text("⚠️ لا يوجد ملف محفوظ. أعد العملية.")
        return ConversationHandler.END

    # مجلد الحفظ المحلي
    out_dir = os.path.join("uploads", "schedules")
    os.makedirs(out_dir, exist_ok=True)
    local_path = os.path.join(out_dir, filename)

    try:
        the_file = await q.get_bot().get_file(file_id)
        await the_file.download_to_drive(local_path)
    except Exception as e:
        await q.edit_message_text(f"⚠️ فشل تنزيل الصورة: {e}")
        return ConversationHandler.END

    # حفظ المراجع في DB
    user = q.from_user
    with SessionLocal() as s:
        # سجل ScheduleImage
        si = ScheduleImage(
            file_id=file_id,
            file_path=local_path,
            uploader_id=user.id,
            uploaded_at=datetime.utcnow()
        )
        s.add(si)
        s.commit()

        # سجل DailySchedule (نضع سجل جديد يُشير لآخر جدول)
        ds = DailySchedule(
            date=datetime.utcnow(),
            photo_path=local_path,
            uploaded_by=user.id
        )
        s.add(ds)
        s.commit()

    context.user_data.pop("schedule_file_id", None)
    context.user_data.pop("schedule_filename", None)

    await q.edit_message_text("✅ تم حفظ جدول اليوم وإتاحته للمستخدمين.")
    return ConversationHandler.END

@require_admin
async def cancel_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # إلغاء عبر رسالة نصية (بديل)
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

def register(app):
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 جدول اليوم$"), start_upload_schedule)],
        states={
            UPLOAD_IMAGE: [MessageHandler((filters.PHOTO | (filters.Document.IMAGE)) & ~filters.COMMAND, receive_image)],
            CONFIRM_SAVE: [CallbackQueryHandler(handle_confirm, pattern="^save:(yes|no)$")],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ إلغاء$"), cancel_flow)],
        per_chat=True,
        per_user=True,
        name="admin_schedule_conv",
    )
    app.add_handler(conv)
