#!/usr/bin/env python3
# سكريبت تحديث المستشفيات

from db.session import SessionLocal
from db.models import Hospital

# القائمة الجديدة - 41 مستشفى
hospitals_list = [
    "Silverline Diagnostics",
    "Manipal Hospital, Old Airport Road",
    "Manipal Hospital, Yelahanka",
    "Fortis Hospital, BG Road",
    "Sakra World Hospital",
    "Aster Whitefield Hospital",
    "M S Ramaiah Memorial Hospital",
    "Aster RV",
    "St. John's Medical College Hospital",
    "SPARSH Hospital, Hennur Road",
    "Sankara Eye Hospital",
    "KARE Prosthetics & Orthotics",
    "SPARSH Hospital, Infantry Road",
    "Apollo Hospital, BG",
    "L V Prasad Eye Institute, Hyderabad",
    "Narayana Hospital, Bommasandra",
    "Rainbow Children's Hospital, Marathahalli",
    "Bhagwan Mahaveer Jain Hospital",
    "Manipal Hospital - Millers Road",
    "Trilife Hospital",
    "Aster CMI",
    "NU Hospitals, Rajajinagar",
    "Zion Hospital",
    "Cura Hospital",
    "KIMS Hospital, Mahadevapura",
    "NU hospital padmanabhanagar",
    "Kiran Diagnostic Center",
    "Nueclear Diagnostics",
    "AIG Hospitals, Hyderabad",
    "BLK-Max Super Specialty Hospital, Delhi",
    "Max Super Speciality Hospital, Saket, Delhi",
    "Rainbow Children's Hospital, Delhi",
    "HCG Hospital K R Road",
    "Gleneagles Global Hospital, Kengeri",
    "Rela Hospital, Chennai",
    "Narayana Nethralaya, Bannerghatta",
    "Narayana Nethralaya Eye Hospital, Rajajinagar",
    "Narayana Nethralaya Bommasandra",
    "Manipal Hospital - Yeshwanthpur",
    "Manipal Hospital - Sarjapur Road",
    "Sankara Eye Hospital, Chennai"
]

print(f"🏥 تحديث قائمة المستشفيات...")
print(f"📊 عدد المستشفيات الجديدة: {len(hospitals_list)}")

s = SessionLocal()

# حذف جميع المستشفيات الحالية
old_count = s.query(Hospital).count()
print(f"🗑️ حذف {old_count} مستشفى قديم...")
s.query(Hospital).delete()
s.commit()

# إضافة القائمة الجديدة
print(f"➕ إضافة {len(hospitals_list)} مستشفى جديد...")
for name in hospitals_list:
    h = Hospital(name=name)
    s.add(h)
s.commit()

# التحقق
new_count = s.query(Hospital).count()
print(f"✅ تم! إجمالي المستشفيات: {new_count}")

s.close()

