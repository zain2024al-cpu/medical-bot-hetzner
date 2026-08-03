# -*- coding: utf-8 -*-
"""Backfill: يملأ الأعمدة المخصصة الجديدة (operation_details, operation_name_en,
success_rate, benefit_rate, admission_reason, admission_summary, therapy_details,
device_details, admission_notes, admission_type) للتقارير القديمة التي نُشرت قبل
توحيد سجل الحقول (field_registry.py) — حيث كانت هذه الحقول تُخزَّن فقط داخل نص
Report.doctor_decision المركّب، بلا عمود مستقل.

منذ هذا التعديل، save_report_to_database() و save_edit_to_database()
(bot/handlers/user/user_reports_edit.py) يكتبان مباشرة إلى هذه الأعمدة، وشاشة
التعديل بعد النشر (handle_report_selection) تقرأ منها أولاً — نص doctor_decision
يبقى fallback فقط للتقارير القديمة غير المُرحَّلة. هذا السكربت يُرحِّل التقارير
القديمة فعلياً حتى لا تبقى معتمدة على استخراج النص فقط (خطوة إلزامية قبل حذف
كود الاستخراج القديم — بدونها تُفقَد قابلية تعديل هذه الحقول للتقارير القديمة).

يستخدم نفس منطق الاستخراج الموجود في handle_report_selection/handle_republish
(bot/handlers/user/user_reports_edit.py) — نفس العلامات النصية بالضبط.

الاستخدام:
    venv/bin/python scripts/backfill_legacy_report_fields.py            # معاينة
    venv/bin/python scripts/backfill_legacy_report_fields.py --apply    # تنفيذ

خذ نسخة احتياطية من قاعدة البيانات قبل --apply. السكربت لا يكتب فوق أي قيمة
موجودة فعلاً في العمود المخصص (يتخطى أي تقرير مُرحَّل بالفعل أو جديد).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal, init_database
from db.models import Report

# نفس الأعمدة المستهدَفة لكل نوع إجراء — يجب أن تبقى فارغة (None/"") في العمود
# لتُعتبر "غير مُرحَّلة بعد" ويُحاوَل استخراجها من doctor_decision.
_TARGET_COLUMNS_BY_ACTION = {
    'عملية': ('operation_details', 'operation_name_en'),
    'خروج من المستشفى': ('admission_summary', 'operation_details', 'operation_name_en'),
    'خروج': ('admission_summary', 'operation_details', 'operation_name_en'),
    'علاج طبيعي': ('therapy_details',),
    'علاج طبيعي وإعادة تأهيل': ('therapy_details',),
    'أجهزة تعويضية': ('device_details',),
    'ترقيد': ('admission_reason',),
    'استشارة مع قرار عملية': ('operation_name_en', 'success_rate', 'benefit_rate'),
    'طوارئ': ('admission_notes', 'admission_type', 'operation_details'),
}


def _extract(report) -> dict:
    """نفس منطق الاستخراج من doctor_decision في handle_report_selection/
    handle_republish (user_reports_edit.py) — مُكرَّر عمداً هنا (سكربت
    مستقل لمرة واحدة، لا يستحق ربطه ببنية المحادثة الحية)."""
    dd = report.doctor_decision or ""
    action = (report.medical_action or "").strip()
    out = {}

    if action == 'عملية':
        if 'تفاصيل العملية:' in dd:
            rest = dd.split('تفاصيل العملية:', 1)[1]
            if 'اسم العملية بالإنجليزي:' in rest:
                out['operation_details'] = rest.split('اسم العملية بالإنجليزي:')[0].strip()
                rest2 = rest.split('اسم العملية بالإنجليزي:', 1)[1]
                if 'ملاحظات:' in rest2:
                    out['operation_name_en'] = rest2.split('ملاحظات:')[0].strip()
                else:
                    out['operation_name_en'] = rest2.strip()
            else:
                out['operation_details'] = rest.strip()
        elif dd.strip():
            out['operation_details'] = dd.strip()

    elif action in ('خروج من المستشفى', 'خروج'):
        if 'ملخص الرقود:' in dd:
            rest = dd.split('ملخص الرقود:', 1)[1]
            if 'تفاصيل العملية:' in rest:
                out['admission_summary'] = rest.split('تفاصيل العملية:')[0].strip()
                rest2 = rest.split('تفاصيل العملية:', 1)[1]
                if 'اسم العملية بالإنجليزي:' in rest2:
                    out['operation_details'] = rest2.split('اسم العملية بالإنجليزي:')[0].strip()
                    out['operation_name_en'] = rest2.split('اسم العملية بالإنجليزي:', 1)[1].strip()
                else:
                    out['operation_details'] = rest2.strip()
            else:
                out['admission_summary'] = rest.strip()
        elif 'تفاصيل العملية:' in dd:
            rest = dd.split('تفاصيل العملية:', 1)[1]
            if 'اسم العملية بالإنجليزي:' in rest:
                out['operation_details'] = rest.split('اسم العملية بالإنجليزي:')[0].strip()
                out['operation_name_en'] = rest.split('اسم العملية بالإنجليزي:', 1)[1].strip()
            else:
                out['operation_details'] = rest.strip()

    elif action in ('علاج طبيعي', 'علاج طبيعي وإعادة تأهيل'):
        if 'تفاصيل جلسة العلاج الطبيعي:' in dd:
            out['therapy_details'] = dd.split('تفاصيل جلسة العلاج الطبيعي:', 1)[1].strip()
        elif 'تفاصيل الجلسة:' in dd:
            out['therapy_details'] = dd.split('تفاصيل الجلسة:', 1)[1].strip()
        elif dd.strip():
            out['therapy_details'] = dd.strip()

    elif action == 'أجهزة تعويضية':
        if 'تفاصيل الجهاز:' in dd:
            out['device_details'] = dd.split('تفاصيل الجهاز:', 1)[1].strip()
        elif dd.strip():
            out['device_details'] = dd.strip()

    elif action == 'ترقيد':
        if 'سبب الرقود:' in dd:
            rest = dd.split('سبب الرقود:', 1)[1]
            if 'رقم الغرفة:' in rest:
                out['admission_reason'] = rest.split('رقم الغرفة:')[0].strip()
            elif 'ملاحظات:' in rest:
                out['admission_reason'] = rest.split('ملاحظات:')[0].strip()
            else:
                out['admission_reason'] = rest.strip()
        elif dd.strip():
            out['admission_reason'] = dd.strip()
        elif report.complaint_text and report.complaint_text.strip():
            out['admission_reason'] = report.complaint_text.strip()

    elif action == 'استشارة مع قرار عملية':
        for section in dd.split('\n\n'):
            section = section.strip()
            if section.startswith('اسم العملية بالإنجليزي:'):
                out['operation_name_en'] = section.replace('اسم العملية بالإنجليزي:', '', 1).strip()
            elif section.startswith('نسبة نجاح العملية:'):
                out['success_rate'] = section.replace('نسبة نجاح العملية:', '', 1).strip()
            elif section.startswith('نسبة الاستفادة من العملية:'):
                out['benefit_rate'] = section.replace('نسبة الاستفادة من العملية:', '', 1).strip()

    elif action == 'طوارئ':
        if 'ملاحظات الرقود:' in dd:
            rest = dd.split('ملاحظات الرقود:', 1)[1]
            if 'نوع الترقيد:' in rest:
                out['admission_notes'] = rest.split('نوع الترقيد:')[0].strip()
                out['admission_type'] = rest.split('نوع الترقيد:', 1)[1].strip()
            else:
                out['admission_notes'] = rest.strip()
        if 'تفاصيل العملية:' in dd:
            out['operation_details'] = dd.split('تفاصيل العملية:', 1)[1].strip()

    # تنظيف: لا نُرجع قيماً فارغة أو "لا يوجد"
    return {k: v for k, v in out.items() if v and v not in ("لا يوجد", "غير محدد")}


def main() -> None:
    apply = "--apply" in sys.argv
    init_database()

    total_reports = 0
    total_fields = 0

    with SessionLocal() as s:
        actions = list(_TARGET_COLUMNS_BY_ACTION.keys())
        reports = (
            s.query(Report)
            .filter(Report.medical_action.in_(actions))
            .order_by(Report.id)
            .all()
        )

        for r in reports:
            target_cols = _TARGET_COLUMNS_BY_ACTION[(r.medical_action or "").strip()]
            # يبقى "غير مُرحَّل" فقط إن كانت كل الأعمدة المستهدَفة لهذا النوع فارغة بعد
            already_migrated = all(getattr(r, col, None) for col in target_cols)
            if already_migrated:
                continue

            extracted = _extract(r)
            if not extracted:
                continue

            changes = []
            for col, new_val in extracted.items():
                if col not in target_cols:
                    continue
                current = getattr(r, col, None)
                if current:  # لا نكتب فوق قيمة موجودة فعلاً (تقرير مُرحَّل جزئياً أو مُعدَّل يدوياً)
                    continue
                changes.append((col, new_val))
                if apply:
                    setattr(r, col, new_val)

            if changes:
                total_reports += 1
                total_fields += len(changes)
                preview = ", ".join(f"{c}={v[:40]!r}" for c, v in changes)
                print(f"[#{r.id}] {(r.patient_name or '')[:20]:20s} {r.medical_action:20s} → {preview}")

        if apply:
            s.commit()

    print(f"\nالمجموع: {total_reports} تقرير، {total_fields} حقل")
    if apply:
        print("✅ نُفِّذ الترحيل وحُفِظ.")
    else:
        print("ℹ️  معاينة فقط — لم يُعدَّل شيء. أعد التشغيل مع --apply للتنفيذ.")


if __name__ == "__main__":
    main()
