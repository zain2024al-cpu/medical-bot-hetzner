#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة حقل room_number إلى جدول reports
"""

import sqlite3
import os
import sys

# مسار قاعدة البيانات
DB_PATH = os.path.join("db", "medical_reports.db")

def add_room_number_column():
    """إضافة حقل room_number إلى جدول reports"""
    if not os.path.exists(DB_PATH):
        print(f"❌ قاعدة البيانات غير موجودة: {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # التحقق من وجود الحقل
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'room_number' in columns:
            print("✅ حقل room_number موجود بالفعل في جدول reports")
            conn.close()
            return True
        
        # إضافة الحقل
        print("🔧 إضافة حقل room_number إلى جدول reports...")
        cursor.execute("ALTER TABLE reports ADD COLUMN room_number TEXT")
        conn.commit()
        
        # التحقق مرة أخرى
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'room_number' in columns:
            print("✅ تم إضافة حقل room_number بنجاح!")
            conn.close()
            return True
        else:
            print("❌ فشل إضافة حقل room_number")
            conn.close()
            return False
            
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("✅ حقل room_number موجود بالفعل")
            return True
        else:
            print(f"❌ خطأ في قاعدة البيانات: {e}")
            conn.close()
            return False
    except Exception as e:
        print(f"❌ خطأ: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("إضافة حقل room_number إلى قاعدة البيانات")
    print("=" * 50)
    print()
    
    if add_room_number_column():
        print("\n✅ تم بنجاح!")
        sys.exit(0)
    else:
        print("\n❌ فشل!")
        sys.exit(1)
