# ================================================
# bot/handlers/shared/medical_files_access.py
# 📂 زر "فتح التقارير الطبية" — إرسال الملفات الطبية خاصة لأي مستخدم يضغط الزر
# ================================================

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_medical_files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عند الضغط على '📂 فتح التقارير الطبية' في بطاقة الحالة —
    يرسل كل الملفات الطبية المرتبطة بهذا التقرير خاصةً لمن ضغط الزر،
    باستخدام الـfile_id المحفوظ مسبقاً (بدون بحث في مجموعة الملفات)."""
    query = update.callback_query
    if not query or not query.data:
        return

    try:
        parts = query.data.split(':', 1)
        if len(parts) < 2:
            await query.answer("⚠️ لم يتم تحديد التقرير.", show_alert=True)
            return
        try:
            report_id = int(parts[1])
        except Exception:
            await query.answer("⚠️ معرف تقرير غير صالح.", show_alert=True)
            return

        from services.medical_attachment_files_service import get_medical_attachment_files
        files = get_medical_attachment_files(report_id)

        if not files:
            await query.answer("لا توجد ملفات طبية مرفقة بهذه الحالة.", show_alert=True)
            return

        # نُقر فوراً لتفادي بقاء دوران "التحميل" على الزر أثناء إرسال الملفات
        await query.answer()

        clicker_id = query.from_user.id
        sent_count = 0
        for f in files:  # بترتيب الرفع الأصلي — for عادي وليس gather
            ftype = f.get("file_type")
            fid = f.get("file_id")
            if not fid:
                continue
            try:
                if ftype == "photo":
                    await context.bot.send_photo(chat_id=clicker_id, photo=fid)
                elif ftype == "video":
                    await context.bot.send_video(chat_id=clicker_id, video=fid)
                elif ftype == "audio":
                    await context.bot.send_audio(chat_id=clicker_id, audio=fid)
                elif ftype == "voice":
                    await context.bot.send_voice(chat_id=clicker_id, voice=fid)
                else:  # "document" أو نوع غير معروف → الخيار الأكثر أماناً
                    await context.bot.send_document(chat_id=clicker_id, document=fid)
                sent_count += 1
            except Exception as send_err:
                error_msg = str(send_err).lower()
                if "bot was blocked by the user" in error_msg or "chat not found" in error_msg:
                    try:
                        await query.answer(
                            "⚠️ يرجى فتح محادثة خاصة مع البوت (اضغط /start) ثم إعادة الضغط على الزر.",
                            show_alert=True,
                        )
                    except Exception:
                        pass
                    return
                logger.warning(
                    f"⚠️ medical_files_access: فشل إرسال ملف (report_id={report_id}, type={ftype}): {send_err}"
                )

        if sent_count == 0:
            try:
                await query.answer("⚠️ تعذّر إرسال الملفات حالياً. حاول لاحقاً.", show_alert=True)
            except Exception:
                pass

    except Exception as e:
        logger.exception(f"❌ خطأ في handle_medical_files_callback: {e}")
        try:
            await update.callback_query.answer("⚠️ حدث خطأ أثناء جلب الملفات.", show_alert=True)
        except Exception:
            pass


__all__ = ["handle_medical_files_callback"]
