# ================================================
# db/persistent_storage.py
# 🔹 Persistent Storage Manager - Cloud Storage Integration
# ================================================

import os
import logging
from pathlib import Path
from google.cloud import storage

logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = "lunar-standard-477302-a6"
BUCKET_NAME = f"{PROJECT_ID}-sqlite-backups"
DATABASE_PATH = os.getenv("DATABASE_PATH", "db/medical_reports.db")
PERSISTENT_DB_PATH = "persistent/medical_reports.db"  # Path in GCS

class PersistentStorageManager:
    """
    Manages database persistence across Cloud Run deployments
    
    Features:
    - Download database from GCS on startup
    - Upload database to GCS on shutdown
    - Automatic sync
    """
    
    def __init__(self):
        self.bucket_name = BUCKET_NAME
        self.local_path = DATABASE_PATH
        self.cloud_path = PERSISTENT_DB_PATH
        self.client = None
        self.bucket = None
        self._init_storage()
    
    def _init_storage(self):
        """Initialize Google Cloud Storage client"""
        try:
            self.client = storage.Client(project=PROJECT_ID)
            self.bucket = self.client.bucket(BUCKET_NAME)
            
            if not self.bucket.exists():
                logger.info(f"Creating bucket: {BUCKET_NAME}")
                self.bucket = self.client.create_bucket(BUCKET_NAME, location="asia-south1")
            
            logger.info(f"✅ Cloud Storage initialized: {BUCKET_NAME}")
        except Exception as e:
            logger.error(f"❌ Failed to init Cloud Storage: {e}")
    
    def download_database(self) -> bool:
        """
        Download database from Cloud Storage on startup
        
        Returns:
            True if downloaded successfully, False if no backup exists
        """
        try:
            if not self.bucket:
                return False
            
            blob = self.bucket.blob(self.cloud_path)
            
            if not blob.exists():
                return False
            
            # Create directory if needed
            os.makedirs(os.path.dirname(self.local_path), exist_ok=True)
            
            # Download database (fast, no logging during download)
            blob.download_to_filename(self.local_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to download database: {e}")
            return False
    
    def upload_database(self) -> bool:
        """
        Upload database to Cloud Storage
        
        Returns:
            True if uploaded successfully
        """
        try:
            if not self.bucket:
                logger.warning("⚠️ Bucket not available")
                return False
            
            if not os.path.exists(self.local_path):
                logger.warning(f"⚠️ Database file not found: {self.local_path}")
                return False
            
            blob = self.bucket.blob(self.cloud_path)
            blob.upload_from_filename(self.local_path)
            
            size_kb = os.path.getsize(self.local_path) / 1024
            logger.info(f"✅ Database uploaded to Cloud Storage")
            logger.info(f"   Size: {size_kb:.2f} KB")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload database: {e}")
            return False
    
    def sync_to_cloud(self) -> bool:
        """Quick sync to cloud (called periodically)"""
        return self.upload_database()


# Global instance
_storage_manager = None

def get_storage_manager() -> PersistentStorageManager:
    """Get the global storage manager instance"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = PersistentStorageManager()
    return _storage_manager


def restore_database_on_startup():
    """
    Restore database from Cloud Storage on startup
    Call this before initializing the database
    """
    manager = get_storage_manager()
    return manager.download_database()


def save_database_to_cloud():
    """
    Save database to Cloud Storage
    Call this periodically or on shutdown
    """
    manager = get_storage_manager()
    return manager.upload_database()

