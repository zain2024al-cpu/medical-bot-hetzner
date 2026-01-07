#!/usr/bin/env python3
"""إضافة عمود room_number لجدول التقارير"""

import sqlite3
import os

# مسار قاعدة البيانات
db_path = os.path.join(os.path.dirname(__file__), 'db', 'medical_reports.db')

print(f"🗄️ مسار قاعدة البيانات: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # التحقق من وجود العمود
    cursor.execute("PRAGMA table_info(reports)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'room_number' not in columns:
        print("➕ إضافة عمود room_number...")
        cursor.execute("ALTER TABLE reports ADD COLUMN room_number TEXT")
        conn.commit()
        print("✅ تم إضافة عمود room_number بنجاح!")
    else:
        print("✅ عمود room_number موجود مسبقاً")
    
    conn.close()
    print("🎉 تم بنجاح!")
    
except Exception as e:
    print(f"❌ خطأ: {e}")
