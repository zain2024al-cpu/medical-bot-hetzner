#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص قاعدة البيانات المحلية
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import create_engine, text

db_path = "db/medical_reports.db"

if not os.path.exists(db_path):
    print(f"❌ قاعدة البيانات غير موجودة: {db_path}")
    exit(1)

# حجم الملف
size_kb = os.path.getsize(db_path) / 1024

print("=" * 70)
print("📊 فحص قاعدة البيانات المحلية")
print("=" * 70)
print(f"📁 المسار: {db_path}")
print(f"💾 الحجم: {size_kb:.2f} KB")

# الاتصال بقاعدة البيانات
engine = create_engine(f"sqlite:///{db_path}")

with engine.connect() as conn:
    # عدد المستخدمين
    users_result = conn.execute(text(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN is_approved=1 THEN 1 ELSE 0 END) as approved "
        "FROM users"
    )).fetchone()
    
    # عدد التقارير
    reports_result = conn.execute(text("SELECT COUNT(*) FROM reports")).fetchone()
    
    # عدد المستشفيات
    hospitals_result = conn.execute(text("SELECT COUNT(*) FROM hospitals")).fetchone()
    
    # عدد الأطباء
    doctors_result = conn.execute(text("SELECT COUNT(*) FROM doctors")).fetchone()
    
    # عدد المترجمين
    translators_result = conn.execute(text("SELECT COUNT(*) FROM translators")).fetchone()
    
    # عدد المرضى
    patients_result = conn.execute(text("SELECT COUNT(*) FROM patients")).fetchone()
    
    print("\n📊 إحصائيات قاعدة البيانات:")
    print("-" * 70)
    print(f"👥 المستخدمين:       {users_result[0]:>6} (منهم {users_result[1]} معتمد)")
    print(f"📄 التقارير:         {reports_result[0]:>6}")
    print(f"🏥 المستشفيات:       {hospitals_result[0]:>6}")
    print(f"👨‍⚕️ الأطباء:          {doctors_result[0]:>6}")
    print(f"🗣️ المترجمين:        {translators_result[0]:>6}")
    print(f"🤒 المرضى:           {patients_result[0]:>6}")
    
    # آخر 5 تقارير
    last_reports = conn.execute(text(
        "SELECT id, patient_name, medical_action, created_at "
        "FROM reports "
        "ORDER BY id DESC "
        "LIMIT 5"
    )).fetchall()
    
    print("\n📋 آخر 5 تقارير:")
    print("-" * 70)
    for r in last_reports:
        print(f"  #{r[0]:>4} | {r[1][:25]:<25} | {r[2][:20]:<20} | {r[3][:10]}")

print("\n" + "=" * 70)
print("✅ قاعدة البيانات تعمل بشكل صحيح!")
print("=" * 70)
