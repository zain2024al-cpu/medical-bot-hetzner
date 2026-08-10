#!/usr/bin/env python3
"""
معالجة السجلات العالقة في شاشة "📋 التقارير المعلقة".

── لماذا تعلق أصلاً ───────────────────────────────────────────────────────────
ثلاثة أسباب مختلفة رُصِدت في الكود، لكلٍّ علاج مختلف:

  🅐 **يتيم — تقريره محذوف**: حذف التقرير (من المترجم أو الأدمن) لم يكن
     ينظّف سجله المعلَّق. الشاشة تقرأ نوع الفحص من `reports` عبر
     `report_id`، فيظهر الصف بـ«🩺 نوع الفحص: —» ويبقى للأبد — لا يمكن
     رفع مرفق لتقرير غير موجود فلا شيء يُغلقه. (أُصلح المصدر؛ هذا
     السكربت ينظّف ما تراكم قبل الإصلاح.)

  🅑 **مرفوع فعلاً لكنه لم يُغلَق**: الرفع عبر «🔍 بحث بلا قيود» كان
     مستثنى من تتبّع الإكمال، فالمرفقات محفوظة فعلاً في
     `medical_attachment_files` لكن السجل بقي `status='pending'`.
     (أُصلح المصدر أيضاً؛ هذا السكربت يُغلق ما علق سابقاً.)

  🅒 **معلَّق بحق**: لا مرفقات ولا حذف — ينتظر المترجم فعلاً. **لا يُمَسّ.**

⚠️ لا يحذف السكربت أي تقرير ولا أي مرفق — يعمل حصراً على جدول
`pending_reports` (سجلات المتابعة). التقارير والمرفقات لا تُمَسّ إطلاقاً.

── التشغيل ────────────────────────────────────────────────────────────────────
    venv/bin/python scripts/fix_stuck_pending_reports.py           # فحص فقط
    venv/bin/python scripts/fix_stuck_pending_reports.py --apply   # التنفيذ
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal                                  # noqa: E402
from db.models import PendingReport, Report, MedicalAttachmentFile    # noqa: E402


def main() -> int:
    apply = "--apply" in sys.argv

    orphans: list[tuple] = []      # 🅐 تقريره محذوف
    uploaded: list[tuple] = []     # 🅑 له مرفقات فعلية
    genuine: list[tuple] = []      # 🅒 معلَّق بحق

    with SessionLocal() as s:
        pending = (
            s.query(PendingReport)
            .filter(PendingReport.status == "pending")
            .order_by(PendingReport.created_at.asc())
            .all()
        )

        report_ids = [p.report_id for p in pending if p.report_id]
        existing_ids = set()
        if report_ids:
            existing_ids = {
                rid for (rid,) in
                s.query(Report.id).filter(Report.id.in_(report_ids)).all()
            }

        attach_counts: dict[int, int] = {}
        if report_ids:
            from sqlalchemy import func
            for rid, cnt in (
                s.query(MedicalAttachmentFile.report_id, func.count(MedicalAttachmentFile.id))
                .filter(MedicalAttachmentFile.report_id.in_(report_ids))
                .group_by(MedicalAttachmentFile.report_id)
                .all()
            ):
                attach_counts[rid] = cnt

        for p in pending:
            days = (datetime.utcnow() - p.created_at).days if p.created_at else 0
            row = (p.id, p.report_id, p.patient_name, p.translator_name, days)
            if p.report_id and p.report_id not in existing_ids:
                orphans.append(row)
            elif attach_counts.get(p.report_id, 0) > 0:
                uploaded.append(row + (attach_counts[p.report_id],))
            else:
                genuine.append(row)

    print("=" * 68)
    print("السجلات العالقة في شاشة التقارير المعلقة")
    print("=" * 68)
    print(f"الإجمالي بحالة pending: {len(orphans) + len(uploaded) + len(genuine)}")

    print(f"\n🅐 يتيم — تقريره محذوف: {len(orphans)}   ⇒ يُحذف سجل المتابعة")
    print("   (هذه التي تظهر لك بـ«🩺 نوع الفحص: —»)")
    for pid, rid, name, tr, days in orphans:
        print(f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  منذ {days} يوم")

    print(f"\n🅑 مرفوع فعلاً لكنه لم يُغلَق: {len(uploaded)}   ⇒ يُغلَق (completed)")
    for pid, rid, name, tr, days, n in uploaded:
        print(f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  {n} مرفق  منذ {days} يوم")

    print(f"\n🅒 معلَّق بحق — لا مرفقات ولا حذف: {len(genuine)}   ⇒ لا يُمَسّ")
    for pid, rid, name, tr, days in genuine:
        print(f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  منذ {days} يوم")

    if not apply:
        print("\n" + "=" * 68)
        print("وضع الفحص — لم يُغيَّر شيء.")
        print(f"التنفيذ سيحذف {len(orphans)} سجل متابعة يتيم ويُغلق {len(uploaded)}.")
        print("أعد التشغيل مع --apply للتنفيذ.")
        print("=" * 68)
        return 0

    with SessionLocal() as s:
        for pid, *_ in orphans:
            row = s.query(PendingReport).filter_by(id=pid).first()
            if row:
                s.delete(row)
        for pid, *_ in uploaded:
            row = s.query(PendingReport).filter_by(id=pid).first()
            if row:
                row.status = "completed"
                row.completed_at = datetime.utcnow()
                row.uploaded_count = max(int(row.uploaded_count or 0),
                                         int(row.expected_count or 1))
        s.commit()

    print("\n" + "=" * 68)
    print(f"✅ حُذِف {len(orphans)} سجل يتيم · أُغلق {len(uploaded)} سجل مرفوع.")
    print(f"بقي {len(genuine)} سجلاً معلَّقاً بحق — لم يُمَسّ.")
    print("افتح شاشة «التقارير المعلقة» واضغط 🔄 تحديث.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
