#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة عمود radiation_therapy_recommendations إلى جدول reports
"""

import sqlite3
import os
import sys

# مسار قاعدة البيانات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "medical_reports.db")

if not os.path.exists(DB_PATH):
    print(f"ERROR: Database not found at: {DB_PATH}")
    sys.exit(1)

def add_column():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # التحقق من وجود العمود
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'radiation_therapy_recommendations' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN radiation_therapy_recommendations TEXT")
            conn.commit()
            print("SUCCESS: Added column radiation_therapy_recommendations")
        else:
            print("INFO: Column radiation_therapy_recommendations already exists")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to add column: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    add_column()
