# ================================================
# bot/handlers/shared/medical_files_access.py
# 📂 زر "فتح التقارير الطبية" — إرسال الملفات خاصةً لمن ضغط الزر فقط
# ================================================
#
# ✅ التصميم: الملفات تُرسَل دائماً إلى محادثة المستخدم الخاصة مع البوت
# (عبر query.from_user.id — هوية الضاغط تحديداً، وليس query.message.chat.id
# الذي كان يشير لمحادثة المجموعة نفسها حيث ضُغط الزر). لا تُرسَل أي رسالة
# جديدة إلى المجموعة إطلاقاً تحت أي ظرف — لا الملفات، ولا رسائل الخطأ/
# التنبيه، فكل هذه تُعرَض للضاغط فقط عبر Alert (query.answer(show_alert=True))
# أو تُرسَل لمحادثته الخاصة.
#
# ✅ حالة "لم يبدأ المستخدم محادثة خاصة مع البوت": تيليجرام يرفع
# telegram.error.Forbidden عند محاولة مراسلة مستخدم لم يضغط Start في الخاص
# (أو حظر البوت). نلتقط هذا تحديداً ونعرض تنبيهاً واضحاً للضاغط بدل فشل صامت
# أو تسريب أي شيء للمجموعة.

import logging

from telegram import Update
from telegram.error import Forbidden
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_START_BOT_ALERT = (
    "⚠️ يرجى فتح البوت والضغط على Start مرة واحدة "
    "حتى أتمكن من إرسال الملفات إليك."
)


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
    """عند الضغط على '📂 فتح التقارير الطبية' في بطاقة الحالة (سواء كانت
    البطاقة في مجموعة أو في الخاص) — يرسل كل الملفات الطبية المرتبطة بهذا
    التقرير إلى محادثة الضاغط الخاصة مع البوت تحديداً، باستخدام الـfile_id
    المحفوظ مسبقاً. لا تظهر أي رسالة جديدة في المجموعة أياً كانت النتيجة."""
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

        # ✅ هوية الضاغط تحديداً — مصدر الحقيقة الوحيد لوجهة الإرسال، بصرف
        # النظر تماماً عن نوع المحادثة التي ضُغط فيها الزر (مجموعة أو خاص).
        presser_id = query.from_user.id

        # ⚠️ لا نستدعي query.answer() الآن — Telegram لا يعتد فعلياً إلا
        # بأول استدعاء لكل ضغطة، فننتظر معرفة النتيجة النهائية (نجاح/حظر/
        # فشل) لنُبلغ الضاغط بها في استدعاء واحد فقط في نهاية المعالجة.
        sent_count = 0
        blocked = False
        for f in files:  # بترتيب الرفع الأصلي — for عادي وليس gather
            ftype = f.get("file_type")
            fid = f.get("file_id")
            if not fid:
                continue
            try:
                await _send_one_medical_file(context.bot, presser_id, ftype, fid)
                sent_count += 1
            except Forbidden:
                # المستخدم لم يبدأ محادثة خاصة مع البوت (أو حظره) — هذا
                # ينطبق على كامل المحادثة، فلا فائدة من محاولة بقية الملفات.
                blocked = True
                break
            except Exception as send_err:
                logger.warning(
                    f"⚠️ medical_files_access: فشل إرسال ملف (report_id={report_id}, type={ftype}): {send_err}"
                )

        if blocked:
            await query.answer(_START_BOT_ALERT, show_alert=True)
            return

        if sent_count == 0:
            await query.answer("⚠️ تعذّر إرسال الملفات حالياً. حاول لاحقاً.", show_alert=True)
            return

        await query.answer(f"✅ تم إرسال {sent_count} ملف إلى محادثتك الخاصة.")

    except Exception as e:
        logger.exception(f"❌ خطأ في handle_medical_files_callback: {e}")
        try:
            await update.callback_query.answer("⚠️ حدث خطأ أثناء جلب الملفات.", show_alert=True)
        except Exception:
            pass


__all__ = ["handle_medical_files_callback"]
