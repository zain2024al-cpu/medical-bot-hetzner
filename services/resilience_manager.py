# ================================================
# services/resilience_manager.py
# 🛡️ نظام شامل لتحسين الأداء والاستقرار
# ================================================

import asyncio
import logging
import time
import gc
from typing import Optional, Callable, Any
from functools import wraps
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import datetime, timedelta
from sqlalchemy.exc import OperationalError, DisconnectionError, TimeoutError as SQLTimeoutError
from telegram.error import TimedOut, NetworkError, RetryAfter, BadRequest

logger = logging.getLogger(__name__)

# ================================================
# Circuit Breaker Pattern
# ================================================

class CircuitBreaker:
    """Circuit Breaker لمنع التحميل الزائد"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60, expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
        
    def call(self, func: Callable, *args, **kwargs):
        """تنفيذ دالة مع circuit breaker"""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
                logger.info(f"🔄 Circuit breaker: {func.__name__} - Moving to half-open state")
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'half_open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info(f"✅ Circuit breaker: {func.__name__} - Closed (recovered)")
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.warning(f"⚠️ Circuit breaker: {func.__name__} - OPENED after {self.failure_count} failures")
            
            raise

# Circuit breakers للعمليات المختلفة
db_circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60, expected_exception=OperationalError)
network_circuit_breaker = CircuitBreaker(failure_threshold=10, timeout=30, expected_exception=NetworkError)

# ================================================
# Retry Logic with Exponential Backoff
# ================================================

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
    *args,
    **kwargs
) -> Any:
    """
    إعادة المحاولة مع exponential backoff
    
    Args:
        func: الدالة المراد تنفيذها
        max_retries: عدد المحاولات
        initial_delay: التأخير الأولي (بالثواني)
        max_delay: الحد الأقصى للتأخير
        exponential_base: قاعدة الأس
        exceptions: أنواع الأخطاء التي يجب إعادة المحاولة عندها
    """
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Retry {attempt + 1}/{max_retries} for {func.__name__}: {str(e)[:100]}")
                await asyncio.sleep(delay)
                delay = min(delay * exponential_base, max_delay)
            else:
                logger.error(f"❌ Max retries reached for {func.__name__}: {str(e)[:100]}")
    
    raise last_exception

# ================================================
# Database Resilience
# ================================================

# ملاحظة: resilient_db_session() تم استبداله باستخدام get_db() مباشرة
# get_db() في db/session.py يحتوي الآن على retry logic مدمج
# يمكن استخدام get_db() مباشرة بدلاً من resilient_db_session()

# ================================================
# Health Check System
# ================================================

class HealthMonitor:
    """نظام مراقبة الصحة"""
    
    def __init__(self):
        self.checks = {}
        self.last_check_time = {}
        self.check_interval = 300  # 5 دقائق
        
    def register_check(self, name: str, check_func: Callable):
        """تسجيل فحص صحة"""
        self.checks[name] = check_func
        
    async def run_checks(self) -> dict:
        """تنفيذ جميع فحوصات الصحة"""
        results = {}
        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                results[name] = {
                    'status': 'healthy' if result else 'unhealthy',
                    'timestamp': datetime.now().isoformat()
                }
            except Exception as e:
                logger.error(f"❌ Health check '{name}' failed: {e}")
                results[name] = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
        return results
    
    async def start_monitoring(self, interval: int = 300):
        """بدء المراقبة الدورية"""
        while True:
            try:
                await asyncio.sleep(interval)
                results = await self.run_checks()
                
                # تسجيل النتائج
                unhealthy = [name for name, result in results.items() if result['status'] != 'healthy']
                if unhealthy:
                    logger.warning(f"⚠️ Unhealthy services: {unhealthy}")
                else:
                    logger.debug("✅ All health checks passed")
                    
            except Exception as e:
                logger.error(f"❌ Health monitoring error: {e}")

# إنشاء instance عام
health_monitor = HealthMonitor()

# ================================================
# Memory Management
# ================================================

class MemoryManager:
    """إدارة الذاكرة"""
    
    def __init__(self):
        self.cleanup_interval = 300  # 5 دقائق
        self.last_cleanup = time.time()
        self.memory_threshold = 500 * 1024 * 1024  # 500 MB
        
    async def cleanup(self):
        """تنظيف الذاكرة"""
        try:
            # Garbage collection
            collected = gc.collect()
            if collected > 0:
                logger.debug(f"🧹 Garbage collected: {collected} objects")
            
            # إحصائيات الذاكرة (إذا كان psutil متاحاً)
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                if memory_mb > self.memory_threshold / 1024 / 1024:
                    logger.warning(f"⚠️ High memory usage: {memory_mb:.2f} MB")
                    # تنظيف إضافي
                    for _ in range(3):
                        gc.collect()
            except ImportError:
                # psutil غير متاح - تخطي مراقبة الذاكرة
                pass
            
            self.last_cleanup = time.time()
        except Exception as e:
            logger.warning(f"⚠️ Memory cleanup error: {e}")
    
    async def start_cleanup_loop(self):
        """بدء حلقة التنظيف الدورية"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup()
            except Exception as e:
                logger.error(f"❌ Cleanup loop error: {e}")

# إنشاء instance عام
memory_manager = MemoryManager()

# ================================================
# Error Rate Limiting
# ================================================

class ErrorRateLimiter:
    """تحديد معدل الأخطاء"""
    
    def __init__(self, max_errors: int = 10, time_window: int = 60):
        self.max_errors = max_errors
        self.time_window = time_window
        self.error_times = []
        
    def record_error(self):
        """تسجيل خطأ"""
        now = time.time()
        self.error_times.append(now)
        
        # إزالة الأخطاء القديمة
        self.error_times = [t for t in self.error_times if now - t < self.time_window]
        
    def is_rate_limited(self) -> bool:
        """التحقق من تجاوز الحد"""
        return len(self.error_times) >= self.max_errors
    
    def get_error_rate(self) -> float:
        """الحصول على معدل الأخطاء"""
        if not self.error_times:
            return 0.0
        return len(self.error_times) / self.time_window

# إنشاء instance عام
error_rate_limiter = ErrorRateLimiter()

# ================================================
# Decorators
# ================================================

def resilient(func: Callable) -> Callable:
    """Decorator لإضافة المرونة للدوال"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await retry_with_backoff(
                func,
                max_retries=3,
                initial_delay=1.0,
                exceptions=(OperationalError, NetworkError, TimedOut),
                *args,
                **kwargs
            )
        except Exception as e:
            error_rate_limiter.record_error()
            logger.error(f"❌ Resilient function {func.__name__} failed: {e}")
            raise
    return wrapper

def safe_database_operation(func: Callable) -> Callable:
    """
    Decorator للعمليات الآمنة على قاعدة البيانات
    يستخدم get_db() مباشرة مع retry logic المدمج
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # استخدام get_db() مباشرة - يحتوي على retry logic مدمج
        from db.session import get_db
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        
        def sync_get_db():
            return get_db()
        
        # تنفيذ get_db() في thread منفصل (لأنه synchronous)
        try:
            db_context = await loop.run_in_executor(executor, sync_get_db)
            session = db_context.__enter__()
            try:
                result = await func(session, *args, **kwargs)
                # commit يتم تلقائياً في __exit__ إذا لم يكن هناك خطأ
                db_context.__exit__(None, None, None)
                return result
            except Exception as e:
                # rollback يتم تلقائياً في __exit__ عند الخطأ
                exc_type, exc_val, exc_tb = type(e), e, e.__traceback__
                db_context.__exit__(exc_type, exc_val, exc_tb)
                raise
        except Exception as e:
            logger.error(f"❌ Error in safe_database_operation: {e}")
            raise
    return wrapper

# ================================================
# Initialization
# ================================================

async def initialize_resilience_system():
    """تهيئة نظام المرونة"""
    logger.info("🛡️ Initializing resilience system...")
    
    # تسجيل فحوصات الصحة
    async def db_health_check():
        from db.session import health_check
        return health_check()
    
    health_monitor.register_check('database', db_health_check)
    
    # بدء المراقبة
    asyncio.create_task(health_monitor.start_monitoring())
    asyncio.create_task(memory_manager.start_cleanup_loop())
    
    logger.info("✅ Resilience system initialized")

