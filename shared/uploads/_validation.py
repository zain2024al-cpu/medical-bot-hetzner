# shared/uploads/_validation.py
# Pure validation layer for the upload collector.
# No I/O, no context — data in, ValidationError|None out.
#
# allowed_types values:
#   "photo"          — Telegram-compressed photo (message.photo)
#   "document"       — any document regardless of mime (message.document)
#   "pdf"            — document with mime_type == "application/pdf"
#   "image_document" — document with mime_type starting "image/"

from dataclasses import dataclass


# Mime types unconditionally rejected to prevent executable uploads.
_BLOCKED_MIMES: frozenset = frozenset({
    "application/x-msdownload",
    "application/x-executable",
    "application/x-sh",
    "application/x-bat",
})
_BLOCKED_PREFIXES: tuple = (
    "application/x-",
)


@dataclass(frozen=True)
class ValidationError:
    code:    str   # "too_large" | "wrong_type" | "duplicate" | "max_reached" | "blocked"
    message: str   # Arabic user-facing message


def validate_incoming(
    *,
    mime_type:       str,
    file_size:       int,
    file_unique_id:  str,
    is_photo:        bool,
    is_document:     bool,
    allowed_types:   list[str],
    max_file_size_mb: int,
    max_files:       int,
    current_count:   int,
    seen_unique_ids: list[str],
) -> ValidationError | None:
    """
    Returns None if the file passes all checks, or a ValidationError describing
    the first failing constraint.

    Checked in order: max_files → duplicate → type → blocked → size.
    """
    # ── Max files ─────────────────────────────────────────────────────────────
    if max_files > 0 and current_count >= max_files:
        return ValidationError(
            code="max_reached",
            message=f"⚠️ وصلت للحد الأقصى ({max_files} ملفات). تأكد أو احذف ملفاً أولاً.",
        )

    # ── Duplicate ─────────────────────────────────────────────────────────────
    if file_unique_id in seen_unique_ids:
        return ValidationError(
            code="duplicate",
            message="⚠️ هذا الملف مرفوع بالفعل.",
        )

    # ── Type check ────────────────────────────────────────────────────────────
    if not _type_allowed(mime_type, is_photo, is_document, allowed_types):
        return ValidationError(
            code="wrong_type",
            message="⚠️ نوع الملف غير مدعوم في هذه العملية.",
        )

    # ── Blocked mimes ─────────────────────────────────────────────────────────
    if mime_type in _BLOCKED_MIMES or any(
        mime_type.startswith(p) for p in _BLOCKED_PREFIXES
    ):
        return ValidationError(
            code="blocked",
            message="⚠️ نوع الملف محظور لأسباب أمنية.",
        )

    # ── File size (documents only — photos are server-compressed by Telegram) ─
    if is_document and max_file_size_mb > 0 and file_size > 0:
        size_mb = file_size / (1024 * 1024)
        if size_mb > max_file_size_mb:
            return ValidationError(
                code="too_large",
                message=f"⚠️ حجم الملف ({size_mb:.1f} MB) يتجاوز الحد الأقصى {max_file_size_mb} MB.",
            )

    return None


# ── Private helpers ───────────────────────────────────────────────────────────

def _type_allowed(
    mime_type:    str,
    is_photo:     bool,
    is_document:  bool,
    allowed_types: list[str],
) -> bool:
    for t in allowed_types:
        if t == "photo" and is_photo:
            return True
        if t == "document" and is_document:
            return True
        if t == "pdf" and is_document and mime_type == "application/pdf":
            return True
        if t == "image_document" and is_document and mime_type.startswith("image/"):
            return True
    return False
