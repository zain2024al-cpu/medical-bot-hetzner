# -*- coding: utf-8 -*-
"""
حذف الاسمين المختصرين "ياسر" و"يحيى" من دليل المترجمين (جدول translators).

السبب: يلتبسان بالاسمين الصحيحين "ياسر ابو عمار" و"يحيى ابو حمزه"
فيحصل خلط عند اختيار المترجم في التقارير.

⚠️ أمان:
  • المطابقة **تامة** بعد إزالة المسافات — لن يُمَسّ أي اسم يحتوي
    الكلمة ضمنه ("ياسر ابو عمار" آمن تماماً).
  • الوضع الافتراضي **معاينة فقط** (لا يحذف شيئاً). للتنفيذ الفعلي
    أضف --apply.
  • التقارير القديمة لا تتأثر: Report.translator_name نص محفوظ
    بشكل مستقل، وحذف الاسم من الدليل يمنع اختياره مستقبلاً فقط.

الاستخدام على الخادم:
    python scripts/delete_short_translator_names.py            # معاينة
    python scripts/delete_short_translator_names.py --apply    # تنفيذ
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TARGETS = ["ياسر", "يحيى"]


def main() -> int:
    apply_changes = "--apply" in sys.argv

    from db.session import SessionLocal
    from db.models import TranslatorDirectory, Report

    with SessionLocal() as s:
        all_rows = s.query(TranslatorDirectory).all()

        exact = [r for r in all_rows if (r.name or "").strip() in TARGETS]
        similar = [
            r for r in all_rows
            if (r.name or "").strip() not in TARGETS
            and any(t in (r.name or "") for t in TARGETS)
        ]

        print("=" * 66)
        print("الأسماء المطابقة تماماً (ستُحذف):")
        if not exact:
            print("  — لا يوجد (ربما حُذفت مسبقاً)")
        for r in exact:
            cnt = (
                s.query(Report)
                .filter(Report.translator_name == (r.name or "").strip())
                .count()
            )
            real_id = "معرّف تيليجرام حقيقي" if (r.translator_id or 0) >= 100_000 else "رقم داخلي"
            print(f"  • {r.name!r}  | id={r.translator_id} ({real_id}) | تقارير باسمه: {cnt}")

        print()
        print("الأسماء المشابهة (لن تُمَسّ — للتأكيد فقط):")
        if not similar:
            print("  — لا يوجد")
        for r in similar:
            print(f"  ✓ {r.name!r}  | id={r.translator_id}")
        print("=" * 66)

        if not exact:
            print("لا شيء للحذف.")
            return 0

        if not apply_changes:
            print("🔍 معاينة فقط — لم يُحذف شيء.")
            print("   للتنفيذ: python scripts/delete_short_translator_names.py --apply")
            return 0

        for r in exact:
            s.delete(r)
        s.commit()
        print(f"🗑️ تم حذف {len(exact)} اسم من دليل المترجمين.")
        print("   أعد تشغيل البوت: pm2 restart medbot")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
