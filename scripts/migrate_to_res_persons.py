# -*- coding: utf-8 -*-
"""
هجرة لمرة واحدة: من مخطط "المرحلة الأولى" (res_profiles/res_companions
— ملف واحد لكل مريض، مرافقون بلا حالة مستقلة) إلى نظام دورة الحياة
الكامل (res_persons موحَّد، علاقة ذاتية parent_id، حالة مستقلة لكل شخص).

يقرأ كل صفّ موجود فعلاً في الجداول القديمة (إن وُجدت — قد تكون فارغة
تقريباً بما أن المرحلة الأولى نُشِرت للتو) وينسخه إلى res_persons:
  • المريض (res_profiles) → res_persons بـparent_id=None.
    submitted=True → status=SUBMITTED، وإلا WAITING_ARRIVAL.
  • كل مرافق (res_companions) → res_persons بـparent_id=<معرّف المريض
    الجديد>، بنفس حالة المريض المنسوخة إليه (لم يكن للمرافقين حالة
    مستقلة في المرحلة الأولى أصلاً).
ثم يُسقِط الجدولين القديمين.

الوضع الافتراضي **معاينة فقط**. للتنفيذ الفعلي أضف --apply.

الاستخدام على الخادم:
    venv/bin/python3 scripts/migrate_to_res_persons.py            # معاينة
    venv/bin/python3 scripts/migrate_to_res_persons.py --apply    # تنفيذ
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    apply_changes = "--apply" in sys.argv

    from db.session import engine
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    if "res_profiles" not in existing:
        print("لا يوجد جدول res_profiles قديم — لا شيء لهجرته.")
        return 0

    with engine.connect() as conn:
        old_profiles = conn.execute(text(
            "SELECT id, name, submitted FROM res_profiles"
        )).fetchall()
        old_companions = []
        if "res_companions" in existing:
            old_companions = conn.execute(text(
                "SELECT id, profile_id, name FROM res_companions"
            )).fetchall()

    print("=" * 66)
    print(f"مرضى في res_profiles القديم: {len(old_profiles)}")
    for row in old_profiles:
        print(f"  • id={row[0]}  name={row[1]!r}  submitted={row[2]!r}")
    print(f"مرافقون في res_companions القديم: {len(old_companions)}")
    for row in old_companions:
        print(f"  • id={row[0]}  profile_id={row[1]}  name={row[2]!r}")
    print("=" * 66)

    if not old_profiles and not old_companions:
        print("لا توجد بيانات فعلية للهجرة — سيُسقَط الجدولان القديمان فقط.")

    if not apply_changes:
        print("🔍 معاينة فقط — لم يُنقَل أو يُحذف شيء.")
        print("   للتنفيذ: python3 scripts/migrate_to_res_persons.py --apply")
        return 0

    from db.session import get_db
    from db.models import ResidencyPerson, ResidencyStatusLog

    id_map: dict[int, int] = {}
    migrated = 0
    with get_db() as db:
        for row in old_profiles:
            old_id, name, submitted = row[0], row[1], row[2]
            status = "SUBMITTED" if submitted else "WAITING_ARRIVAL"
            person = ResidencyPerson(name=name or "—", status=status)
            db.add(person)
            db.flush()
            id_map[old_id] = person.id
            db.add(ResidencyStatusLog(person_id=person.id, old_status="", new_status=status))
            migrated += 1

        for row in old_companions:
            _, old_profile_id, name = row[0], row[1], row[2]
            new_parent_id = id_map.get(old_profile_id)
            if not new_parent_id:
                continue
            parent = db.query(ResidencyPerson).filter_by(id=new_parent_id).first()
            status = parent.status if parent else "WAITING_ARRIVAL"
            comp = ResidencyPerson(name=name or "—", parent_id=new_parent_id, status=status)
            db.add(comp)
            db.flush()
            db.add(ResidencyStatusLog(person_id=comp.id, old_status="", new_status=status))
            migrated += 1

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE res_profiles"))
        if "res_companions" in existing:
            conn.execute(text("DROP TABLE res_companions"))
        conn.commit()

    print(f"✅ تم نقل {migrated} شخصاً إلى res_persons، وإسقاط الجدولين القديمين.")
    print("   أعد تشغيل البوت: pm2 restart all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
