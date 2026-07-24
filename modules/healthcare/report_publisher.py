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

import io
import re

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
    # ── ENTRY LOG — first thing executed, before any I/O ─────────────────────
    logger.info(
        f"[report_publisher] publish ENTERED"
        f"  workflow={data.workflow_type}"
        f"  patient={data.patient_name!r}"
        f"  images={len(data.images)}"
        f"  admin_ids={ADMIN_IDS}"
    )

    try:
        text = _build_report_text(data)
    except Exception:
        logger.exception("[report_publisher] _build_report_text FAILED")
        return

    # 1. Notify every admin
    logger.info(f"[report_publisher] notifying admins: {ADMIN_IDS}")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info(f"[report_publisher] admin notified  admin={admin_id}")
        except Exception as exc:
            logger.warning(
                f"[report_publisher] admin notify failed  admin={admin_id}: {exc}"
            )

    # 1b. Send a copy of the published report back to the submitter (skip if
    # they're already an admin — they'd otherwise get the exact same message twice).
    if data.created_by_id and data.created_by_id not in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=data.created_by_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info(f"[report_publisher] submitter notified with report copy  user={data.created_by_id}")
        except Exception as exc:
            logger.warning(
                f"[report_publisher] submitter notify failed  user={data.created_by_id}: {exc}"
            )

    # 2. Publish to healthcare documentation group
    group_id = _resolve_group_id()
    logger.info(f"[report_publisher] group_id resolved → {group_id!r}")
    if group_id:
        try:
            await bot.send_message(
                chat_id=group_id,
                text=text,
                parse_mode="Markdown",
            )
            logger.info(f"[report_publisher] text sent to group  group_id={group_id}")
        except Exception as exc:
            logger.warning(f"[report_publisher] group text send failed: {exc}")
    else:
        logger.warning("[report_publisher] HEALTHCARE_GROUP_ID not configured — skipping group publish")

    # 3. Convert images to PDF and send to the group and the submitter
    logger.info(
        f"[report_publisher] images check: {len(data.images)} image(s)"
    )
    if data.images:
        pdf_targets: list = []
        if group_id:
            pdf_targets.append(group_id)
        if data.created_by_id and data.created_by_id not in ADMIN_IDS and data.created_by_id != group_id:
            pdf_targets.append(data.created_by_id)
        if pdf_targets:
            await _send_pdf_to_targets(bot, pdf_targets, data)


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


_PDF_PREFIX: dict[str, str] = {
    "woundcare":   "WoundCare",
    "followup":    "MedFollowup",
    "medications": "Medication",
    "supplies":    "Supplies",
    "other":       "Healthcare",
}


async def _send_pdf_to_targets(
    bot,
    chat_ids: list,
    data: HealthcarePublishData,
) -> None:
    """
    Download all images attached to the record, merge them into a single PDF
    (one image per page, no cover or extra formatting), and send that same
    PDF to every chat id in chat_ids (e.g. the healthcare group and/or the
    submitter) — built once, sent to each target independently so one
    recipient's send failure never affects the others.

    Falls back silently — any failure is logged and swallowed.
    """
    from PIL import Image

    file_ids = [d.get("file_id", "") for d in data.images if d.get("file_id")]
    logger.info(f"[report_publisher] _send_pdf_to_targets  file_ids={len(file_ids)}  raw_images={len(data.images)}  targets={chat_ids}")
    if not file_ids:
        logger.warning("[report_publisher] no valid file_ids found in data.images — PDF skipped")
        return

    # ── 1. Download every image from Telegram ────────────────────────────────
    pil_images: list[Image.Image] = []
    for i, fid in enumerate(file_ids):
        try:
            logger.debug(f"[report_publisher] downloading image {i+1}/{len(file_ids)}  fid={fid[:20]}...")
            tg_file = await bot.get_file(fid)
            raw     = await tg_file.download_as_bytearray()
            img     = Image.open(io.BytesIO(bytes(raw))).convert("RGB")
            pil_images.append(img)
            logger.debug(f"[report_publisher] image {i+1} downloaded OK  size={img.size}")
        except Exception:
            logger.exception(f"[report_publisher] image download FAILED  index={i}  fid={fid[:20]}...")

    logger.info(f"[report_publisher] downloaded {len(pil_images)}/{len(file_ids)} images")
    if not pil_images:
        logger.warning("[report_publisher] all image downloads failed — PDF skipped")
        return

    # ── 2. Build PDF in memory ────────────────────────────────────────────────
    pdf_bytes: bytes
    pdf_buffer = io.BytesIO()
    try:
        pil_images[0].save(
            pdf_buffer,
            format="PDF",
            save_all=True,
            append_images=pil_images[1:],
            resolution=150.0,
        )
        pdf_bytes = pdf_buffer.getvalue()
        logger.info(f"[report_publisher] PDF built  pages={len(pil_images)}  size={len(pdf_bytes):,} bytes")
    except Exception:
        logger.exception("[report_publisher] PDF generation FAILED")
        return

    # ── 3. Build filename and caption ─────────────────────────────────────────
    prefix    = _PDF_PREFIX.get(data.workflow_type, "Healthcare")
    safe_name = re.sub(r"[^\w؀-ۿ]", "_", data.patient_name)[:20]
    date_str  = (data.record_date or "")[:10]
    filename  = f"{prefix}_{safe_name}_{date_str}.pdf"

    caption = (
        f"👤 {data.patient_name}\n"
        f"📋 {data.workflow_label}\n"
        f"👨‍⚕️ {data.specialist_name or '—'}\n"
        f"📅 {date_str}"
    )

    # ── 4. Send the same PDF to each target ───────────────────────────────────
    for chat_id in chat_ids:
        logger.info(f"[report_publisher] sending PDF  file={filename}  chat={chat_id}")
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=io.BytesIO(pdf_bytes),
                filename=filename,
                caption=caption,
            )
            logger.info(
                f"[report_publisher] PDF sent OK  file={filename}"
                f"  pages={len(pil_images)}  patient={data.patient_name!r}  chat={chat_id}"
            )
        except Exception:
            logger.exception(f"[report_publisher] PDF send FAILED  file={filename}  chat={chat_id}")


def _resolve_group_id() -> int | str | None:
    """Return the configured healthcare group ID, or None if not set."""
    gid = HEALTHCARE_GROUP_ID
    if not gid:
        return None
    try:
        return int(gid)
    except (ValueError, TypeError):
        return str(gid) if gid else None
