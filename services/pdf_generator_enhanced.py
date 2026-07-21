#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 PDF Generator Enhanced - مولد PDF بجداول احترافية
يُنشئ تقارير تحليل البيانات بجداول منظمة ومنسقة
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

# ✅ استيراد WeasyPrint حسب نظام التشغيل
if sys.platform.startswith('win'):
    # Windows: نستخدم ReportLab بدلاً من WeasyPrint
    WEASYPRINT_AVAILABLE = False
    logger.warning("⚠️ WeasyPrint معطل على Windows - استخدام ReportLab بدلاً منه")
else:
    # Linux/Mac: استخدام WeasyPrint
    try:
        from weasyprint import HTML, CSS
        WEASYPRINT_AVAILABLE = True
    except Exception as e:
        # ✅ Exception كاملة وليس ImportError فقط — نقص مكتبة نظام (libpango)
        # يرمي OSError، وكان يتسرّب ويُسقط استيراد الوحدة.
        WEASYPRINT_AVAILABLE = False
        HTML = None
        CSS = None
        logger.warning(f"⚠️ WeasyPrint غير متوفر ({type(e).__name__}: {e})")

# المسارات (مطلقة لضمان توفر القوالب داخل Docker)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = str(BASE_DIR / "templates")
OUTPUT_DIR = str(BASE_DIR / "exports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# إعدادات PDF - عرضي
DEFAULT_PDF_OPTIONS = {
    'enable-local-file-access': None,
    'print-media-type': None,
    'encoding': 'UTF-8',
    'page-size': 'A4',
    'orientation': 'Landscape',
    'margin-top': '1.5cm',
    'margin-right': '2cm',
    'margin-bottom': '1.5cm',
    'margin-left': '2cm',
    'dpi': 300,
    'no-outline': None,
    'quiet': None,
}

# ====================================================
# 📊 إنشاء PDF بجداول احترافية
# ====================================================

async def generate_data_analysis_pdf_with_tables(
    analysis_data: Dict[str, Any],
    ai_insights: Optional[str] = None,
    charts: Optional[Dict] = None
) -> str:
    """
    إنشاء تقرير PDF بجداول احترافية لتحليل البيانات
    
    Args:
        analysis_data: بيانات التحليل
        ai_insights: رؤى AI (اختياري)
        charts: رسوم بيانية (اختياري)
    
    Returns:
        str: مسار ملف PDF
    """
    try:
        logger.info("📊 Generating PDF with tables...")
        
        # تحميل القالب الاحترافي المحسّن
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template('data_analysis_professional.html')
        
        # تجهيز البيانات
        context = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date_from': analysis_data.get('date_from', 'غير محدد'),
            'date_to': analysis_data.get('date_to', 'غير محدد'),
            'total_reports': analysis_data.get('total_reports', 0),
            'total_patients': analysis_data.get('total_patients', 0),
            'hospitals_count': analysis_data.get('hospitals_count', 0),
            'doctors_count': analysis_data.get('doctors_count', 0),
            'hospitals_data': analysis_data.get('hospitals_data', []),
            'departments_data': analysis_data.get('departments_data', []),
            'doctors_data': analysis_data.get('doctors_data', []),
            'complaints_data': analysis_data.get('complaints_data', []),
            'actions_data': analysis_data.get('actions_data', []),
            'top_patients': analysis_data.get('top_patients', []),
            'ai_insights': ai_insights,
            'charts': charts
        }
        
        # إنشاء HTML
        html_content = template.render(**context)
        
        # إنشاء PDF
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data_analysis_tables_{timestamp}.pdf"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        if WEASYPRINT_AVAILABLE:
            # استخدام WeasyPrint (Linux/Cloud Run)
            HTML(string=html_content, base_url=TEMPLATE_DIR).write_pdf(output_path)
            logger.info(f"✅ PDF with tables created using WeasyPrint: {output_path}")
        else:
            # Windows: استخدام ReportLab أو حفظ HTML
            # للآن سنحفظ HTML فقط
            html_path = output_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.warning(f"⚠️ PDF غير متوفر على Windows - تم حفظ HTML بدلاً: {html_path}")
            return html_path
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Error creating PDF: {e}")
        raise


def prepare_hospitals_table_data(hospitals_stats: Dict) -> List[Dict]:
    """تجهيز بيانات جدول المستشفيات"""
    hospitals_data = []
    total_reports = sum(hospitals_stats.values())
    
    for hospital, count in sorted(hospitals_stats.items(), key=lambda x: x[1], reverse=True):
        percentage = round((count / total_reports * 100), 1) if total_reports > 0 else 0
        hospitals_data.append({
            'name': hospital,
            'count': count,  # ✅ تم التوحيد مع template
            'reports_count': count,  # للتوافقية
            'patients_count': count,
            'percentage': percentage
        })
    
    return hospitals_data


def prepare_departments_table_data(departments_stats: Dict) -> List[Dict]:
    """تجهيز بيانات جدول الأقسام"""
    departments_data = []
    total = sum(departments_stats.values())
    
    for dept, count in sorted(departments_stats.items(), key=lambda x: x[1], reverse=True)[:15]:
        percentage = round((count / total * 100), 1) if total > 0 else 0
        departments_data.append({
            'name': dept,
            'count': count,
            'percentage': percentage
        })
    
    return departments_data


def prepare_doctors_table_data(doctors_stats: Dict) -> List[Dict]:
    """تجهيز بيانات جدول الأطباء"""
    doctors_data = []
    total = sum(doctors_stats.values())
    
    for doctor, count in sorted(doctors_stats.items(), key=lambda x: x[1], reverse=True)[:15]:
        percentage = round((count / total * 100), 1) if total > 0 else 0
        doctors_data.append({
            'name': doctor,
            'count': count,  # ✅ تم التوحيد مع template
            'reports_count': count,  # للتوافقية
            'patients_count': count,
            'percentage': percentage  # ✅ إضافة النسبة المئوية
        })
    
    return doctors_data


def prepare_complaints_table_data(complaints_stats: Dict) -> List[Dict]:
    """تجهيز بيانات جدول الشكاوى"""
    complaints_data = []
    total = sum(complaints_stats.values())
    
    for complaint, count in sorted(complaints_stats.items(), key=lambda x: x[1], reverse=True)[:15]:
        percentage = round((count / total * 100), 1) if total > 0 else 0
        complaints_data.append({
            'name': complaint,
            'count': count,
            'percentage': percentage
        })
    
    return complaints_data


def prepare_actions_table_data(actions_stats: Dict) -> List[Dict]:
    """تجهيز بيانات جدول الإجراءات"""
    actions_data = []
    total = sum(actions_stats.values())
    
    for action, count in sorted(actions_stats.items(), key=lambda x: x[1], reverse=True)[:15]:
        percentage = round((count / total * 100), 1) if total > 0 else 0
        actions_data.append({
            'name': action,
            'count': count,
            'percentage': percentage
        })
    
    return actions_data


def prepare_top_patients_data(patients_data: List[Dict]) -> List[Dict]:
    """تجهيز بيانات المرضى الأكثر زيارة"""
    top_patients = []
    
    for patient in sorted(patients_data, key=lambda x: x.get('visits', 0), reverse=True)[:15]:
        visits_count = patient.get('visits', 0)
        top_patients.append({
            'name': patient.get('name', 'غير محدد'),
            'count': visits_count,  # ✅ تم التوحيد مع template
            'visits': visits_count,  # للتوافقية
            'last_visit': patient.get('last_visit', 'غير محدد')
        })
    
    return top_patients


# ====================================================
# 🧪 اختبار
# ====================================================

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("="*60)
        print("🧪 اختبار PDF Generator Enhanced")
        print("="*60)
        
        test_data = {
            'date_from': '2025-10-01',
            'date_to': '2025-10-29',
            'total_reports': 150,
            'total_patients': 45,
            'hospitals_count': 5,
            'doctors_count': 12,
            'hospitals_data': [
                {'name': 'مستشفى الملك فيصل', 'reports_count': 60, 'patients_count': 20, 'percentage': 40.0},
                {'name': 'مستشفى المركز الطبي', 'reports_count': 45, 'patients_count': 15, 'percentage': 30.0},
                {'name': 'مستشفى الأمل', 'reports_count': 30, 'patients_count': 8, 'percentage': 20.0},
            ],
            'departments_data': [
                {'name': 'الطوارئ', 'count': 50, 'percentage': 33.3},
                {'name': 'الباطنية', 'count': 35, 'percentage': 23.3},
                {'name': 'القلب', 'count': 25, 'percentage': 16.7},
            ],
            'complaints_data': [
                {'name': 'ألم صدر', 'count': 25, 'percentage': 16.7},
                {'name': 'صداع', 'count': 20, 'percentage': 13.3},
            ],
        }
        
        pdf_path = await generate_data_analysis_pdf_with_tables(test_data)
        print(f"\n✅ تم إنشاء PDF: {pdf_path}")
        print("="*60)
    
    asyncio.run(test())

