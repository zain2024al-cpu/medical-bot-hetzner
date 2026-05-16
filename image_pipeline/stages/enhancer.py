# image_pipeline/stages/enhancer.py
# Stage 4 — Conservative Document Enhancement
#
# Design rules:
#   - Preserve Arabic text, handwriting, stamps, signatures
#   - No black backgrounds
#   - No aggressive thresholding
#   - No over-sharpening
#   - Output must look naturally scanned, not processed
#
# Pipeline:
#   1. Illumination normalisation (divide by blurred background)
#   2. CLAHE contrast enhancement (mild)
#   3. NLMeans denoise (low strength)
#   4. Unsharp mask (very mild)
#   5. Gamma correction

import logging
import cv2
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


def enhance(image: np.ndarray, cfg) -> Tuple[np.ndarray, bool]:
    """
    Apply conservative enhancement pipeline to a BGR image.

    Returns:
        (enhanced_image, was_enhanced)
    """
    if not cfg.enabled:
        return image, False

    try:
        img = image.copy()

        if cfg.illumination_normalize:
            img = _normalize_illumination(img)

        img = _clahe_enhancement(img, cfg)

        if cfg.denoise_strength > 0:
            img = _denoise(img, cfg.denoise_strength)

        if cfg.sharpen_strength > 0:
            img = _mild_sharpen(img, cfg.sharpen_strength)

        if cfg.gamma != 1.0:
            img = _gamma_correction(img, cfg.gamma)

        logger.info("[enhancer] enhancement applied")
        return img, True

    except Exception as exc:
        logger.warning(f"[enhancer] {exc} — returning original")
        return image, False


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _normalize_illumination(image: np.ndarray) -> np.ndarray:
    """
    Divide each channel by a heavily blurred version to remove
    uneven lighting (phone shadows, fold shadows).
    Result stays in natural colour range.
    """
    # Work in float
    img_f = image.astype(np.float32)

    # Large Gaussian blur = estimated background illumination
    kernel = 2 * (max(image.shape[:2]) // 10) + 1  # ~10% of image size, odd
    kernel = max(kernel, 51)
    blurred = cv2.GaussianBlur(img_f, (kernel, kernel), 0)

    # Avoid division by zero
    blurred = np.maximum(blurred, 1.0)

    # Normalise: result ≈ image / illumination * mean_illumination
    mean_lum = np.mean(blurred)
    normalised = img_f / blurred * mean_lum

    # Clip to [0, 255] without hard clipping artefacts
    normalised = np.clip(normalised, 0, 255).astype(np.uint8)
    return normalised


def _clahe_enhancement(image: np.ndarray, cfg) -> np.ndarray:
    """
    CLAHE on L channel (LAB) only — preserves colour, improves local contrast.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(
        clipLimit=cfg.clahe_clip_limit,
        tileGridSize=tuple(cfg.clahe_tile_grid),
    )
    l_enhanced = clahe.apply(l)

    enhanced_lab = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)


def _denoise(image: np.ndarray, strength: int) -> np.ndarray:
    """
    Non-local means denoise. Low strength preserves fine strokes.
    h=5 is borderline invisible; h=10 starts blurring handwriting.
    """
    # strength is 1–10; map to h parameter (3–8)
    h_val = int(3 + (strength / 10.0) * 5)
    return cv2.fastNlMeansDenoisingColored(image, None, h_val, h_val, 7, 21)


def _mild_sharpen(image: np.ndarray, strength: float) -> np.ndarray:
    """
    Unsharp mask — standard formula: result = image + strength * (image - blur)
    Strength 0.25 = very mild, good for WhatsApp-compressed images.
    """
    blur = cv2.GaussianBlur(image, (0, 0), sigmaX=1.5)
    sharpened = cv2.addWeighted(image, 1.0 + strength, blur, -strength, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def _gamma_correction(image: np.ndarray, gamma: float) -> np.ndarray:
    """LUT-based gamma correction — fast on CPU."""
    inv_gamma = 1.0 / gamma
    table = np.array(
        [((i / 255.0) ** inv_gamma) * 255 for i in range(256)], dtype=np.uint8
    )
    return cv2.LUT(image, table)
