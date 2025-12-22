# ================================================
# services/performance_monitor.py
# 📊 مراقبة الأداء تحت الضغط العالي
# ================================================

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)

# ================================================
# Performance Metrics
# ================================================

class PerformanceMonitor:
    """مراقب الأداء للبوت"""
    
    def __init__(self):
        self.request_times = defaultdict(list)
        self.error_count = defaultdict(int)
        self.success_count = defaultdict(int)
        self.active_requests = 0
        self.max_active_requests = 0
        self.start_time = time.time()
        self.total_requests = 0
        
    def record_request(self, handler_name: str, duration: float, success: bool):
        """تسجيل طلب"""
        self.total_requests += 1
        self.request_times[handler_name].append(duration)
        
        # الاحتفاظ بآخر 1000 طلب فقط
        if len(self.request_times[handler_name]) > 1000:
            self.request_times[handler_name] = self.request_times[handler_name][-1000:]
        
        if success:
            self.success_count[handler_name] += 1
        else:
            self.error_count[handler_name] += 1
    
    def start_request(self):
        """بدء طلب جديد"""
        self.active_requests += 1
        if self.active_requests > self.max_active_requests:
            self.max_active_requests = self.active_requests
    
    def end_request(self):
        """إنهاء طلب"""
        if self.active_requests > 0:
            self.active_requests -= 1
    
    def get_stats(self) -> Dict:
        """الحصول على إحصائيات"""
        uptime = time.time() - self.start_time
        
        stats = {
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "active_requests": self.active_requests,
            "max_active_requests": self.max_active_requests,
            "requests_per_second": self.total_requests / uptime if uptime > 0 else 0,
            "handlers": {}
        }
        
        for handler_name in self.request_times:
            times = self.request_times[handler_name]
            if times:
                stats["handlers"][handler_name] = {
                    "count": len(times),
                    "success": self.success_count[handler_name],
                    "errors": self.error_count[handler_name],
                    "avg_duration": sum(times) / len(times),
                    "min_duration": min(times),
                    "max_duration": max(times),
                    "p95_duration": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else None
                }
        
        return stats
    
    def log_stats(self):
        """طباعة الإحصائيات"""
        stats = self.get_stats()
        logger.info("=" * 60)
        logger.info("📊 Performance Statistics:")
        logger.info(f"  Uptime: {stats['uptime_seconds']:.1f} seconds")
        logger.info(f"  Total Requests: {stats['total_requests']}")
        logger.info(f"  Active Requests: {stats['active_requests']}")
        logger.info(f"  Max Active Requests: {stats['max_active_requests']}")
        logger.info(f"  Requests/Second: {stats['requests_per_second']:.2f}")
        logger.info("=" * 60)


# Global Performance Monitor
_performance_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """الحصول على مراقب الأداء"""
    return _performance_monitor


async def start_performance_monitoring(interval=300):
    """بدء مراقبة الأداء الدورية"""
    logger.info("📊 بدء مراقبة الأداء...")
    
    while True:
        try:
            await asyncio.sleep(interval)
            _performance_monitor.log_stats()
        except Exception as e:
            logger.error(f"❌ خطأ في مراقبة الأداء: {e}")


# ================================================
# Decorator لمراقبة الأداء
# ================================================

def monitor_performance(handler_name: str = None):
    """Decorator لمراقبة أداء handler"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            name = handler_name or func.__name__
            start_time = time.time()
            _performance_monitor.start_request()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                _performance_monitor.record_request(name, duration, success=True)
                return result
            except Exception as e:
                duration = time.time() - start_time
                _performance_monitor.record_request(name, duration, success=False)
                raise
            finally:
                _performance_monitor.end_request()
        
        return wrapper
    return decorator

