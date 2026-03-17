"""
نسخ احتياطي يومي لقاعدة البيانات
أضفه في crontab على السيرفر:
  crontab -e
  0 0 * * * cd /home/botuser/medical-bot-hetzner && python3 backup_db.py

يحتفظ بآخر 7 نسخ فقط
"""
import sqlite3
import shutil
import os
import glob
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "medical_reports.db")
BACKUP_DIR = os.path.join(BASE_DIR, "db_backups")
MAX_BACKUPS = 7

os.makedirs(BACKUP_DIR, exist_ok=True)

now = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = os.path.join(BACKUP_DIR, f"medical_reports_{now}.db")

# نسخ آمن باستخدام sqlite3 backup API
try:
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    src.backup(dst)
    dst.close()
    src.close()
    print(f"Backup OK: {backup_path}")

    # حذف النسخ القديمة (الاحتفاظ بآخر 7)
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "medical_reports_*.db")))
    while len(backups) > MAX_BACKUPS:
        old = backups.pop(0)
        os.remove(old)
        print(f"Deleted old: {old}")

    # فحص سلامة النسخة
    check = sqlite3.connect(backup_path)
    result = check.execute("PRAGMA integrity_check").fetchone()
    check.close()
    if result[0] == "ok":
        print("Integrity: OK")
    else:
        print(f"WARNING: {result[0]}")

except Exception as e:
    print(f"Backup FAILED: {e}")
