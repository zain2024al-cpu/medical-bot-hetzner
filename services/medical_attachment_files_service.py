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
from db.models import MedicalAttachmentFile

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
