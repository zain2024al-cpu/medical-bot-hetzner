# image_pipeline/stages/detector.py
# Stage 1 — Document Detection
# Uses YOLOv8-seg to locate document polygon.
# Always falls back to full-image rectangle if model unavailable or fails.

import logging
import numpy as np
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    success: bool
    polygon: np.ndarray        # (N, 2) float32 pixel coords
    confidence: float
    fallback_used: bool
    message: str = ""


def detect_document(image: np.ndarray, cfg) -> DetectionResult:
    """
    Detect document boundary.
    Returns full-image rectangle on any failure.
    """
    if not cfg.enabled:
        return _full_image(image, "detector disabled")

    h, w = image.shape[:2]

    try:
        from ultralytics import YOLO
        model = _get_model(cfg.model_path)
        results = model(image, conf=cfg.confidence, iou=cfg.iou_threshold, verbose=False)
        best = _pick_best(results, h, w, cfg)

        if best is not None:
            logger.info(f"[detector] document found  conf={best['conf']:.2f}")
            return DetectionResult(
                success=True,
                polygon=best["polygon"],
                confidence=best["conf"],
                fallback_used=False,
            )

        logger.info("[detector] no confident detection — falling back to full image")
        return _full_image(image, "no confident detection")

    except ImportError:
        logger.warning("[detector] ultralytics not installed — using full image")
        return _full_image(image, "ultralytics not installed")
    except Exception as exc:
        logger.warning(f"[detector] {exc} — using full image fallback")
        if cfg.fallback_on_failure:
            return _full_image(image, str(exc))
        raise


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_model(path: str):
    if not hasattr(_get_model, "_cache"):
        _get_model._cache = {}
    if path not in _get_model._cache:
        from ultralytics import YOLO
        _get_model._cache[path] = YOLO(path)
    return _get_model._cache[path]


def _pick_best(results, h: int, w: int, cfg) -> Optional[dict]:
    image_area = h * w
    best = None
    best_area = 0.0

    for result in results:
        # --- segmentation masks (preferred) ---
        if result.masks is not None:
            for i, mask_xy in enumerate(result.masks.xy):
                if len(mask_xy) < 4:
                    continue
                conf = float(result.boxes.conf[i]) if result.boxes is not None else 1.0
                if conf < cfg.confidence:
                    continue
                poly = np.array(mask_xy, dtype=np.float32)
                x0, y0 = poly.min(axis=0)
                x1, y1 = poly.max(axis=0)
                area = (x1 - x0) * (y1 - y0)
                if area / image_area < cfg.min_area_ratio:
                    continue
                if area > best_area:
                    best_area = area
                    best = {"polygon": poly, "conf": conf}

        # --- bounding boxes only ---
        elif result.boxes is not None:
            for i, box in enumerate(result.boxes.xyxy):
                conf = float(result.boxes.conf[i])
                if conf < cfg.confidence:
                    continue
                x0, y0, x1, y1 = box.tolist()
                area = (x1 - x0) * (y1 - y0)
                if area / image_area < cfg.min_area_ratio:
                    continue
                if area > best_area:
                    best_area = area
                    poly = np.array(
                        [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float32
                    )
                    best = {"polygon": poly, "conf": conf}

    return best


def _full_image(image: np.ndarray, reason: str) -> DetectionResult:
    h, w = image.shape[:2]
    poly = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    return DetectionResult(
        success=False, polygon=poly, confidence=0.0, fallback_used=True, message=reason
    )
