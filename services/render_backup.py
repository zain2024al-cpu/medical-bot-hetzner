# ================================================
# services/render_backup.py
# 🔹 نظام النسخ الاحتياطي لـ Render
# ================================================

import os
import shutil
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ================================================
# إعدادات النسخ الاحتياطي
# ================================================

# استخدام نفس المسار من db/session.py أو المسار الافتراضي لـ Render
try:
    from db.session import DATABASE_PATH as DB_PATH
    # في Render، استخدم /app/db/medical_reports.db، محلياً استخدم db/medical_reports.db
    if os.path.exists("/app/db/medical_reports.db"):
        DATABASE_PATH = "/app/db/medical_reports.db"
        BACKUP_DIR = "/app/db/backups"
    else:
        DATABASE_PATH = DB_PATH
        BACKUP_DIR = os.path.join(os.path.dirname(DATABASE_PATH), "backups")
except Exception:
    # Fallback
    DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/db/medical_reports.db")
    BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/db/backups")

MAX_LOCAL_BACKUPS = int(os.getenv("MAX_LOCAL_BACKUPS", "10"))  # عدد النسخ المحلية


# ================================================
# نظام النسخ الاحتياطي المحلي
# ================================================

def _run_integrity_check(db_file: str) -> bool:
    """فحص سلامة قاعدة البيانات (على نسخة backup وليس الملف الحي قدر الإمكان)."""
    try:
        conn = sqlite3.connect(db_file, timeout=30)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        conn.close()
        return bool(row and str(row[0]).strip().lower() == "ok")
    except Exception as e:
        logger.error(f"❌ integrity_check failed for {db_file}: {e}")
        return False


def _checkpoint_wal(db_file: str):
    """تقليل مخاطر تلف النسخ عبر checkpoint لملفات WAL قبل النسخ."""
    try:
        conn = sqlite3.connect(db_file, timeout=30)
        cur = conn.cursor()
        # PASSIVE avoids forcing a heavy lock during active bot traffic.
        cur.execute("PRAGMA wal_checkpoint(PASSIVE)")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"⚠️ WAL checkpoint skipped: {e}")


def _sqlite_backup_copy(src_db: str, dst_db: str):
    """نسخ آمن باستخدام SQLite backup API بدل copy2 المباشر."""
    src_conn = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True, timeout=60)
    try:
        dst_conn = sqlite3.connect(dst_db, timeout=60)
        try:
            src_conn.backup(dst_conn, pages=1000, sleep=0.01)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def create_local_backup(prefix: str = "backup") -> Optional[str]:
    """
    إنشاء نسخة احتياطية محلية لقاعدة البيانات
    
    Returns:
        مسار النسخة الاحتياطية أو None إذا فشل
    """
    try:
        if not os.path.exists(DATABASE_PATH):
            logger.warning(f"⚠️ قاعدة البيانات غير موجودة: {DATABASE_PATH}")
            return None
        
        # إنشاء مجلد النسخ الاحتياطية
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # إنشاء اسم النسخة الاحتياطية
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{prefix}_{timestamp}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        # WAL checkpoint + SQLite backup API = نسخة أكثر ثباتاً من copy2
        _checkpoint_wal(DATABASE_PATH)
        _sqlite_backup_copy(DATABASE_PATH, backup_path)

        # فحص سلامة النسخة الاحتياطية فوراً
        if not _run_integrity_check(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                logger.debug("تم تجاهل استثناء في create_local_backup", exc_info=True)
            logger.error("❌ النسخة الاحتياطية فشلت integrity_check وتم حذفها")
            return None
        
        db_size = os.path.getsize(DATABASE_PATH) / 1024
        backup_size = os.path.getsize(backup_path) / 1024
        
        logger.info(f"✅ تم إنشاء نسخة احتياطية محلية")
        logger.info(f"   📁 المسار: {backup_path}")
        logger.info(f"   💾 الحجم: {backup_size:.2f} KB (الأصل: {db_size:.2f} KB)")
        
        # تنظيف النسخ القديمة
        cleanup_old_backups()
        
        return backup_path
        
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        import traceback
        traceback.print_exc()
        return None


def cleanup_old_backups():
    """حذف النسخ الاحتياطية القديمة (الاحتفاظ بآخر N نسخة)"""
    try:
        if not os.path.exists(BACKUP_DIR):
            return
        
        # الحصول على جميع النسخ الاحتياطية
        backups = []
        for file in os.listdir(BACKUP_DIR):
            if file.endswith(".db") and (
                file.startswith("backup_")
                or file.startswith("quick_")
                or file.startswith("daily_")
            ):
                file_path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(file_path)
                backups.append((mtime, file_path))
        
        # ترتيب حسب تاريخ التعديل (الأحدث أولاً)
        backups.sort(reverse=True)
        
        # حذف النسخ الزائدة
        if len(backups) > MAX_LOCAL_BACKUPS:
            for mtime, file_path in backups[MAX_LOCAL_BACKUPS:]:
                try:
                    os.remove(file_path)
                    logger.info(f"🗑️ تم حذف نسخة احتياطية قديمة: {os.path.basename(file_path)}")
                except Exception as e:
                    logger.warning(f"⚠️ فشل حذف نسخة احتياطية: {e}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في تنظيف النسخ الاحتياطية: {e}")


def restore_from_local_backup(backup_filename: str) -> bool:
    """
    استعادة قاعدة البيانات من نسخة احتياطية محلية
    
    Args:
        backup_filename: اسم ملف النسخة الاحتياطية
    
    Returns:
        True إذا نجحت العملية
    """
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        if not os.path.exists(backup_path):
            logger.error(f"❌ النسخة الاحتياطية غير موجودة: {backup_path}")
            return False
        
        # إنشاء نسخة احتياطية من قاعدة البيانات الحالية
        if os.path.exists(DATABASE_PATH):
            current_backup = f"{DATABASE_PATH}.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(DATABASE_PATH, current_backup)
            logger.info(f"💾 تم حفظ نسخة احتياطية من قاعدة البيانات الحالية: {current_backup}")
        
        # استعادة من النسخة الاحتياطية
        shutil.copy2(backup_path, DATABASE_PATH)
        
        logger.info(f"✅ تم استعادة قاعدة البيانات من: {backup_filename}")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في استعادة قاعدة البيانات: {e}")
        return False


def list_local_backups() -> list:
    """
    قائمة بالنسخ الاحتياطية المحلية
    
    Returns:
        قائمة بمعلومات النسخ الاحتياطية
    """
    backups = []
    
    try:
        if not os.path.exists(BACKUP_DIR):
            return backups
        
        for file in os.listdir(BACKUP_DIR):
            if file.startswith("backup_") and file.endswith(".db"):
                file_path = os.path.join(BACKUP_DIR, file)
                mtime = os.path.getmtime(file_path)
                size = os.path.getsize(file_path) / 1024
                
                backups.append({
                    "filename": file,
                    "path": file_path,
                    "size_kb": size,
                    "modified": datetime.fromtimestamp(mtime)
                })
        
        # ترتيب حسب التاريخ (الأحدث أولاً)
        backups.sort(key=lambda x: x["modified"], reverse=True)
        
    except Exception as e:
        logger.error(f"❌ خطأ في قائمة النسخ الاحتياطية: {e}")
    
    return backups


def get_latest_backup() -> Optional[str]:
    """الحصول على أحدث نسخة احتياطية"""
    backups = list_local_backups()
    if backups:
        return backups[0]["path"]
    return None


# ================================================
# دالة النسخ الاحتياطي التلقائي
# ================================================

def auto_backup_job():
    """مهمة النسخ الاحتياطي التلقائي (تُستدعى من scheduler)"""
    try:
        backup_path = create_local_backup(prefix="quick")
        if backup_path:
            logger.info(f"✅ النسخ الاحتياطي التلقائي نجح: {backup_path}")
            return True
        else:
            logger.warning("⚠️ فشل النسخ الاحتياطي التلقائي")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ في النسخ الاحتياطي التلقائي: {e}")
        return False


def create_monthly_archive(year: Optional[int] = None, month: Optional[int] = None) -> Optional[str]:
    """
    إنشاء أرشيف شهري (SQLite) للتقارير:
    - ملف مستقل لكل شهر
    - يفيد في الحفظ طويل الأمد وتقليل أثر أي تلف لاحق
    """
    try:
        now = datetime.utcnow()
        if year is None or month is None:
            # افتراضياً: الشهر السابق
            if now.month == 1:
                year, month = now.year - 1, 12
            else:
                year, month = now.year, now.month - 1

        start = f"{year}-{month:02d}-01 00:00:00"
        if month == 12:
            end = f"{year + 1}-01-01 00:00:00"
        else:
            end = f"{year}-{month + 1:02d}-01 00:00:00"

        os.makedirs(BACKUP_DIR, exist_ok=True)
        archive_name = f"archive_{year}_{month:02d}.db"
        archive_path = os.path.join(BACKUP_DIR, archive_name)

        # لا نعيد إنشاء نفس الأرشيف إذا كان موجوداً وسليمًا
        if os.path.exists(archive_path) and _run_integrity_check(archive_path):
            logger.info(f"ℹ️ الأرشيف الشهري موجود مسبقاً: {archive_name}")
            return archive_path

        if os.path.exists(archive_path):
            os.remove(archive_path)

        _checkpoint_wal(DATABASE_PATH)
        src_conn = sqlite3.connect(DATABASE_PATH, timeout=60)
        dst_conn = sqlite3.connect(archive_path, timeout=60)
        try:
            src_cur = src_conn.cursor()
            dst_cur = dst_conn.cursor()
            src_cur.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='reports'"
            )
            create_sql_row = src_cur.fetchone()
            if not create_sql_row or not create_sql_row[0]:
                raise RuntimeError("reports table schema not found")

            dst_cur.execute(create_sql_row[0])
            dst_cur.execute(
                "INSERT INTO reports SELECT * FROM main.reports "
                "WHERE COALESCE(report_date, created_at) >= ? "
                "AND COALESCE(report_date, created_at) < ?",
                (start, end),
            )
            # فهارس أساسية للاستعلامات اللاحقة
            dst_cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_id ON reports(id)")
            dst_cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_report_date ON reports(report_date)")
            dst_cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)")
            dst_conn.commit()
        finally:
            dst_conn.close()
            src_conn.close()

        if not _run_integrity_check(archive_path):
            try:
                os.remove(archive_path)
            except Exception:
                logger.debug("تم تجاهل استثناء في create_monthly_archive", exc_info=True)
            logger.error(f"❌ الأرشيف الشهري فشل integrity_check: {archive_name}")
            return None

        logger.info(f"✅ تم إنشاء الأرشيف الشهري: {archive_path}")
        return archive_path
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء الأرشيف الشهري: {e}")
        return None


# ================================================
# تصدير
# ================================================

__all__ = [
    'create_local_backup',
    'create_monthly_archive',
    'restore_from_local_backup',
    'list_local_backups',
    'get_latest_backup',
    'cleanup_old_backups',
    'auto_backup_job',
]

