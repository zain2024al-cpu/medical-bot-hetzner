# ================================================
# services/pdf_generation/pdf_renderer_arabic.py
# 🌍 معالج العربية للـ PDF
# ================================================

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ArabicTextRenderer:
    """معالج العربية والنصوص RTL"""
    
    @staticmethod
    def reshape_text(text: str) -> str:
        """
        تشكيل النصوص العربية
        
        Args:
            text: النص الأصلي
            
        Returns:
            النص المشكل
        """
        try:
            import re
            from arabic_reshaper import reshape
            from bidi.algorithm import get_display

            if not text:
                return text

            s = str(text)
            # ⚠️ النص الخالي من العربية يُعاد كما هو — تمرير تاريخ مثل
            # "2026/07/01 — 2026/08/05" عبر get_display بأساس RTL يقلب
            # ترتيب التاريخين فعلياً.
            if not re.search(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]", s):
                return s

            # ⚠️ base_dir="R" صراحةً — بدونه تستنتج المكتبة الاتجاه من أول
            # حرف قوي، فنص مثل "500mg باراسيتامول" (اسم دواء لاتيني أولاً)
            # يُعامَل كفقرة LTR فيظهر جزؤه العربي في الطرف الخاطئ ويبدو
            # معكوساً، بينما جاره العربي الصرف يظهر سليماً.
            return get_display(reshape(s), base_dir="R")
        except ImportError:
            logger.warning("⚠️ مكتبات العربية غير متوفرة")
            return text
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة النصوص العربية: {e}")
            return text
    
    @staticmethod
    def apply_bidi_algorithm(text: str) -> str:
        """تطبيق خوارزمية BiDi"""
        return ArabicTextRenderer.reshape_text(text)
    
    @staticmethod
    def escape_html_entities(text: str) -> str:
        """تجنب أحرف HTML الخاصة"""
        if not text:
            return text
        
        replacements = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }
        
        for char, entity in replacements.items():
            text = text.replace(char, entity)
        
        return text
    
    @staticmethod
    def fit_text_to_width(text: str, max_width: int, ellipsis: str = "...") -> str:
        """ملاءمة النص للعرض المحدد"""
        if len(text) <= max_width:
            return text
        
        return text[:max_width - len(ellipsis)] + ellipsis
