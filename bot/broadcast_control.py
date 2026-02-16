# broadcast_control.py
# ملف تحكم في تفعيل/إيقاف إرسال التقارير للمجموعة

BROADCAST_ENABLED = True

def toggle_broadcast():
    """تبديل حالة البث (من True إلى False أو العكس)"""
    global BROADCAST_ENABLED
    BROADCAST_ENABLED = not BROADCAST_ENABLED
    return BROADCAST_ENABLED

def set_broadcast_enabled(enabled: bool):
    """تعيين حالة البث مباشرة"""
    global BROADCAST_ENABLED
    BROADCAST_ENABLED = enabled
    return BROADCAST_ENABLED

def is_broadcast_enabled():
    """التحقق من حالة البث"""
    return BROADCAST_ENABLED
