# ================================================
# bot/handlers/shared/medical_files_access.py
# 📂 زر "فتح التقارير الطبية" — إرسال الملفات في نفس المحادثة لكل من يضغط الزر
# ================================================
#
# ✅ التصميم: الملفات تُرسَل دائماً في نفس المحادثة التي ضُغط فيها الزر
# (وليس خاصةً)، بحيث يعمل الزر بنفس الطريقة تماماً للأدمن ولأي مستخدم
# آخر — بلا اعتماد على ما إذا كان الشخص قد بدأ محادثة خاصة مع البوت من
# قبل أم لا (قيد منصة تيليجرام لا يمكن تجاوزه لولا هذا التصميم).

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def _send_one_medical_file(bot, chat_id, file_type, file_id):
    if file_type == "photo":
        await bot.send_photo(chat_id=chat_id, photo=file_id)
    elif file_type == "video":
        await bot.send_video(chat_id=chat_id, video=file_id)
    elif file_type == "audio":
        await bot.send_audio(chat_id=chat_id, audio=file_id)
    elif file_type == "voice":
        await bot.send_voice(chat_id=chat_id, voice=file_id)
    else:  # "document" أو نوع غير معروف → الخيار الأكثر أماناً
        await bot.send_document(chat_id=chat_id, document=file_id)


async def handle_medical_files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عند الضغط على '📂 فتح التقارير الطبية' في بطاقة الحالة —
    يرسل كل الملفات الطبية المرتبطة بهذا التقرير في نفس المحادثة التي
    ضُغط فيها الزر (لكل المستخدمين بلا استثناء)، باستخدام الـfile_id
    المحفوظ مسبقاً (بدون بحث في مجموعة الملفات)."""
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

        # ✅ نُقر مرة واحدة فقط هنا (answerCallbackQuery لا يمكن استخدامه
        # أكثر من مرة فعلياً لنفس الضغطة) — أي رسائل لاحقة تُرسَل كرسائل
        # عادية عبر send_message وليس عبر query.answer() مرة ثانية.
        await query.answer()

        target_chat_id = query.message.chat.id if query.message else query.from_user.id

        sent_count = 0
        for f in files:  # بترتيب الرفع الأصلي — for عادي وليس gather
            ftype = f.get("file_type")
            fid = f.get("file_id")
            if not fid:
                continue
            try:
                await _send_one_medical_file(context.bot, target_chat_id, ftype, fid)
                sent_count += 1
            except Exception as send_err:
                logger.warning(
                    f"⚠️ medical_files_access: فشل إرسال ملف (report_id={report_id}, type={ftype}): {send_err}"
                )

        if sent_count == 0:
            try:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text="⚠️ تعذّر إرسال الملفات حالياً. حاول لاحقاً.",
                )
            except Exception:
                pass

    except Exception as e:
        logger.exception(f"❌ خطأ في handle_medical_files_callback: {e}")
        try:
            await update.callback_query.answer("⚠️ حدث خطأ أثناء جلب الملفات.", show_alert=True)
        except Exception:
            pass


__all__ = ["handle_medical_files_callback"]
