# ================================================
# services/sqlite_backup.py
# 🔹 SQLite Backup to Google Cloud Storage
# ================================================

import os
import logging
import shutil
from datetime import datetime
from typing import Optional
from google.cloud import storage
from pathlib import Path

logger = logging.getLogger(__name__)

# ================================================
# Configuration
# ================================================

PROJECT_ID = "lunar-standard-477302-a6"
BUCKET_NAME = f"{PROJECT_ID}-sqlite-backups"
DATABASE_PATH = os.getenv("DATABASE_PATH", "db/medical_reports.db")

# ================================================
# SQLite Backup Service
# ================================================

class SQLiteBackupService:
    """
    SQLite Database Backup to Google Cloud Storage
    
    Features:
    - Full database backup to GCS
    - Automatic daily backups
    - Manual backup on-demand
    - Retention policy (last 30 days)
    - Simple and reliable
    """
    
    def __init__(self):
        self.database_path = DATABASE_PATH
        self.ensure_bucket_exists()
    
    def ensure_bucket_exists(self):
        """Ensure GCS bucket exists"""
        try:
            client = storage.Client(project=PROJECT_ID)
            bucket = client.bucket(BUCKET_NAME)
            
            if not bucket.exists():
                logger.info(f"📦 Creating backup bucket: {BUCKET_NAME}")
                bucket = client.create_bucket(
                    BUCKET_NAME,
                    location="asia-south1"
                )
                logger.info(f"✅ Backup bucket created!")
            
            self.bucket = bucket
            logger.info(f"✅ Backup bucket ready: {BUCKET_NAME}")
            
        except Exception as e:
            logger.error(f"❌ Error ensuring bucket: {e}")
            self.bucket = None
    
    def backup_database(self, backup_type: str = "manual") -> bool:
        """
        Backup SQLite database to Google Cloud Storage
        
        Args:
            backup_type: "manual", "auto", or "daily"
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            logger.error("❌ GCS bucket not available")
            return False
        
        try:
            # Check if database exists
            if not os.path.exists(self.database_path):
                logger.error(f"❌ Database not found: {self.database_path}")
                return False

            # أنشئ نسخة محلية متسقة أولاً (SQLite backup API + integrity_check)
            local_backup_path = None
            try:
                from services.render_backup import create_local_backup
                local_backup_path = create_local_backup(prefix=f"gcs_{backup_type}")
            except Exception as local_backup_error:
                logger.warning(f"⚠️ Could not create safe local backup before GCS upload: {local_backup_error}")
                local_backup_path = None

            upload_source = local_backup_path if local_backup_path and os.path.exists(local_backup_path) else self.database_path
            
            # Generate timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            
            # Backup file name
            backup_filename = f"{backup_type}_backup_{timestamp}.db"
            blob_path = f"backups/{backup_filename}"
            
            logger.info(f"☁️ Starting {backup_type} database backup...")
            logger.info(f"   Database source: {upload_source}")
            logger.info(f"   Size: {os.path.getsize(upload_source) / 1024:.2f} KB")
            
            # Upload to GCS
            blob = self.bucket.blob(blob_path)
            blob.upload_from_filename(upload_source)
            
            # Also save as "latest" for easy recovery
            latest_blob = self.bucket.blob(f"backups/latest_{backup_type}.db")
            latest_blob.upload_from_filename(upload_source)
            
            # Save as persistent database (for automatic restore on redeploy)
            persistent_blob = self.bucket.blob("persistent/medical_reports.db")
            persistent_blob.upload_from_filename(upload_source)
            
            logger.info(f"✅ Backup completed successfully!")
            logger.info(f"   📁 File: gs://{BUCKET_NAME}/{blob_path}")
            logger.info(f"   💾 Persistent copy updated")
            
            # Clean old backups (keep last 30 days)
            self.cleanup_old_backups(days=30)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup failed: {e}")
            return False
    
    def restore_database(self, backup_blob_name: str) -> bool:
        """
        Restore database from a backup
        
        Args:
            backup_blob_name: Name of the backup blob in GCS
            
        Returns:
            True if successful, False otherwise
        """
        if not self.bucket:
            logger.error("❌ GCS bucket not available")
            return False
        
        try:
            logger.info(f"🔄 Restoring database from: {backup_blob_name}")
            
            # Download backup
            blob = self.bucket.blob(backup_blob_name)
            
            if not blob.exists():
                logger.error(f"❌ Backup not found: {backup_blob_name}")
                return False
            
            # Create backup of current database
            if os.path.exists(self.database_path):
                backup_current = f"{self.database_path}.before_restore"
                shutil.copy2(self.database_path, backup_current)
                logger.info(f"   💾 Current database backed up to: {backup_current}")
            
            # Download and restore
            blob.download_to_filename(self.database_path)
            
            logger.info(f"✅ Database restored successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False
    
    def list_backups(self, limit: int = 50) -> list:
        """
        List available backups
        
        Args:
            limit: Maximum number of backups to list
            
        Returns:
            List of backup information dictionaries
        """
        if not self.bucket:
            return []
        
        try:
            blobs = self.bucket.list_blobs(prefix="backups/", max_results=limit)
            
            backups = []
            for blob in blobs:
                if blob.name.endswith(".db"):
                    backups.append({
                        "name": blob.name,
                        "size_kb": blob.size / 1024,
                        "created": blob.time_created,
                        "updated": blob.updated
                    })
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x["created"], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"❌ Error listing backups: {e}")
            return []
    
    def cleanup_old_backups(self, days: int = 30):
        """
        Delete backups older than specified days
        
        Args:
            days: Number of days to keep backups
        """
        if not self.bucket:
            return
        
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            blobs = self.bucket.list_blobs(prefix="backups/")
            deleted_count = 0
            
            for blob in blobs:
                # Skip "latest" backups
                if "latest" in blob.name:
                    continue
                
                # Delete old backups
                if blob.time_created.replace(tzinfo=None) < cutoff_date:
                    blob.delete()
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"🗑️ Cleaned up {deleted_count} old backups (>{days} days)")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning old backups: {e}")
    
    def get_backup_info(self) -> dict:
        """
        Get backup service information
        
        Returns:
            Dictionary with backup service stats
        """
        info = {
            "bucket_name": BUCKET_NAME,
            "database_path": self.database_path,
            "bucket_available": self.bucket is not None
        }
        
        try:
            if os.path.exists(self.database_path):
                info["database_exists"] = True
                info["database_size_kb"] = os.path.getsize(self.database_path) / 1024
            else:
                info["database_exists"] = False
            
            # Get backup count
            if self.bucket:
                backups = self.list_backups(limit=1000)
                info["total_backups"] = len(backups)
                if backups:
                    info["latest_backup"] = backups[0]["created"].isoformat()
            
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    def quick_backup(self) -> bool:
        """
        Quick backup (alias for auto backup)
        Used by scheduler for automatic backups
        """
        return self.backup_database(backup_type="auto")


# ================================================
# Global Instance
# ================================================

_backup_service = None

def get_backup_service() -> SQLiteBackupService:
    """Get the global SQLite backup service instance"""
    global _backup_service
    if _backup_service is None:
        _backup_service = SQLiteBackupService()
    return _backup_service


# ================================================
# Convenience Functions
# ================================================

def backup_now() -> bool:
    """Backup database now (manual)"""
    service = get_backup_service()
    return service.backup_database(backup_type="manual")


def auto_backup() -> bool:
    """Automatic backup (called by scheduler)"""
    service = get_backup_service()
    return service.backup_database(backup_type="auto")


def list_all_backups(limit: int = 50) -> list:
    """List all available backups"""
    service = get_backup_service()
    return service.list_backups(limit=limit)


def restore_from_backup(backup_name: str) -> bool:
    """Restore database from a backup"""
    service = get_backup_service()
    return service.restore_database(backup_name)


# ================================================
# Testing
# ================================================

if __name__ == "__main__":
    # Test backup service
    logging.basicConfig(level=logging.INFO)
    
    logger.info("="*60)
    logger.info("🧪 Testing SQLite Backup Service")
    logger.info("="*60)
    
    service = get_backup_service()
    
    # Get info
    info = service.get_backup_info()
    logger.info(f"\n📊 Backup Service Info:")
    for key, value in info.items():
        logger.info(f"   {key}: {value}")
    
    # Test backup
    logger.info(f"\n🧪 Testing backup...")
    success = service.backup_database(backup_type="test")
    
    if success:
        logger.info("\n✅ Backup test PASSED!")
    else:
        logger.error("\n❌ Backup test FAILED!")
    
    # List backups
    logger.info(f"\n📋 Recent Backups:")
    backups = service.list_backups(limit=10)
    for backup in backups:
        logger.info(f"   • {backup['name']} - {backup['size_kb']:.2f} KB")
    
    logger.info("\n" + "="*60)

