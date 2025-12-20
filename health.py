# ================================================
# health.py - Health Check Endpoint للأداء العالي
# 🚀 يتحقق من حالة البوت والنظام تحت الضغط
# ================================================

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class HealthChecker:
    """
    فاحص حالة شامل للنظام تحت الضغط العالي
    """

    def __init__(self):
        self.start_time = time.time()
        self.last_health_check = time.time()

    async def check_database(self) -> Dict[str, Any]:
        """فحص قاعدة البيانات"""
        try:
            from db.session import SessionLocal
            start_time = time.time()

            with SessionLocal() as session:
                # استعلام بسيط للتحقق من الاتصال
                result = session.execute("SELECT 1").scalar()

            response_time = time.time() - start_time

            return {
                "status": "healthy" if result == 1 else "unhealthy",
                "response_time": round(response_time, 3),
                "message": "Database connection successful"
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Database connection failed"
            }

    async def check_cache_system(self) -> Dict[str, Any]:
        """فحص نظام التخزين المؤقت"""
        try:
            from services.caching import get_cache_stats
            stats = get_cache_stats()

            return {
                "status": "healthy",
                "cache_items": stats["total_items"],
                "default_ttl": stats["default_ttl"],
                "cleanup_active": stats["cleanup_task_active"]
            }
        except Exception as e:
            logger.error(f"Cache system health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def check_performance(self) -> Dict[str, Any]:
        """فحص الأداء"""
        try:
            from services.performance_utils import get_performance_stats
            stats = get_performance_stats()

            # تقييم حالة الأداء
            if stats["avg_response_time"] > 10.0:  # أكثر من 10 ثوان
                status = "degraded"
                message = "High response time detected"
            elif stats["error_rate"] > 5.0:  # أكثر من 5% أخطاء
                status = "degraded"
                message = "High error rate detected"
            else:
                status = "healthy"
                message = "Performance within acceptable limits"

            return {
                "status": status,
                "message": message,
                **stats
            }
        except Exception as e:
            logger.error(f"Performance health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def check_system_resources(self) -> Dict[str, Any]:
        """فحص موارد النظام"""
        try:
            import psutil

            # فحص الذاكرة
            memory = psutil.virtual_memory()
            memory_usage_percent = memory.percent

            # فحص CPU
            cpu_percent = psutil.cpu_percent(interval=1)

            # فحص القرص
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent

            # تقييم الحالة العامة
            if memory_usage_percent > 90 or cpu_percent > 95 or disk_usage_percent > 95:
                status = "critical"
                message = "System resources critically high"
            elif memory_usage_percent > 80 or cpu_percent > 80 or disk_usage_percent > 80:
                status = "warning"
                message = "System resources high"
            else:
                status = "healthy"
                message = "System resources normal"

            return {
                "status": status,
                "message": message,
                "memory_usage_percent": memory_usage_percent,
                "cpu_usage_percent": cpu_percent,
                "disk_usage_percent": disk_usage_percent,
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2)
            }
        except Exception as e:
            logger.error(f"System resources health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """فحص شامل لجميع المكونات"""
        self.last_health_check = time.time()

        # تشغيل جميع الفحوصات بالتوازي
        tasks = [
            self.check_database(),
            self.check_cache_system(),
            self.check_performance(),
            self.check_system_resources()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # تجميع النتائج
        health_data = {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.start_time,
            "service": "Medical Reports Bot",
            "version": "2.0.0-High-Performance",
            "checks": {
                "database": results[0] if not isinstance(results[0], Exception) else {"status": "error", "error": str(results[0])},
                "cache_system": results[1] if not isinstance(results[1], Exception) else {"status": "error", "error": str(results[1])},
                "performance": results[2] if not isinstance(results[2], Exception) else {"status": "error", "error": str(results[2])},
                "system_resources": results[3] if not isinstance(results[3], Exception) else {"status": "error", "error": str(results[3])}
            }
        }

        # تحديد الحالة العامة
        statuses = [check.get("status", "unknown") for check in health_data["checks"].values()]

        if "critical" in statuses:
            overall_status = "critical"
        elif "unhealthy" in statuses or "error" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses or "warning" in statuses:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        health_data["status"] = overall_status
        health_data["last_check_duration"] = time.time() - self.last_health_check

        logger.info(f"🏥 Health check completed: {overall_status}")
        return health_data

# إنشاء instance عالمي
health_checker = HealthChecker()

# دوال مساعدة للاستخدام السريع
async def get_health_status() -> Dict[str, Any]:
    """إرجاع حالة النظام الصحية"""
    return await health_checker.comprehensive_health_check()

def health_check():
    """Simple health check for backward compatibility"""
    try:
        # Check if bot token exists (basic validation)
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return {
                "status": "error",
                "message": "BOT_TOKEN not configured",
                "timestamp": datetime.utcnow().isoformat()
            }

        return {
            "status": "healthy",
            "message": "Medical Reports Bot is running (High-Performance Mode)",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0-High-Performance"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    # For local testing - simple version
    result = health_check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
