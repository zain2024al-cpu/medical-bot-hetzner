#!/usr/bin/env python3
"""
إضافة الأعمدة المفقودة إلى جدول schedule_images
"""
import sqlite3
import os

def fix_schedule_images_table():
    db_path = 'db/medical_reports.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(schedule_images)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    print(f"✅ Existing columns: {existing_columns}")
    
    # Columns to add (all columns from the model)
    columns_to_add = [
        ('translator_id', 'INTEGER'),
        ('translator_name', 'VARCHAR(255)'),
        ('upload_date', 'DATETIME'),
        ('extracted_text', 'TEXT'),
        ('status', 'VARCHAR(50) DEFAULT "active"'),
        ('created_at', 'DATETIME'),
    ]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE schedule_images ADD COLUMN {col_name} {col_type}")
                print(f"✅ Added column: {col_name}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Could not add {col_name}: {e}")
        else:
            print(f"ℹ️ Column already exists: {col_name}")
    
    conn.commit()
    
    # Verify
    cursor.execute("PRAGMA table_info(schedule_images)")
    final_columns = {row[1] for row in cursor.fetchall()}
    print(f"\n✅ Final columns: {final_columns}")
    
    conn.close()
    return True

if __name__ == "__main__":
    fix_schedule_images_table()
