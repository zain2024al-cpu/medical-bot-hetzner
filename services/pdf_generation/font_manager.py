# ================================================
# services/pdf_generation/font_manager.py
# 🔤 إدارة خطوط PDF Builder
# ================================================

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


class FontManager:
    """Register a professional PDF font family with known variants."""

    FONT_FAMILY = "PDFArabic"
    FONT_VARIANTS = {
        "normal": ("Arabic-Regular.ttf", "PDFArabic-Regular"),
        "bold": ("Arabic-Bold.ttf", "PDFArabic-Bold"),
        "italic": ("Arabic-Regular.ttf", "PDFArabic-Italic"),
        "bolditalic": ("Arabic-Bold.ttf", "PDFArabic-BoldItalic"),
    }

    SYSTEM_FALLBACKS = {
        "normal": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ],
        "bold": [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ],
    }

    _fonts_registered = False

    @classmethod
    def _font_dir(cls) -> Path:
        return Path(__file__).resolve().parents[2] / "assets" / "fonts"

    @classmethod
    def _resolve_local_font(cls, filename: str) -> Optional[Path]:
        path = cls._font_dir() / filename
        return path if path.is_file() else None

    @classmethod
    def _find_system_fallback(cls, variant: str) -> Optional[Path]:
        candidates = cls.SYSTEM_FALLBACKS.get(variant, [])
        for candidate in candidates:
            if os.path.isfile(candidate):
                return Path(candidate)
        return None

    @classmethod
    def _get_variant_path(cls, variant: str) -> Optional[Path]:
        filename, _ = cls.FONT_VARIANTS[variant]
        path = cls._resolve_local_font(filename)
        if path:
            return path

        if variant in ("italic", "bolditalic"):
            fallback = "normal" if variant == "italic" else "bold"
            path = cls._resolve_local_font(cls.FONT_VARIANTS[fallback][0])
            if path:
                return path

        return cls._find_system_fallback("bold" if "bold" in variant else "normal")

    @classmethod
    def register_all_fonts(cls) -> None:
        if cls._fonts_registered:
            return

        registered_names: Dict[str, str] = {}

        for variant, (_, registered_name) in cls.FONT_VARIANTS.items():
            path = cls._get_variant_path(variant)
            if not path:
                continue

            if registered_name in pdfmetrics.getRegisteredFontNames():
                registered_names[variant] = registered_name
                continue

            try:
                pdfmetrics.registerFont(TTFont(registered_name, str(path)))
                registered_names[variant] = registered_name
            except Exception as exc:
                logger.warning(
                    f"⚠️ Failed to register PDF font '{registered_name}' from '{path}': {exc}"
                )

        if not registered_names.get("normal"):
            raise RuntimeError(
                "No valid PDF base font was registered for PDFBuilder. "
                "Ensure Arabic-Regular.ttf or a system fallback is available."
            )

        pdfmetrics.registerFontFamily(
            cls.FONT_FAMILY,
            normal=registered_names.get("normal", "PDFArabic-Regular"),
            bold=registered_names.get("bold", registered_names.get("normal")),
            italic=registered_names.get("italic", registered_names.get("normal")),
            boldItalic=registered_names.get("bolditalic", registered_names.get("bold", registered_names.get("normal"))),
        )

        cls._fonts_registered = True

    @classmethod
    def get_family_name(cls) -> str:
        return cls.FONT_FAMILY

    @classmethod
    def get_registered_font_names(cls) -> Dict[str, str]:
        return {variant: registered_name for variant, (_, registered_name) in cls.FONT_VARIANTS.items()}
