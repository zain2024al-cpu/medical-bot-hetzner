#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import io
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from db.session import SessionLocal
from db.models import Patient, Hospital, Department, Doctor
from sqlalchemy import func

# استخدام قاعدة البيانات الجديدة
import sqlite3
old_db_path = "db/medical_reports.db"
new_db_path = "db/medical_reports_new.db"

if not os.path.exists(new_db_path):
    print(f"❌ الملف الجديد غير موجود: {new_db_path}")
    sys.exit(1)

# نسخ قاعدة البيانات الجديدة مؤقتاً للفحص
temp_db_path = "db/medical_reports_temp_check.db"
if os.path.exists(temp_db_path):
    os.remove(temp_db_path)

import shutil
shutil.copy2(new_db_path, temp_db_path)

# تغيير مسار قاعدة البيانات مؤقتاً
import db.session
original_db_path = db.session.DATABASE_PATH
db.session.DATABASE_PATH = temp_db_path

# إعادة إنشاء engine
from sqlalchemy import create_engine
db.session.engine = create_engine(f"sqlite:///{temp_db_path}", echo=False)
db.session.SessionLocal = db.session.sessionmaker(bind=db.session.engine)

print("=" * 50)
print("فحص قاعدة البيانات الجديدة من السيرفر")
print("=" * 50)
print()

file_size = os.path.getsize(new_db_path) / (1024 * 1024)
print(f"📊 حجم قاعدة البيانات: {file_size:.2f} MB")
print()

try:
    with SessionLocal() as session:
        patients_count = session.query(func.count(Patient.id)).scalar()
        print(f"👥 عدد المرضى: {patients_count}")
        
        hospitals_count = session.query(func.count(Hospital.id)).scalar()
        print(f"🏥 عدد المستشفيات: {hospitals_count}")
        
        if hospitals_count > 0:
            hospitals = session.query(Hospital).order_by(Hospital.name).all()
            print("   قائمة المستشفيات:")
            for h in hospitals:
                print(f"   - {h.name or 'بدون اسم'}")
        
        print()
        departments_count = session.query(func.count(Department.id)).scalar()
        print(f"🏢 عدد الأقسام: {departments_count}")
        
        doctors_count = session.query(func.count(Doctor.id)).scalar()
        print(f"👨‍⚕️ عدد الأطباء: {doctors_count}")
        
        print()
        print("=" * 50)
        
        if hospitals_count >= 38:
            print("✅ قاعدة البيانات محدثة! (38 مستشفى أو أكثر)")
        else:
            print(f"⚠️  قاعدة البيانات تحتوي على {hospitals_count} مستشفى فقط (متوقع 38)")
            
except Exception as e:
    print(f"❌ خطأ: {e}")
    import traceback
    traceback.print_exc()
finally:
    # استعادة المسار الأصلي
    db.session.DATABASE_PATH = original_db_path
    # حذف الملف المؤقت
    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)






