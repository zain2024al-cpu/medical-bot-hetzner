# modules/residency/report_publisher.py
# Publishes residency lifecycle events to admins and optional RESIDENCY_GROUP_ID.
# Errors are logged and swallowed — publication failure never crashes the flow.

from __future__ import annotations
import logging
from datetime import datetime

from config.settings import ADMIN_IDS

logger = logging.getLogger(__name__)


async def publish_event(
    bot,
    *,
    action_label: str,
    patient_name: str,
    body_lines: list[str],
) -> None:
    """Send a residency event notification to all admins (and GS group if configured)."""
    from modules.general_services.views import format_arabic_date
    date_str = format_arabic_date(datetime.utcnow())
    lines = [
        f"🪪 *{action_label}*",
        f"📅 {date_str}",
        f"👤 {patient_name}",
        "",
    ] + body_lines
    text = "\n".join(lines)

    for admin_id in (ADMIN_IDS or []):
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        except Exception as exc:
            logger.warning(f"[res_publisher] admin={admin_id}: {exc}")

    group_id = _resolve_group_id()
    if not group_id:
        return
    try:
        await bot.send_message(chat_id=group_id, text=text, parse_mode="Markdown")
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
