# ================================================
# bot/safe_callback.py
# 🔹 دوال مساعدة آمنة للتعامل مع Callback Queries
# ================================================

from telegram import CallbackQuery
from telegram.error import BadRequest, TimedOut, NetworkError


async def safe_answer_callback(query: CallbackQuery, text: str = None, show_alert: bool = False):
    """
    الرد على callback query بشكل آمن مع معالجة الأخطاء الشائعة
    
    Args:
        query: الـ CallbackQuery المراد الرد عليه
        text: النص المراد عرضه (اختياري)
        show_alert: عرض تنبيه منبثق بدلاً من إشعار صغير
    
    Returns:
        bool: True إذا نجح، False إذا فشل
    """
    try:
        await query.answer(text=text, show_alert=show_alert)
        return True
    except BadRequest as e:
        error_msg = str(e)
        # تجاهل الأخطاء الشائعة وغير الضارة
        if any(x in error_msg for x in [
            "Query is too old",
            "query id is invalid",
            "QUERY_ID_INVALID"
        ]):
            # هذا طبيعي - المستخدم ضغط على زر قديم
            return False
        # أخطاء أخرى - طباعتها للتشخيص
        print(f"⚠️ BadRequest في safe_answer_callback: {e}")
        return False
    except (TimedOut, NetworkError) as e:
        print(f"⚠️ مشكلة شبكة في safe_answer_callback: {e}")
        return False
    except Exception as e:
        print(f"❌ خطأ غير متوقع في safe_answer_callback: {e}")
        return False


async def safe_edit_message(query: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    """
    تعديل رسالة callback query بشكل آمن
    
    Args:
        query: الـ CallbackQuery
        text: النص الجديد
        reply_markup: الكيبورد الجديد (اختياري)
        parse_mode: وضع التنسيق (Markdown, HTML, etc)
    
    Returns:
        bool: True إذا نجح، False إذا فشل
    """
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
        return True
    except BadRequest as e:
        error_msg = str(e)
        # تجاهل الأخطاء الشائعة
        if any(x in error_msg for x in [
            "Message is not modified",
            "Message can't be edited",
            "Message to edit not found",
            "MESSAGE_ID_INVALID"
        ]):
            return False
        print(f"⚠️ BadRequest في safe_edit_message: {e}")
        return False
    except Exception as e:
        print(f"❌ خطأ غير متوقع في safe_edit_message: {e}")
        return False


async def safe_delete_message(query: CallbackQuery):
    """
    حذف رسالة callback query بشكل آمن
    
    Args:
        query: الـ CallbackQuery
    
    Returns:
        bool: True إذا نجح، False إذا فشل
    """
    try:
        await query.message.delete()
        return True
    except BadRequest as e:
        error_msg = str(e)
        if "Message to delete not found" in error_msg:
            return False
        print(f"⚠️ BadRequest في safe_delete_message: {e}")
        return False
    except Exception as e:
        print(f"❌ خطأ غير متوقع في safe_delete_message: {e}")
        return False


















