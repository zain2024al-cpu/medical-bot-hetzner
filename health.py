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
            from sqlalchemy import text
            start_time = time.time()

            with SessionLocal() as session:
                # استعلام بسيط للتحقق من الاتصال
                result = session.execute(text("SELECT 1")).scalar()

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

# إنشاء instance عالمي
health_checker = HealthChecker()

def health_check():
    """Simple health check for backward compatibility"""
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv("config.env")
        
        # Check if bot token exists (basic validation)
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return {
                "status": "error",
                "message": "BOT_TOKEN not configured",
                "timestamp": datetime.now().isoformat()
            }

        return {
            "status": "healthy",
            "message": "Medical Reports Bot is running (High-Performance Mode)",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0-High-Performance"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    # For local testing - simple version
    result = health_check()
    print(json.dumps(result, indent=2, ensure_ascii=False))