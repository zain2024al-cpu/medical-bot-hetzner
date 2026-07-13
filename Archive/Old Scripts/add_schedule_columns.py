#!/usr/bin/env python3
"""
إضافة أعمدة translator_id و translator_name لجدول schedule_images
"""

import sqlite3
import os

def add_schedule_columns():
    """إضافة الأعمدة الناقصة لجدول schedule_images"""
    
    db_path = "db/medical_reports.db"
    
    if not os.path.exists(db_path):
        print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # فحص الأعمدة الموجودة
        cursor.execute("PRAGMA table_info(schedule_images)")
        columns = [col[1] for col in cursor.fetchall()]
        
        print(f"📋 الأعمدة الموجودة حالياً: {columns}")
        
        # إضافة translator_id إذا لم يكن موجوداً
        if 'translator_id' not in columns:
            print("➕ إضافة عمود translator_id...")
            cursor.execute("""
                ALTER TABLE schedule_images 
                ADD COLUMN translator_id INTEGER
            """)
            print("✅ تم إضافة translator_id")
        else:
            print("✓ translator_id موجود مسبقاً")
        
        # إضافة translator_name إذا لم يكن موجوداً
        if 'translator_name' not in columns:
            print("➕ إضافة عمود translator_name...")
            cursor.execute("""
                ALTER TABLE schedule_images 
                ADD COLUMN translator_name VARCHAR(255)
            """)
            print("✅ تم إضافة translator_name")
        else:
            print("✓ translator_name موجود مسبقاً")
        
        # إضافة upload_date إذا لم يكن موجوداً
        if 'upload_date' not in columns:
            print("➕ إضافة عمود upload_date...")
            cursor.execute("""
                ALTER TABLE schedule_images 
                ADD COLUMN upload_date DATETIME
            """)
            print("✅ تم إضافة upload_date")
        else:
            print("✓ upload_date موجود مسبقاً")
        
        # إضافة extracted_text إذا لم يكن موجوداً
        if 'extracted_text' not in columns:
            print("➕ إضافة عمود extracted_text...")
            cursor.execute("""
                ALTER TABLE schedule_images 
                ADD COLUMN extracted_text TEXT
            """)
            print("✅ تم إضافة extracted_text")
        else:
            print("✓ extracted_text موجود مسبقاً")
        
        # إضافة status إذا لم يكن موجوداً
        if 'status' not in columns:
            print("➕ إضافة عمود status...")
            cursor.execute("""
                ALTER TABLE schedule_images 
                ADD COLUMN status VARCHAR(50) DEFAULT 'active'
            """)
            print("✅ تم إضافة status")
        else:
            print("✓ status موجود مسبقاً")
        
        # إضافة created_at إذا لم يكن موجوداً
        if 'created_at' not in columns:
            print("➕ إضافة عمود created_at...")
            cursor.execute("""
                ALTER TABLE schedule_images 
                ADD COLUMN created_at DATETIME
            """)
            print("✅ تم إضافة created_at")
        else:
            print("✓ created_at موجود مسبقاً")
        
        conn.commit()
        
        # فحص النتيجة
        cursor.execute("PRAGMA table_info(schedule_images)")
        columns_after = [col[1] for col in cursor.fetchall()]
        
        print(f"\n📋 الأعمدة بعد التحديث: {columns_after}")
        print("\n✅ تم تحديث الجدول بنجاح!")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return

if __name__ == "__main__":
    add_schedule_columns()
