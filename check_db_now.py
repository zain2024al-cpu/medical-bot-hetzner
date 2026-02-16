#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص سريع لقاعدة البيانات على السيرفر
"""

import subprocess
import sys
import tempfile
import os
import io

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SERVER_IP = "5.223.58.71"
BOT_USER = "botuser"
REMOTE_DB_PATH = "/home/botuser/medical-bot/db/medical_reports.db"
REMOTE_SCRIPT = "/tmp/check_db_quick.py"

# سكريبت Python للفحص السريع
check_script = f'''#!/usr/bin/env python3
import sqlite3
import sys

try:
    conn = sqlite3.connect('{REMOTE_DB_PATH}')
    cursor = conn.cursor()
    
    print("=" * 70)
    print("DATABASE CHECK RESULTS")
    print("=" * 70)
    print()
    
    # 1. Counts
    print("1. Record Counts:")
    print("-" * 70)
    tables = {{'reports': 'Reports', 'patients': 'Patients', 'hospitals': 'Hospitals', 
              'doctors': 'Doctors', 'translators': 'Translators'}}
    
    for table, name in tables.items():
        try:
            cursor.execute(f'SELECT COUNT(*) FROM {{table}}')
            count = cursor.fetchone()[0]
            print(f"   {{name:15s}}: {{count:5d}}")
        except:
            print(f"   {{name:15s}}: ERROR")
    
    print()
    print("=" * 70)
    
    # 2. Last 5 reports
    print("2. Last 5 Reports:")
    print("-" * 70)
    cursor.execute("""
        SELECT id, patient_name, medical_action, DATE(created_at)
        FROM reports 
        ORDER BY id DESC 
        LIMIT 5
    """)
    
    for r in cursor.fetchall():
        print(f"   ID {{r[0]:4d}} | {{r[1]:30s}} | {{r[2]:30s}} | {{r[3]}}")
    
    print()
    print("=" * 70)
    
    # 3. Medical action stats
    print("3. Medical Action Statistics:")
    print("-" * 70)
    cursor.execute("""
        SELECT medical_action, COUNT(*) as count
        FROM reports
        WHERE medical_action IS NOT NULL
        GROUP BY medical_action
        ORDER BY count DESC
        LIMIT 10
    """)
    
    for action, count in cursor.fetchall():
        print(f"   {{action:40s}}: {{count:4d}}")
    
    print()
    print("=" * 70)
    
    # 4. Check specific flow types
    print("4. Specific Flow Types:")
    print("-" * 70)
    
    # Radiation therapy
    cursor.execute("SELECT COUNT(*) FROM reports WHERE medical_action = 'جلسة إشعاعي'")
    rad_count = cursor.fetchone()[0]
    print(f"   Radiation Therapy: {{rad_count}}")
    
    # Periodic followup
    cursor.execute("SELECT COUNT(*) FROM reports WHERE medical_action = 'مراجعة / عودة دورية'")
    periodic_count = cursor.fetchone()[0]
    print(f"   Periodic Followup: {{periodic_count}}")
    
    # New consult
    cursor.execute("SELECT COUNT(*) FROM reports WHERE medical_action = 'استشارة جديدة'")
    consult_count = cursor.fetchone()[0]
    print(f"   New Consult: {{consult_count}}")
    
    print()
    print("=" * 70)
    
    # 5. Data integrity
    print("5. Data Integrity:")
    print("-" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE medical_action IS NULL")
    null_action = cursor.fetchone()[0]
    print(f"   Reports without medical_action: {{null_action}}")
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE patient_name IS NULL")
    null_patient = cursor.fetchone()[0]
    print(f"   Reports without patient_name: {{null_patient}}")
    
    print()
    print("=" * 70)
    print("CHECK COMPLETE!")
    print("=" * 70)
    
    conn.close()
    
except Exception as e:
    print(f"ERROR: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''

print("=" * 70)
print("DATABASE CHECK - ONLINE SERVER")
print("=" * 70)
print()
print(f"Server: {SERVER_IP}")
print(f"User: {BOT_USER}")
print(f"Database: {REMOTE_DB_PATH}")
print()

try:
    # Create temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(check_script)
        temp_script = f.name
    
    # Upload script
    print("Uploading check script...")
    upload_cmd = ["scp", "-o", "StrictHostKeyChecking=no", temp_script, 
                  f"{BOT_USER}@{SERVER_IP}:{REMOTE_SCRIPT}"]
    result = subprocess.run(upload_cmd, capture_output=True)
    
    if result.returncode != 0:
        print(f"ERROR uploading: {result.stderr.decode('utf-8', errors='ignore')}")
        sys.exit(1)
    
    print("Script uploaded successfully")
    print()
    
    # Run script
    print("Running check on server...")
    print("=" * 70)
    print()
    
    run_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", 
               f"{BOT_USER}@{SERVER_IP}", f"python3 {REMOTE_SCRIPT}"]
    result = subprocess.run(run_cmd, capture_output=True)
    
    # Display results
    if result.stdout:
        print(result.stdout.decode('utf-8', errors='ignore'))
    
    if result.stderr:
        print("WARNINGS/ERRORS:")
        print(result.stderr.decode('utf-8', errors='ignore'))
    
    # Cleanup
    os.unlink(temp_script)
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no",
                   f"{BOT_USER}@{SERVER_IP}", f"rm -f {REMOTE_SCRIPT}"], 
                   capture_output=True)
    
    print()
    print("=" * 70)
    print("CHECK COMPLETE!")
    print("=" * 70)
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print()
