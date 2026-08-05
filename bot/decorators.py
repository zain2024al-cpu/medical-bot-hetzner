# ================================================
# bot/decorators.py
# 🛡️ Decorators لمراقبة الأخطاء
# ================================================

import logging
import functools
from typing import Callable, Any
from services.error_monitoring import error_monitor

logger = logging.getLogger(__name__)


def error_handler_decorator(func: Callable) -> Callable:
    """Decorator لمعالجة الأخطاء في الدوال"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            
            # محاولة استخراج update و context من args
            update = None
            context = None
            for arg in args:
                if hasattr(arg, 'callback_query') or hasattr(arg, 'message'):
                    update = arg
                elif hasattr(arg, 'user_data'):
                    context = arg
            
            error_monitor.log_error(
                error=e,
                context=context,
                update=update,
                additional_info={"function": func.__name__}
            )
            
            # إعادة رفع الخطأ للتعامل معه في error_handler الرئيسي
            raise
    
    return wrapper


def safe_execute(func: Callable) -> Callable:
    """Decorator لتنفيذ آمن - لا يرفع الأخطاء"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Error in {func.__name__} (ignored): {e}")
            return None
    
    return wrapper


def admin_handler(func: Callable) -> Callable:
    """
    Decorator خاص لمعالجات الأدمن - يحمي البوت من التوقف
    ويرسل رسالة للمستخدم عند حدوث خطأ
    ويُنهي المحادثة لتحرير الزر للاستخدام مرة أخرى
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        from telegram.ext import ConversationHandler
        
        update = None
        context = None
        
        # استخراج update و context
        for arg in args:
            if hasattr(arg, 'callback_query') or hasattr(arg, 'message'):
                update = arg
            elif hasattr(arg, 'user_data'):
                context = arg
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"❌ خطأ في {func.__name__}:\n{error_details}")
            
            # مسح بيانات المستخدم لإعادة تعيين الحالة
            if context and hasattr(context, 'user_data'):
                try:
                    context.user_data.clear()
                except Exception:
                    logger.debug("تم تجاهل استثناء في wrapper", exc_info=True)
            
            # محاولة إرسال رسالة للمستخدم
            try:
                if update:
                    if hasattr(update, 'callback_query') and update.callback_query:
                        try:
                            await update.callback_query.answer(
                                "⚠️ حدث خطأ، يرجى المحاولة مرة أخرى",
                                show_alert=True
                            )
                        except Exception:
                            logger.debug("تم تجاهل استثناء في wrapper", exc_info=True)
                        try:
                            await update.callback_query.edit_message_text(
                                f"❌ **حدث خطأ**\n\n"
                                f"الخطأ: `{str(e)[:100]}`\n\n"
                                f"✅ تم إعادة تعيين الحالة\n"
                                f"اضغط الزر مرة أخرى أو /start للبدء من جديد",
                                parse_mode="Markdown"
                            )
                        except Exception:
                            logger.debug("تم تجاهل استثناء في wrapper", exc_info=True)
                    elif hasattr(update, 'message') and update.message:
                        await update.message.reply_text(
                            f"❌ **حدث خطأ**\n\n"
                            f"الخطأ: `{str(e)[:100]}`\n\n"
                            f"✅ تم إعادة تعيين الحالة\n"
                            f"اضغط الزر مرة أخرى أو /start للبدء من جديد",
                            parse_mode="Markdown"
                        )
            except Exception as send_error:
                logger.warning(f"⚠️ فشل إرسال رسالة الخطأ: {send_error}")
            
            # ✅ إنهاء المحادثة لتحرير الزر
            return ConversationHandler.END
    
    return wrapper



