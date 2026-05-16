# image_pipeline/stages/cropper.py
# Stage 2 — Smart Crop
# Crops the image to the detected document polygon with safe padding.
# Never cuts closer than safe_margin_px to the image border.

import logging
import cv2
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


def smart_crop(
    image: np.ndarray,
    polygon: np.ndarray,
    cfg,
) -> Tuple[np.ndarray, bool]:
    """
    Crop image to the bounding box of polygon with padding.

    Returns:
        (cropped_image, did_crop)
        did_crop=False means the full image was returned unchanged.
    """
    if not cfg.enabled:
        return image, False

    h, w = image.shape[:2]

    try:
        x0 = float(polygon[:, 0].min())
        y0 = float(polygon[:, 1].min())
        x1 = float(polygon[:, 0].max())
        y1 = float(polygon[:, 1].max())

        # Add proportional padding
        pad_x = (x1 - x0) * cfg.padding_ratio
        pad_y = (y1 - y0) * cfg.padding_ratio

        # Clamp to image dimensions while respecting safe margin
        margin = cfg.safe_margin_px
        x0 = max(margin, int(x0 - pad_x))
        y0 = max(margin, int(y0 - pad_y))
        x1 = min(w - margin, int(x1 + pad_x))
        y1 = min(h - margin, int(y1 + pad_y))

        crop_w = x1 - x0
        crop_h = y1 - y0

        # Sanity check — crop must be meaningful
        if crop_w < 64 or crop_h < 64:
            logger.warning("[cropper] crop too small — returning full image")
            return image, False

        cropped = image[y0:y1, x0:x1]
        logger.info(f"[cropper] cropped {w}x{h} → {crop_w}x{crop_h}")
        return cropped, True

    except Exception as exc:
        logger.warning(f"[cropper] {exc} — returning full image")
        return image, False
