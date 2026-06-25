# ================================================
# services/pdf_generation/pdf_builder.py
# 🎨 PDF Builder احترافي
# ================================================

import logging
import io
from datetime import datetime
from typing import Optional, List

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.units import mm, cm
# reportlab may not expose `pt` on all versions; define locally as 1 point
pt = 1.0
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle

from services.reporting_engine.report_data import ReportData
from .pdf_styles import PDFConfig, PDFColors, FONT_FAMILY, get_styles, setup_arabic_fonts
from .pdf_tables import TableRenderer
from .pdf_charts import ChartRenderer
from .pdf_renderer_arabic import ArabicTextRenderer

logger = logging.getLogger(__name__)


class PDFBuilder:
    """
    PDF Builder احترافي ومستقل
    
    يتولى:
    1. بناء صفحة الغلاف
    2. رسم الجداول
    3. رسم الرسوم البيانية
    4. ترقيم الصفحات
    5. Header و Footer موحدة
    """
    
    def __init__(self):
        logger.info("🎨 تهيئة PDF Builder")
        setup_arabic_fonts()
        self.styles = get_styles()
        self.elements = []
        self.arabic_renderer = ArabicTextRenderer()
    
    def build_from_report_data(self, report_data: ReportData) -> io.BytesIO:
        """
        بناء PDF كامل من ReportData
        
        Args:
            report_data: بيانات التقرير
            
        Returns:
            BytesIO object
        """
        
        logger.info(f"🔨 بناء PDF للتقرير: {report_data.title}")
        
        # مسح العناصر السابقة
        self.elements = []
        
        try:
            # 1. صفحة الغلاف
            logger.info("📄 إضافة صفحة الغلاف")
            self._add_cover_page(report_data)
            self.elements.append(PageBreak())
            
            # 2. ملخص تنفيذي
            if report_data.executive_summary:
                logger.info("📝 إضافة الملخص التنفيذي")
                self._add_executive_summary(report_data)
                self.elements.append(PageBreak())
            
            # 3. المؤشرات الرئيسية
            if report_data.key_metrics:
                logger.info("📊 إضافة المؤشرات الرئيسية")
                self._add_key_metrics(report_data)
                self.elements.append(Spacer(1, 12*pt))
            
            # 4. الجداول
            if report_data.tables:
                logger.info("📋 إضافة الجداول")
                self._add_tables(report_data)
                self.elements.append(PageBreak())
            
            # 5. الرسوم البيانية
            if report_data.charts:
                logger.info("📈 إضافة الرسوم البيانية")
                self._add_charts(report_data)
                self.elements.append(PageBreak())
            
            # 6. التسلسل الزمني
            if report_data.timeline:
                logger.info("⏱️ إضافة التسلسل الزمني")
                self._add_timeline(report_data)
                self.elements.append(PageBreak())
            
            # 7. التفاصيل
            if report_data.detailed_rows:
                logger.info("📑 إضافة التفاصيل")
                self._add_details(report_data)
                self.elements.append(PageBreak())
            
            # 8. الخاتمة
            if report_data.conclusion:
                logger.info("🏁 إضافة الخاتمة")
                self._add_conclusion(report_data)
            
            # بناء PDF
            logger.info("🔧 بناء ملف PDF")
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=PDFConfig.MARGIN_RIGHT,
                leftMargin=PDFConfig.MARGIN_LEFT,
                topMargin=PDFConfig.MARGIN_TOP,
                bottomMargin=PDFConfig.MARGIN_BOTTOM,
            )
            
            doc.build(self.elements)
            buffer.seek(0)
            
            logger.info(f"✅ تم بناء PDF بنجاح")
            return buffer
        
        except Exception as e:
            logger.error(f"❌ خطأ في بناء PDF: {e}", exc_info=True)
            raise
    
    def _add_cover_page(self, report_data: ReportData):
        """إضافة صفحة الغلاف"""
        
        # عنوان
        title_para = Paragraph(
            f"<b>{self.arabic_renderer.reshape_text(report_data.title)}</b>",
            self.styles['ArabicTitle']
        )
        self.elements.append(title_para)
        self.elements.append(Spacer(1, 20*pt))
        
        # عنوان فرعي
        if report_data.subtitle:
            subtitle_para = Paragraph(
                self.arabic_renderer.reshape_text(report_data.subtitle),
                self.styles['ArabicHeading']
            )
            self.elements.append(subtitle_para)
            self.elements.append(Spacer(1, 20*pt))
        
        # البيانات الوصفية
        metadata_text = f"""
        <b>نوع التقرير:</b> {report_data.report_type.value}<br/>
        <b>الفترة:</b> {report_data.period}<br/>
        <b>تاريخ الإنشاء:</b> {report_data.created_at.strftime('%Y-%m-%d %H:%M')}<br/>
        <b>أنشأه:</b> {report_data.created_by}
        """
        metadata_para = Paragraph(metadata_text, self.styles['ArabicBody'])
        self.elements.append(metadata_para)
    
    def _add_executive_summary(self, report_data: ReportData):
        """إضافة الملخص التنفيذي"""
        
        heading = Paragraph("📝 الملخص التنفيذي", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        if report_data.executive_summary:
            summary_para = Paragraph(
                self.arabic_renderer.reshape_text(report_data.executive_summary),
                self.styles['ArabicBody']
            )
            self.elements.append(summary_para)
        
        self.elements.append(Spacer(1, 12*pt))
    
    def _add_key_metrics(self, report_data: ReportData):
        """إضافة المؤشرات الرئيسية"""
        
        heading = Paragraph("📊 المؤشرات الرئيسية", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        # إنشاء جدول المؤشرات
        metrics_data = []
        for metric in report_data.key_metrics:
            metrics_data.append([
                metric.icon,
                self.arabic_renderer.reshape_text(metric.label),
                f"<b>{metric.value}</b> {metric.unit}",
            ])
        
        if metrics_data:
            metrics_table = Table(
                metrics_data,
                colWidths=[30*mm, 80*mm, 50*mm]
            )
            
            metrics_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), PDFColors.LIGHT_BG),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 0), (-1, -1), FONT_FAMILY),
            ]))
            
            self.elements.append(metrics_table)
    
    def _add_tables(self, report_data: ReportData):
        """إضافة الجداول"""
        
        heading = Paragraph("📋 الجداول الإحصائية", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        for table_data in report_data.tables:
            # عنوان الجدول
            table_title = Paragraph(
                f"<b>{self.arabic_renderer.reshape_text(table_data.title)}</b>",
                self.styles['ArabicSubHeading']
            )
            self.elements.append(table_title)
            self.elements.append(Spacer(1, 6*pt))
            
            # الجدول
            table = TableRenderer.create_table(
                headers=table_data.headers,
                rows=table_data.rows,
                title=table_data.title,
            )
            self.elements.append(table)
            self.elements.append(Spacer(1, 12*pt))
    
    def _add_charts(self, report_data: ReportData):
        """إضافة الرسوم البيانية"""
        
        heading = Paragraph("📈 الرسوم البيانية", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        for chart in report_data.charts:
            # عنوان الرسم
            chart_title = Paragraph(
                f"<b>{self.arabic_renderer.reshape_text(chart.title)}</b>",
                self.styles['ArabicSubHeading']
            )
            self.elements.append(chart_title)
            self.elements.append(Spacer(1, 6*pt))

            # إنتاج صورة الرسم بناءً على النوع
            try:
                if chart.type == 'bar':
                    img_buffer = ChartRenderer.create_bar_chart(
                        labels=chart.data.get('labels', []),
                        values=chart.data.get('values', []),
                        title=chart.title,
                    )
                elif chart.type == 'pie':
                    img_buffer = ChartRenderer.create_pie_chart(
                        labels=chart.data.get('labels', []),
                        values=chart.data.get('values', []),
                        title=chart.title,
                    )
                elif chart.type == 'line':
                    img_buffer = ChartRenderer.create_line_chart(
                        x_data=chart.data.get('x', []),
                        y_data=chart.data.get('y', []),
                        title=chart.title,
                    )
                else:
                    img_buffer = None

                if img_buffer:
                    # إدراج الصورة في المستند
                    img = Image(img_buffer)
                    # ضبط العرض والارتفاع بحسب إعدادات PDFConfig
                    try:
                        img.drawWidth = PDFConfig.CHART_WIDTH
                        img.drawHeight = PDFConfig.CHART_HEIGHT
                    except Exception:
                        pass
                    self.elements.append(img)
                    self.elements.append(Spacer(1, 12*pt))

            except Exception as e:
                logger.error(f"خطأ في توليد/إدراج الرسم البياني: {e}", exc_info=True)
    
    def _add_timeline(self, report_data: ReportData):
        """إضافة التسلسل الزمني"""
        
        heading = Paragraph("⏱️ التسلسل الزمني", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        # تحويل بيانات التسلسل الزمني إلى جدول
        timeline_rows = []
        for item in report_data.timeline:
            timeline_rows.append([
                item.date,
                self.arabic_renderer.reshape_text(item.title),
                self.arabic_renderer.reshape_text(item.description),
            ])
        
        if timeline_rows:
            timeline_table = Table(
                timeline_rows,
                colWidths=[40*mm, 50*mm, 70*mm]
            )
            timeline_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), FONT_FAMILY),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, PDFColors.GRID),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            self.elements.append(timeline_table)
    
    def _add_details(self, report_data: ReportData):
        """إضافة التفاصيل"""
        
        heading = Paragraph("📑 التفاصيل", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        # تحويل الصفوف التفصيلية إلى جدول
        rows = []
        for row in report_data.detailed_rows:
            table_row = []
            for header in report_data.detailed_headers:
                value = row.data.get(header, "")
                table_row.append(str(value) if value else "-")
            rows.append(table_row)
        
        if rows:
            details_table = TableRenderer.create_table(
                headers=report_data.detailed_headers,
                rows=rows,
                title="التفاصيل الكاملة",
            )
            self.elements.append(details_table)
    
    def _add_conclusion(self, report_data: ReportData):
        """إضافة الخاتمة"""
        
        heading = Paragraph("🏁 الخاتمة", self.styles['ArabicHeading'])
        self.elements.append(heading)
        self.elements.append(Spacer(1, 10*pt))
        
        conclusion_para = Paragraph(
            self.arabic_renderer.reshape_text(report_data.conclusion),
            self.styles['ArabicBody']
        )
        self.elements.append(conclusion_para)
        
        # تذييل
        self.elements.append(Spacer(1, 20*pt))
        footer_text = f"تم إنشاء هذا التقرير بواسطة نظام التقارير - {datetime.now().strftime('%Y-%m-%d')}"
        footer_para = Paragraph(footer_text, self.styles['ArabicSmall'])
        self.elements.append(footer_para)
