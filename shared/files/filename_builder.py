# shared/files/filename_builder.py
# Shared utility: build deterministic, human-readable filenames for
# bot-generated medical PDFs.
#
# ── Rules ────────────────────────────────────────────────────────────────────
# • User-uploaded files KEEP their original filenames.
#   Call this ONLY for PDFs that the bot generates itself.
# • Arabic text is preserved as-is (Unicode NFC) — safe on all modern systems.
# • Invalid filesystem characters are stripped.
# • Whitespace and hyphens are collapsed to underscores.
# • Result is capped at MAX_BASE_LEN characters (before ".pdf").
# • Always returns a string ending in ".pdf".
# • Fallback: "medical_report.pdf" when all inputs are empty after sanitization.
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

    # ── optional workflow tag ─────────────────────────────────────────────────
    if workflow_type:
        w = _sanitize_part(str(workflow_type))
        if w:
            parts.append(w)

    if not parts:
        return "medical_report.pdf"

    base = "_".join(parts)

    # Truncate to avoid filesystem limits (leave room for ".pdf").
    if len(base) > _MAX_BASE_LEN:
        base = base[:_MAX_BASE_LEN].rstrip("_")

    return f"{base}.pdf"
