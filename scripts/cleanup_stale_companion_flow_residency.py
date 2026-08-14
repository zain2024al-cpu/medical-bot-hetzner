# -*- coding: utf-8 -*-
"""
تنظيف ملفات الإقامة اليتيمة المتبقية من الخلل القديم — كانت تُنشأ فوراً
عند إضافة اسم عبر "🤝 مريض جديد مع مرافقين" (قبل تأكيد "🛬 الوصول"
فعلياً)، بمصدر source='companion_flow' — أُزيل هذا الإنشاء المبكر
بالكامل من الكود (راجع MAINTENANCE_LOG.md (٣٣))، لكن الصفوف التي أُنشئت
قبل ذلك التاريخ تبقى في قاعدة البيانات.

✅ أمان: source='companion_flow' لم يعد يُكتَب من أي مكان في الكود الحالي
إطلاقاً (بحث كامل في المشروع يؤكّد ذلك) — أي صفّ بهذا المصدر هو بالضرورة
بقية من الخلل القديم، بصرف النظر عن وجود Patient مطابق له من عدمه.

الوضع الافتراضي **معاينة فقط**. للتنفيذ الفعلي أضف --apply.

الاستخدام على الخادم:
    python3 scripts/cleanup_stale_companion_flow_residency.py            # معاينة
    python3 scripts/cleanup_stale_companion_flow_residency.py --apply    # تنفيذ
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    apply_changes = "--apply" in sys.argv

    from db.session import SessionLocal
    from db.models import Patient, ResidencyProfile, ResidencyCompanion, ResidencyUpdate

    with SessionLocal() as s:
        profiles = (
            s.query(ResidencyProfile)
            .filter(ResidencyProfile.source == "companion_flow")
            .all()
        )

        if not profiles:
            print("لا توجد ملفات إقامة متبقية من الخلل القديم — لا شيء للتنظيف.")
            return 0

        print("=" * 70)
        print(f"ملفات الإقامة المتبقية من الخلل القديم ({len(profiles)}):")
        for pr in profiles:
            patient_exists = s.query(Patient).filter_by(full_name=pr.name).first() is not None
            comps = s.query(ResidencyCompanion).filter_by(profile_id=pr.id).all()
            print(
                f"  • id={pr.id}  name={pr.name!r}  status={pr.status!r}  "
                f"created_at={pr.created_at}  "
                f"Patient موجود={'نعم' if patient_exists else 'لا — يتيم بالكامل'}  "
                f"مرافقون={[c.name for c in comps]}"
            )
        print("=" * 70)

        if not apply_changes:
            print("🔍 معاينة فقط — لم يُحذف شيء.")
            print("   للتنفيذ: python3 scripts/cleanup_stale_companion_flow_residency.py --apply")
            return 0

        total_companions = 0
        for pr in profiles:
            comps = s.query(ResidencyCompanion).filter_by(profile_id=pr.id).all()
            total_companions += len(comps)
            s.query(ResidencyUpdate).filter_by(profile_id=pr.id).delete()
            s.query(ResidencyCompanion).filter_by(profile_id=pr.id).delete()
            s.delete(pr)

        s.commit()
        print(f"🗑️ تم حذف {len(profiles)} ملف إقامة قديم (+{total_companions} مرافق تابع لها).")
        print("   أعد تشغيل البوت: pm2 restart all")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
