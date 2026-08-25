# services/report_groups.py
# مصدر الحقيقة الوحيد لـ«في أي مجموعة تعيش بطاقة هذا التقرير؟»
#
# ⚠️ لماذا هذا الملف موجود:
# `Report.group_message_id` يخزّن معرّف رسالة البطاقة، لكن **معرّفات
# الرسائل في تيليجرام مرتبطة بالمحادثة** — نفس الرقم يشير لرسالة مختلفة
# تماماً في كل مجموعة. وتقارير تشناي تُنشَر بطاقاتها في
# `CHENNAI_REPORTS_GROUP_ID` (عبر `target_group_id` في
# broadcast_service.broadcast_new_report) لا في المجموعة الرئيسة.
#
# ورغم ذلك كانت ثلاثة مواضع تستدعي `delete_message` / `edit_message_*`
# بـ`chat_id=REPORTS_GROUP_ID` الثابت مع معرّف رسالة قد يخصّ مجموعة
# تشناي:
#   • user_medical_attachments — تحديث زر البطاقة بعد رفع المرفقات
#   • user_reports_delete      — حذف البطاقة عند حذف التقرير
#   • user_reports_edit        — حذف البطاقة القديمة قبل نشر المعدَّلة
#
# النتيجة المرصودة في السجلّ: «Message can't be edited» لكل تقرير تشناي،
# فتبقى بطاقته في المجموعة معروضة بحالتها القديمة رغم اكتمال الرفع.
#
# 🔴 والأخطر أن الفشل ليس مضموناً: لو صادف أن الرقم نفسه يخصّ رسالة بوت
# قابلة للتعديل/الحذف في المجموعة الرئيسة، لتغيّرت أزرار **بطاقة تقرير
# آخر** — أو حُذفت — بلا أي خطأ يُسجَّل. هذا سبب توحيد الحلّ هنا بدل
# ترك ثلاث نسخ مستقلة.

import logging

logger = logging.getLogger(__name__)


def resolve_report_card_group_id(report_id) -> str | int | None:
    """مجموعة **بطاقة** التقرير — تشناي لمرضاها، وإلا المجموعة الرئيسة.

    تُشتَقّ من نوع مريض التقرير نفسه (لا من جلسة المستخدم) فتبقى صحيحة
    مهما تأخّر التعديل/الحذف عن وقت النشر.

    ترجع `None` إن لم تُضبَط المجموعة أصلاً — يتحقّق المستدعي قبل النداء.
    """
    from config.settings import REPORTS_GROUP_ID

    if not report_id:
        return REPORTS_GROUP_ID or None
    try:
        from db.session import SessionLocal
        from db.models import Report, Patient
        from config.settings import CHENNAI_REPORTS_GROUP_ID

        with SessionLocal() as s:
            rep = s.query(Report).filter_by(id=report_id).first()
            if rep is not None and rep.patient_id:
                pat = s.query(Patient).filter_by(id=rep.patient_id).first()
                if pat is not None and (getattr(pat, "patient_type", None) or "") == "chennai":
                    return CHENNAI_REPORTS_GROUP_ID or REPORTS_GROUP_ID or None
    except Exception as exc:
        # السقوط للمجموعة الرئيسة هو السلوك السابق — لا نُسقِط العملية
        logger.warning(f"⚠️ resolve_report_card_group_id({report_id}) failed: {exc}")
    return REPORTS_GROUP_ID or None
