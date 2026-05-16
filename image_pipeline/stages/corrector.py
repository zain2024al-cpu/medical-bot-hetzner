# image_pipeline/stages/corrector.py
# Stage 3 — Perspective & Rotation Correction
# Uses OpenCV only. Conservative: skips correction if tilt looks extreme.

import logging
import cv2
import numpy as np
from typing import Tuple

logger = logging.getLogger(__name__)


def correct_perspective(
    image: np.ndarray,
    polygon: np.ndarray,
    cfg,
) -> Tuple[np.ndarray, bool]:
    """
    Apply perspective warp to straighten the document.
    polygon should be the 4-corner convex hull of the detected document.

    Returns:
        (corrected_image, was_corrected)
    """
    if not cfg.enabled:
        return image, False

    try:
        corners = _get_four_corners(polygon)
        if corners is None:
            return image, False

        # Measure how much tilt/warp exists
        tilt_deg = _estimate_tilt(corners)
        if tilt_deg > cfg.max_warp_angle_deg:
            logger.info(f"[corrector] tilt {tilt_deg:.1f}° > max — skipping")
            return image, False

        h, w = image.shape[:2]
        image_area = h * w
        quad_area = _quad_area(corners)
        if quad_area / image_area < cfg.min_quad_area_ratio:
            logger.info(f"[corrector] quad too small ({quad_area/image_area:.2f}) — skipping")
            return image, False

        # Order corners: top-left, top-right, bottom-right, bottom-left
        ordered = _order_corners(corners)
        dst_w, dst_h = _output_size(ordered)

        dst_pts = np.array([
            [0, 0],
            [dst_w - 1, 0],
            [dst_w - 1, dst_h - 1],
            [0, dst_h - 1],
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(ordered.astype(np.float32), dst_pts)
        warped = cv2.warpPerspective(
            image, M, (dst_w, dst_h),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_REPLICATE,
        )

        logger.info(f"[corrector] perspective corrected  tilt={tilt_deg:.1f}°  out={dst_w}x{dst_h}")
        return warped, True

    except Exception as exc:
        logger.warning(f"[corrector] {exc} — returning original")
        return image, False


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_four_corners(polygon: np.ndarray) -> np.ndarray:
    """
    Reduce an arbitrary polygon to exactly 4 corners via convex hull + Douglas–Peucker.
    Returns None if we can't get exactly 4.
    """
    if polygon.shape[0] == 4:
        return polygon

    hull = cv2.convexHull(polygon.reshape(-1, 1, 2).astype(np.float32))
    hull = hull.reshape(-1, 2)

    # Try different epsilon values to get 4 corners
    for eps_factor in [0.02, 0.05, 0.08, 0.12]:
        peri = cv2.arcLength(hull.reshape(-1, 1, 2).astype(np.float32), True)
        approx = cv2.approxPolyDP(
            hull.reshape(-1, 1, 2).astype(np.float32),
            eps_factor * peri,
            True,
        )
        if len(approx) == 4:
            return approx.reshape(-1, 2).astype(np.float32)

    return None


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def _output_size(ordered: np.ndarray) -> Tuple[int, int]:
    """Compute output width/height from ordered corners."""
    tl, tr, br, bl = ordered
    w1 = np.linalg.norm(br - bl)
    w2 = np.linalg.norm(tr - tl)
    w = max(int(w1), int(w2))
    h1 = np.linalg.norm(tr - br)
    h2 = np.linalg.norm(tl - bl)
    h = max(int(h1), int(h2))
    return w, h


def _estimate_tilt(corners: np.ndarray) -> float:
    """Estimate the maximum tilt angle of the document in degrees."""
    ordered = _order_corners(corners)
    tl, tr, _, _ = ordered
    dx = float(tr[0] - tl[0])
    dy = float(tr[1] - tl[1])
    if dx == 0:
        return 90.0
    return abs(float(np.degrees(np.arctan(dy / dx))))


def _quad_area(corners: np.ndarray) -> float:
    """Shoelace formula for quadrilateral area."""
    n = len(corners)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += corners[i][0] * corners[j][1]
        area -= corners[j][0] * corners[i][1]
    return abs(area) / 2.0
