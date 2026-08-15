# -*- coding: utf-8 -*-
"""
إسقاط جداول الإقامة القديمة (المخطط السابق للإعادة الكاملة للبناء
2026-08-15) — res_profiles، res_companions، res_updates، res_missing_items.

⚠️ لا تُشغِّل هذا إلا بعد التأكد من وجود نسخة احتياطية حديثة (خُذت فعلاً
عبر create_backup قبل هذا التغيير). بعد الإسقاط، ستُنشَأ نسخة جديدة من
res_profiles/res_companions بمخطط مبسَّط تلقائياً عند إقلاع البوت
القادم (Base.metadata.create_all لا يُعدِّل جدولاً موجوداً — الإسقاط
ضروري ليُنشَأ الجدول بالشكل الجديد).

الوضع الافتراضي **معاينة فقط**. للتنفيذ الفعلي أضف --apply.

الاستخدام على الخادم:
    venv/bin/python3 scripts/drop_old_residency_tables.py            # معاينة
    venv/bin/python3 scripts/drop_old_residency_tables.py --apply    # تنفيذ
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OLD_TABLES = ["res_profiles", "res_companions", "res_updates", "res_missing_items"]


def main() -> int:
    apply_changes = "--apply" in sys.argv

    from db.session import engine
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    print("=" * 66)
    for t in OLD_TABLES:
        if t in existing:
            with engine.connect() as conn:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"  • {t}  ({count} صفّاً)")
        else:
            print(f"  • {t}  (غير موجود أصلاً)")
    print("=" * 66)

    if not apply_changes:
        print("🔍 معاينة فقط — لم يُحذف شيء.")
        print("   للتنفيذ: python3 scripts/drop_old_residency_tables.py --apply")
        return 0

    with engine.connect() as conn:
        for t in OLD_TABLES:
            if t in existing:
                conn.execute(text(f"DROP TABLE {t}"))
                print(f"🗑️ تم إسقاط الجدول: {t}")
        conn.commit()

    print("✅ تم — أعد تشغيل البوت الآن ليُنشئ res_profiles/res_companions بالمخطط الجديد:")
    print("   pm2 restart all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
