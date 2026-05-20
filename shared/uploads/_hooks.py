# shared/uploads/_hooks.py
# Processing hook registry — forward-looking, minimal implementation.
#
# Hooks are async callables registered by modules at startup.
# The upload system stores raw Telegram file references at collection time.
# Processing happens at download time, when callers explicitly invoke a hook.
#
# ── Registration (at app startup) ─────────────────────────────────────────────
#
#   from shared.uploads import hooks
#   hooks.register("enhance_image", my_ai_enhancer)
#
# ── Invocation (at download/processing time, by the caller) ───────────────────
#
#   processor = hooks.get("enhance_image")
#   if processor:
#       processed_bytes = await processor(raw_bytes, metadata)
#
# ── Built-in hook names (convention, not enforced) ────────────────────────────
#
#   "enhance_image"   — AI/CLAHE image enhancement (see image_pipeline/)
#   "ocr"             — text extraction from image or PDF
#   "pdf_convert"     — image → PDF conversion
#   "compress"        — lossless/lossy compression
#   "thumbnail"       — thumbnail generation

import logging
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)

_registry: dict[str, Callable[..., Awaitable[bytes]]] = {}


def register(name: str, processor: Callable[..., Awaitable[bytes]]) -> None:
    """
    Register a processing hook by name.

    processor signature: async (raw_bytes: bytes, metadata: dict) -> bytes
    """
    if name in _registry:
        logger.warning(f"[upload_hooks] overwriting existing hook: {name!r}")
    _registry[name] = processor
    logger.debug(f"[upload_hooks] registered hook: {name!r}")


def get(name: str) -> Callable | None:
    """Return a registered hook by name, or None if not registered."""
    return _registry.get(name)


def registered() -> list[str]:
    """Return the names of all currently registered hooks."""
    return list(_registry.keys())


def clear(name: str | None = None) -> None:
    """Remove one hook by name, or all hooks if name is None. Mainly for testing."""
    if name is None:
        _registry.clear()
    else:
        _registry.pop(name, None)
