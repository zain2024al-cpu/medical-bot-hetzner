# image_pipeline/stages/pdf_builder.py
# Stage 5 — PDF Generation
# Converts one or more enhanced images into a single PDF (BytesIO).
# Uses img2pdf for lossless-quality embedding, with PIL for format normalisation.

import io
import logging
import cv2
import numpy as np
from typing import List

logger = logging.getLogger(__name__)


def build_pdf(images: List[np.ndarray], cfg) -> io.BytesIO:
    """
    Convert a list of BGR numpy images into a single PDF.

    Args:
        images: list of BGR numpy arrays (one per page)
        cfg:    PDFConfig

    Returns:
        BytesIO containing the PDF, rewound to position 0
    """
    if not images:
        raise ValueError("build_pdf: no images provided")

    img_buffers = []

    for i, img in enumerate(images):
        buf = _image_to_jpeg_bytes(img, cfg)
        img_buffers.append(buf)
        logger.debug(f"[pdf_builder] page {i+1}: {len(buf)} bytes")

    try:
        import img2pdf
        pdf_bytes = img2pdf.convert(img_buffers)
        out = io.BytesIO(pdf_bytes)
        out.seek(0)
        logger.info(f"[pdf_builder] PDF generated  pages={len(images)}  size={len(pdf_bytes)/1024:.1f} KB")
        return out

    except ImportError:
        # Fallback: use Pillow to build a multi-page PDF
        logger.warning("[pdf_builder] img2pdf not installed — using Pillow fallback")
        return _pillow_pdf_fallback(img_buffers)


def _image_to_jpeg_bytes(image: np.ndarray, cfg) -> bytes:
    """
    Convert BGR numpy array → JPEG bytes.
    Handles large images by downscaling while preserving aspect ratio.
    """
    from PIL import Image as PILImage

    h, w = image.shape[:2]
    max_px = cfg.max_dimension_px

    # Downscale only if needed (never upscale)
    if max(h, w) > max_px:
        scale = max_px / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        logger.debug(f"[pdf_builder] resized {w}x{h} → {new_w}x{new_h}")

    # BGR → RGB for PIL
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_img = PILImage.fromarray(rgb)

    # Ensure RGB (no alpha)
    if pil_img.mode not in ("RGB",):
        pil_img = pil_img.convert("RGB")

    buf = io.BytesIO()
    pil_img.save(
        buf,
        format="JPEG",
        quality=cfg.jpeg_quality,
        subsampling=cfg.jpeg_subsampling,
        optimize=True,
    )
    return buf.getvalue()


def _pillow_pdf_fallback(jpeg_buffers: List[bytes]) -> io.BytesIO:
    """Fallback PDF builder using Pillow (no img2pdf needed)."""
    from PIL import Image as PILImage

    pages = [PILImage.open(io.BytesIO(b)).convert("RGB") for b in jpeg_buffers]
    out = io.BytesIO()
    if len(pages) == 1:
        pages[0].save(out, format="PDF")
    else:
        pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:])
    out.seek(0)
    return out
