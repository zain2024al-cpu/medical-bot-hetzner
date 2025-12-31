# =============================
# navigation.py
# Navigation Stack Implementation
# نظام سجل التنقل المبني على context.user_data['history']
# =============================

import logging

logger = logging.getLogger(__name__)


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
    
    # ✅ منع التكرار: لا نضيف نفس الـ state مرتين متتاليتين
    if state is not None and (not history or history[-1] != state):
        history.append(state)
        logger.info(f"📝 NAV_PUSH: ✅ Added state {state}, history={history}")
        # طباعة مباشرة للتحقق
        print(f"📝 NAV_PUSH: ✅ Added state {state}")
        print(f"📝 NAV_PUSH: Full history = {history}")
        import sys
        sys.stdout.flush()
    else:
        logger.info(f"📝 NAV_PUSH: ⚠️ Skipped duplicate state {state}, history={history}")
        print(f"📝 NAV_PUSH: ⚠️ Skipped duplicate state {state}, history={history}")
        import sys
        sys.stdout.flush()


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
        logger.info(f"📝 NAV_POP: Removed state {popped}, remaining history={history}")
        return popped
    logger.warning("📝 NAV_POP: History is empty")
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
    logger.info("📝 NAV_CLEAR: History cleared")


def nav_get_history(context):
    """
    الحصول على نسخة من سجل التنقل الكامل
    
    Args:
        context: ContextTypes.DEFAULT_TYPE
    
    Returns:
        List of states
    """
    return context.user_data.get('history', []).copy()






