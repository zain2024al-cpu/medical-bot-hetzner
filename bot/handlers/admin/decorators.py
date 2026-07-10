# ================================================
# bot/decorators.py
# 🛡️ Decorators لمراقبة الأخطاء
# ================================================

import logging
import functools
from typing import Callable, Any
from services.error_monitoring import error_monitor

logger = logging.getLogger(__name__)


def require_admin(func: Callable) -> Callable:
    """🛡️ حماية موحّدة: يمنع أي مستخدم غير أدمن من الوصول للمعالج مهما كانت
    وسيلة الوصول (زر ظاهر، أمر مكتوب، أو callback_data مُرسَل يدوياً/مُعاد).

    - يُستخرَج المستخدم من كائن Update داخل الوسائط (لا يعتمد على ترتيب ثابت).
    - غير الأدمن يُرفَض برسالة عامة مهذّبة (بلا أي بيانات) ويُعاد
      ConversationHandler.END لتحرير أي محادثة قد تكون بدأت — آمن حتى لو لم
      يكن المعالج ضمن ConversationHandler (القيمة المُعادة تُتجاهَل حينها).
    - الأدمن يمر دون أي تغيير في السلوك (تمرير كامل للوسائط، ولا نستدعي
      query.answer() هنا حتى لا نتعارض مع رد المعالج الأصلي).

    يُطبَّق على نقاط دخول الأدمن (dispatcher الـcallbacks المستقلة، أوامر
    الأدمن، أزرار القوائم، ونقاط دخول ConversationHandler). لا يحتاج تطبيقه
    على معالجات الحالات الداخلية للمحادثة لأنها غير قابلة للوصول إلا بعد
    اجتياز نقطة دخول محمية — لكن تطبيقه عليها أيضاً غير ضار (حماية زائدة)."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        from telegram.ext import ConversationHandler
        from bot.shared_auth import is_admin

        update = None
        for a in args:
            if hasattr(a, "effective_user"):
                update = a
                break

        user = getattr(update, "effective_user", None) if update is not None else None
        if user is None or not is_admin(user.id):
            uid = getattr(user, "id", "unknown")
            fname = getattr(func, "__name__", "?")
            logger.warning(f"🚫 require_admin blocked non-admin user={uid} from {fname}")
            try:
                if update is not None and getattr(update, "callback_query", None):
                    await update.callback_query.answer(
                        "🚫 هذه الميزة مخصصة للإدارة فقط.", show_alert=True
                    )
                elif update is not None and getattr(update, "message", None):
                    await update.message.reply_text("🚫 هذه الميزة مخصصة للإدارة فقط.")
            except Exception:
                pass
            return ConversationHandler.END

        return await func(*args, **kwargs)

    return wrapper


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
                except:
                    pass
            
            # محاولة إرسال رسالة للمستخدم
            try:
                if update:
                    # ✅ رسالة عامة فقط — لا تُكشف أي تفاصيل تقنية (نص الاستثناء)
                    # للمستخدم. التفاصيل الكاملة مُسجَّلة في الـlog أعلاه فقط.
                    if hasattr(update, 'callback_query') and update.callback_query:
                        try:
                            await update.callback_query.answer(
                                "⚠️ حدث خطأ، يرجى المحاولة مرة أخرى",
                                show_alert=True
                            )
                        except:
                            pass
                        try:
                            await update.callback_query.edit_message_text(
                                "❌ **حدث خطأ غير متوقع**\n\n"
                                "يرجى المحاولة لاحقاً.\n"
                                "✅ تم إعادة تعيين الحالة — اضغط الزر مرة أخرى أو /start للبدء من جديد",
                                parse_mode="Markdown"
                            )
                        except:
                            pass
                    elif hasattr(update, 'message') and update.message:
                        await update.message.reply_text(
                            "❌ **حدث خطأ غير متوقع**\n\n"
                            "يرجى المحاولة لاحقاً.\n"
                            "✅ تم إعادة تعيين الحالة — اضغط الزر مرة أخرى أو /start للبدء من جديد",
                            parse_mode="Markdown"
                        )
            except Exception as send_error:
                logger.warning(f"⚠️ فشل إرسال رسالة الخطأ: {send_error}")
            
            # ✅ إنهاء المحادثة لتحرير الزر
            return ConversationHandler.END
    
    return wrapper



