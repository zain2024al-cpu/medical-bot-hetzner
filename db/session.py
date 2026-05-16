# ================================================
# db/session.py
# 🔹 SQLite Session Manager - Pure SQLAlchemy
# ================================================

import os
import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from db.models import Base

logger = logging.getLogger(__name__)

# ================================================
# Database Configuration
# ================================================

# SQLite database path
# ✅ مهم: اجعل المسار ثابتاً بالنسبة للمشروع لتفادي إنشاء DB جديدة عند التشغيل من CWD مختلف.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "db", "medical_reports.db")
DATABASE_PATH = os.getenv("DATABASE_PATH") or _DEFAULT_DB_PATH

# Create SQLite URL
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 🚀 Create engine with high-performance settings for heavy load
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
        "isolation_level": None
    },
    pool_pre_ping=True,
    pool_recycle=600,   # إعادة تدوير الاتصالات كل 10 دقائق
    pool_size=5,        # SQLite ملف واحد — pool صغير يقلل الـ contention
    max_overflow=10,
    pool_timeout=20,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """
    Enforce SQLite PRAGMAs on every new connection to avoid drift.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("PRAGMA busy_timeout=3000")
        cursor.execute("PRAGMA cache_size=-32000")    # 32MB cache في الذاكرة
        cursor.execute("PRAGMA temp_store=MEMORY")    # العمليات المؤقتة في RAM
        cursor.execute("PRAGMA mmap_size=134217728")  # 128MB memory-mapped I/O
        cursor.execute("PRAGMA wal_autocheckpoint=100")
    finally:
        cursor.close()

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

        try:
            from services.translators_service import seed_translators_directory, sync_reports_translator_ids
            seeded = seed_translators_directory()
            synced = sync_reports_translator_ids()
            if seeded or synced:
                logger.info(f"✅ Translators seeded/updated: {seeded}, Reports synced: {synced}")
        except Exception as seed_error:
            logger.warning(f"⚠️ Seed/sync translators skipped: {seed_error}")
        
        # Enable WAL mode for better concurrency
        try:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL"))
                conn.execute(text("PRAGMA synchronous=NORMAL"))
                conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB cache
                conn.execute(text("PRAGMA temp_store=MEMORY"))
                conn.execute(text("PRAGMA foreign_keys=OFF"))  # Disabled: Report model uses denormalized fields
                conn.execute(text("PRAGMA busy_timeout=5000")) # 5s busy timeout
                conn.commit()
            logger.info(f"✅ WAL mode enabled for optimal concurrency")
            
            # Run startup health check
            from db.maintenance import DatabaseMaintenance
            DatabaseMaintenance.check_db_health_startup()
            
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

# Download database from Cloud Storage on startup (DISABLED FOR FRESH START)
# This will be re-enabled after first successful deployment
# try:
#     from db.persistent_storage import restore_database_on_startup
#     if restore_database_on_startup():
#         logger.info("DB restored from GCS")
# except Exception as e:
#     pass  # Continue silently
logger.info("Database restore DISABLED - starting fresh")

# Create database directory if it doesn't exist
try:
    import os
    import shutil
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    # Check if database exists and is not empty
    db_exists = os.path.exists(DATABASE_PATH) and os.path.getsize(DATABASE_PATH) > 0
    
    if not db_exists:
        # Try to load from initial database file (for first deployment)
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
        db_size = os.path.getsize(DATABASE_PATH) / 1024
        logger.info(f"✅ Database loaded: {db_size:.2f} KB")
        # Ensure all tables exist (for migrations)
        Base.metadata.create_all(bind=engine)
except Exception as e:
    logger.warning(f"Database init warning: {e}")
    import traceback
    traceback.print_exc()
