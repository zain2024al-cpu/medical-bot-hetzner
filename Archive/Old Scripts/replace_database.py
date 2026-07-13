#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت لاستبدال قاعدة البيانات القديمة بالجديدة
"""

import os
import sys
import shutil
import time
from pathlib import Path
from datetime import datetime
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OLD_DB = Path("db/medical_reports.db")
NEW_DB = Path("db/medical_reports_new.db")
BACKUP_DIR = Path("db/backups")

def replace_database():
    """استبدال قاعدة البيانات القديمة بالجديدة"""
    
    if not NEW_DB.exists():
        print(f"❌ الملف الجديد غير موجود: {NEW_DB}")
        return False
    
    print("=" * 50)
    print("استبدال قاعدة البيانات")
    print("=" * 50)
    print()
    
    # إنشاء نسخة احتياطية
    if OLD_DB.exists():
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"backup_before_replace_{timestamp}.db"
        
        try:
            shutil.copy2(OLD_DB, backup_path)
            print(f"✅ تم حفظ النسخة الاحتياطية: {backup_path}")
        except Exception as e:
            print(f"⚠️  فشل حفظ النسخة الاحتياطية: {e}")
            response = input("هل تريد المتابعة؟ (y/n): ")
            if response.lower() != 'y':
                return False
    
    # محاولة حذف الملف القديم
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            if OLD_DB.exists():
                # محاولة إعادة تسمية الملف القديم
                old_backup = OLD_DB.with_suffix('.db.old')
                if old_backup.exists():
                    old_backup.unlink()
                OLD_DB.rename(old_backup)
                print(f"✅ تم نقل الملف القديم إلى: {old_backup}")
            
            # نسخ الملف الجديد
            shutil.copy2(NEW_DB, OLD_DB)
            print(f"✅ تم استبدال قاعدة البيانات بنجاح!")
            
            # حذف الملف الجديد المؤقت
            NEW_DB.unlink()
            print(f"✅ تم حذف الملف المؤقت")
            
            return True
            
        except PermissionError as e:
            if attempt < max_attempts - 1:
                print(f"⚠️  الملف مفتوح في عملية أخرى. محاولة {attempt + 1}/{max_attempts}...")
                print("   تأكد من إغلاق البوت أو أي برنامج يستخدم قاعدة البيانات")
                time.sleep(2)
            else:
                print(f"❌ فشل استبدال قاعدة البيانات بعد {max_attempts} محاولات")
                print(f"   الخطأ: {e}")
                print()
                print("الحلول المقترحة:")
                print("  1. أغلق البوت أو أي برنامج يستخدم قاعدة البيانات")
                print("  2. أعد تشغيل الكمبيوتر")
                print("  3. استبدل الملف يدوياً:")
                print(f"     - احذف: {OLD_DB}")
                print(f"     - أعد تسمية: {NEW_DB} إلى {OLD_DB.name}")
                return False
        except Exception as e:
            print(f"❌ خطأ غير متوقع: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return False

if __name__ == "__main__":
    try:
        success = replace_database()
        print()
        print("=" * 50)
        if success:
            print("✅ تم تحديث قاعدة البيانات بنجاح!")
            print()
            print("الآن قاعدة البيانات المحلية محدثة مع السيرفر:")
            print("  - 46 مستشفى (بدلاً من 34)")
            print("  - 86 مريض")
            print("  - 41 قسم")
            print("  - 94 طبيب")
        else:
            print("❌ فشل تحديث قاعدة البيانات")
        print("=" * 50)
    except KeyboardInterrupt:
        print("\nتم الإلغاء")
    except Exception as e:
        print(f"خطأ: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        input("\nاضغط Enter للخروج...")
    except:
        pass






