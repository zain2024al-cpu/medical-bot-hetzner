# ================================================
# services/error_monitoring.py
# 🔍 نظام مراقبة الأخطاء الشامل
# ================================================

import logging
import traceback
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

# إنشاء مجلد logs إذا لم يكن موجوداً
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# تكوين logger للأخطاء
error_logger = logging.getLogger("error_monitoring")
error_logger.setLevel(logging.ERROR)

# Handler لملف الأخطاء
error_file_handler = logging.FileHandler(
    LOGS_DIR / "errors.log",
    encoding='utf-8',
    mode='a'
)
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
)

# Handler لملف جميع الأحداث
all_events_handler = logging.FileHandler(
    LOGS_DIR / "all_events.log",
    encoding='utf-8',
    mode='a'
)
all_events_handler.setLevel(logging.DEBUG)
all_events_handler.setFormatter(
    logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
)

error_logger.addHandler(error_file_handler)
error_logger.addHandler(all_events_handler)

# Logger عام
general_logger = logging.getLogger("general")
general_logger.addHandler(all_events_handler)
general_logger.setLevel(logging.INFO)


class ErrorMonitor:
    """نظام مراقبة الأخطاء الشامل"""
    
    def __init__(self):
        self.error_count = 0
        self.last_error_time = None
        self.error_history = []
    
    def log_error(
        self,
        error: Exception,
        context: Optional[ContextTypes.DEFAULT_TYPE] = None,
        update: Optional[Update] = None,
        additional_info: Optional[dict] = None
    ):
        """تسجيل خطأ مع معلومات تفصيلية"""
        self.error_count += 1
        self.last_error_time = datetime.now()
        
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat(),
            "traceback": traceback.format_exc(),
        }
        
        if update:
            error_info["update_id"] = update.update_id
            if update.effective_user:
                error_info["user_id"] = update.effective_user.id
                error_info["username"] = update.effective_user.username
            if update.effective_chat:
                error_info["chat_id"] = update.effective_chat.id
            if update.callback_query:
                error_info["callback_data"] = update.callback_query.data
            if update.message:
                error_info["message_text"] = update.message.text
        
        if context:
            if context.user_data is not None:
                error_info["user_data_keys"] = list(context.user_data.keys())
            else:
                error_info["user_data_keys"] = []
            
            if context.bot_data is not None:
                error_info["bot_data_keys"] = list(context.bot_data.keys())
            else:
                error_info["bot_data_keys"] = []
        
        if additional_info:
            error_info.update(additional_info)
        
        # حفظ في التاريخ (آخر 100 خطأ)
        self.error_history.append(error_info)
        if len(self.error_history) > 100:
            self.error_history.pop(0)
        
        # تسجيل الخطأ
        error_logger.error(
            f"Error #{self.error_count}:\n"
            f"Type: {error_info['error_type']}\n"
            f"Message: {error_info['error_message']}\n"
            f"User ID: {error_info.get('user_id', 'N/A')}\n"
            f"Callback Data: {error_info.get('callback_data', 'N/A')}\n"
            f"Traceback:\n{error_info['traceback']}"
        )
        
        return error_info
    
    async def notify_admin(self, error_info: dict, bot):
        """إرسال إشعار للأدمن عند حدوث خطأ"""
        try:
            from config.settings import ADMIN_IDS
            
            if not ADMIN_IDS:
                return
            
            error_summary = (
                f"🔴 **خطأ في البوت**\n\n"
                f"**نوع الخطأ:** {error_info['error_type']}\n"
                f"**الرسالة:** {error_info['error_message'][:200]}\n"
                f"**المستخدم:** {error_info.get('user_id', 'N/A')}\n"
                f"**الوقت:** {error_info['timestamp']}\n"
                f"**رقم الخطأ:** #{self.error_count}"
            )
            
            if error_info.get('callback_data'):
                error_summary += f"\n**Callback:** {error_info['callback_data'][:50]}"
            
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=error_summary,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    error_logger.error(f"Failed to notify admin {admin_id}: {e}")
        except Exception as e:
            error_logger.error(f"Error in notify_admin: {e}")
    
    def get_error_stats(self) -> dict:
        """الحصول على إحصائيات الأخطاء"""
        return {
            "total_errors": self.error_count,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "recent_errors": len(self.error_history)
        }


# إنشاء instance عام
error_monitor = ErrorMonitor()


async def comprehensive_error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
    """معالج أخطاء شامل ومحسّن"""
    import sys
    import traceback
    
    error = context.error
    
    # طباعة مباشرة في الكونسول - بدون emojis لتجنب UnicodeEncodeError في Windows console
    try:
        print("\n" + "=" * 80)
        print("=" * 80)
        print("=" * 80)
        print("ERROR_HANDLER: Error caught!")
        print("=" * 80)
        print(f"ERROR_HANDLER: Error type = {type(error).__name__}")
        print(f"ERROR_HANDLER: Error message = {str(error)}")
        if update:
            print(f"ERROR_HANDLER: Update ID = {update.update_id}")
            print(f"ERROR_HANDLER: User ID = {update.effective_user.id if update.effective_user else 'N/A'}")
            if update.message:
                try:
                    msg_text = update.message.text[:100] if update.message.text else 'N/A'
                    print(f"ERROR_HANDLER: Message text = {msg_text}")
                except UnicodeEncodeError:
                    print(f"ERROR_HANDLER: Message text = [Unicode text - see logs]")
            if update.callback_query:
                print(f"ERROR_HANDLER: Callback data = {update.callback_query.data}")
        if context:
            current_state = context.user_data.get('_conversation_state', 'NOT SET') if context.user_data else 'NOT SET'
            print(f"ERROR_HANDLER: Current conversation state = {current_state}")
        print("=" * 80)
        print("ERROR_HANDLER: FULL TRACEBACK:")
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80)
        print("=" * 80)
        print("=" * 80 + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        # إذا فشلت الطباعة بسبب Unicode، استخدم logger فقط
        error_logger.error("ERROR_HANDLER: Error caught (details in logs)", exc_info=True)
    
    # تجاهل الأخطاء الشائعة التي لا تحتاج إشعار
    ignored_errors = [
        "Query is too old",
        "query id is invalid",
        "MESSAGE_ID_INVALID",
        "Message is not modified",
        "Message can't be edited",
        "Message to edit not found",
        "can't parse entities",
        "can't find end of the entity",
        "Bad Request: message is not modified",
        "Bad Request: query is too old",
        "NetworkError",
        "httpx.ReadError",
        "httpx.ConnectError",
        "getaddrinfo failed",
        "Connection",
        "Read timeout",
        "Connect timeout",
        "Conflict",
        "terminated by other getUpdates",
        "make sure that only one bot instance is running",
    ]
    
    error_message = str(error)
    error_type = type(error).__name__
    
    # تجاهل أخطاء الشبكة العادية
    if any(ignored in error_message or ignored in error_type for ignored in ignored_errors):
        if "parse entities" in error_message or "can't find end" in error_message:
            general_logger.warning(f"Markdown parsing error (ignored): {error_message}")
        # تجاهل أخطاء الشبكة بصمت
        if "NetworkError" in error_type or "httpx" in error_message or "getaddrinfo" in error_message:
            return
        return
    
    # تسجيل الخطأ
    error_info = error_monitor.log_error(
        error=error,
        context=context,
        update=update,
        additional_info={
            "handler_name": context.error.__class__.__name__ if context.error else "Unknown"
        }
    )
    
    # إشعار الأدمن (فقط للأخطاء المهمة)
    critical_errors = [
        "AttributeError",
        "TypeError",
        "ValueError",
        "KeyError",
        "IndexError",
        "DatabaseError",
        "OperationalError",
    ]
    
    if any(critical in error_info['error_type'] for critical in critical_errors):
        try:
            await error_monitor.notify_admin(error_info, context.bot)
        except Exception:
            error_logger.debug("تم تجاهل استثناء في comprehensive_error_handler", exc_info=True)
    
    # محاولة إرسال رسالة للمستخدم
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ حدث خطأ غير متوقع، يرجى المحاولة مرة أخرى.\n"
                "إذا استمرت المشكلة، يرجى التواصل مع الإدارة."
            )
        except Exception:
            error_logger.debug("تم تجاهل استثناء في comprehensive_error_handler", exc_info=True)
    
    # محاولة الرد على callback query
    if update and update.callback_query:
        try:
            await update.callback_query.answer(
                f"❌ خطأ: {error_message[:50]}",
                show_alert=True
            )
        except Exception:
            error_logger.debug("تم تجاهل استثناء في comprehensive_error_handler", exc_info=True)


def setup_logging():
    """إعداد نظام logging شامل"""
    # تقليل مستوى logging للمكتبات الخارجية أولاً (قبل إعداد handlers)
    # هذا مهم جداً - يجب أن يكون قبل إعداد root logger
    external_loggers = [
        "matplotlib",
        "matplotlib.font_manager",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
        "httpx",
        "telegram",
        "telegram.ext",
        "telegram.ext.ExtBot",
        "telegram.ext.Updater",
        "telegram.ext.Application",
        "apscheduler",
        "apscheduler.scheduler",
    ]
    
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
        # أيضاً تعطيل propagation للأطفال
        logging.getLogger(logger_name).propagate = False
    
    # تكوين root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Handler للكونسول مع دعم UTF-8 على Windows
    import io
    import sys
    
    # إنشاء StreamHandler مع encoding UTF-8
    if sys.platform == 'win32':
        # على Windows، استخدام TextIOWrapper مع UTF-8
        try:
            console_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except Exception:
            # إذا فشل، استخدم stdout العادي مع errors='replace'
            console_stream = sys.stdout
    else:
        console_stream = sys.stdout
    
    console_handler = logging.StreamHandler(console_stream)
    console_handler.setLevel(logging.INFO)  # عرض INFO والأعلى في الكونسول
    
    # Formatter مع معالجة الأخطاء
    class SafeFormatter(logging.Formatter):
        def format(self, record):
            try:
                return super().format(record)
            except UnicodeEncodeError:
                # إذا فشل الترميز، استبدل الرموز التعبيرية
                record.msg = str(record.msg).encode('ascii', errors='replace').decode('ascii')
                return super().format(record)
    
    console_handler.setFormatter(
        SafeFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    )
    
    # Handler لملف جميع الأحداث
    file_handler = logging.FileHandler(
        LOGS_DIR / "bot.log",
        encoding='utf-8',
        mode='a'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger

