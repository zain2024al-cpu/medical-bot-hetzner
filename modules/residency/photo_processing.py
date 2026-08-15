# modules/residency/photo_processing.py
# ضبط الصورة الشخصية على مقاس 4×6 (الصورة الشخصية القياسية للمستندات).
#
# 4 سم عرضاً × 6 سم ارتفاعاً (توجّه عمودي — الاصطلاح المعتاد لصور
# الجوازات/التأشيرات)، مُخرَجة عند 300 نقطة/إنش لجودة طباعة:
#   4 سم = 4 / 2.54 × 300 ≈ 472 بكسل
#   6 سم = 6 / 2.54 × 300 ≈ 709 بكسل

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

TARGET_WIDTH_PX  = 472
TARGET_HEIGHT_PX = 709
_TARGET_RATIO = TARGET_WIDTH_PX / TARGET_HEIGHT_PX


def resize_to_4x6(raw: bytes) -> bytes:
    """
    يقصّ الصورة من المنتصف لمطابقة نسبة 4:6 ثم يُصغّرها/يُكبّرها إلى المقاس
    الدقيق بالبكسل. القصّ (لا التمديد) يحافظ على تناسب الوجه بلا تشويه.

    يرفع الاستثناء عند فشل المعالجة — المتصل مسؤول عن قرار "احفظ الأصل
    كما هو" أو "أخبر المستخدم بالفشل"، فلا تُقرَّر هنا سياسة صامتة.
    """
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)  # يحترم دوران الكاميرا المسجَّل بالبيانات الوصفية
    img = img.convert("RGB")

    w, h = img.size
    src_ratio = w / h

    if src_ratio > _TARGET_RATIO:
        # أعرض من اللازم نسبةً — يُقصّ الجانبان
        new_w = round(h * _TARGET_RATIO)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    elif src_ratio < _TARGET_RATIO:
        # أطول من اللازم نسبةً — يُقصّ الأعلى والأسفل
        new_h = round(w / _TARGET_RATIO)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img = img.resize((TARGET_WIDTH_PX, TARGET_HEIGHT_PX), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, dpi=(300, 300))
    return out.getvalue()
