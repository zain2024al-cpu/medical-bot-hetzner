# ================================================
# services/request_processor.py
# 🔥 معالج قوي للطلبات - يتحمل الضغط العالي
# ================================================

import asyncio
import logging
from typing import Callable, Any, Optional
from collections import deque
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# ================================================
# Request Queue System - نظام قائمة انتظار للطلبات
# ================================================

class RequestQueue:
    """نظام قائمة انتظار ذكي للطلبات"""
    
    def __init__(self, max_size=1000, max_workers=50):
        self.queue = asyncio.Queue(maxsize=max_size)
        self.max_workers = max_workers
        self.workers = []
        self.active_tasks = 0
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = time.time()
        
    async def add_request(self, handler: Callable, *args, **kwargs):
        """إضافة طلب جديد للقائمة"""
        try:
            await self.queue.put((handler, args, kwargs))
            logger.debug(f"✅ تم إضافة طلب للقائمة. الحجم الحالي: {self.queue.qsize()}")
        except asyncio.QueueFull:
            logger.warning(f"⚠️ القائمة ممتلئة! الحجم: {self.queue.qsize()}")
            raise Exception("القائمة ممتلئة، يرجى المحاولة لاحقاً")
    
    async def worker(self, worker_id: int):
        """عامل معالجة الطلبات"""
        logger.info(f"🚀 بدء العامل {worker_id}")
        while True:
            try:
                # انتظار طلب جديد (مع timeout)
                item = await asyncio.wait_for(self.queue.get(), timeout=60.0)
                handler, args, kwargs = item
                
                self.active_tasks += 1
                logger.debug(f"🔄 العامل {worker_id} يعالج طلب. المهام النشطة: {self.active_tasks}")
                
                try:
                    # تنفيذ المعالج
                    if asyncio.iscoroutinefunction(handler):
                        await handler(*args, **kwargs)
                    else:
                        handler(*args, **kwargs)
                    
                    self.processed_count += 1
                    logger.debug(f"✅ العامل {worker_id} أنهى طلب بنجاح")
                    
                except Exception as e:
                    self.failed_count += 1
                    logger.error(f"❌ العامل {worker_id} فشل في معالجة طلب: {e}", exc_info=True)
                
                finally:
                    self.active_tasks -= 1
                    self.queue.task_done()
                    
            except asyncio.TimeoutError:
                # Timeout - العامل لا يزال نشطاً
                continue
            except Exception as e:
                logger.error(f"❌ خطأ في العامل {worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)  # انتظار قبل إعادة المحاولة
    
    async def start_workers(self):
        """بدء العمال"""
        logger.info(f"🚀 بدء {self.max_workers} عامل للمعالجة المتوازية")
        for i in range(self.max_workers):
            worker = asyncio.create_task(self.worker(i))
            self.workers.append(worker)
        logger.info(f"✅ تم بدء جميع العمال")
    
    async def stop_workers(self):
        """إيقاف العمال"""
        logger.info("🛑 إيقاف العمال...")
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        logger.info("✅ تم إيقاف جميع العمال")
    
    def get_stats(self) -> dict:
        """الحصول على إحصائيات"""
        uptime = time.time() - self.start_time
        return {
            "queue_size": self.queue.qsize(),
            "active_tasks": self.active_tasks,
            "processed": self.processed_count,
            "failed": self.failed_count,
            "workers": len(self.workers),
            "uptime_seconds": uptime,
            "requests_per_second": self.processed_count / uptime if uptime > 0 else 0
        }


# ================================================
# Global Request Queue Instance
# ================================================

_request_queue: Optional[RequestQueue] = None


def get_request_queue() -> RequestQueue:
    """الحصول على instance القائمة"""
    global _request_queue
    if _request_queue is None:
        _request_queue = RequestQueue(max_size=1000, max_workers=50)
    return _request_queue


async def start_request_processor():
    """بدء معالج الطلبات"""
    queue = get_request_queue()
    await queue.start_workers()
    logger.info("✅ تم بدء معالج الطلبات القوي")


async def stop_request_processor():
    """إيقاف معالج الطلبات"""
    queue = get_request_queue()
    await queue.stop_workers()
    logger.info("✅ تم إيقاف معالج الطلبات")


# ================================================
# Decorator للعمليات الثقيلة
# ================================================

def async_heavy_operation(max_concurrent=10):
    """
    Decorator لتنفيذ العمليات الثقيلة بشكل متوازي مع حد أقصى
    
    Args:
        max_concurrent: الحد الأقصى للعمليات المتزامنة
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with semaphore:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"❌ خطأ في عملية ثقيلة {func.__name__}: {e}", exc_info=True)
                    raise
        return wrapper
    return decorator


# ================================================
# Rate Limiter - للتحكم في معدل الطلبات
# ================================================

class RateLimiter:
    """محدد معدل الطلبات لكل مستخدم"""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # {user_id: [timestamps]}
    
    def is_allowed(self, user_id: int) -> bool:
        """التحقق من السماح بالطلب"""
        now = time.time()
        
        # تنظيف الطلبات القديمة
        if user_id in self.requests:
            self.requests[user_id] = [
                ts for ts in self.requests[user_id]
                if now - ts < self.window_seconds
            ]
        else:
            self.requests[user_id] = []
        
        # التحقق من الحد
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # إضافة الطلب الحالي
        self.requests[user_id].append(now)
        return True
    
    def get_remaining(self, user_id: int) -> int:
        """الحصول على عدد الطلبات المتبقية"""
        if user_id not in self.requests:
            return self.max_requests
        
        now = time.time()
        self.requests[user_id] = [
            ts for ts in self.requests[user_id]
            if now - ts < self.window_seconds
        ]
        
        return max(0, self.max_requests - len(self.requests[user_id]))


# Global Rate Limiter
_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)


def check_rate_limit(user_id: int):
    """
    التحقق من حد المعدل
    
    Returns:
        (is_allowed, remaining_requests)
    """
    is_allowed = _rate_limiter.is_allowed(user_id)
    remaining = _rate_limiter.get_remaining(user_id)
    return is_allowed, remaining

