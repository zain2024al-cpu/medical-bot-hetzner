# shared/files/filename_builder.py
# Shared utility: build deterministic, human-readable filenames for
# bot-generated medical PDFs, and for renaming translator-uploaded medical
# attachments (documents) so they carry the patient/department/action in
# their displayed filename instead of the phone's original export name.
#
# ── Rules ────────────────────────────────────────────────────────────────────
# • build_medical_pdf_filename():        for PDFs the bot generates itself —
#   always returns a ".pdf" filename.
# • build_medical_attachment_filename(): for re-uploading a file the user
#   actually sent (bot.handlers.user.user_medical_attachments) — preserves
#   the ORIGINAL file extension (Telegram does not allow renaming a file
#   resent by file_id, so the caller must download + re-upload the bytes
#   with this new name).
# • Arabic text is preserved as-is (Unicode NFC) — safe on all modern systems.
# • Invalid filesystem characters are stripped.
# • Whitespace and hyphens are collapsed to underscores.
# • Result is capped at MAX_BASE_LEN characters (before the extension).
# • Fallback: "medical_report.pdf" / "مرفق_طبي.<ext>" when all inputs are
#   empty after sanitization.
#
# ── Usage ────────────────────────────────────────────────────────────────────
#   from shared.files.filename_builder import build_medical_pdf_filename
#
#   name = build_medical_pdf_filename(
#       patient_name="انور محمد",
#       departments="جراحة الأورام",
#   )
#   # → "انور_محمد_جراحة_الأورام.pdf"

import re
import unicodedata
from typing import Union

# Characters that are invalid in Windows filenames (superset of Linux/macOS limits).
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
# Internal whitespace, hyphens, and Unicode dash variants → single underscore.
# This includes em dash (—, U+2014), en dash (–, U+2013), and related
# characters that are used as placeholder values in this codebase.
_WHITESPACE_OR_HYPHEN = re.compile(r'[\s\-‐-―−﹘﹣－]+')
# Collapse consecutive underscores.
_MULTI_UNDERSCORE = re.compile(r'_+')
# Strip leading / trailing underscores and dots.
_EDGE_STRIP = re.compile(r'^[_.\s]+|[_.\s]+$')

# Maximum filename base length (before ".pdf").
# 80 characters keeps well within the 255-byte FS limit even for long Arabic strings.
_MAX_BASE_LEN = 80


def _sanitize_part(text: str) -> str:
    """
    Sanitize one segment of a filename.

    - NFC-normalizes Unicode (keeps Arabic correctly composed).
    - Removes OS-invalid characters.
    - Collapses whitespace / hyphens to underscores.
    - Strips leading / trailing underscores and dots.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text.strip())
    text = _INVALID_CHARS.sub("", text)
    text = _WHITESPACE_OR_HYPHEN.sub("_", text)
    text = _MULTI_UNDERSCORE.sub("_", text)
    text = _EDGE_STRIP.sub("", text)
    return text


def _build_base_name(
    patient_name: Union[str, None],
    departments: Union[str, list, None],
    workflow_type: Union[str, None],
) -> str:
    """Shared part-joining logic used by both filename builders below."""
    parts: list[str] = []

    # ── patient name ─────────────────────────────────────────────────────────
    if patient_name:
        p = _sanitize_part(str(patient_name))
        if p:
            parts.append(p)

    # ── department(s) ─────────────────────────────────────────────────────────
    if departments:
        if isinstance(departments, str):
            d = _sanitize_part(departments)
            if d:
                parts.append(d)
        else:
            for dept in departments:
                d = _sanitize_part(str(dept))
                if d:
                    parts.append(d)

    # ── optional workflow tag (e.g. medical action type) ───────────────────────
    if workflow_type:
        w = _sanitize_part(str(workflow_type))
        if w:
            parts.append(w)

    if not parts:
        return ""

    base = "_".join(parts)

    # Truncate to avoid filesystem limits (leave room for the extension).
    if len(base) > _MAX_BASE_LEN:
        base = base[:_MAX_BASE_LEN].rstrip("_")

    return base


def build_medical_pdf_filename(
    patient_name: Union[str, None] = None,
    departments: Union[str, list, None] = None,
    workflow_type: Union[str, None] = None,
) -> str:
    """
    Build a dynamic, human-readable filename for a bot-generated medical PDF.

    Args:
        patient_name:  Patient name (Arabic or Latin).
                       Example: "انور محمد"
        departments:   Department name as a string, or a list of department names.
                       Example: "جراحة الأورام"  or  ["جراحة الأورام", "الطوارئ"]
        workflow_type: Optional context tag appended after patient + department.
                       Example: "مرفقات"

    Returns:
        A safe, non-empty filename string ending in ".pdf".

        Examples:
            "انور_محمد_جراحة_الأورام.pdf"
            "سارة_علي_الطوارئ_مرفقات.pdf"
            "medical_report.pdf"   ← fallback when all inputs are empty
    """
    base = _build_base_name(patient_name, departments, workflow_type)
    return f"{base}.pdf" if base else "medical_report.pdf"


def build_medical_attachment_filename(
    patient_name: Union[str, None] = None,
    departments: Union[str, list, None] = None,
    workflow_type: Union[str, None] = None,
    original_filename: Union[str, None] = None,
) -> str:
    """
    Build a human-readable filename for a translator-uploaded medical
    attachment (document sent via the "📎 المرفقات الطبية" flow), while
    preserving the ORIGINAL file extension (.pdf, .docx, .jpg, ...) so the
    file still opens correctly on the recipient's device.

    Unlike build_medical_pdf_filename(), this is meant for re-uploading a
    file the user actually sent (not a bot-generated PDF) — the caller is
    expected to download the original bytes and re-upload them with this
    name, since Telegram does not allow renaming a file resent by file_id.

    Args:
        patient_name:      Patient name.
        departments:        Department name(s).
        workflow_type:      Optional tag — pass the medical action type here,
                            e.g. "متابعة في الرقود", so the filename also
                            reflects what kind of procedure the attachment
                            belongs to.
        original_filename:  The original filename as uploaded by the user
                            (e.g. "DOC-20260628-WA0046.pdf") — only its
                            extension is used; the rest is discarded.

    Returns:
        A safe, non-empty filename string ending in the original extension
        (or ".dat" if none could be detected).

        Example:
            build_medical_attachment_filename(
                "انور محمد", "جراحة الأورام", "متابعة في الرقود",
                "DOC-20260628-WA0046.pdf",
            )
            → "انور_محمد_جراحة_الأورام_متابعة_في_الرقود.pdf"
    """
    base = _build_base_name(patient_name, departments, workflow_type) or "مرفق_طبي"

    ext = ""
    if original_filename and "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].strip().lower()
    # Guard against a pathological/overlong "extension" (e.g. no real dot found).
    if not ext or len(ext) > 10:
        ext = ".dat"

    return f"{base}{ext}"


def extract_sent_file_info(sent_message) -> tuple[Union[str, None], Union[str, None], Union[str, None]]:
    """
    Extract (file_id, file_type, file_name) from an already-sent telegram.Message.

    Used after a medical attachment is actually sent to a group (not from the
    user's original upload) — for photo-batches converted to a single PDF, or
    documents re-uploaded under a new name, the resend-able file_id only
    exists on the message Telegram returns from the send call itself.

    Returns (None, None, None) if the message carries none of the recognized
    media types.
    """
    if sent_message is None:
        return None, None, None
    if sent_message.document:
        return sent_message.document.file_id, "document", sent_message.document.file_name
    if sent_message.photo:
        return sent_message.photo[-1].file_id, "photo", None
    if sent_message.video:
        return sent_message.video.file_id, "video", None
    if sent_message.audio:
        return sent_message.audio.file_id, "audio", None
    if sent_message.voice:
        return sent_message.voice.file_id, "voice", None
    return None, None, None
