#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكربت لإضافة عمود radiation_therapy_recommendations إلى جدول reports
يمكن تنفيذه محلياً أو على السيرفر
"""

import sqlite3
import os
import sys

# إصلاح مشكلة الترميز على Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# مسارات محتملة لقاعدة البيانات
possible_paths = [
    os.path.join(os.path.dirname(__file__), "db", "medical_reports.db"),
    "/home/botuser/medical-bot/db/medical_reports.db",
    "db/medical_reports.db",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "medical_reports.db"),
]

DB_PATH = None
for path in possible_paths:
    if os.path.exists(path):
        DB_PATH = path
        print(f"✅ تم العثور على قاعدة البيانات: {DB_PATH}")
        break

if not DB_PATH:
    print("❌ لم يتم العثور على قاعدة البيانات في المسارات التالية:")
    for path in possible_paths:
        print(f"   - {path}")
    sys.exit(1)

def add_radiation_recommendations_column():
    """إضافة عمود radiation_therapy_recommendations إلى جدول reports"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # التحقق من وجود العمود
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'radiation_therapy_recommendations' in columns:
            print("✅ العمود radiation_therapy_recommendations موجود بالفعل")
            conn.close()
            return True
        
        # إضافة العمود
        print("⏳ جاري إضافة العمود radiation_therapy_recommendations...")
        cursor.execute("ALTER TABLE reports ADD COLUMN radiation_therapy_recommendations TEXT")
        conn.commit()
        
        # التحقق مرة أخرى
        cursor.execute("PRAGMA table_info(reports)")
        columns_after = [column[1] for column in cursor.fetchall()]
        
        if 'radiation_therapy_recommendations' in columns_after:
            print("✅ تم إضافة العمود radiation_therapy_recommendations بنجاح")
            conn.close()
            return True
        else:
            print("❌ فشل إضافة العمود")
            conn.close()
            return False
        
    except Exception as e:
        print(f"❌ خطأ في إضافة العمود: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("إضافة عمود radiation_therapy_recommendations")
    print("=" * 50)
    
    if add_radiation_recommendations_column():
        print("\n✅ تمت العملية بنجاح!")
        sys.exit(0)
    else:
        print("\n❌ فشلت العملية!")
        sys.exit(1)
