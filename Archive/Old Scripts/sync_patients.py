#!/usr/bin/env python3
# سكريبت مزامنة أسماء المرضى من قاعدة البيانات إلى الملف

from db.session import SessionLocal
from db.models import Patient

print("🔄 مزامنة أسماء المرضى...")

s = SessionLocal()

# جلب جميع الأسماء من قاعدة البيانات
patients = s.query(Patient).order_by(Patient.full_name).all()
names = [p.full_name for p in patients if p.full_name]

print(f"📊 عدد الأسماء في قاعدة البيانات: {len(names)}")

# حفظ في الملف
with open('data/patient_names.txt', 'w', encoding='utf-8') as f:
    f.write("# أسماء المرضى\n")
    for name in names:
        f.write(f"{name}\n")

print(f"✅ تم حفظ {len(names)} اسم في الملف")

# عرض الأسماء
print("\n📋 قائمة الأسماء:")
for i, name in enumerate(names, 1):
    print(f"{i}. {name}")

s.close()

