# ================================================
# services/pdf_generation/pdf_tables.py
# 📊 رسم الجداول الاحترافية
# ================================================

import logging
from typing import List, Dict, Any
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.units import mm, cm, inch

from .pdf_styles import PDFColors

logger = logging.getLogger(__name__)


class TableRenderer:
    """رسم الجداول بشكل احترافي وموحد"""
    
    @staticmethod
    def create_table(
        headers: List[str],
        rows: List[List[Any]],
        title: str = "",
        col_widths: List[float] = None,
    ) -> Table:
        """
        إنشاء جدول احترافي
        
        Args:
            headers: رؤوس الأعمدة
            rows: البيانات
            title: عنوان الجدول
            col_widths: عرض الأعمدة
            
        Returns:
            Table object
        """
        
        logger.info(f"📊 إنشاء جدول: {title}")
        
        # إضافة الرؤوس
        data = [headers] + rows
        
        # إعدادات الألوان والأنماط
        style = [
            # ستايل الرؤوس
            ('BACKGROUND', (0, 0), (-1, 0), PDFColors.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Tahoma'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # ستايل الخلايا
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, -1), 'Tahoma'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, PDFColors.LIGHT_BG]),
            ('GRID', (0, 0), (-1, -1), 1, PDFColors.GRID),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            
            # RTL للنصوص العربية
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ]
        
        # إذا كان هناك صف تذييل
        if len(rows) > 1:
            # آخر صف بلون مختلف (اختياري)
            pass
        
        # إنشاء الجدول
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle(style))
        
        logger.info(f"✅ تم إنشاء جدول بـ {len(rows)} صف")
        return table
    
    @staticmethod
    def create_summary_table(
        metrics: List[Dict[str, str]],
    ) -> Table:
        """
        إنشاء جدول ملخص المؤشرات
        
        Args:
            metrics: قائمة المؤشرات
            
        Returns:
            Table object
        """
        
        logger.info("📊 إنشاء جدول المؤشرات")
        
        data = []
        for metric in metrics:
            data.append([
                metric.get("icon", ""),
                metric.get("label", ""),
                metric.get("value", ""),
            ])
        
        style = [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Tahoma'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BACKGROUND', (0, 0), (-1, -1), PDFColors.LIGHT_BG),
            ('GRID', (0, 0), (-1, -1), 1, PDFColors.GRID),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]
        
        table = Table(data, colWidths=[40, 150, 100])
        table.setStyle(TableStyle(style))
        
        return table
