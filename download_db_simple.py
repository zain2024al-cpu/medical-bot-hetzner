#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت بسيط لجلب قاعدة البيانات من السيرفر
"""

import os
import sys
import shutil
from pathlib import Path

# إصلاح مشكلة الترميز
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SERVER_IP = "5.223.58.71"
BOT_USER = "botuser"
REMOTE_DB_PATH = "/home/botuser/medical-bot/db/medical_reports.db"
LOCAL_DB_PATH = Path("db/medical_reports.db")
BACKUP_DIR = Path("db/backups")

def main():
    print("=" * 50)
    print("جلب قاعدة البيانات من السيرفر")
    print("=" * 50)
    print()
    
    # إنشاء مجلدات
    LOCAL_DB_PATH.parent.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)
    
    # نسخ احتياطي
    if LOCAL_DB_PATH.exists():
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_before_download_{timestamp}.db"
        try:
            shutil.copy2(LOCAL_DB_PATH, backup_path)
            print(f"تم حفظ النسخة الاحتياطية: {backup_path}")
        except Exception as e:
            print(f"تحذير: فشل حفظ النسخة الاحتياطية: {e}")
            # محاولة نقل الملف
            try:
                old_path = LOCAL_DB_PATH.with_suffix('.db.old')
                if old_path.exists():
                    old_path.unlink()
                LOCAL_DB_PATH.rename(old_path)
                print(f"تم نقل الملف القديم إلى: {old_path}")
            except:
                pass
    
    # إغلاق أي اتصالات مفتوحة
    import time
    if LOCAL_DB_PATH.exists():
        try:
            # محاولة حذف الملف (سيفشل إذا كان مفتوحاً)
            temp_path = LOCAL_DB_PATH.with_suffix('.db.temp')
            if temp_path.exists():
                temp_path.unlink()
            LOCAL_DB_PATH.rename(temp_path)
            print("تم إغلاق الملف الحالي")
        except Exception as e:
            print(f"تحذير: الملف قد يكون مفتوحاً: {e}")
            print("تأكد من إغلاق البوت أو أي برنامج يستخدم قاعدة البيانات")
            response = input("هل تريد المتابعة؟ (y/n): ")
            if response.lower() != 'y':
                return
    
    # جلب قاعدة البيانات
    print()
    print("جاري جلب قاعدة البيانات من السيرفر...")
    print(f"السيرفر: {BOT_USER}@{SERVER_IP}")
    print(f"المسار: {REMOTE_DB_PATH}")
    print()
    print("سيتم طلب كلمة المرور: bot123456")
    print()
    
    import subprocess
    
    # استخدام scp مع مسار Windows
    local_path_str = str(LOCAL_DB_PATH.absolute())
    cmd = [
        "scp",
        f"{BOT_USER}@{SERVER_IP}:{REMOTE_DB_PATH}",
        local_path_str
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        print()
        print("=" * 50)
        print("تم جلب قاعدة البيانات بنجاح!")
        print("=" * 50)
        
        # التحقق من الملف
        if LOCAL_DB_PATH.exists():
            file_size = LOCAL_DB_PATH.stat().st_size / (1024 * 1024)
            print(f"حجم قاعدة البيانات: {file_size:.2f} MB")
            print()
            
            # التحقق من المحتويات
            print("التحقق من محتويات قاعدة البيانات...")
            print()
            try:
                from check_database_after_download import check_database
                check_database()
            except Exception as e:
                print(f"تحذير: فشل التحقق من المحتويات: {e}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 50)
        print("فشل جلب قاعدة البيانات")
        print("=" * 50)
        print()
        print("تأكد من:")
        print("  - الاتصال بالإنترنت")
        print("  - صحة كلمة المرور: bot123456")
        print("  - إغلاق البوت أو أي برنامج يستخدم قاعدة البيانات")
        return False
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nتم الإلغاء")
    except Exception as e:
        print(f"خطأ: {e}")
        import traceback
        traceback.print_exc()






