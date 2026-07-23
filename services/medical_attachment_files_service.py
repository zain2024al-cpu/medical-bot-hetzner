# services/medical_attachment_files_service.py
"""
خدمة سجلات الملفات الطبية المرفقة بكل تقرير (medical_attachment_files)

وظائفها:
1. حفظ سجل ملف واحد بعد إرساله فعلياً لمجموعة الملفات
2. جلب كل الملفات المرتبطة بتقرير معين بترتيب الرفع
3. عدّ الملفات المرتبطة بتقرير معين (لعرض/إخفاء الزر)
"""

import logging
from datetime import datetime
from db.session import SessionLocal
from db.models import MedicalAttachmentFile, Report, Patient

logger = logging.getLogger(__name__)


def add_medical_attachment_file(
    report_id: int,
    file_id: str,
    file_type: str,
    file_name: str | None = None,
    uploaded_by: str | None = None,
    uploaded_by_tg_id: int | None = None,
    source: str = "creation",
    upload_order: int | None = None,
) -> bool:
    """إدراج سجل ملف طبي واحد. يُستدعى مرة واحدة لكل ملف تم إرساله فعلياً."""
    if not report_id or not file_id:
        return False
    try:
        with SessionLocal() as session:
            row = MedicalAttachmentFile(
                report_id=report_id,
                file_id=file_id,
                file_type=file_type,
                file_name=file_name,
                uploaded_by=uploaded_by,
                uploaded_by_tg_id=uploaded_by_tg_id,
                source=source,
                upload_order=upload_order,
                created_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            logger.info(f"✅ medical_attachment_files: تم حفظ ملف للتقرير #{report_id} (type={file_type})")
            return True
    except Exception as e:
        logger.error(f"❌ medical_attachment_files: فشل حفظ ملف للتقرير #{report_id}: {e}", exc_info=True)
        return False


def get_medical_attachment_files(report_id: int) -> list[dict]:
    """جلب كل الملفات الطبية لتقرير معين، مرتبة حسب ترتيب الرفع."""
    if not report_id:
        return []
    try:
        with SessionLocal() as session:
            rows = (
                session.query(MedicalAttachmentFile)
                .filter(MedicalAttachmentFile.report_id == report_id)
                .order_by(MedicalAttachmentFile.upload_order.asc(), MedicalAttachmentFile.id.asc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "file_id": r.file_id,
                    "file_type": r.file_type,
                    "file_name": r.file_name,
                    "uploaded_by": r.uploaded_by,
                    "created_at": r.created_at,
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"❌ medical_attachment_files: فشل جلب ملفات التقرير #{report_id}: {e}", exc_info=True)
        return []


def get_medical_attachment_files_for_patient(patient_id: int) -> list[dict]:
    """جلب كل الملفات الطبية المرفقة بكل تقارير/زيارات مريض معيّن مجمَّعة معاً،
    مرتبة حسب تاريخ التقرير ثم ترتيب الرفع داخل كل تقرير — تُستخدم لتجميع
    كل مرفقات المريض عبر تاريخه الطبي بالكامل في ملف واحد.

    ✅ تجمع تقارير من مصدرين معاً حتى لا يختفي أي تقرير فعلي من التجميع:
    1) تقارير مرتبطة مباشرة بـpatient_id (الحالة الطبيعية).
    2) تقارير Report.patient_id فارغ (NULL) أو غير مرتبط، لكن اسمها
       النصي المخزَّن (Report.patient_name — عمود منفصل تماماً عن جدول
       المرضى) يطابق اسم هذا المريض بالضبط. عمود patient_id في Report
       nullable وبعض مسارات الإدخال (لصق التقرير، الحالة الأولية) قد لا
       تربطه دائماً بنجاح رغم حفظ الاسم الصحيح — فتكون هذه التقارير
       "يتيمة" ومفقودة تماماً من أي تجميع يعتمد على patient_id فقط، حتى
       لو اسم المريض نفسه موحَّد وبلا أي تكرار في جدول المرضى.
    """
    if not patient_id:
        return []
    try:
        with SessionLocal() as session:
            target = session.query(Patient).filter(Patient.id == patient_id).first()
            if not target:
                return []

            id_matched_report_ids = {
                rid for (rid,) in session.query(Report.id)
                .filter(Report.patient_id == patient_id)
                .all()
            }

            name_matched_report_ids: set[int] = set()
            if target.full_name and target.full_name.strip():
                name_matched_report_ids = {
                    rid for (rid,) in session.query(Report.id)
                    .filter(Report.patient_name == target.full_name)
                    .all()
                }

            all_report_ids = id_matched_report_ids | name_matched_report_ids
            if not all_report_ids:
                return []

            rows = (
                session.query(
                    MedicalAttachmentFile,
                    Report.report_date,
                    Report.department,
                    Report.medical_action,
                )
                .join(Report, Report.id == MedicalAttachmentFile.report_id)
                .filter(MedicalAttachmentFile.report_id.in_(all_report_ids))
                .order_by(
                    Report.report_date.asc(),
                    MedicalAttachmentFile.upload_order.asc(),
                    MedicalAttachmentFile.id.asc(),
                )
                .all()
            )
            return [
                {
                    "id": r.id,
                    "report_id": r.report_id,
                    "file_id": r.file_id,
                    "file_type": r.file_type,
                    "file_name": r.file_name,
                    "uploaded_by": r.uploaded_by,
                    "created_at": r.created_at,
                    "report_date": report_date,
                    "department": department,
                    "medical_action": medical_action,
                }
                for r, report_date, department, medical_action in rows
            ]
    except Exception as e:
        logger.error(f"❌ medical_attachment_files: فشل جلب مرفقات المريض #{patient_id}: {e}", exc_info=True)
        return []


def get_reports_with_paper_report_for_patient(patient_id: int) -> list[dict]:
    """
    تقارير هذا المريض التي عليها has_paper_report=1 (المترجم أكّد وجود
    تقرير طبي وقت الإنشاء) — بنفس منطق مطابقة patient_id/patient_name
    المستخدَم في get_medical_attachment_files_for_patient، لمقارنة عدد
    التقارير "المؤكَّد عليها تقرير طبي" مع عدد المرفقات الفعلي المجمَّع
    فعلاً، وكشف أي تقرير فشل إرسال/تسجيل مرفقه بصمت وقت النشر.
    """
    if not patient_id:
        return []
    try:
        with SessionLocal() as session:
            target = session.query(Patient).filter(Patient.id == patient_id).first()
            if not target:
                return []

            base = session.query(Report).filter(Report.has_paper_report == 1)
            id_matched = base.filter(Report.patient_id == patient_id).all()

            name_matched = []
            if target.full_name and target.full_name.strip():
                name_matched = base.filter(Report.patient_name == target.full_name).all()

            seen_ids = set()
            reports = []
            for r in list(id_matched) + list(name_matched):
                if r.id in seen_ids:
                    continue
                seen_ids.add(r.id)
                reports.append({
                    "report_id": r.id,
                    "report_date": r.report_date,
                    "department": r.department,
                    "medical_action": r.medical_action,
                })
            return reports
    except Exception as e:
        logger.error(f"❌ medical_attachment_files: فشل جلب تقارير المريض #{patient_id} ذات التقرير الطبي: {e}", exc_info=True)
        return []


def get_reports_missing_attachments(limit: int = 200) -> list[dict]:
    """يجلب التقارير التي عليها has_paper_report=1 (المترجم أكّد وجود تقرير
    طبي مرفوع وقت الإنشاء) لكن لا يوجد لها أي سجل فعلي في
    medical_attachment_files — يكشف فشلاً صامتاً في إرسال المرفق وقت البث
    (بطاقة التقرير تنجح، لكن PDF الصور/الملف يفشل داخلياً بلا أي أثر ظاهر
    للمترجم — انظر broadcast_service._send_medical_attachments)."""
    try:
        from sqlalchemy import func

        with SessionLocal() as session:
            rows = (
                session.query(Report)
                .outerjoin(MedicalAttachmentFile, MedicalAttachmentFile.report_id == Report.id)
                .filter(Report.has_paper_report == 1)
                .group_by(Report.id)
                .having(func.count(MedicalAttachmentFile.id) == 0)
                .order_by(Report.report_date.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "report_id": r.id,
                    "patient_name": r.patient_name,
                    "department": r.department,
                    "translator_name": r.translator_name,
                    "medical_action": r.medical_action,
                    "report_date": r.report_date,
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"❌ medical_attachment_files: فشل جلب التقارير الناقصة المرفقات: {e}", exc_info=True)
        return []


def count_medical_attachment_files(report_id: int) -> int:
    """عدد الملفات الطبية المرتبطة بتقرير — يُستخدم لتحديد ظهور الزر عند إعادة النشر."""
    if not report_id:
        return 0
    try:
        with SessionLocal() as session:
            return (
                session.query(MedicalAttachmentFile)
                .filter(MedicalAttachmentFile.report_id == report_id)
                .count()
            )
    except Exception as e:
        logger.error(f"❌ medical_attachment_files: فشل عدّ ملفات التقرير #{report_id}: {e}", exc_info=True)
        return 0
