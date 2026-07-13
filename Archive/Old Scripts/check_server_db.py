#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت للتحقق من عدد المستشفيات في السيرفر
"""

import subprocess
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SERVER_IP = "5.223.58.71"
BOT_USER = "botuser"
REMOTE_SCRIPT = "/tmp/check_hospitals_count.py"

# سكريبت Python للتحقق من عدد المستشفيات
check_script = '''import sqlite3
import sys
conn = sqlite3.connect('/home/botuser/medical-bot/db/medical_reports.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM hospitals')
count = cursor.fetchone()[0]
print(count)
conn.close()
'''

print("=" * 50)
print("التحقق من عدد المستشفيات في السيرفر")
print("=" * 50)
print()

# رفع السكريبت إلى السيرفر
print("1. رفع سكريبت التحقق إلى السيرفر...")
try:
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(check_script)
        temp_script = f.name
    
    upload_cmd = ["scp", temp_script, f"{BOT_USER}@{SERVER_IP}:{REMOTE_SCRIPT}"]
    subprocess.run(upload_cmd, check=True, capture_output=True)
    print("✅ تم رفع السكريبت")
    
    # تشغيل السكريبت على السيرفر
    print()
    print("2. تشغيل السكريبت على السيرفر...")
    run_cmd = ["ssh", f"{BOT_USER}@{SERVER_IP}", f"python3 {REMOTE_SCRIPT}"]
    result = subprocess.run(run_cmd, check=True, capture_output=True, text=True)
    
    hospitals_count = int(result.stdout.strip())
    
    print()
    print("=" * 50)
    print(f"🏥 عدد المستشفيات في السيرفر: {hospitals_count}")
    print("=" * 50)
    
    # مقارنة مع قاعدة البيانات المحلية
    print()
    print("مقارنة مع قاعدة البيانات المحلية:")
    try:
        import sqlite3
        local_conn = sqlite3.connect("db/medical_reports.db")
        local_cursor = local_conn.cursor()
        local_cursor.execute("SELECT COUNT(*) FROM hospitals")
        local_count = local_cursor.fetchone()[0]
        local_conn.close()
        
        print(f"  - المحلية: {local_count} مستشفى")
        print(f"  - السيرفر: {hospitals_count} مستشفى")
        print()
        
        if local_count < hospitals_count:
            print("⚠️  قاعدة البيانات المحلية قديمة!")
            print(f"   الفرق: {hospitals_count - local_count} مستشفى")
            print()
            print("الحل: استخدم replace_database.py لاستبدال قاعدة البيانات")
        elif local_count > hospitals_count:
            print("⚠️  قاعدة البيانات المحلية أحدث من السيرفر!")
        else:
            print("✅ قاعدة البيانات المحلية محدثة")
            
    except Exception as e:
        print(f"⚠️  فشل فحص قاعدة البيانات المحلية: {e}")
    
    # تنظيف
    import os
    os.unlink(temp_script)
    subprocess.run(["ssh", f"{BOT_USER}@{SERVER_IP}", f"rm -f {REMOTE_SCRIPT}"], 
                   capture_output=True)
    
except subprocess.CalledProcessError as e:
    print(f"❌ خطأ: {e}")
    if e.stderr:
        print(f"الخطأ: {e.stderr}")
except Exception as e:
    print(f"❌ خطأ غير متوقع: {e}")
    import traceback
    traceback.print_exc()

print()
input("اضغط Enter للخروج...")






