# ================================================
# db/session.py
# 🔹 SQLite Session Manager - Pure SQLAlchemy
# ================================================

import os
import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from db.models import Base

logger = logging.getLogger(__name__)

# ================================================
# Database Configuration
# ================================================

# SQLite database path - يعمل محلياً وأونلاين
# على Hetzner: /home/botuser/medical-bot/db/medical_reports.db
# محلياً: db/medical_reports.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "db", "medical_reports.db")
DATABASE_PATH = os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)

# Create SQLite URL
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    connect_args={
        "check_same_thread": False,  # Allow multi-threading
        "timeout": 120,  # 120 second timeout - زيادة كبيرة لدعم الضغط العالي و20+ مستخدم
        "isolation_level": None  # Enable autocommit for WAL mode
    },
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_size=30,  # Connection pool size - زيادة لدعم 20+ مستخدم
    max_overflow=20  # Max additional connections - زيادة للضغط العالي
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ================================================
# Database Initialization
# ================================================

def init_database():
    """
    Initialize database - create all tables
    This is safe to call multiple times
    """
    try:
        logger.info("🔧 Initializing SQLite database...")
        
        # Create all tables first
        Base.metadata.create_all(bind=engine)
        logger.info(f"✅ Database tables created: {DATABASE_PATH}")
        
        # Enable WAL mode for better concurrency
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB cache
                conn.execute(text("PRAGMA temp_store=MEMORY"))
                conn.commit()
            logger.info(f"✅ WAL mode enabled for optimal concurrency")
        except Exception as pragma_error:
            logger.warning(f"⚠️ Could not set PRAGMA settings: {pragma_error}")
            # Continue anyway - database will work without optimizations
        
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def drop_all_tables():
    """
    Drop all tables - USE WITH CAUTION!
    Only for testing/development
    """
    logger.warning("⚠️ Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("✅ All tables dropped")


# ================================================
# Session Management
# ================================================

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session with automatic cleanup
    
    Usage:
        with get_db() as db:
            user = db.query(User).first()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Database error: {e}")
        raise
    finally:
        session.close()


def get_session() -> Session:
    """
    Get a new database session
    
    Note: You must close this session manually!
    Prefer using get_db() context manager instead.
    """
    return SessionLocal()


# ================================================
# Database Health Check
# ================================================

def health_check() -> bool:
    """
    Check if database is accessible and healthy
    
    Returns:
        True if database is healthy, False otherwise
    """
    try:
        from sqlalchemy import text
        with get_db() as db:
            # Try a simple query
            db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return False


def get_database_info() -> dict:
    """
    Get database information
    
    Returns:
        Dictionary with database stats
    """
    try:
        with get_db() as db:
            from db.models import User, Report, Patient
            
            info = {
                "path": DATABASE_PATH,
                "url": DATABASE_URL,
                "healthy": True,
                "users_count": db.query(User).count(),
                "reports_count": db.query(Report).count(),
                "patients_count": db.query(Patient).count()
            }
            return info
    except Exception as e:
        logger.error(f"❌ Error getting database info: {e}")
        return {
            "path": DATABASE_PATH,
            "url": DATABASE_URL,
            "healthy": False,
            "error": str(e)
        }


# ================================================
# Cleanup
# ================================================

def close_connection():
    """
    Close database connection pool
    Call this on application shutdown
    """
    try:
        engine.dispose()
        logger.info("✅ Database connection pool closed")
    except Exception as e:
        logger.error(f"❌ Error closing database: {e}")


# ================================================
# Auto-initialization
# ================================================

# ================================================
# Persistent Storage Integration
# ================================================

# Download database from Cloud Storage on startup
# محاولة استعادة قاعدة البيانات من GCS عند البدء
try:
    from db.persistent_storage import restore_database_on_startup
    if restore_database_on_startup():
        logger.info("✅ Database restored from GCS successfully")
    else:
        logger.info("ℹ️ No GCS backup found or local database exists - continuing with local database")
except Exception as e:
    logger.warning(f"⚠️ GCS restore attempt failed: {e}")
    logger.info("   Continuing with local database initialization")

# Create database directory if it doesn't exist
try:
    import shutil
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:  # تأكد من وجود مجلد
        os.makedirs(db_dir, exist_ok=True)
    
    # Check if database exists and is not empty
    db_exists = os.path.exists(DATABASE_PATH) and os.path.getsize(DATABASE_PATH) > 0
    
    if not db_exists:
        # قاعدة البيانات غير موجودة - تمت محاولة الاستعادة من GCS أعلاه
        # إذا لم تنجح الاستعادة من GCS، جرب الملف الأولي المحلي
        initial_db_path = os.path.join(os.path.dirname(DATABASE_PATH), "medical_reports_initial.db")
        
        if os.path.exists(initial_db_path) and os.path.getsize(initial_db_path) > 0:
            logger.info("📥 Loading database from initial file...")
            try:
                shutil.copy2(initial_db_path, DATABASE_PATH)
                db_size = os.path.getsize(DATABASE_PATH) / 1024
                logger.info(f"✅ Database loaded from initial file: {db_size:.2f} KB")
            except Exception as copy_error:
                logger.warning(f"⚠️ Failed to copy initial database: {copy_error}")
                logger.info("Creating new database tables...")
                Base.metadata.create_all(bind=engine)
                logger.info("✅ Database tables created")
        else:
            logger.info("Creating new database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created")
    else:
        # قاعدة البيانات موجودة (إما محلية أو تمت استعادتها من GCS)
        db_size = os.path.getsize(DATABASE_PATH) / 1024
        logger.info(f"✅ Database loaded: {db_size:.2f} KB")
        # Ensure all tables exist (for migrations)
        Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.warning(f"Database init warning: {e}")
    import traceback
    traceback.print_exc()
