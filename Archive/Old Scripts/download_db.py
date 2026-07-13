#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت لجلب قاعدة البيانات من السيرفر
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# إصلاح مشكلة الترميز في Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

SERVER_IP = "5.223.58.71"
BOT_USER = "botuser"
REMOTE_DB_PATH = "/home/botuser/medical-bot/db/medical_reports.db"
LOCAL_DB_PATH = os.path.join("db", "medical_reports.db")
BACKUP_DIR = os.path.join("db", "backups")

def create_backup():
    """إنشاء نسخة احتياطية من قاعدة البيانات الحالية"""
    if not os.path.exists(LOCAL_DB_PATH):
        print("قاعدة البيانات المحلية غير موجودة - لا حاجة لنسخة احتياطية")
        return True
    
    # إنشاء مجلد backups
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # اسم النسخة الاحتياطية
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = os.path.join(BACKUP_DIR, f"backup_before_download_{timestamp}.db")
    
    try:
        shutil.copy2(LOCAL_DB_PATH, backup_name)
        file_size = os.path.getsize(backup_name) / (1024 * 1024)  # MB
        print(f"تم حفظ النسخة الاحتياطية: {backup_name}")
        print(f"الحجم: {file_size:.2f} MB")
        return True
    except Exception as e:
        print(f"خطأ في إنشاء النسخة الاحتياطية: {e}")
        return False

def download_database():
    """جلب قاعدة البيانات من السيرفر"""
    print("=" * 50)
    print("جلب قاعدة البيانات من السيرفر")
    print("=" * 50)
    print()
    
    # إنشاء نسخة احتياطية
    print("1. إنشاء نسخة احتياطية من قاعدة البيانات الحالية...")
    if not create_backup():
        print("تحذير: فشل إنشاء النسخة الاحتياطية")
        response = input("هل تريد المتابعة؟ (y/n): ")
        if response.lower() != 'y':
            return False
    print()
    
    # إنشاء مجلد db إذا لم يكن موجوداً
    os.makedirs(os.path.dirname(LOCAL_DB_PATH), exist_ok=True)
    
    # جلب قاعدة البيانات
    print("2. جلب قاعدة البيانات من السيرفر...")
    print(f"   السيرفر: {BOT_USER}@{SERVER_IP}")
    print(f"   المسار: {REMOTE_DB_PATH}")
    print()
    
    # استخدام scp
    import subprocess
    cmd = [
        "scp",
        f"{BOT_USER}@{SERVER_IP}:{REMOTE_DB_PATH}",
        LOCAL_DB_PATH
    ]
    
    try:
        print("جاري التنزيل... (سيتم طلب كلمة المرور)")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("تم جلب قاعدة البيانات بنجاح!")
        print()
        
        # التحقق من الملف
        if os.path.exists(LOCAL_DB_PATH):
            file_size = os.path.getsize(LOCAL_DB_PATH) / (1024 * 1024)  # MB
            print(f"حجم قاعدة البيانات: {file_size:.2f} MB")
            print()
            
            # التحقق من المحتويات
            print("3. التحقق من محتويات قاعدة البيانات...")
            print()
            from check_database_after_download import check_database
            check_database()
            
            return True
        else:
            print("خطأ: قاعدة البيانات غير موجودة بعد الجلب")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"خطأ في جلب قاعدة البيانات: {e}")
        if e.stderr:
            print(f"الخطأ: {e.stderr}")
        print()
        print("تأكد من:")
        print("  - الاتصال بالإنترنت")
        print("  - الاتصال بـ VPN إذا كان مطلوباً")
        print("  - صحة عنوان IP: 5.223.58.71")
        print("  - صحة اسم المستخدم: botuser")
        print("  - كلمة المرور: bot123456")
        print()
        print("يمكنك أيضاً استخدام السكريبت download_database_from_server.bat")
        return False
    except Exception as e:
        print(f"خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = download_database()
    
    print()
    print("=" * 50)
    if success:
        print("تم تحديث قاعدة البيانات بنجاح!")
    else:
        print("فشل تحديث قاعدة البيانات")
    print("=" * 50)
    
    try:
        input("\nاضغط Enter للخروج...")
    except (EOFError, KeyboardInterrupt):
        pass

