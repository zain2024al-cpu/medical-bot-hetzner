# ================================================
# db/maintenance.py
# 🔹 Database Maintenance & Strengthening Tools
# ================================================

import logging
import os
import time
from datetime import datetime
from sqlalchemy import text
from db.session import engine, DATABASE_PATH, get_db

logger = logging.getLogger(__name__)

class DatabaseMaintenance:
    """
    Tools to strengthen, repair, and maintain the SQLite database.
    """
    
    @staticmethod
    def run_maintenance():
        """
        Run full database maintenance routine.
        1. Check integrity
        2. Optimize (Vacuum + Analyze)
        3. Verify WAL mode
        """
        logger.info("🔧 Starting database maintenance...")
        
        results = {
            "integrity_check": False,
            "vacuum": False,
            "wal_mode": False,
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. Integrity Check
        try:
            with engine.connect() as conn:
                logger.info("🔍 Running PRAGMA integrity_check...")
                result = conn.execute(text("PRAGMA integrity_check")).scalar()
                
                if result == "ok":
                    logger.info("✅ Database integrity check passed.")
                    results["integrity_check"] = True
                else:
                    logger.error(f"❌ Database integrity check FAILED: {result}")
                    results["integrity_check_error"] = result
        except Exception as e:
            logger.error(f"❌ Error during integrity check: {e}")
            results["error"] = str(e)

        # 2. Optimize (Vacuum & Analyze)
        # Note: VACUUM requires no active transactions.
        # We try to do it, but if it fails due to locks, we log it.
        try:
            # We need a raw connection for VACUUM usually, or autocommit mode
            with engine.connect() as conn:
                conn.execution_options(isolation_level="AUTOCOMMIT")
                logger.info("🧹 Running VACUUM...")
                conn.execute(text("VACUUM"))
                
                logger.info("📊 Running ANALYZE...")
                conn.execute(text("ANALYZE"))
                
                logger.info("✅ Database optimized.")
                results["vacuum"] = True
        except Exception as e:
            logger.warning(f"⚠️ Optimization skipped (database might be busy): {e}")
            results["vacuum_error"] = str(e)

        # 3. Verify WAL Mode
        try:
            with engine.connect() as conn:
                mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                if mode.upper() == "WAL":
                    logger.info("✅ WAL mode is active.")
                    results["wal_mode"] = True
                else:
                    logger.warning(f"⚠️ WAL mode is NOT active (Current: {mode}). Attempting to enable...")
                    conn.execute(text("PRAGMA journal_mode=WAL"))
                    new_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
                    if new_mode.upper() == "WAL":
                        logger.info("✅ WAL mode enabled successfully.")
                        results["wal_mode"] = True
                    else:
                        logger.error(f"❌ Failed to enable WAL mode. Current: {new_mode}")
        except Exception as e:
            logger.error(f"❌ Error checking WAL mode: {e}")

        logger.info("✅ Database maintenance completed.")
        return results

    @staticmethod
    def check_db_health_startup():
        """
        Run a quick health check on startup.
        If database is corrupted, try to restore from backup (if implemented) 
        or at least warn loudly.
        """
        logger.info("🏥 Running startup database health check...")
        try:
            with engine.connect() as conn:
                # Quick integrity check (quick_check is faster but less thorough)
                # Note: 'PRAGMA quick_check' is available in newer SQLite versions
                try:
                    check = conn.execute(text("PRAGMA quick_check")).scalar()
                except:
                    # Fallback to full check if quick_check not supported
                    check = conn.execute(text("PRAGMA integrity_check")).scalar()
                
                if check == "ok":
                    logger.info("✅ Database is healthy.")
                    return True
                else:
                    logger.critical(f"❌ DATABASE CORRUPTION DETECTED: {check}")
                    # Here we could trigger a restore process
                    return False
        except Exception as e:
            logger.critical(f"❌ Failed to access database on startup: {e}")
            return False

def run_scheduled_maintenance(context=None):
    """
    Function to be called by the job queue.
    """
    try:
        DatabaseMaintenance.run_maintenance()
        # Also trigger backup if available
        try:
            from services.sqlite_backup import SQLiteBackupService
            backup_service = SQLiteBackupService()
            backup_service.backup_database(backup_type="daily_maintenance")
        except Exception as backup_error:
            logger.error(f"❌ Backup during maintenance failed: {backup_error}")
            
    except Exception as e:
        logger.error(f"❌ Scheduled maintenance failed: {e}")
