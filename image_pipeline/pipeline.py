# image_pipeline/pipeline.py
# Main orchestrator — runs stages in order, saves debug outputs.
#
# Usage (sync):
#   from image_pipeline.pipeline import run_pipeline
#   pdf_bytes_io = run_pipeline([image_bytes, ...])
#
# Usage (async wrapper):
#   pdf_bytes_io = await run_pipeline_async([image_bytes, ...])

import io
import logging
import os
import cv2
import numpy as np
from typing import List, Optional

from .config import PipelineConfig, DEFAULT_CONFIG
from .stages.detector import detect_document
from .stages.cropper import smart_crop
from .stages.corrector import correct_perspective
from .stages.enhancer import enhance
from .stages.pdf_builder import build_pdf

logger = logging.getLogger(__name__)


def run_pipeline(
    image_bytes_list: List[bytes],
    config: Optional[PipelineConfig] = None,
    job_id: Optional[str] = None,
) -> io.BytesIO:
    """
    Process a list of raw image byte strings through the full pipeline
    and return a PDF as BytesIO.

    Args:
        image_bytes_list: list of raw image bytes (JPEG, PNG, WEBP …)
        config:           PipelineConfig (uses DEFAULT_CONFIG if None)
        job_id:           optional string used for debug filenames

    Returns:
        BytesIO object containing the final PDF, position rewound to 0.
    """
    cfg = config or DEFAULT_CONFIG
    job_id = job_id or _make_job_id()

    _ensure_debug_dir(cfg.debug)

    processed_images: List[np.ndarray] = []

    for page_idx, raw_bytes in enumerate(image_bytes_list):
        try:
            img = _decode_image(raw_bytes)
            if img is None:
                logger.warning(f"[pipeline] page {page_idx}: could not decode image — skipping")
                continue

            _save_debug(img, cfg.debug, job_id, page_idx, "original")
            logger.info(f"[pipeline] page {page_idx}: {img.shape[1]}x{img.shape[0]}")

            # Stage 1 — Detect
            detection = detect_document(img, cfg.detector)

            # Stage 2 — Crop
            img, _ = smart_crop(img, detection.polygon, cfg.cropper)
            _save_debug(img, cfg.debug, job_id, page_idx, "cropped")

            # Stage 3 — Perspective correction
            # Only apply warp if detection actually found a quadrilateral document
            if detection.success and not detection.fallback_used:
                img, corrected = correct_perspective(img, detection.polygon, cfg.corrector)
                if corrected:
                    _save_debug(img, cfg.debug, job_id, page_idx, "corrected")

            # Stage 4 — Enhancement
            img, _ = enhance(img, cfg.enhancer)
            _save_debug(img, cfg.debug, job_id, page_idx, "enhanced")

            processed_images.append(img)

        except Exception as exc:
            logger.error(f"[pipeline] page {page_idx} failed: {exc}", exc_info=True)
            # Fallback: use the original undecoded image if possible
            fallback = _safe_decode(raw_bytes)
            if fallback is not None:
                processed_images.append(fallback)
                logger.info(f"[pipeline] page {page_idx}: using original as fallback")

    if not processed_images:
        raise RuntimeError("[pipeline] all pages failed — cannot generate PDF")

    # Stage 5 — Build PDF
    pdf = build_pdf(processed_images, cfg.pdf)

    # Save final PDF debug copy
    if cfg.debug.enabled:
        debug_pdf_path = os.path.join(
            cfg.debug.output_dir, f"{job_id}_final.pdf"
        )
        try:
            pdf.seek(0)
            with open(debug_pdf_path, "wb") as f:
                f.write(pdf.read())
            pdf.seek(0)
            logger.info(f"[pipeline] debug PDF saved: {debug_pdf_path}")
        except Exception:
            pass

    logger.info(f"[pipeline] done  job={job_id}  pages={len(processed_images)}")
    return pdf


async def run_pipeline_async(
    image_bytes_list: List[bytes],
    config: Optional[PipelineConfig] = None,
    job_id: Optional[str] = None,
) -> io.BytesIO:
    """
    Async wrapper — runs the CPU-bound pipeline in a thread pool
    so it doesn't block the Telegram bot event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: run_pipeline(image_bytes_list, config, job_id),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_image(raw: bytes) -> Optional[np.ndarray]:
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _safe_decode(raw: bytes) -> Optional[np.ndarray]:
    try:
        return _decode_image(raw)
    except Exception:
        return None


def _save_debug(image: np.ndarray, debug_cfg, job_id: str, page: int, stage: str):
    if not debug_cfg.enabled:
        return
    try:
        filename = f"{job_id}_p{page:02d}_{stage}.jpg"
        path = os.path.join(debug_cfg.output_dir, filename)
        cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    except Exception:
        pass


def _ensure_debug_dir(debug_cfg):
    if debug_cfg.enabled:
        os.makedirs(debug_cfg.output_dir, exist_ok=True)


def _make_job_id() -> str:
    import time
    return f"job_{int(time.time() * 1000) % 10_000_000:07d}"
