# ================================================
# Error Handler Utilities - معالجة الأخطاء الشاملة
# ================================================

import logging
import asyncio
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from db.session import SessionLocal

logger = logging.getLogger(__name__)

# ================================================
# Decorator لمعالجة الأخطاء تلقائياً
# ================================================

def safe_handler(max_retries=3, timeout=30):
    """
    Decorator لمعالجة الأخطاء تلقائياً في handlers
    
    Args:
        max_retries: عدد المحاولات عند الفشل
        timeout: timeout بالثواني
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # تنفيذ الدالة مع timeout
                    result = await asyncio.wait_for(
                        func(update, context, *args, **kwargs),
                        timeout=timeout
                    )
                    return result
                    
                except asyncio.TimeoutError:
                    error_msg = f"⏱️ Timeout في {func.__name__} (محاولة {attempt + 1}/{max_retries})"
                    logger.warning(error_msg)
                    last_error = "Timeout"
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # انتظار قصير قبل إعادة المحاولة
                    else:
                        # آخر محاولة - إرسال رسالة للمستخدم
                        try:
                            if update.message:
                                await update.message.reply_text(
                                    "⏱️ **انتهت مهلة الانتظار**\n\n"
                                    "يرجى المحاولة مرة أخرى أو استخدام /cancel للإلغاء.",
                                    parse_mode="Markdown"
                                )
                            elif update.callback_query:
                                await update.callback_query.answer(
                                    "⏱️ انتهت مهلة الانتظار",
                                    show_alert=True
                                )
                        except Exception as e:
                            logger.error(f"❌ فشل إرسال رسالة timeout: {e}")
                        
                        # إرجاع state آمن
                        return get_safe_state(context)
                        
                except Exception as e:
                    error_msg = f"❌ خطأ في {func.__name__} (محاولة {attempt + 1}/{max_retries}): {e}"
                    logger.error(error_msg, exc_info=True)
                    last_error = e
                    
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5)  # انتظار قصير قبل إعادة المحاولة
                    else:
                        # آخر محاولة - إرسال رسالة للمستخدم
                        try:
                            if update.message:
                                await update.message.reply_text(
                                    "❌ **حدث خطأ غير متوقع**\n\n"
                                    "يرجى المحاولة مرة أخرى أو استخدام /cancel للإلغاء.\n\n"
                                    "إذا استمرت المشكلة، يرجى التواصل مع الإدارة.",
                                    parse_mode="Markdown"
                                )
                            elif update.callback_query:
                                await update.callback_query.answer(
                                    "❌ حدث خطأ",
                                    show_alert=True
                                )
                        except Exception as e:
                            logger.error(f"❌ فشل إرسال رسالة خطأ: {e}")
                        
                        # إرجاع state آمن
                        return get_safe_state(context)
            
            # إذا فشلت جميع المحاولات
            logger.error(f"❌ فشل {func.__name__} بعد {max_retries} محاولات. آخر خطأ: {last_error}")
            return get_safe_state(context)
            
        return wrapper
    return decorator


# ================================================
# Helper Functions
# ================================================

def get_safe_state(context: ContextTypes.DEFAULT_TYPE):
    """الحصول على state آمن للعودة إليه"""
    from bot.handlers.user.user_reports_add_new_system import (
        STATE_SELECT_PATIENT,
        R_ACTION_TYPE,
        ConversationHandler.END
    )
    
    # محاولة الحصول على state الحالي
    current_state = context.user_data.get('_conversation_state')
    if current_state:
        return current_state
    
    # محاولة الحصول على state من report_tmp
    report_tmp = context.user_data.get("report_tmp", {})
    if report_tmp.get("patient_name"):
        return STATE_SELECT_PATIENT
    
    # إرجاع state افتراضي آمن
    return R_ACTION_TYPE


async def safe_database_operation(operation, *args, **kwargs):
    """
    تنفيذ عملية قاعدة بيانات بشكل آمن مع retry
    
    Args:
        operation: دالة قاعدة البيانات
        *args, **kwargs: معاملات الدالة
    """
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        session = None
        try:
            session = SessionLocal()
            result = await operation(session, *args, **kwargs)
            session.commit()
            return result
            
        except Exception as e:
            last_error = e
            logger.warning(f"⚠️ خطأ في قاعدة البيانات (محاولة {attempt + 1}/{max_retries}): {e}")
            
            if session:
                try:
                    session.rollback()
                except:
                    pass
                try:
                    session.close()
                except:
                    pass
            
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)  # انتظار قبل إعادة المحاولة
            else:
                logger.error(f"❌ فشل عملية قاعدة البيانات بعد {max_retries} محاولات: {last_error}")
                raise
    
    raise Exception(f"فشل عملية قاعدة البيانات: {last_error}")


async def safe_send_message(update: Update, text: str, **kwargs):
    """إرسال رسالة بشكل آمن مع retry"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if update.message:
                return await update.message.reply_text(text, **kwargs)
            elif update.callback_query:
                return await update.callback_query.message.reply_text(text, **kwargs)
            else:
                logger.warning("⚠️ لا توجد رسالة أو callback_query في update")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️ فشل إرسال رسالة (محاولة {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
            else:
                logger.error(f"❌ فشل إرسال رسالة بعد {max_retries} محاولات")
                raise


async def safe_edit_message(query, text: str, **kwargs):
    """تعديل رسالة بشكل آمن مع retry"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            return await query.edit_message_text(text, **kwargs)
        except Exception as e:
            logger.warning(f"⚠️ فشل تعديل رسالة (محاولة {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)
            else:
                # Fallback: إرسال رسالة جديدة
                try:
                    return await query.message.reply_text(text, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"❌ فشل إرسال رسالة بديلة: {fallback_error}")
                    raise

