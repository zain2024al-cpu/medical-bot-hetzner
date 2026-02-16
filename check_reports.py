# -*- coding: utf-8 -*-
import sqlite3
import os
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

db_path = "db/medical_reports.db"

if os.path.exists(db_path):
    print("Database exists")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # عدد التقارير
    cursor.execute("SELECT COUNT(*) FROM reports")
    count = cursor.fetchone()[0]
    print(f"Total reports: {count}")
    
    # آخر تقرير
    cursor.execute("SELECT id, patient_name, created_at FROM reports ORDER BY created_at DESC LIMIT 1")
    last_report = cursor.fetchone()
    if last_report:
        print(f"Last report: ID={last_report[0]}, Patient={last_report[1]}, Date={last_report[2]}")
    
    conn.close()
else:
    print("Database NOT found")

