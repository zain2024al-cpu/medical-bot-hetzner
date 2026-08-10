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

  🅑 **مرفوع ومكتمل العدد**: الرفع عبر «🔍 بحث بلا قيود» كان مستثنى من
     تتبّع الإكمال، فالمرفقات محفوظة فعلاً في `medical_attachment_files`
     لكن السجل بقي `status='pending'`. (أُصلح المصدر أيضاً؛ هذا السكربت
     يُغلق ما علق سابقاً.)

  🅓 **مرفوع جزئياً — لا يُمَسّ**: له مرفقات، لكن `expected_count > 1`
     و`uploaded_count` لم يبلغه بعد. ⚠️ **وجود مرفق لا يعني الاكتمال**:
     حالة تنتظر 3 فحوصات قد يكون وصل منها واحد. إغلاقها قسراً يُخفي حالة
     **ناقصة فعلاً** — وهو بالضبط ما بُنيت آلية expected_count لمنعه.
     تُعرَض بتقدّمها (uploaded/expected) لقرارك أنت.

  🅒 **معلَّق بحق**: لا مرفقات ولا حذف — ينتظر المترجم فعلاً. **لا يُمَسّ.**

⚠️ لا يحذف السكربت أي تقرير ولا أي مرفق — يعمل حصراً على جدول
`pending_reports` (سجلات المتابعة). التقارير والمرفقات لا تُمَسّ إطلاقاً.

── التشغيل ────────────────────────────────────────────────────────────────────
    fix_stuck_pending_reports.py                    # فحص
    fix_stuck_pending_reports.py --apply            # حذف اليتيم + إغلاق المكتمل
    fix_stuck_pending_reports.py --reconcile        # فحص تصحيح العدّاد
    fix_stuck_pending_reports.py --reconcile --apply  # تنفيذ تصحيح العدّاد

`--reconcile` يختار العملية و`--apply` ينفّذها؛ فالتشغيل بلا `--apply`
معاينة آمنة دائماً مهما كانت العملية.

⚠️ `--reconcile` عملية **منفصلة تماماً** عن `--apply`، وتمسّ الفئة 🅓 وحدها:
تضبط `uploaded_count` على عدد المرفقات الفعلية (بحدّ أقصى `expected_count`)
**بلا إغلاق أي سجل**. سببها أن العدّاد نفسه أفسده العطب: سجل له مرفق واحد
قد يقرأ `0/2` لأن `increment_pending_upload` لم تُستدعَ أصلاً في مسار البحث
المفتوح — فلو رفع المترجم الفحص الناقص لاحقاً لصار `1/2` وبقي معلَّقاً رغم
اكتماله فعلياً. التصحيح يُعيد العدّاد للواقع فتُغلَق الحالة تلقائياً وبشكل
صحيح عند رفع الباقي.

⚠️ **وهو تقدير لا يقين**: عدد الملفات ≠ عدد الفحوصات بالضرورة (ملف PDF واحد
قد يضمّ فحصين). لذلك لا يُغلق السكربت شيئاً هنا؛ إن بلغ العدّاد
`expected_count` بعد التصحيح سيظهر السجل في الفئة 🅑 عند الفحص التالي
**لقرارك أنت**، لا إغلاقاً صامتاً.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal                                  # noqa: E402
from db.models import PendingReport, Report, MedicalAttachmentFile    # noqa: E402


def main() -> int:
    apply = "--apply" in sys.argv
    reconcile = "--reconcile" in sys.argv

    # `--reconcile` يختار العملية، و`--apply` ينفّذها — كما في بقية السكربت:
    # التشغيل بلا `--apply` معاينة آمنة دائماً، مهما كانت العملية.

    orphans: list[tuple] = []      # 🅐 تقريره محذوف
    uploaded: list[tuple] = []     # 🅑 مرفوع ومكتمل العدد
    partial: list[tuple] = []      # 🅓 مرفوع جزئياً — يحتاج حكمك
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

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        for p in pending:
            days = (now_utc - p.created_at).days if p.created_at else 0
            exp = max(1, int(p.expected_count or 1))
            up = int(p.uploaded_count or 0)
            row = (p.id, p.report_id, p.patient_name, p.translator_name, days)
            n_files = attach_counts.get(p.report_id, 0)

            if p.report_id and p.report_id not in existing_ids:
                orphans.append(row)
            elif n_files > 0:
                # ⚠️ وجود مرفقات لا يعني الاكتمال دائماً: حالة تنتظر عدة
                # فحوصات (expected_count > 1) قد يكون وصل منها واحد فقط.
                # إغلاقها قسراً يُخفي حالة **ناقصة فعلاً** — وهو بالضبط ما
                # بُنيت آلية expected_count/uploaded_count لمنعه. تُفصَل هنا
                # لقرار بشري بدل إغلاق أعمى.
                if exp <= 1 or up >= exp:
                    uploaded.append(row + (n_files, up, exp))
                else:
                    partial.append(row + (n_files, up, exp))
            else:
                genuine.append(row)

    print("=" * 68)
    print("السجلات العالقة في شاشة التقارير المعلقة")
    print("=" * 68)
    print(f"الإجمالي بحالة pending: "
          f"{len(orphans) + len(uploaded) + len(partial) + len(genuine)}")

    print(f"\n🅐 يتيم — تقريره محذوف: {len(orphans)}   ⇒ يُحذف سجل المتابعة")
    print("   (هذه التي تظهر لك بـ«🩺 نوع الفحص: —»)")
    for pid, rid, name, tr, days in orphans:
        print(f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  منذ {days} يوم")

    print(f"\n🅑 مرفوع ومكتمل العدد: {len(uploaded)}   ⇒ يُغلَق (completed)")
    for pid, rid, name, tr, days, n, up, exp in uploaded:
        print(f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  "
              f"{n} مرفق  التقدّم {up}/{exp}  منذ {days} يوم")

    _p_action = "⇒ يُصحَّح العدّاد فقط" if reconcile else "⇒ ⚠️ لا يُمَسّ"
    print(f"\n🅓 مرفوع **جزئياً**: {len(partial)}   {_p_action}")
    if partial and not reconcile:
        print("   له مرفقات لكن عدد الفحوصات المنتظَرة لم يكتمل بعد —")
        print("   إغلاقه قسراً يُخفي حالة ناقصة فعلاً. راجعها يدوياً.")
    for pid, rid, name, tr, days, n, up, exp in partial:
        line = (f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  "
                f"{n} مرفق  التقدّم {up}/{exp}  منذ {days} يوم")
        if reconcile:
            new_up = min(n, exp)
            line += f"   ← سيصير {new_up}/{exp}" if new_up != up else "   (لا تغيير)"
        print(line)

    print(f"\n🅒 معلَّق بحق — لا مرفقات ولا حذف: {len(genuine)}   ⇒ لا يُمَسّ")
    for pid, rid, name, tr, days in genuine:
        print(f"     pending#{pid}  report#{rid}  {name}  (مترجم: {tr})  منذ {days} يوم")

    if reconcile:
        # يمسّ الفئة 🅓 وحدها: العدّاد فقط، بلا إغلاق وبلا حذف.
        changes = [(pid, up, min(n, exp), exp)
                   for pid, _rid, _nm, _tr, _d, n, up, exp in partial
                   if min(n, exp) != up]
        print("\n" + "=" * 68)
        if not changes:
            print("لا عدّاد يحتاج تصحيحاً — كلها مطابقة لعدد المرفقات أصلاً.")
            print("=" * 68)
            return 0

        if not apply:
            print("وضع الفحص — لم يُغيَّر شيء.")
            print(f"التنفيذ سيصحّح عدّاد {len(changes)} سجل، بلا إغلاق أي سجل.")
            print("أعد التشغيل مع --reconcile --apply للتنفيذ.")
            print("=" * 68)
            return 0

        with SessionLocal() as s:
            for pid, _old, new_up, _exp in changes:
                row = s.query(PendingReport).filter_by(id=pid).first()
                if row:
                    row.uploaded_count = new_up
            s.commit()

        print(f"✅ صُحِّح عدّاد {len(changes)} سجل — بلا إغلاق أي سجل.")
        for pid, old, new_up, exp in changes:
            print(f"     pending#{pid}:  {old}/{exp}  ←  {new_up}/{exp}")

        reached = [c for c in changes if c[2] >= c[3]]
        if reached:
            print(f"\n⚠️ بلغ {len(reached)} منها العدد المتوقَّع، فسيظهر في الفئة 🅑")
            print("   عند الفحص التالي — **لقرارك**، لم يُغلَق الآن.")
        print("=" * 68)
        return 0

    if not apply:
        print("\n" + "=" * 68)
        print("وضع الفحص — لم يُغيَّر شيء.")
        print(f"التنفيذ سيحذف {len(orphans)} سجل متابعة يتيم ويُغلق {len(uploaded)}.")
        print(f"ولن يمسّ {len(partial)} جزئياً و{len(genuine)} معلَّقاً بحق.")
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
                row.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                row.uploaded_count = max(int(row.uploaded_count or 0),
                                         int(row.expected_count or 1))
        s.commit()

    print("\n" + "=" * 68)
    print(f"✅ حُذِف {len(orphans)} سجل يتيم · أُغلق {len(uploaded)} سجل مرفوع.")
    print(f"لم يُمَسّ: {len(partial)} جزئياً · {len(genuine)} معلَّقاً بحق.")
    print("افتح شاشة «التقارير المعلقة» واضغط 🔄 تحديث.")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
