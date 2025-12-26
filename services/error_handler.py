# ================================================
# services/error_handler.py
# 🛡️ معالج أخطاء شامل وقوي ومحسّن
# ================================================

import logging
import traceback
import asyncio
from telegram import Update
from telegram.error import TimedOut, NetworkError, RetryAfter, BadRequest, Conflict
from telegram.ext import ContextTypes
from services.resilience_manager import error_rate_limiter, retry_with_backoff

logger = logging.getLogger(__name__)

# ================================================
# Comprehensive Error Handler
# ================================================

async def comprehensive_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج أخطاء شامل - يمنع توقف البوت عند أي خطأ
    """
    try:
        error = context.error
        
        # معلومات الخطأ
        error_type = type(error).__name__
        error_message = str(error)
        
        # معلومات المستخدم
        user_id = None
        chat_id = None
        if update:
            if update.effective_user:
                user_id = update.effective_user.id
            if update.effective_chat:
                chat_id = update.effective_chat.id
        
        # تسجيل الخطأ في error rate limiter
        error_rate_limiter.record_error()
        
        # التحقق من تجاوز معدل الأخطاء
        if error_rate_limiter.is_rate_limited():
            logger.critical(f"🚨 HIGH ERROR RATE DETECTED: {error_rate_limiter.get_error_rate():.2f} errors/sec")
            # لا نحاول إرسال رسائل إضافية عند تجاوز الحد
        
        # تجاهل أخطاء timeout والاتصال - لا نحتاج لتسجيلها كأخطاء حرجة
        ignored_errors = [
            "TimedOut",
            "NetworkError",
            "httpx.ReadError",
            "httpx.ConnectError",
            "httpx.ConnectTimeout",
            "Connection timeout",
            "Read timeout",
            "Connect timeout",
            "RetryAfter",  # إضافة RetryAfter للقائمة
        ]
        
        is_network_error = any(ignored in error_type or ignored in error_message for ignored in ignored_errors)
        
        # معالجة RetryAfter بشكل خاص
        if isinstance(error, RetryAfter):
            retry_after = error.retry_after
            logger.warning(f"⏳ Rate limit hit, retry after {retry_after} seconds")
            if update and update.effective_chat:
                try:
                    if update.message:
                        await update.message.reply_text(
                            f"⏳ **تم تجاوز الحد المسموح**\n\n"
                            f"يرجى المحاولة بعد {retry_after} ثانية.",
                            parse_mode="Markdown"
                        )
                    elif update.callback_query:
                        await update.callback_query.answer(
                            f"⏳ يرجى المحاولة بعد {retry_after} ثانية",
                            show_alert=True
                        )
                except:
                    pass
            return
        
        if is_network_error:
            # تسجيل تحذير فقط بدون traceback كامل
            logger.warning(f"⚠️ خطأ اتصال (مُتجاهل): {error_type} - {error_message[:100]}")
            return  # لا نحاول إرسال رسالة خطأ للمستخدم
        
        # تسجيل الخطأ للأخطاء غير المتعلقة بالشبكة
        logger.error("=" * 80)
        logger.error(f"❌ خطأ غير متوقع في البوت:")
        logger.error(f"   النوع: {error_type}")
        logger.error(f"   الرسالة: {error_message}")
        logger.error(f"   المستخدم: {user_id}")
        logger.error(f"   الدردشة: {chat_id}")
        logger.error(f"   Traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        
        # محاولة إرسال رسالة للمستخدم (فقط للأخطاء غير المتعلقة بالشبكة)
        if update and update.effective_chat and not error_rate_limiter.is_rate_limited():
            try:
                # رسالة خطأ واضحة
                error_msg = (
                    "⚠️ **حدث خطأ غير متوقع**\n\n"
                    "يرجى المحاولة مرة أخرى.\n\n"
                    "إذا استمرت المشكلة، استخدم /cancel ثم ابدأ من جديد."
                )
                
                # استخدام retry مع backoff لإرسال الرسالة
                async def send_error_message():
                    if update.message:
                        await update.message.reply_text(
                            error_msg,
                            parse_mode="Markdown"
                        )
                    elif update.callback_query:
                        await update.callback_query.answer(
                            "⚠️ حدث خطأ. يرجى المحاولة مرة أخرى.",
                            show_alert=True
                        )
                        try:
                            await update.callback_query.message.reply_text(
                                error_msg,
                                parse_mode="Markdown"
                            )
                        except:
                            pass
                
                await retry_with_backoff(
                    send_error_message,
                    max_retries=2,
                    initial_delay=0.5,
                    exceptions=(TimedOut, NetworkError, BadRequest)
                )
                        
            except Exception as send_error:
                logger.error(f"❌ فشل إرسال رسالة خطأ للمستخدم: {send_error}")
        
        # تنظيف البيانات المؤقتة في حالة الأخطاء الحرجة
        if "database" in error_message.lower() or "connection" in error_message.lower():
            try:
                if context.user_data:
                    # تنظيف جزئي فقط - لا نحذف كل شيء
                    context.user_data.pop("_temp_error_state", None)
            except:
                pass
        
    except Exception as handler_error:
        # حتى معالج الأخطاء فشل!
        logger.critical(f"💥 فشل معالج الأخطاء نفسه: {handler_error}")
        logger.critical(traceback.format_exc())






