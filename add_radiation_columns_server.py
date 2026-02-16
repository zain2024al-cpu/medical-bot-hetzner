#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة أعمدة radiation_therapy إلى قاعدة البيانات
"""
import sqlite3
import sys

DB_PATH = '/home/botuser/medical-bot/db/medical_reports.db'

print("=" * 70)
print("إضافة أعمدة radiation_therapy إلى قاعدة البيانات")
print("=" * 70)
print()

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # قائمة الأعمدة المطلوبة
    columns_to_add = [
        ("radiation_therapy_type", "VARCHAR(255)"),
        ("radiation_therapy_session_number", "VARCHAR(100)"),
        ("radiation_therapy_remaining", "VARCHAR(100)"),
        ("radiation_therapy_return_date", "DATETIME"),
        ("radiation_therapy_return_reason", "TEXT"),
        ("radiation_therapy_final_notes", "TEXT"),
        ("radiation_therapy_completed", "INTEGER DEFAULT 0"),
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            # التحقق من وجود العمود
            cursor.execute(f"PRAGMA table_info(reports)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if col_name not in columns:
                # إضافة العمود
                cursor.execute(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}")
                print(f"✅ تم إضافة العمود: {col_name}")
            else:
                print(f"ℹ️  العمود موجود مسبقاً: {col_name}")
        
        except Exception as e:
            print(f"❌ خطأ في إضافة {col_name}: {e}")
    
    conn.commit()
    conn.close()
    
    print()
    print("=" * 70)
    print("✅ تم الانتهاء من إضافة الأعمدة!")
    print("=" * 70)
    
except Exception as e:
    print(f"❌ خطأ عام: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
