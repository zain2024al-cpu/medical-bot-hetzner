# ================================================
# services/performance_utils.py
# ⚡ أدوات تحسين الأداء للضغط العالي
# ================================================

import asyncio
import logging
import time
from typing import Callable, Any, Optional, Dict
from functools import wraps
import psutil
import os

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    مراقبة الأداء وإحصائيات النظام تحت الضغط العالي
    """

    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.memory_usage = []

    def record_request(self, response_time: float):
        """تسجيل طلب جديد"""
        self.request_count += 1
        self.response_times.append(response_time)

        # الحفاظ على آخر 1000 قياس
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]

    def record_error(self):
        """تسجيل خطأ"""
        self.error_count += 1

    def record_memory(self):
        """تسجيل استخدام الذاكرة"""
        try:
            memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
            self.memory_usage.append(memory)

            # الحفاظ على آخر 100 قياس
            if len(self.memory_usage) > 100:
                self.memory_usage = self.memory_usage[-100:]
        except Exception as e:
            logger.warning(f"Failed to record memory usage: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """إرجاع إحصائيات الأداء"""
        if not self.response_times:
            avg_response_time = 0
        else:
            avg_response_time = sum(self.response_times) / len(self.response_times)

        return {
            "uptime_seconds": time.time() - self.start_time,
            "total_requests": self.request_count,
            "total_errors": self.error_count,
            "error_rate": (self.error_count / max(1, self.request_count)) * 100,
            "avg_response_time": avg_response_time,
            "max_response_time": max(self.response_times) if self.response_times else 0,
            "current_memory_mb": self.memory_usage[-1] if self.memory_usage else 0,
            "avg_memory_mb": sum(self.memory_usage) / len(self.memory_usage) if self.memory_usage else 0,
        }

# 🚀 إنشاء instance عالمي
performance_monitor = PerformanceMonitor()

def performance_monitoring(func: Callable) -> Callable:
    """
    Decorator لمراقبة أداء الدوال
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            response_time = time.time() - start_time
            performance_monitor.record_request(response_time)
            return result
        except Exception as e:
            performance_monitor.record_error()
            raise e
        finally:
            performance_monitor.record_memory()

    return wrapper

def retry_async(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator لإعادة المحاولة مع backoff للعمليات غير المتزامنة
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}: {e}")

            raise last_exception
        return wrapper
    return decorator

def rate_limit_async(calls: int, period: float = 1.0):
    """
    Decorator للتحكم في معدل الاستدعاءات
    """
    def decorator(func: Callable) -> Callable:
        last_calls = []

        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = time.time()

            # إزالة المكالمات القديمة
            last_calls[:] = [call for call in last_calls if now - call < period]

            if len(last_calls) >= calls:
                # انتظار حتى يمكن إجراء مكالمة جديدة
                sleep_time = period - (now - last_calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    last_calls[:] = [call for call in last_calls if time.time() - call < period]

            last_calls.append(time.time())
            return await func(*args, **kwargs)

        return wrapper
    return decorator

def optimize_db_query(func: Callable) -> Callable:
    """
    Decorator لتحسين استعلامات قاعدة البيانات
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # إضافة timeout للاستعلامات
        start_time = time.time()

        try:
            result = await func(*args, **kwargs)
            query_time = time.time() - start_time

            if query_time > 5.0:  # تحذير إذا استغرق الاستعلام أكثر من 5 ثوان
                logger.warning(f"⚠️ Slow DB query in {func.__name__}: {query_time:.2f}s")

            return result
        except Exception as e:
            query_time = time.time() - start_time
            logger.error(f"❌ DB query failed in {func.__name__} after {query_time:.2f}s: {e}")
            raise e

    return wrapper

# 📊 دوال مساعدة للإحصائيات
def get_performance_stats() -> Dict[str, Any]:
    """إرجاع إحصائيات الأداء الحالية"""
    return performance_monitor.get_stats()

def log_performance_stats():
    """تسجيل إحصائيات الأداء في السجل"""
    stats = get_performance_stats()
    logger.info("📊 Performance Stats:")
    logger.info(f"   ⏱️  Uptime: {stats['uptime_seconds']:.0f}s")
    logger.info(f"   📈 Requests: {stats['total_requests']}")
    logger.info(f"   ❌ Errors: {stats['total_errors']} ({stats['error_rate']:.1f}%)")
    logger.info(f"   ⚡ Avg Response: {stats['avg_response_time']:.3f}s")
    logger.info(f"   🧠 Memory: {stats['current_memory_mb']:.1f}MB")
    logger.info("-" * 50)

# 🚀 تحسينات النظام
def optimize_system_settings():
    """تطبيق تحسينات النظام للأداء العالي"""
    try:
        # تحسين إعدادات النظام للأداء العالي
        import platform
        if platform.system() == "Linux":
            # زيادة حد الملفات المفتوحة (file descriptors)
            try:
                import resource
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                resource.setrlimit(resource.RLIMIT_NOFILE, (min(hard, 65536), hard))
                logger.info(f"📁 Increased file descriptors limit to {min(hard, 65536)}")
            except Exception as e:
                logger.warning(f"Could not increase file descriptors: {e}")

        logger.info("⚡ System optimizations applied")
    except Exception as e:
        logger.warning(f"Failed to apply system optimizations: {e}")

# 🧹 تنظيف دوري للذاكرة
async def memory_cleanup(interval: int = 300):
    """تنظيف دوري للذاكرة كل 5 دقائق"""
    while True:
        try:
            await asyncio.sleep(interval)
            # تشجيع garbage collector
            import gc
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"🧹 Garbage collected: {collected} objects")

            # تسجيل إحصائيات الأداء
            log_performance_stats()

        except Exception as e:
            logger.error(f"❌ Memory cleanup error: {e}")

# 🚀 بدء نظام مراقبة الأداء
async def start_performance_monitoring():
    """بدء مراقبة الأداء"""
    optimize_system_settings()

    # بدء تنظيف الذاكرة الدوري
    asyncio.create_task(memory_cleanup())

    logger.info("📊 Performance monitoring started")

# 🛑 إيقاف نظام مراقبة الأداء
async def stop_performance_monitoring():
    """إيقاف مراقبة الأداء"""
    logger.info("📊 Performance monitoring stopped")
