# ================================================
# services/handler_timeout.py
# ⏱️ نظام timeout شامل لجميع handlers
# ================================================

import asyncio
import logging
from functools import wraps
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ================================================
# Timeout Decorator
# ================================================

def with_timeout(timeout_seconds: float = 30.0, default_response: str = None):
    """
    Decorator لإضافة timeout للـ handlers
    يضمن أن الـ handler لا يعلق أكثر من timeout_seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                # تنفيذ الـ handler مع timeout
                result = await asyncio.wait_for(
                    func(update, context, *args, **kwargs),
                    timeout=timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                logger.warning(
                    f"⏱️ Handler timeout: {func.__name__} exceeded {timeout_seconds}s "
                    f"for update {update.update_id if update else 'N/A'}"
                )
                
                # إرسال رد افتراضي إذا كان متوفراً
                if default_response and update:
                    try:
                        if update.message:
                            await update.message.reply_text(
                                default_response or 
                                "⏱️ **استغرق الأمر وقتاً طويلاً**\n\n"
                                "يرجى المحاولة مرة أخرى.",
                                parse_mode="Markdown"
                            )
                        elif update.callback_query:
                            await update.callback_query.answer(
                                "⏱️ استغرق الأمر وقتاً طويلاً",
                                show_alert=True
                            )
                    except Exception as send_error:
                        logger.error(f"❌ Failed to send timeout response: {send_error}")
                
                # إرجاع END لإنهاء المحادثة
                from telegram.ext import ConversationHandler
                return ConversationHandler.END
            except Exception as e:
                logger.error(f"❌ Error in handler {func.__name__}: {e}", exc_info=True)
                raise
        
        return wrapper
    return decorator

# ================================================
# Quick Response Helper
# ================================================

async def send_quick_response(update: Update, message: str = None):
    """إرسال رد سريع للمستخدم"""
    try:
        if not message:
            message = "⏳ **جاري المعالجة...**\n\nيرجى الانتظار."
        
        if update.message:
            await update.message.reply_text(message, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.answer("⏳ جاري المعالجة...")
    except Exception as e:
        logger.error(f"❌ Failed to send quick response: {e}")

