# modules/residency/report_publisher.py
# Publishes residency lifecycle events to admins and optional RESIDENCY_GROUP_ID.
# Errors are logged and swallowed — publication failure never crashes the flow.

from __future__ import annotations
import logging
from datetime import datetime

from config.settings import ADMIN_IDS, GS_NOTIFY_ADMINS

logger = logging.getLogger(__name__)


async def publish_event(
    bot,
    *,
    action_label: str,
    patient_name: str,
    body_lines: list[str],
    attachments: list[tuple[str, str]] | None = None,
    submitted_by: int | None = None,
) -> None:
    """
    Send a residency event notification to all admins (and GS group if configured)
    plus the user who submitted the action.

    `attachments` — [(file_id, caption), …] لملفات الوثائق المرتبطة بالحدث
    (مثل ملف الإقامة الذي صدر للتو). تُرسَل بعد نص الإشعار — فشل إرسال
    مرفق واحد لا يوقف الباقي ولا يُسقط النصّ نفسه.

    `submitted_by` — معرّف من نفَّذ الإجراء. يستلم نسخة من التقرير الفعلي
    دائماً (لا رسالة نجاح مختصرة فقط)، بصرف النظر عن كونه أدمناً مُدرَجاً
    في `ADMIN_IDS` أو عضو صلاحية وحدة فقط، وبصرف النظر عن `GS_NOTIFY_ADMINS`
    — طلب المستخدم صراحةً: يرى ما نشره فعلياً.
    """
    from modules.general_services.views import format_arabic_date
    date_str = format_arabic_date(datetime.utcnow())
    lines = [
        f"🪪 *{action_label}*",
        f"📅 {date_str}",
        f"👤 {patient_name}",
        "",
    ] + body_lines
    text = "\n".join(lines)

    async def _send_attachments(chat_id) -> None:
        for file_id, caption in (attachments or []):
            if not file_id:
                continue
            try:
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=caption)
            except Exception as exc:
                logger.warning(f"[res_publisher] attachment send failed  chat={chat_id}: {exc}")

    notified_user_ids: set[int] = set()

    if GS_NOTIFY_ADMINS:
        for admin_id in (ADMIN_IDS or []):
            try:
                await bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
                await _send_attachments(admin_id)
                notified_user_ids.add(admin_id)
            except Exception as exc:
                logger.warning(f"[res_publisher] admin={admin_id}: {exc}")
    else:
        logger.info("[res_publisher] GS_NOTIFY_ADMINS=0 — تُخطّى إشعارات الأدمن الخاصة")

    # ✅ لا يُكرَّر إن كان submitted_by أدمناً استلم النسخة أعلاه بالفعل.
    if submitted_by and submitted_by not in notified_user_ids:
        try:
            await bot.send_message(chat_id=submitted_by, text=text, parse_mode="Markdown")
            await _send_attachments(submitted_by)
        except Exception as exc:
            logger.warning(f"[res_publisher] submitter copy failed user={submitted_by}: {exc}")

    group_id = _resolve_group_id()
    if not group_id:
        return
    try:
        await bot.send_message(chat_id=group_id, text=text, parse_mode="Markdown")
        await _send_attachments(group_id)
    except Exception as exc:
        logger.warning(f"[res_publisher] group send failed: {exc}")


def _resolve_group_id() -> int | str | None:
    try:
        from config.settings import RESIDENCY_GROUP_ID
        gid = RESIDENCY_GROUP_ID
        if not gid:
            return None
        try:
            return int(gid)
        except (ValueError, TypeError):
            return str(gid) if gid else None
    except Exception:
        return None
