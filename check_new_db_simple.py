#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import os
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

new_db_path = "db/medical_reports_new.db"

if not os.path.exists(new_db_path):
    print(f"❌ الملف غير موجود: {new_db_path}")
    sys.exit(1)

print("=" * 50)
print("فحص قاعدة البيانات الجديدة من السيرفر")
print("=" * 50)
print()

file_size = os.path.getsize(new_db_path) / (1024 * 1024)
print(f"📊 حجم قاعدة البيانات: {file_size:.2f} MB")
print()

conn = sqlite3.connect(new_db_path)
cursor = conn.cursor()

try:
    # عدد المستشفيات
    cursor.execute("SELECT COUNT(*) FROM hospitals")
    hospitals_count = cursor.fetchone()[0]
    print(f"🏥 عدد المستشفيات: {hospitals_count}")
    
    if hospitals_count > 0:
        cursor.execute("SELECT name FROM hospitals ORDER BY name")
        hospitals = cursor.fetchall()
        print("   قائمة المستشفيات:")
        for h in hospitals:
            print(f"   - {h[0] or 'بدون اسم'}")
    
    print()
    
    # عدد المرضى
    cursor.execute("SELECT COUNT(*) FROM patients")
    patients_count = cursor.fetchone()[0]
    print(f"👥 عدد المرضى: {patients_count}")
    
    # عدد الأقسام
    cursor.execute("SELECT COUNT(*) FROM departments")
    departments_count = cursor.fetchone()[0]
    print(f"🏢 عدد الأقسام: {departments_count}")
    
    # عدد الأطباء
    cursor.execute("SELECT COUNT(*) FROM doctors")
    doctors_count = cursor.fetchone()[0]
    print(f"👨‍⚕️ عدد الأطباء: {doctors_count}")
    
    print()
    print("=" * 50)
    
    if hospitals_count >= 38:
        print("✅ قاعدة البيانات محدثة! (38 مستشفى أو أكثر)")
        print()
        print("يمكنك الآن استبدال قاعدة البيانات القديمة:")
        print("  1. أغلق البوت أو أي برنامج يستخدم قاعدة البيانات")
        print("  2. استبدل db\\medical_reports.db بـ db\\medical_reports_new.db")
    else:
        print(f"⚠️  قاعدة البيانات تحتوي على {hospitals_count} مستشفى فقط (متوقع 38)")
        
except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()






