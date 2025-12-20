# ================================================
# services/caching.py
# 🚀 نظام التخزين المؤقت للأداء العالي
# ================================================

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
import hashlib

logger = logging.getLogger(__name__)

class CacheManager:
    """
    نظام تخزين مؤقت متقدم لتحسين الأداء تحت الضغط العالي
    """

    def __init__(self, default_ttl: int = 300):  # 5 دقائق افتراضياً
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
        self._cleanup_task: Optional[asyncio.Task] = None

    def _generate_key(self, *args, **kwargs) -> str:
        """توليد مفتاح فريد للتخزين المؤقت"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """تخزين قيمة مع TTL"""
        expiry = datetime.now() + timedelta(seconds=ttl or self.default_ttl)
        self.cache[key] = {
            "value": value,
            "expiry": expiry,
            "created": datetime.now()
        }
        logger.debug(f"📦 Cached: {key[:16]}... (TTL: {ttl or self.default_ttl}s)")

    def get(self, key: str) -> Optional[Any]:
        """استرجاع قيمة من الـ cache"""
        if key not in self.cache:
            return None

        item = self.cache[key]
        if datetime.now() > item["expiry"]:
            # انتهت صلاحية البيانات
            del self.cache[key]
            return None

        logger.debug(f"⚡ Cache hit: {key[:16]}...")
        return item["value"]

    def delete(self, key: str) -> bool:
        """حذف عنصر من الـ cache"""
        if key in self.cache:
            del self.cache[key]
            logger.debug(f"🗑️ Cache deleted: {key[:16]}...")
            return True
        return False

    def clear(self) -> int:
        """مسح جميع البيانات المخزنة"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"🧹 Cache cleared: {count} items removed")
        return count

    def cleanup_expired(self) -> int:
        """تنظيف البيانات المنتهية الصلاحية"""
        expired_keys = []
        for key, item in self.cache.items():
            if datetime.now() > item["expiry"]:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"🧽 Cleaned {len(expired_keys)} expired cache items")
        return len(expired_keys)

    async def start_cleanup_task(self, interval: int = 60):
        """بدء مهمة تنظيف دورية"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

        self._cleanup_task = asyncio.create_task(self._periodic_cleanup(interval))
        logger.info(f"🧹 Started cache cleanup task (every {interval}s)")

    async def _periodic_cleanup(self, interval: int):
        """تنظيف دوري للبيانات المنتهية الصلاحية"""
        while True:
            try:
                await asyncio.sleep(interval)
                self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Cache cleanup error: {e}")

    async def stop_cleanup_task(self):
        """إيقاف مهمة التنظيف"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("🛑 Cache cleanup task stopped")

# 🚀 إنشاء instance عالمي للـ cache
cache_manager = CacheManager()

# 🔧 دوال مساعدة للاستخدام السريع
def cached(ttl: Optional[int] = None):
    """Decorator لتخزين نتائج الدوال مؤقتاً"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            key = cache_manager._generate_key(func.__name__, *args, **kwargs)
            cached_result = cache_manager.get(key)
            if cached_result is not None:
                return cached_result

            result = await func(*args, **kwargs)
            cache_manager.set(key, result, ttl)
            return result
        return wrapper
    return decorator

# 📊 إحصائيات الـ cache
def get_cache_stats() -> Dict[str, Any]:
    """إرجاع إحصائيات الـ cache"""
    return {
        "total_items": len(cache_manager.cache),
        "default_ttl": cache_manager.default_ttl,
        "cleanup_task_active": cache_manager._cleanup_task is not None and not cache_manager._cleanup_task.done()
    }

# 🧹 تنظيف يدوي
def clear_cache():
    """مسح جميع البيانات المخزنة مؤقتاً"""
    return cache_manager.clear()

# 🚀 بدء الـ cache system
async def start_cache_system():
    """بدء نظام التخزين المؤقت"""
    await cache_manager.start_cleanup_task()
    logger.info("🚀 Cache system started")

# 🛑 إيقاف الـ cache system
async def stop_cache_system():
    """إيقاف نظام التخزين المؤقت"""
    await cache_manager.stop_cleanup_task()
    logger.info("🛑 Cache system stopped")
