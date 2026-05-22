# modules/healthcare/report_publisher.py
# Unified report publication system for all healthcare sub-modules.
#
# After a healthcare record is saved to the DB, call publish() to:
#   1. Format a structured Arabic report text
#   2. Send the report text to every admin
#   3. Send the report text to the healthcare documentation group
#   4. Send images to the group (media group if multiple, single photo if one)
#
# All I/O errors are caught and logged — publication failure never crashes the flow.
# The healthcare group is optional: if HEALTHCARE_GROUP_ID is empty, group
# publishing is silently skipped.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from telegram import InputMediaPhoto

from config.settings import ADMIN_IDS, HEALTHCARE_GROUP_ID
from modules.healthcare.views import format_arabic_datetime, format_image_count

logger = logging.getLogger(__name__)


# ── Publish data contract ─────────────────────────────────────────────────────

@dataclass
class HealthcarePublishData:
    """
    Standardized data object passed to publish() by every healthcare sub-module.
    All fields are plain values — no ORM objects, no PTB objects.
    """
    workflow_type:    str           # "woundcare" | "followup" | "medications" | "other"
    workflow_label:   str           # Arabic display name, e.g. "رعاية الجروح"
    workflow_icon:    str           # emoji, e.g. "🩺"
    record_id:        int
    patient_name:     str
    operations:       list[str]     # human-readable operation/procedure labels
    images:           list[dict]    # list of UploadedFile.to_dict() dicts (may be empty)
    notes:            str           # may be empty
    specialist_name:  str           # may be empty
    created_by_id:    Optional[int] # Telegram user ID of the submitter
    created_by_name:  str           # display name of the submitter
    # Workflow-specific sections rendered before operations in the report.
    # Each tuple: (header_with_markdown, content_text)
    # If content is non-empty  → header on its own line, then content on the next line(s)
    # If content is empty ("")  → header line only (value embedded in the header string itself)
    extra_sections: list[tuple[str, str]] = field(default_factory=list)
    record_date:    str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ── Public API ────────────────────────────────────────────────────────────────

async def publish(bot, data: HealthcarePublishData) -> None:
    """
    Publish a healthcare record after it has been saved to the DB.

    Errors are logged and swallowed — this must never raise.
    """
    text = _build_report_text(data)

    # 1. Notify every admin
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.warning(
                f"[report_publisher] admin notify failed  admin={admin_id}: {exc}"
            )

    # 2. Publish to healthcare documentation group
    group_id = _resolve_group_id()
    if not group_id:
        logger.debug("[report_publisher] HEALTHCARE_GROUP_ID not configured — skipping group publish")
        return

    try:
        await bot.send_message(
            chat_id=group_id,
            text=text,
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.warning(f"[report_publisher] group text send failed: {exc}")

    # 3. Send images to group
    if data.images:
        await _send_images_to_group(bot, group_id, data)


# ── Per-workflow operations label ─────────────────────────────────────────────
# Maps workflow_type to the correct Arabic section header for the published report.
# The icon + label must match what the review screen shows for that department.

_OPERATIONS_LABEL: dict[str, str] = {
    "woundcare":    "🩹 *أنواع الجروح:*",
    "followup":     "📋 *الإجراءات الطبية:*",
    "medications":  "💊 *الأدوية:*",
    "other":        "📝 *الإجراءات:*",
}
_OPERATIONS_LABEL_DEFAULT = "🔹 *الإجراءات:*"

# ── Report title header — first line of every published report ────────────────

_REPORT_TITLE: dict[str, str] = {
    "woundcare":   "🩺 تقرير مجارحة جديد",
    "followup":    "📋 تقرير متابعة طبية جديد",
    "medications": "💊 تقرير صرف أدوية جديد",
    "other":       "📝 تقرير إجراء صحي جديد",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_report_text(data: HealthcarePublishData) -> str:
    """Build the structured Arabic report text."""
    date_str        = format_arabic_datetime(data.record_date)
    ops_label       = _OPERATIONS_LABEL.get(data.workflow_type, _OPERATIONS_LABEL_DEFAULT)
    operations_text = "\n".join(f"  • {op}" for op in data.operations) if data.operations else "  —"
    title           = _REPORT_TITLE.get(data.workflow_type, f"{data.workflow_icon} تقرير صحي جديد")

    lines = [
        f"*{title}*",
        "",
        f"📅 *التاريخ:*  {date_str}",
        f"👤 *المريض:*  {data.patient_name}",
    ]

    # Extra workflow-specific sections (departments, vitals, item_count, etc.)
    for header, content in data.extra_sections:
        if content:
            lines += ["", header, content]
        else:
            lines += ["", header]

    # Operations / procedures — skip if empty
    if data.operations:
        lines += ["", ops_label, operations_text]

    if data.images:
        lines += ["", f"📎 *الصور:*  {format_image_count(len(data.images))}"]

    if data.notes:
        lines += ["", f"📝 *الملاحظات:*", data.notes]

    if data.specialist_name:
        lines += ["", f"👨‍⚕️ *المختص الصحي:*  {data.specialist_name}"]

    return "\n".join(lines)


async def _send_images_to_group(
    bot,
    group_id: int | str,
    data: HealthcarePublishData,
) -> None:
    """Send all images from the record to the healthcare group."""
    file_ids = [
        d.get("file_id", "")
        for d in data.images
        if d.get("file_id")
    ]
    if not file_ids:
        return

    caption = (
        f"📎 {data.workflow_icon} {data.workflow_label}\n"
        f"المريض: {data.patient_name} — التقرير #{data.record_id}"
    )

    if len(file_ids) == 1:
        try:
            await bot.send_photo(
                chat_id=group_id,
                photo=file_ids[0],
                caption=caption,
            )
        except Exception as exc:
            logger.warning(f"[report_publisher] single photo to group failed: {exc}")
        return

    # Multiple images — send as media group (max 10 per Telegram API)
    media = [
        InputMediaPhoto(
            media=fid,
            caption=caption if i == 0 else "",
        )
        for i, fid in enumerate(file_ids[:10])
    ]
    try:
        await bot.send_media_group(chat_id=group_id, media=media)
    except Exception as exc:
        logger.warning(
            f"[report_publisher] media_group to group failed ({exc}) — sending individually"
        )
        for fid in file_ids[:10]:
            try:
                await bot.send_photo(chat_id=group_id, photo=fid)
            except Exception as exc2:
                logger.warning(f"[report_publisher] individual photo failed: {exc2}")


def _resolve_group_id() -> int | str | None:
    """Return the configured healthcare group ID, or None if not set."""
    gid = HEALTHCARE_GROUP_ID
    if not gid:
        return None
    try:
        return int(gid)
    except (ValueError, TypeError):
        return str(gid) if gid else None
