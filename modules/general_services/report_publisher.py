# modules/general_services/report_publisher.py
# Unified publish system for all general-services sub-modules.
# Errors are logged and swallowed — publication failure never crashes the flow.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from telegram import InputMediaPhoto

from config.settings import ADMIN_IDS, GENERAL_SERVICES_GROUP_ID

logger = logging.getLogger(__name__)


@dataclass
class GSPublishData:
    """Data passed to publish() by every GS sub-module."""
    workflow_type:    str           # "arrivals" | "departures" | "public_services"
    workflow_label:   str           # Arabic label
    workflow_icon:    str           # emoji
    body_lines:       list[str]     # pre-formatted Arabic lines for the report body
    images:           list[dict] = field(default_factory=list)  # UploadedFile.to_dict() list
    created_by_id:    Optional[int] = None
    created_by_name:  str = ""
    record_date:      str = field(default_factory=lambda: datetime.utcnow().isoformat())


async def publish(bot, data: GSPublishData) -> None:
    """Publish a GS record to admins + the GS group."""
    text = _build_text(data)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="Markdown")
        except Exception as exc:
            logger.warning(f"[gs_publisher] admin notify failed admin={admin_id}: {exc}")

    group_id = _resolve_group_id()
    if not group_id:
        logger.debug("[gs_publisher] GENERAL_SERVICES_GROUP_ID not configured — skipping")
        return

    try:
        await bot.send_message(chat_id=group_id, text=text, parse_mode="Markdown")
    except Exception as exc:
        logger.warning(f"[gs_publisher] group text send failed: {exc}")

    if data.images:
        await _send_images(bot, group_id, data)


def _build_text(data: GSPublishData) -> str:
    from modules.general_services.views import format_arabic_datetime
    date_str = format_arabic_datetime(data.record_date)
    lines = [
        f"*{data.workflow_icon} {data.workflow_label}*",
        f"📅 *التاريخ:*  {date_str}",
        "",
    ] + data.body_lines
    return "\n".join(lines)


async def _send_images(bot, group_id, data: GSPublishData) -> None:
    file_ids = [d.get("file_id") for d in data.images if d.get("file_id")]
    if not file_ids:
        return
    caption = f"📎 {data.workflow_icon} {data.workflow_label}"
    if len(file_ids) == 1:
        try:
            await bot.send_photo(chat_id=group_id, photo=file_ids[0], caption=caption)
        except Exception as exc:
            logger.warning(f"[gs_publisher] photo send failed: {exc}")
        return
    media = [
        InputMediaPhoto(media=fid, caption=caption if i == 0 else "")
        for i, fid in enumerate(file_ids[:10])
    ]
    try:
        await bot.send_media_group(chat_id=group_id, media=media)
    except Exception as exc:
        logger.warning(f"[gs_publisher] media group failed: {exc}")


def _resolve_group_id() -> int | str | None:
    gid = GENERAL_SERVICES_GROUP_ID
    if not gid:
        return None
    try:
        return int(gid)
    except (ValueError, TypeError):
        return str(gid) if gid else None
