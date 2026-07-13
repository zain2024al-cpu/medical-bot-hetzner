#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سكريبت للتحقق من قاعدة البيانات بعد جلبها من السيرفر
"""

import os
import sys
import io
from pathlib import Path

# إصلاح مشكلة الترميز في Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# إضافة المسار الحالي إلى Python path
sys.path.insert(0, str(Path(__file__).parent))

from db.session import SessionLocal
from db.models import Patient, Hospital, Department, Doctor
from sqlalchemy import func

def check_database():
    """التحقق من قاعدة البيانات"""
    
    db_path = "db/medical_reports.db"
    
    if not os.path.exists(db_path):
        print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
        return False
    
    file_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
    print(f"📊 حجم قاعدة البيانات: {file_size:.2f} MB")
    print()
    
    try:
        with SessionLocal() as session:
            # التحقق من المرضى
            patients_count = session.query(func.count(Patient.id)).scalar()
            print(f"👥 عدد المرضى: {patients_count}")
            
            if patients_count > 0:
                # عرض أول 5 مرضى
                patients = session.query(Patient).limit(5).all()
                print("   أمثلة:")
                for p in patients:
                    print(f"   - {p.full_name or 'بدون اسم'}")
            
            print()
            
            # التحقق من المستشفيات
            hospitals_count = session.query(func.count(Hospital.id)).scalar()
            print(f"🏥 عدد المستشفيات: {hospitals_count}")
            
            if hospitals_count > 0:
                # عرض أول 5 مستشفيات
                hospitals = session.query(Hospital).limit(5).all()
                print("   أمثلة:")
                for h in hospitals:
                    print(f"   - {h.name or 'بدون اسم'}")
            
            print()
            
            # التحقق من الأقسام
            departments_count = session.query(func.count(Department.id)).scalar()
            print(f"🏢 عدد الأقسام: {departments_count}")
            
            if departments_count > 0:
                # عرض أول 5 أقسام
                departments = session.query(Department).limit(5).all()
                print("   أمثلة:")
                for d in departments:
                    print(f"   - {d.name or 'بدون اسم'} ({d.hospital_name or 'بدون مستشفى'})")
            
            print()
            
            # التحقق من الأطباء
            doctors_count = session.query(func.count(Doctor.id)).scalar()
            print(f"👨‍⚕️ عدد الأطباء: {doctors_count}")
            
            if doctors_count > 0:
                # عرض أول 5 أطباء
                doctors = session.query(Doctor).limit(5).all()
                print("   أمثلة:")
                for d in doctors:
                    hospital_name = "بدون مستشفى"
                    if d.hospital_id:
                        hospital = session.query(Hospital).filter(Hospital.id == d.hospital_id).first()
                        if hospital:
                            hospital_name = hospital.name or "بدون اسم"
                    print(f"   - {d.name or 'بدون اسم'} ({hospital_name})")
            
            print()
            print("=" * 50)
            
            if patients_count == 0 and hospitals_count == 0:
                print("⚠️  تحذير: قاعدة البيانات فارغة أو لم يتم تحديثها بعد")
                print("   تأكد من جلب قاعدة البيانات من السيرفر")
                return False
            else:
                print("✅ قاعدة البيانات تحتوي على بيانات")
                return True
                
    except Exception as e:
        print(f"❌ خطأ في فحص قاعدة البيانات: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("فحص قاعدة البيانات بعد الجلب من السيرفر")
    print("=" * 50)
    print()
    
    check_database()

