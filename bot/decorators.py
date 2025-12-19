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



