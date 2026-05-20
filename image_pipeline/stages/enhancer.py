# image_pipeline/stages/enhancer.py
# Stage 4 — Adaptive Conservative Document Enhancement
#
# Design rules:
#   - Preserve Arabic text, handwriting, stamps, signatures, colored ink
#   - No black backgrounds, no aggressive thresholding, no over-sharpening
#   - Output must look like a naturally photographed document, NOT a scanner output
#   - Enhancement strength adapts to measured image quality (high / medium / poor)
#
# Pipeline per image:
#   1. Quality assessment  → tier: 'high' | 'medium' | 'poor'
#   2. Illumination blend  → partial normalisation (blended with original)
#   3. CLAHE               → mild local contrast on L channel only
#   4. NLMeans denoise     → only when noise is significant
#   5. Unsharp mask        → very mild, only for medium/poor tiers
#   6. Gamma correction    → optional global brightness tweak

import logging
import cv2
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier parameter table
# Each tier defines the maximum aggressiveness allowed.
# 'illum_blend' controls how much the illumination-normalised image is blended
# into the original: 0.0 = skip normalisation, 1.0 = full replacement.
# ---------------------------------------------------------------------------
_TIER_PARAMS = {
    'high': {
        # Well-lit, good contrast, low noise — touch as little as possible
        'clahe_clip_limit': 0.8,
        'denoise_strength': 0,      # skip — would only blur handwriting
        'sharpen_strength': 0.0,    # skip — image is already clear
        'illum_blend': 0.20,        # barely normalise; preserve natural paper tone
    },
    'medium': {
        # Typical WhatsApp-compressed phone photo
        'clahe_clip_limit': 1.2,
        'denoise_strength': 3,
        'sharpen_strength': 0.12,
        'illum_blend': 0.45,
    },
    'poor': {
        # Dark, noisy, heavy compression or strong shadows
        'clahe_clip_limit': 1.8,
        'denoise_strength': 5,
        'sharpen_strength': 0.22,
        'illum_blend': 0.65,
    },
}


def enhance(image: np.ndarray, cfg) -> Tuple[np.ndarray, bool]:
    """
    Apply adaptive enhancement to a BGR image.

    Returns:
        (enhanced_image, was_enhanced)
    """
    if not cfg.enabled:
        return image, False

    try:
        quality = _assess_quality(image)
        tier = quality['tier']
        logger.info(
            f"[enhancer] tier={tier}  brightness={quality['mean_brightness']:.0f}"
            f"  contrast={quality['contrast']:.0f}  noise={quality['noise_level']:.3f}"
        )

        if cfg.adaptive_enhance:
            p = _TIER_PARAMS[tier]
        else:
            p = {
                'clahe_clip_limit': cfg.clahe_clip_limit,
                'denoise_strength': cfg.denoise_strength,
                'sharpen_strength': cfg.sharpen_strength,
                'illum_blend': cfg.illum_blend,
            }

        img = image.copy()

        if cfg.illumination_normalize and p['illum_blend'] > 0.0:
            img = _normalize_illumination(img, blend_alpha=p['illum_blend'])

        img = _clahe_enhancement(img, p['clahe_clip_limit'], tuple(cfg.clahe_tile_grid))

        if p['denoise_strength'] > 0:
            img = _denoise(img, p['denoise_strength'])

        if p['sharpen_strength'] > 0.0:
            img = _mild_sharpen(img, p['sharpen_strength'])

        if cfg.gamma != 1.0:
            img = _gamma_correction(img, cfg.gamma)

        logger.info(f"[enhancer] done  tier={tier}  clip={p['clahe_clip_limit']}"
                    f"  denoise={p['denoise_strength']}  sharpen={p['sharpen_strength']}")
        return img, True

    except Exception as exc:
        logger.warning(f"[enhancer] {exc} — returning original")
        return image, False


# ---------------------------------------------------------------------------
# Quality assessment
# ---------------------------------------------------------------------------

def _assess_quality(image: np.ndarray) -> dict:
    """
    Measure image quality and return a tier classification.

    Metrics (all computed on the L channel of LAB colour space):
      mean_brightness  — overall scene brightness
      contrast         — std-dev of luminance; low = flat/washed out
      noise_level      — mean absolute deviation from 5×5 Gaussian; high = noisy

    Tier rules:
      high   — bright paper, decent contrast, clean image
      poor   — dark OR very flat OR noisy
      medium — everything else
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_ch = lab[:, :, 0].astype(np.float32)

    mean_L = float(np.mean(l_ch))
    std_L = float(np.std(l_ch))

    blurred = cv2.GaussianBlur(l_ch, (5, 5), 0)
    noise_level = float(np.mean(np.abs(l_ch - blurred))) / 255.0

    if mean_L >= 155 and std_L >= 32 and noise_level < 0.035:
        tier = 'high'
    elif mean_L < 100 or std_L < 18 or noise_level > 0.07:
        tier = 'poor'
    else:
        tier = 'medium'

    return {
        'tier': tier,
        'mean_brightness': mean_L,
        'contrast': std_L,
        'noise_level': noise_level,
    }


# ---------------------------------------------------------------------------
# Processing steps
# ---------------------------------------------------------------------------

def _normalize_illumination(image: np.ndarray, blend_alpha: float) -> np.ndarray:
    """
    Estimate background illumination via a large Gaussian blur, then divide
    to flatten uneven lighting. The result is *blended* back with the original
    so that natural paper texture and tone are retained.

    blend_alpha=0.0 → pure original (no change)
    blend_alpha=1.0 → fully normalised (aggressive; avoid for good-quality images)
    """
    img_f = image.astype(np.float32)

    kernel = 2 * (max(image.shape[:2]) // 10) + 1
    kernel = max(kernel, 51)
    blurred = cv2.GaussianBlur(img_f, (kernel, kernel), 0)
    blurred = np.maximum(blurred, 1.0)

    mean_lum = np.mean(blurred)
    normalised = np.clip(img_f / blurred * mean_lum, 0, 255).astype(np.uint8)

    # Blend: keep (1-alpha) of original to preserve natural paper appearance
    result = cv2.addWeighted(image, 1.0 - blend_alpha, normalised, blend_alpha, 0)
    return result


def _clahe_enhancement(image: np.ndarray, clip_limit: float, tile_grid: tuple) -> np.ndarray:
    """
    CLAHE on L channel only — preserves colours (stamps, ink) while improving
    local contrast. Result is blended with original at low clip values to
    further reduce the risk of over-processing.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    l_enhanced = clahe.apply(l)

    enhanced_lab = cv2.merge([l_enhanced, a, b])
    result = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # For very mild clip limits, blend with original to keep a natural feel
    if clip_limit <= 1.0:
        blend = clip_limit  # e.g. clip=0.8 → 80% enhanced, 20% original
        result = cv2.addWeighted(image, 1.0 - blend, result, blend, 0)

    return result


def _denoise(image: np.ndarray, strength: int) -> np.ndarray:
    """
    Non-local means denoise. Strength 1–10 maps to h=3–6.
    Kept deliberately low so fine pen strokes and handwriting survive.
    h ≤ 5 is nearly invisible; h > 8 visibly blurs handwriting.
    """
    h_val = int(3 + (strength / 10.0) * 3)   # max h=6 even at strength=10
    return cv2.fastNlMeansDenoisingColored(image, None, h_val, h_val, 7, 21)


def _mild_sharpen(image: np.ndarray, strength: float) -> np.ndarray:
    """
    Unsharp mask: result = image + strength * (image − blur)
    strength ≤ 0.25 keeps a natural look.
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
