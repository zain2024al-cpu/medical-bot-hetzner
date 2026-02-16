#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت شامل لفحص قاعدة البيانات على السيرفر
"""

import subprocess
import sys
import io
import tempfile
import os

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SERVER_IP = "5.223.58.71"
BOT_USER = "botuser"
REMOTE_DB_PATH = "/home/botuser/medical-bot/db/medical_reports.db"
REMOTE_SCRIPT = "/tmp/check_db_detailed.py"

# سكريبت Python للفحص الشامل
check_script = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import sys
from datetime import datetime

try:
    conn = sqlite3.connect('{REMOTE_DB_PATH}')
    cursor = conn.cursor()
    
    print("=" * 60)
    print("📊 فحص شامل لقاعدة البيانات")
    print("=" * 60)
    print()
    
    # 1. عدد السجلات في كل جدول
    print("1️⃣  عدد السجلات:")
    print("-" * 60)
    
    tables = ['reports', 'patients', 'hospitals', 'departments', 'doctors', 'translators', 'users']
    for table in tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM {{table}}')
            count = cursor.fetchone()[0]
            print(f"   📌 {{table:15s}}: {{count:5d}} سجل")
        except:
            print(f"   ❌ {{table:15s}}: الجدول غير موجود")
    
    print()
    print("=" * 60)
    
    # 2. فحص أعمدة جدول reports المهمة
    print("2️⃣  أعمدة جدول reports المهمة:")
    print("-" * 60)
    
    cursor.execute("PRAGMA table_info(reports)")
    columns = cursor.fetchall()
    important_cols = [
        'medical_action', 'radiation_therapy_type', 'radiation_therapy_session_number',
        'radiation_therapy_remaining', 'radiation_therapy_return_date', 
        'radiation_therapy_return_reason', 'followup_date', 'followup_reason'
    ]
    
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        if col_name in important_cols:
            print(f"   ✅ {{col_name:35s}}: {{col_type}}")
    
    print()
    print("=" * 60)
    
    # 3. آخر 5 تقارير
    print("3️⃣  آخر 5 تقارير:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT id, patient_name, medical_action, 
               DATE(created_at) as date
        FROM reports 
        ORDER BY id DESC 
        LIMIT 5
    """)
    
    reports = cursor.fetchall()
    for r in reports:
        print(f"   📄 ID: {{r[0]:4d}} | {{r[1]:30s}} | {{r[2]:25s}} | {{r[3]}}")
    
    print()
    print("=" * 60)
    
    # 4. إحصائيات أنواع الإجراءات
    print("4️⃣  إحصائيات أنواع الإجراءات:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT medical_action, COUNT(*) as count
        FROM reports
        GROUP BY medical_action
        ORDER BY count DESC
    """)
    
    actions = cursor.fetchall()
    for action in actions:
        if action[0]:
            print(f"   📊 {{action[0]:30s}}: {{action[1]:4d}} تقرير")
    
    print()
    print("=" * 60)
    
    # 5. فحص تقارير جلسة إشعاعي
    print("5️⃣  تقارير جلسة إشعاعي:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM reports 
        WHERE medical_action = 'جلسة إشعاعي'
    """)
    
    radiation_count = cursor.fetchone()[0]
    print(f"   📌 عدد تقارير جلسة إشعاعي: {{radiation_count}}")
    
    if radiation_count > 0:
        cursor.execute("""
            SELECT id, patient_name, radiation_therapy_type, 
                   radiation_therapy_session_number
            FROM reports 
            WHERE medical_action = 'جلسة إشعاعي'
            ORDER BY id DESC
            LIMIT 3
        """)
        
        rad_reports = cursor.fetchall()
        print()
        print("   آخر 3 تقارير جلسة إشعاعي:")
        for r in rad_reports:
            print(f"     • ID: {{r[0]:4d}} | {{r[1]:25s}} | {{r[2] or 'غير محدد':15s}} | الجلسة: {{r[3] or 'N/A'}}")
    
    print()
    print("=" * 60)
    
    # 6. فحص تقارير مراجعة دورية
    print("6️⃣  تقارير مراجعة / عودة دورية:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT COUNT(*) 
        FROM reports 
        WHERE medical_action = 'مراجعة / عودة دورية'
    """)
    
    periodic_count = cursor.fetchone()[0]
    print(f"   📌 عدد تقارير مراجعة / عودة دورية: {{periodic_count}}")
    
    if periodic_count > 0:
        cursor.execute("""
            SELECT id, patient_name, followup_date, followup_reason
            FROM reports 
            WHERE medical_action = 'مراجعة / عودة دورية'
            ORDER BY id DESC
            LIMIT 3
        """)
        
        periodic_reports = cursor.fetchall()
        print()
        print("   آخر 3 تقارير مراجعة / عودة دورية:")
        for r in periodic_reports:
            print(f"     • ID: {{r[0]:4d}} | {{r[1]:25s}} | {{r[2] or 'غير محدد':15s}}")
    
    print()
    print("=" * 60)
    
    # 7. فحص صحة البيانات
    print("7️⃣  فحص صحة البيانات:")
    print("-" * 60)
    
    # تقارير بدون نوع إجراء
    cursor.execute("SELECT COUNT(*) FROM reports WHERE medical_action IS NULL OR medical_action = ''")
    null_action = cursor.fetchone()[0]
    if null_action > 0:
        print(f"   ⚠️  {{null_action}} تقرير بدون نوع إجراء")
    else:
        print(f"   ✅ جميع التقارير لديها نوع إجراء")
    
    # تقارير بدون اسم مريض
    cursor.execute("SELECT COUNT(*) FROM reports WHERE patient_name IS NULL OR patient_name = ''")
    null_patient = cursor.fetchone()[0]
    if null_patient > 0:
        print(f"   ⚠️  {{null_patient}} تقرير بدون اسم مريض")
    else:
        print(f"   ✅ جميع التقارير لديها اسم مريض")
    
    # تقارير بدون مستشفى
    cursor.execute("SELECT COUNT(*) FROM reports WHERE hospital_name IS NULL OR hospital_name = ''")
    null_hospital = cursor.fetchone()[0]
    if null_hospital > 0:
        print(f"   ⚠️  {{null_hospital}} تقرير بدون مستشفى")
    else:
        print(f"   ✅ جميع التقارير لديها مستشفى")
    
    print()
    print("=" * 60)
    print("✅ الفحص مكتمل!")
    print("=" * 60)
    
    conn.close()
    
except Exception as e:
    print(f"❌ خطأ: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''

print("=" * 70)
print("🔍 فحص شامل لقاعدة البيانات على السيرفر")
print("=" * 70)
print()
print(f"🌐 السيرفر: {SERVER_IP}")
print(f"👤 المستخدم: {BOT_USER}")
print(f"📁 قاعدة البيانات: {REMOTE_DB_PATH}")
print()
print("⏳ جاري التحقق...")
print()

try:
    # 1. إنشاء ملف مؤقت
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(check_script)
        temp_script = f.name
    
    # 2. رفع السكريبت
    print("📤 رفع سكريبت الفحص إلى السيرفر...")
    upload_cmd = ["scp", "-o", "StrictHostKeyChecking=no", temp_script, 
                  f"{BOT_USER}@{SERVER_IP}:{REMOTE_SCRIPT}"]
    result = subprocess.run(upload_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ فشل رفع السكريبت: {result.stderr}")
        sys.exit(1)
    
    print("✅ تم رفع السكريبت")
    print()
    
    # 3. تشغيل السكريبت
    print("🚀 تشغيل الفحص على السيرفر...")
    print("=" * 70)
    print()
    
    run_cmd = ["ssh", "-o", "StrictHostKeyChecking=no", 
               f"{BOT_USER}@{SERVER_IP}", f"python3 {REMOTE_SCRIPT}"]
    result = subprocess.run(run_cmd, capture_output=True, text=True)
    
    # عرض النتائج
    if result.stdout:
        print(result.stdout)
    
    if result.stderr:
        print("⚠️  تحذيرات/أخطاء:")
        print(result.stderr)
    
    # 4. تنظيف
    os.unlink(temp_script)
    subprocess.run(["ssh", "-o", "StrictHostKeyChecking=no",
                   f"{BOT_USER}@{SERVER_IP}", f"rm -f {REMOTE_SCRIPT}"], 
                   capture_output=True)
    
    print()
    print("=" * 70)
    print("✅ الفحص مكتمل!")
    print("=" * 70)
    
except subprocess.CalledProcessError as e:
    print(f"❌ خطأ في تنفيذ الأمر: {e}")
    if e.stderr:
        print(f"التفاصيل: {e.stderr}")
except Exception as e:
    print(f"❌ خطأ غير متوقع: {e}")
    import traceback
    traceback.print_exc()

print()
input("اضغط Enter للخروج...")
