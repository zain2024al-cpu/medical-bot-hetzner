# =============================
# navigation.py
# Navigation Stack Implementation
# نظام سجل التنقل المبني على context.user_data['history']
# =============================

import logging

logger = logging.getLogger(__name__)

MAX_NAV_DEPTH = 25


def nav_push(context, state):
    """
    إضافة state جديد إلى سجل التنقل (History Stack)

    Args:
        context: ContextTypes.DEFAULT_TYPE
        state: State constant (مثل STATE_SELECT_HOSPITAL)

    Returns:
        None
    """
    if 'history' not in context.user_data:
        context.user_data['history'] = []

    history = context.user_data['history']

    if state is None or (history and history[-1] == state):
        return

    if len(history) >= 2 and history[-2] == state:
        removed = history.pop()
        logger.debug(f"NAV_COLLAPSE: removed={removed} depth={len(history)}")
        return

    history.append(state)
    # Trim oldest entries to prevent unbounded growth
    if len(history) > MAX_NAV_DEPTH:
        del history[:len(history) - MAX_NAV_DEPTH]
    logger.debug(f"NAV_PUSH: added={state} depth={len(history)}")


def nav_pop(context):
    """
    إزالة وإرجاع آخر state من سجل التنقل
    
    Args:
        context: ContextTypes.DEFAULT_TYPE
    
    Returns:
        State constant أو None إذا كان السجل فارغاً
    """
    history = context.user_data.get('history', [])
    if history:
        popped = history.pop()
        logger.debug(f"NAV_POP: removed={popped} depth={len(history)}")
        return popped
    logger.debug("NAV_POP: history empty")
    return None


def nav_peek(context):
    """
    رؤية آخر state بدون إزالته
    
    Args:
        context: ContextTypes.DEFAULT_TYPE
    
    Returns:
        State constant أو None إذا كان السجل فارغاً
    """
    history = context.user_data.get('history', [])
    if history:
        return history[-1]
    return None


def nav_get_previous(context):
    """
    الحصول على الـ state السابق (قبل الأخير)
    
    Args:
        context: ContextTypes.DEFAULT_TYPE
    
    Returns:
        State constant أو None إذا لم يكن هناك state سابق
    """
    history = context.user_data.get('history', [])
    if len(history) >= 2:
        return history[-2]
    return None


def nav_clear(context):
    """
    تنظيف سجل التنقل بالكامل
    
    Args:
        context: ContextTypes.DEFAULT_TYPE
    
    Returns:
        None
    """
    context.user_data['history'] = []
    logger.debug("NAV_CLEAR: history cleared")


def nav_get_history(context):
    """
    الحصول على نسخة من سجل التنقل الكامل
    
    Args:
        context: ContextTypes.DEFAULT_TYPE
    
    Returns:
        List of states
    """
    return context.user_data.get('history', []).copy()






