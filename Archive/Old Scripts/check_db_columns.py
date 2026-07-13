#!/usr/bin/env python3
import sqlite3
import sys

DB_PATH = '/home/botuser/medical-bot/db/medical_reports.db'

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # فحص أعمدة جدول reports
    cursor.execute("PRAGMA table_info(reports)")
    columns = cursor.fetchall()
    
    print("=" * 70)
    print("أعمدة جدول reports المتعلقة بـ radiation:")
    print("=" * 70)
    
    found = False
    for col in columns:
        col_name = col[1]
        if 'radiation' in col_name.lower():
            print(f"✅ {col_name}: {col[2]}")
            found = True
    
    if not found:
        print("❌ لا توجد أعمدة radiation_therapy في قاعدة البيانات!")
        print()
        print("الحل: يجب إضافة الأعمدة إلى قاعدة البيانات")
    
    conn.close()
    
except Exception as e:
    print(f"❌ خطأ: {e}")
    sys.exit(1)
