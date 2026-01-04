#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إضافة الأعمدة المفقودة إلى جدول reports
- submitted_by_user_id
- group_message_id
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

def add_missing_columns():
    """إضافة الأعمدة المفقودة إلى جدول reports"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # التحقق من وجود الأعمدة
        cursor.execute("PRAGMA table_info(reports)")
        columns = [column[1] for column in cursor.fetchall()]
        
        added_columns = []
        
        # إضافة submitted_by_user_id
        if 'submitted_by_user_id' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN submitted_by_user_id INTEGER")
            conn.commit()
            added_columns.append('submitted_by_user_id')
            print("SUCCESS: Added column submitted_by_user_id")
        else:
            print("INFO: Column submitted_by_user_id already exists")
        
        # إضافة group_message_id
        if 'group_message_id' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN group_message_id INTEGER")
            conn.commit()
            added_columns.append('group_message_id')
            print("SUCCESS: Added column group_message_id")
        else:
            print("INFO: Column group_message_id already exists")
        
        # ✅ إضافة أعمدة تأجيل الموعد
        # app_reschedule_reason
        if 'app_reschedule_reason' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN app_reschedule_reason TEXT")
            conn.commit()
            added_columns.append('app_reschedule_reason')
            print("SUCCESS: Added column app_reschedule_reason")
        else:
            print("INFO: Column app_reschedule_reason already exists")
        
        # app_reschedule_return_date
        if 'app_reschedule_return_date' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN app_reschedule_return_date DATETIME")
            conn.commit()
            added_columns.append('app_reschedule_return_date')
            print("SUCCESS: Added column app_reschedule_return_date")
        else:
            print("INFO: Column app_reschedule_return_date already exists")
        
        # app_reschedule_return_reason
        if 'app_reschedule_return_reason' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN app_reschedule_return_reason TEXT")
            conn.commit()
            added_columns.append('app_reschedule_return_reason')
            print("SUCCESS: Added column app_reschedule_return_reason")
        else:
            print("INFO: Column app_reschedule_return_reason already exists")
        
        # ✅ إضافة أعمدة الأشعة والفحوصات
        # radiology_type
        if 'radiology_type' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN radiology_type TEXT")
            conn.commit()
            added_columns.append('radiology_type')
            print("SUCCESS: Added column radiology_type")
        else:
            print("INFO: Column radiology_type already exists")
        
        # radiology_delivery_date
        if 'radiology_delivery_date' not in columns:
            cursor.execute("ALTER TABLE reports ADD COLUMN radiology_delivery_date DATETIME")
            conn.commit()
            added_columns.append('radiology_delivery_date')
            print("SUCCESS: Added column radiology_delivery_date")
        else:
            print("INFO: Column radiology_delivery_date already exists")
        
        # إنشاء فهارس للأعمدة الجديدة
        if added_columns:
            for col in added_columns:
                try:
                    index_name = f"ix_reports_{col}"
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON reports ({col})")
                    conn.commit()
                    print(f"SUCCESS: Created index {index_name}")
                except Exception as idx_error:
                    print(f"WARNING: Could not create index for {col}: {idx_error}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: Failed to add columns: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import sys
    import io
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print("=" * 50)
    print("Starting to add missing columns...")
    print("=" * 50)
    
    if add_missing_columns():
        print("=" * 50)
        print("SUCCESS: Update completed successfully")
        print("=" * 50)
        sys.exit(0)
    else:
        print("=" * 50)
        print("ERROR: Update failed")
        print("=" * 50)
        sys.exit(1)

