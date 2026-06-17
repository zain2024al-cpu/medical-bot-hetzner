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


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone()
    return row is not None


def _table_columns(conn, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    return {
        row[1]
        for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    }


def _add_column_if_missing(conn, table_name: str, columns: set[str], column_name: str, ddl: str) -> None:
    if column_name in columns:
        return
    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
    columns.add(column_name)


def _ensure_schema_compatibility(target_engine=None) -> None:
    """
    Idempotent SQLite compatibility migration for older production databases.

    It never drops or rewrites tables. It only adds nullable columns expected by
    the current User model and links legacy translator-directory rows into the
    users table when translators.translator_id already contains Telegram IDs.
    """
    target_engine = target_engine or engine
    try:
        with target_engine.begin() as conn:
            if not _table_exists(conn, "users"):
                return

            columns = _table_columns(conn, "users")
            for column_name, ddl in {
                "tg_user_id": "INTEGER",
                "chat_id": "INTEGER",
                "first_name": "VARCHAR(255)",
                "last_name": "VARCHAR(255)",
                "full_name": "VARCHAR(255)",
                "username": "VARCHAR(255)",
                "phone_number": "VARCHAR(50)",
                "email": "VARCHAR(255)",
                "role": "VARCHAR(50)",
                "status": "VARCHAR(50)",
                "is_approved": "INTEGER",
                "is_admin": "INTEGER",
                "is_active": "INTEGER",
                "is_suspended": "INTEGER",
                "suspension_reason": "TEXT",
                "suspended_at": "DATETIME",
                "registration_date": "DATETIME",
                "last_active": "DATETIME",
                "total_reports": "INTEGER",
                "created_at": "DATETIME",
                "updated_at": "DATETIME",
            }.items():
                _add_column_if_missing(conn, "users", columns, column_name, ddl)

            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_tg_user_id ON users (tg_user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_approved ON users (is_approved)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_is_active ON users (is_active)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_created_at ON users (created_at)"))

            if not _table_exists(conn, "translators"):
                return

            translator_columns = _table_columns(conn, "translators")
            if not {"translator_id", "name"}.issubset(translator_columns):
                return

            # First repair existing user rows by exact unique name when safe.
            conn.execute(text("""
                UPDATE users
                SET
                    tg_user_id = (
                        SELECT t.translator_id
                        FROM translators t
                        WHERE LOWER(TRIM(COALESCE(t.name, ''))) = LOWER(TRIM(COALESCE(users.full_name, '')))
                        LIMIT 1
                    ),
                    chat_id = COALESCE(chat_id, (
                        SELECT t.translator_id
                        FROM translators t
                        WHERE LOWER(TRIM(COALESCE(t.name, ''))) = LOWER(TRIM(COALESCE(users.full_name, '')))
                        LIMIT 1
                    )),
                    is_approved = COALESCE(is_approved, 1),
                    is_active = COALESCE(is_active, 1),
                    is_suspended = COALESCE(is_suspended, 0),
                    role = COALESCE(role, 'user'),
                    status = COALESCE(status, 'approved'),
                    created_at = COALESCE(created_at, CURRENT_TIMESTAMP),
                    updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP),
                    registration_date = COALESCE(registration_date, CURRENT_TIMESTAMP),
                    last_active = COALESCE(last_active, CURRENT_TIMESTAMP),
                    total_reports = COALESCE(total_reports, 0)
                WHERE (tg_user_id IS NULL OR tg_user_id = 0)
                  AND full_name IS NOT NULL
                  AND TRIM(full_name) != ''
                  AND (
                      SELECT COUNT(*)
                      FROM translators t
                      WHERE LOWER(TRIM(COALESCE(t.name, ''))) = LOWER(TRIM(COALESCE(users.full_name, '')))
                  ) = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM users existing
                      WHERE existing.tg_user_id = (
                          SELECT t.translator_id
                          FROM translators t
                          WHERE LOWER(TRIM(COALESCE(t.name, ''))) = LOWER(TRIM(COALESCE(users.full_name, '')))
                          LIMIT 1
                      )
                  )
            """))

            # Then create platform user rows for remaining directory translators.
            conn.execute(text("""
                INSERT INTO users (
                    tg_user_id,
                    chat_id,
                    full_name,
                    role,
                    status,
                    is_approved,
                    is_admin,
                    is_active,
                    is_suspended,
                    registration_date,
                    last_active,
                    total_reports,
                    created_at,
                    updated_at
                )
                SELECT
                    t.translator_id,
                    t.translator_id,
                    t.name,
                    'user',
                    'approved',
                    1,
                    0,
                    1,
                    0,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP,
                    0,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                FROM translators t
                WHERE t.translator_id IS NOT NULL
                  AND t.translator_id > 0
                  AND NOT EXISTS (
                      SELECT 1
                      FROM users u
                      WHERE u.tg_user_id = t.translator_id
                  )
            """))
            # ── Healthcare: medication_records missing columns ────────────────
            if _table_exists(conn, "medication_records"):
                med_cols = _table_columns(conn, "medication_records")
                _add_column_if_missing(conn, "medication_records", med_cols, "dispense_source", "VARCHAR(50)")

            # ── General services: arrival_status + departure link ─────────────
            if _table_exists(conn, "gs_arrival_patients"):
                ap_cols = _table_columns(conn, "gs_arrival_patients")
                _add_column_if_missing(conn, "gs_arrival_patients", ap_cols, "arrival_status",      "VARCHAR(20)")
                _add_column_if_missing(conn, "gs_arrival_patients", ap_cols, "departure_record_id", "INTEGER")

            if _table_exists(conn, "gs_departure_records"):
                dr_cols = _table_columns(conn, "gs_departure_records")
                _add_column_if_missing(conn, "gs_departure_records", dr_cols, "arrival_patient_ids", "TEXT")

    except Exception as exc:
        logger.warning(f"⚠️ Schema compatibility migration skipped: {exc}")


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
        _ensure_schema_compatibility()
        logger.info(f"✅ Database tables created: {DATABASE_PATH}")

        try:
            from services.translators_service import seed_translators_directory, sync_reports_translator_ids
            seeded = seed_translators_directory()
            synced = sync_reports_translator_ids()
            _ensure_schema_compatibility()
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
                Base.metadata.create_all(bind=engine)
                _ensure_schema_compatibility()
            except Exception as copy_error:
                logger.warning(f"⚠️ Failed to copy initial database: {copy_error}")
                logger.info("Creating new database tables...")
                Base.metadata.create_all(bind=engine)
                _ensure_schema_compatibility()
                logger.info("✅ Database tables created")
        else:
            logger.info("Creating new database tables...")
            Base.metadata.create_all(bind=engine)
            _ensure_schema_compatibility()
            logger.info("✅ Database tables created")
    else:
        db_size = os.path.getsize(DATABASE_PATH) / 1024
        logger.info(f"✅ Database loaded: {db_size:.2f} KB")
        # Ensure all tables exist (for migrations)
        Base.metadata.create_all(bind=engine)
        _ensure_schema_compatibility()
except Exception as e:
    logger.warning(f"Database init warning: {e}")
    import traceback
    traceback.print_exc()
