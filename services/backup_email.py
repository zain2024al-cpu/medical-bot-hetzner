# services/backup_email.py
#
# طبقة حماية إضافية للنسخة الاحتياطية اليومية — إرسال نسخة مضغوطة من ملف
# النسخة المحلية (services/render_backup.py::create_local_backup) بالبريد
# الإلكتروني، حتى تبقى نسخة خارج السيرفر تماماً (لا تتأثر بأي كارثة تصيب
# القرص/السيرفر نفسه).
#
# ✅ best-effort بالكامل: أي فشل هنا (بيانات اعتماد ناقصة، مشكلة شبكة،
# فشل SMTP) لا يجب أن يوقف أو يفشل مهمة النسخ الاحتياطي المحلي الأساسية.
#
# الإعداد المطلوب (في .env على السيرفر — لا تُكتَب هذه القيم هنا أبداً):
#   BACKUP_EMAIL_FROM          = عنوان Gmail المُرسِل
#   BACKUP_EMAIL_APP_PASSWORD  = App Password (وليس كلمة مرور Gmail العادية)
#   BACKUP_EMAIL_TO            = عنوان الوجهة (اختياري — افتراضياً نفس FROM)

from __future__ import annotations

import gzip
import logging
import os
import shutil
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def _get_email_credentials() -> tuple[str, str, str] | None:
    """يقرأ بيانات اعتماد البريد من البيئة. يعيد None إن كانت ناقصة."""
    from_addr = os.getenv("BACKUP_EMAIL_FROM")
    app_password = os.getenv("BACKUP_EMAIL_APP_PASSWORD")
    to_addr = os.getenv("BACKUP_EMAIL_TO") or from_addr
    if not from_addr or not app_password:
        return None
    return from_addr, app_password, to_addr


def _send_email_with_attachment(file_path: str, subject: str, body: str) -> bool:
    """يرسل ملفاً (مضغوطاً مسبقاً أو أي نوع) كمرفق بالبريد. لا يحذف الملف
    ولا يضغطه — هذا مسؤولية المستدعي. best-effort بالكامل."""
    creds = _get_email_credentials()
    if creds is None:
        logger.debug("[backup_email] BACKUP_EMAIL_FROM/APP_PASSWORD غير مضبوطة — تخطي الإرسال")
        return False
    from_addr, app_password, to_addr = creds

    if not file_path or not os.path.exists(file_path):
        logger.warning(f"[backup_email] الملف المطلوب إرساله غير موجود: {file_path}")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"',
        )
        msg.attach(part)

        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=60) as server:
            server.starttls()
            server.login(from_addr, app_password)
            server.sendmail(from_addr, [to_addr], msg.as_string())

        logger.info(f"✅ [backup_email] أُرسل الملف بالبريد إلى {to_addr}: {os.path.basename(file_path)}")
        return True

    except Exception as exc:
        logger.error(f"❌ [backup_email] فشل إرسال الملف بالبريد: {exc}", exc_info=True)
        return False


def send_backup_via_email(backup_path: str) -> bool:
    """يضغط ملف النسخة الاحتياطية (قاعدة بيانات خام) ويرسله بالبريد. يعيد
    True عند النجاح فقط — أي فشل يُسجَّل ويُعاد False بلا رفع أي استثناء."""
    if not backup_path or not os.path.exists(backup_path):
        logger.warning(f"[backup_email] ملف النسخة غير موجود: {backup_path}")
        return False

    gz_path = f"{backup_path}.gz"
    try:
        with open(backup_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        return _send_email_with_attachment(
            gz_path,
            subject=f"نسخة احتياطية يومية — {os.path.basename(backup_path)}",
            body=(
                "نسخة احتياطية تلقائية لقاعدة بيانات البوت الطبي.\n"
                "هذه رسالة آلية — لا حاجة للرد عليها."
            ),
        )
    except Exception as exc:
        logger.error(f"❌ [backup_email] فشل تجهيز نسخة قاعدة البيانات للإرسال: {exc}", exc_info=True)
        return False
    finally:
        try:
            if os.path.exists(gz_path):
                os.remove(gz_path)
        except Exception:
            pass


def send_project_backup_email(archive_path: str) -> bool:
    """يرسل أرشيف مشروع كامل (tar.gz جاهز مسبقاً — يشمل الكود + .env/config.env
    + قاعدة البيانات) بالبريد كنسخة احتياطية أسبوعية خارج السيرفر. الملف
    مضغوط بالفعل من قِبَل السكربت المُستدعي (full_project_backup.sh) —
    هذه الدالة لا تضغطه ولا تحذفه، فقط ترسله."""
    return _send_email_with_attachment(
        archive_path,
        subject=f"نسخة احتياطية أسبوعية كاملة للمشروع — {os.path.basename(archive_path)}",
        body=(
            "نسخة احتياطية أسبوعية تلقائية تشمل كود المشروع كاملاً، ملفات "
            "الإعدادات (.env/config.env)، وقاعدة البيانات.\n"
            "هذه رسالة آلية — لا حاجة للرد عليها."
        ),
    )
