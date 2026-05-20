# shared/uploads/_models.py
# Value objects for the upload system.
# Immutable and JSON-serializable — safe to store in session and pass to callers.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UploadedFile:
    """
    A single collected file reference.

    file_id        — Telegram file_id (may change between bot restarts; use for download only)
    file_unique_id — Telegram file_unique_id (stable; use for deduplication and storage keys)
    mime_type      — e.g. "image/jpeg", "application/pdf" (empty for compressed photos)
    file_size      — bytes (0 if unknown)
    file_name      — original filename for documents; empty for compressed photos
    width/height   — pixels for photos; 0 for documents
    """
    file_id:        str
    file_unique_id: str
    mime_type:      str
    file_size:      int
    file_name:      str = ""
    width:          int = 0
    height:         int = 0

    @property
    def size_mb(self) -> float:
        return self.file_size / (1024 * 1024)

    @property
    def is_photo(self) -> bool:
        return self.mime_type.startswith("image/") or self.mime_type == ""

    @property
    def is_pdf(self) -> bool:
        return self.mime_type == "application/pdf"

    def to_dict(self) -> dict:
        return {
            "file_id":        self.file_id,
            "file_unique_id": self.file_unique_id,
            "mime_type":      self.mime_type,
            "file_size":      self.file_size,
            "file_name":      self.file_name,
            "width":          self.width,
            "height":         self.height,
        }

    @staticmethod
    def from_dict(d: dict) -> "UploadedFile":
        return UploadedFile(
            file_id=        d["file_id"],
            file_unique_id= d["file_unique_id"],
            mime_type=      d.get("mime_type", ""),
            file_size=      d.get("file_size", 0),
            file_name=      d.get("file_name", ""),
            width=          d.get("width",  0),
            height=         d.get("height", 0),
        )


@dataclass(frozen=True)
class UploadResult:
    """
    Delivered to the caller's completion handler via result_router.

    files     — tuple of collected UploadedFile objects (empty if cancelled).
    cancelled — True when the user pressed ❌ Cancel; False on ✅ Confirm.
    """
    files:     tuple   # tuple[UploadedFile, ...]
    cancelled: bool

    @property
    def count(self) -> int:
        return len(self.files)

    def is_empty(self) -> bool:
        return len(self.files) == 0

    # ── Sentinel constructors ─────────────────────────────────────────────────

    @staticmethod
    def cancelled_result() -> "UploadResult":
        return UploadResult(files=(), cancelled=True)

    @staticmethod
    def confirmed(files: list) -> "UploadResult":
        return UploadResult(files=tuple(files), cancelled=False)
