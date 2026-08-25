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


def _first_id(raw) -> str | None:
    """أول معرّف من قيمة قد تحمل عدة معرّفات مفصولة بفواصل.

    ⚠️ `REPORTS_GROUP_ID` في بيئة التشغيل الحالية = "-100…388,-100…845"
    (مجموعتان). تمريرها كما هي لتيليجرام كـ`chat_id` **لا ينجح أبداً** —
    تُعامَل كمعرّف واحد خاطئ. لا يفصلها في المشروع سوى
    scripts/clear_group_reply_keyboard.py، وبقية المواضع تمرّرها خاماً.
    """
    raw = str(raw or "").strip()
    if not raw:
        return None
    first = raw.split(",")[0].strip()
    return first or None


def resolve_report_card_group_id(report_id) -> str | int | None:
    """المحادثة التي تعيش فيها **بطاقة** هذا التقرير.

    الترتيب:
      1. `Report.group_chat_id` المخزَّن وقت النشر — الحقيقة الفعلية، بلا
         تخمين. (يُملأ للتقارير الجديدة فقط.)
      2. تقرير تشناي ⇒ مجموعة تشناي.
      3. أول معرّف في `REPORTS_GROUP_ID` — للتقارير القديمة التي سبقت
         العمود الجديد.

    ترجع `None` إن تعذّر تحديد محادثة صالحة؛ يتحقّق المستدعي قبل النداء
    (تخطّي العملية أسلم من تنفيذها في المحادثة الخطأ).
    """
    from config.settings import REPORTS_GROUP_ID

    fallback = _first_id(REPORTS_GROUP_ID)
    if not report_id:
        return fallback
    try:
        from db.session import SessionLocal
        from db.models import Report, Patient
        from config.settings import CHENNAI_REPORTS_GROUP_ID

        with SessionLocal() as s:
            rep = s.query(Report).filter_by(id=report_id).first()
            if rep is None:
                return fallback

            # (1) المخزَّن وقت النشر — يتجاوز كل تخمين
            stored = _first_id(getattr(rep, "group_chat_id", None))
            if stored:
                return stored

            # (2) تشناي — تُشتَقّ من نوع المريض لا من جلسة المستخدم
            if rep.patient_id:
                pat = s.query(Patient).filter_by(id=rep.patient_id).first()
                if pat is not None and (getattr(pat, "patient_type", None) or "") == "chennai":
                    return _first_id(CHENNAI_REPORTS_GROUP_ID) or fallback
    except Exception as exc:
        logger.warning(f"⚠️ resolve_report_card_group_id({report_id}) failed: {exc}")
    return fallback
