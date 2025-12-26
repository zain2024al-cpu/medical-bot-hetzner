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

# Create engine with SQLite-specific settings - محسّن للأداء العالي والاستقرار
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    connect_args={
        "check_same_thread": False,  # Allow multi-threading
        "timeout": 180,  # 180 second timeout - زيادة لدعم الضغط العالي جداً
        "isolation_level": None  # Enable autocommit for WAL mode
    },
    pool_pre_ping=True,  # Verify connections before using - مهم للاستقرار
    pool_recycle=1800,  # Recycle connections after 30 minutes (أسرع من 1 ساعة)
    pool_size=50,  # Connection pool size - زيادة كبيرة لدعم 50+ مستخدم متزامن
    max_overflow=30,  # Max additional connections - زيادة للضغط العالي
    pool_timeout=60,  # Timeout للحصول على connection من pool
    pool_reset_on_return='commit'  # Reset connections on return for stability
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

def migrate_reports_table_add_created_by():
    """
    Migrate reports table to add created_by_tg_user_id column
    This is safe to call multiple times
    """
    try:
        from sqlalchemy import text, inspect
        from sqlalchemy.exc import OperationalError
        
        logger.info("🔧 Checking reports table structure for created_by_tg_user_id...")
        
        with engine.connect() as conn:
            # Get table info
            inspector = inspect(engine)
            if 'reports' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('reports')]
                
                if 'created_by_tg_user_id' not in columns:
                    logger.info("➕ Adding created_by_tg_user_id column to reports table...")
                    try:
                        conn.execute(text("ALTER TABLE reports ADD COLUMN created_by_tg_user_id INTEGER"))
                        conn.commit()
                        logger.info("✅ Added created_by_tg_user_id column successfully")
                        
                        # Create index
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_reports_created_by_tg_user_id ON reports(created_by_tg_user_id)"))
                            conn.commit()
                            logger.info("✅ Created index for created_by_tg_user_id")
                        except Exception as index_error:
                            logger.warning(f"⚠️ Could not create index: {index_error}")
                    except OperationalError as e:
                        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                            logger.info("ℹ️ created_by_tg_user_id column already exists")
                        else:
                            logger.error(f"❌ Error adding created_by_tg_user_id column: {e}")
                            raise
                else:
                    logger.info("ℹ️ created_by_tg_user_id column already exists")
            else:
                logger.info("ℹ️ reports table doesn't exist yet - will be created by create_all()")
        
        return True
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def migrate_initial_cases_table():
    """
    Migrate initial_cases table to add missing columns
    This is safe to call multiple times
    """
    try:
        from sqlalchemy import text, inspect
        from sqlalchemy.exc import OperationalError
        
        logger.info("🔧 Checking initial_cases table structure...")
        
        with engine.connect() as conn:
            # Get table info
            inspector = inspect(engine)
            if 'initial_cases' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('initial_cases')]
                logger.info(f"📋 Existing columns in initial_cases: {columns}")
                
                # List of columns that should exist (based on InitialCase model)
                required_columns = {
                    'patient_name': 'VARCHAR(255)',
                    'patient_age': 'VARCHAR(255)',  # Changed from Integer to String
                    'main_complaint': 'TEXT',
                    'current_history': 'TEXT',
                    'previous_procedures': 'TEXT',
                    'test_details': 'TEXT',
                    'notes': 'TEXT',
                    'case_details': 'TEXT',
                    'created_by': 'INTEGER',
                    'created_at': 'DATETIME',
                    'status': 'VARCHAR(50)',
                }
                
                # Add missing columns
                for col_name, col_type in required_columns.items():
                    if col_name not in columns:
                        logger.info(f"➕ Adding {col_name} column to initial_cases...")
                        try:
                            conn.execute(text(f"ALTER TABLE initial_cases ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                            logger.info(f"✅ Added {col_name} column successfully")
                        except OperationalError as e:
                            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                                logger.info(f"ℹ️ {col_name} column already exists")
                            else:
                                logger.error(f"❌ Error adding {col_name} column: {e}")
                                raise
                    else:
                        logger.info(f"ℹ️ {col_name} column already exists")
                
                # Change patient_age to String if it's Integer
                # Note: SQLite doesn't support changing column type directly
                # We'll handle this in the model (already changed to String)
                
            else:
                logger.info("ℹ️ initial_cases table doesn't exist yet - will be created by create_all()")
        
        return True
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


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
        
        # Run migrations for existing tables
        migrate_reports_table_add_created_by()
        migrate_initial_cases_table()
        
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
    Get database session with automatic cleanup and resilience
    
    Usage:
        with get_db() as db:
            user = db.query(User).first()
    """
    session = None
    max_retries = 3
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            session = SessionLocal()
            yield session
            session.commit()
            break  # نجح - اخرج من loop
        except (OperationalError, DisconnectionError) as e:
            if session:
                try:
                    session.rollback()
                except:
                    pass
                try:
                    session.close()
                except:
                    pass
            
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Database error (attempt {attempt + 1}/{max_retries}): {e}")
                import time
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                session = None
            else:
                logger.error(f"❌ Database error after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            if session:
                try:
                    session.rollback()
                except:
                    pass
            logger.error(f"❌ Database error: {e}")
            raise
        finally:
            if session:
                try:
                    session.close()
                except Exception as close_error:
                    logger.warning(f"⚠️ Error closing session: {close_error}")


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
        # Run migrations for existing tables
        try:
            migrate_reports_table_add_created_by()
            migrate_initial_cases_table()
        except Exception as migration_error:
            logger.warning(f"⚠️ Migration warning: {migration_error}")
except Exception as e:
    logger.warning(f"Database init warning: {e}")
    import traceback
    traceback.print_exc()
