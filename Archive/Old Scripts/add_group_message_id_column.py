#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة عمود group_message_id إلى جدول reports
"""

import sqlite3
import os
import sys

# مسار قاعدة البيانات - محاولة عدة مسارات
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
        break

if not DB_PATH:
    print("❌ لم يتم العثور على قاعدة البيانات")
    sys.exit(1)

def add_group_message_id_column():
    """إضافة عمود group_message_id إلى جدول reports"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # التحقق من وجود العمود
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'group_message_id' in columns:
            print("✅ العمود group_message_id موجود بالفعل")
            conn.close()
            return True
        
        # إضافة العمود
        cursor.execute("ALTER TABLE reports ADD COLUMN group_message_id INTEGER")
        conn.commit()
        
        print("✅ تم إضافة العمود group_message_id بنجاح")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إضافة العمود: {e}")
        return False

if __name__ == "__main__":
    if add_group_message_id_column():
        print("✅ اكتمل التحديث بنجاح")
        sys.exit(0)
    else:
        print("❌ فشل التحديث")
        sys.exit(1)

