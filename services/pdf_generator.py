import os
import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from db.models import Report

# Configure logging FIRST - before any logger usage
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WeasyPrint يعمل فقط على Linux (Cloud Run)
# على Windows: نستخدم نسخة بديلة للاختبار
IS_WINDOWS = sys.platform.startswith('win')

if not IS_WINDOWS:
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
        font_config = FontConfiguration()
    except ImportError:
        # If weasyprint is not installed, disable it
        HTML = None
        CSS = None
        font_config = None
        logger.warning("weasyprint not installed - PDF generation disabled")
else:
    # على Windows: تعطيل WeasyPrint
    HTML = None
    CSS = None
    font_config = None
    # ملاحظة: WeasyPrint معطل على Windows، سيعمل على Cloud Run فقط

# ============================================================
# 🧾 وحدة إنشاء ملفات PDF من تقارير المرضى (WeasyPrint)
# ============================================================

# Directory paths (absolute to avoid Docker context issues)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = str(BASE_DIR / "templates")
OUTPUT_DIR = str(BASE_DIR / "exports")

# Create output directory if not exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Font configuration (فقط على Linux)
if not IS_WINDOWS and font_config is None:
    from weasyprint.text.fonts import FontConfiguration
    font_config = FontConfiguration()

# CSS للعربي والتنسيق (فقط على Linux)
if not IS_WINDOWS:
    DEFAULT_CSS = CSS(string='''
    @page {
        size: A4;
        margin: 20mm;
    }
    body {
        font-family: 'DejaVu Sans', 'Noto Sans Arabic', Arial, sans-serif;
        direction: rtl;
        text-align: right;
        font-size: 12pt;
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: right;
    }
    th {
        background-color: #3498db;
        color: white;
    }
''', font_config=font_config)
else:
    DEFAULT_CSS = None


def generate_pdf_report(report_id: int, template_name: str = "report_template.html") -> str:
    """
    Generate a PDF file for a specific report by ID from database.
    
    Args:
        report_id: The ID of the report to generate PDF for
        template_name: The HTML template to use (default: report_template.html)
    
    Returns:
        str: Path to the generated PDF file
    
    Raises:
        ValueError: If report not found
        RuntimeError: If PDF generation fails
    """
    
    # على Windows: حفظ HTML بدلاً من PDF
    if IS_WINDOWS:
        logger.warning("⚠️ WeasyPrint معطل على Windows - حفظ HTML بدلاً من PDF")
        
        try:
            # Fetch report from database
            report = Report.get_by_id(report_id)
            if not report:
                raise ValueError(f"⚠️ لم يتم العثور على التقرير بالمعرّف: {report_id}")
            
            # Load template
            env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
            template = env.get_template(template_name)
            
            # Prepare template context
            context = {
                'patient_name': report.patient_name,
                'complaint': report.complaint_text,
                'decision': report.doctor_decision,
                'date': str(report.report_date),
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            
            # Render HTML content
            html_content = template.render(**context)
            
            # Save as HTML
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(OUTPUT_DIR, f"report_{report.id}_{timestamp}.html")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"✅ تم حفظ HTML على Windows: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ فشل حفظ HTML: {e}")
            raise RuntimeError(f"❌ فشل حفظ HTML: {e}")
    
    try:
        # Fetch report from database
        report = Report.get_by_id(report_id)
        if not report:
            raise ValueError(f"⚠️ لم يتم العثور على التقرير بالمعرّف: {report_id}")

        # Load template
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template(template_name)

        # Prepare template context
        context = {
            'patient_name': report.patient_name,
            'complaint': report.complaint_text,
            'decision': report.doctor_decision,
            'date': str(report.report_date),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        # Render HTML content
        html_content = template.render(**context)

        # Generate output file path
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(OUTPUT_DIR, f"report_{report.id}_{timestamp}.pdf")

        # Convert HTML to PDF using WeasyPrint
        HTML(string=html_content).write_pdf(
            output_path,
            stylesheets=[DEFAULT_CSS],
            font_config=font_config
        )
        
        logger.info(f"✅ تم إنشاء PDF بنجاح: {output_path}")
        return output_path

    except TemplateNotFound:
        logger.error(f"❌ لم يتم العثور على القالب: {template_name}")
        raise RuntimeError(f"❌ لم يتم العثور على القالب: {template_name}")
    except Exception as e:
        logger.error(f"❌ فشل إنشاء ملف PDF للتقرير {report_id}: {str(e)}")
        raise RuntimeError(f"❌ فشل إنشاء ملف PDF: {e}")


# ============================================================
# 🧾 دالة لإنشاء تقارير متعددة دفعة واحدة
# ============================================================
def generate_all_reports_pdf() -> str:
    """
    Generate PDF files for all reports in the database.
    
    Returns:
        str: Success message with count of generated PDFs
    """
    try:
        reports = Report.all()
        if not reports:
            return "⚠️ لا توجد تقارير حالياً."

        paths = []
        failed = []
        
        for rep in reports:
            try:
                path = generate_pdf_report(rep.id)
                paths.append(path)
            except Exception as e:
                logger.error(f"❌ خطأ في تقرير {rep.id}: {e}")
                failed.append(rep.id)

        success_msg = f"✅ تم إنشاء {len(paths)} تقرير PDF بنجاح."
        if failed:
            success_msg += f"\n⚠️ فشل إنشاء {len(failed)} تقرير: {failed}"
        
        return success_msg
        
    except Exception as e:
        logger.error(f"❌ فشل إنشاء التقارير: {e}")
        return f"❌ فشل إنشاء التقارير: {e}"


# ============================================================
# 🧾 دالة لإنشاء تقارير متعددة في ملف PDF واحد
# ============================================================
def generate_pdf_reports(
    template_name: str,
    context_data: Dict[str, Any],
    output_path: str,
    custom_options: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a single PDF file containing multiple reports.
    
    Args:
        template_name: Name of the HTML template to use
        context_data: Dictionary containing data to render in template
        output_path: Full path where the PDF will be saved
        custom_options: Optional custom PDF generation options
    
    Returns:
        str: Path to the generated PDF file
    
    Raises:
        RuntimeError: If PDF generation fails
    """
    
    # على Windows: استخدام ReportLab أو حفظ HTML
    if IS_WINDOWS:
        logger.warning("⚠️ WeasyPrint معطل على Windows - حفظ HTML بدلاً من PDF")
        # حفظ HTML بدلاً من PDF
        html_path = output_path.replace('.pdf', '.html')
        
        try:
            # Load template
            env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
            template = env.get_template(template_name)
            
            # Add generation timestamp
            context_data['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Render HTML
            html_content = template.render(**context_data)
            
            # Save as HTML
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"✅ تم حفظ HTML على Windows: {html_path}")
            return html_path
            
        except Exception as e:
            logger.error(f"❌ فشل حفظ HTML: {e}")
            raise RuntimeError(f"❌ فشل حفظ HTML: {e}")
    
    try:
        # Load template
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template(template_name)
        
        # Add generation timestamp to context
        context_data['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Render HTML content
        html_content = template.render(**context_data)
        
        # Convert HTML to PDF using WeasyPrint
        HTML(string=html_content).write_pdf(
            output_path,
            stylesheets=[DEFAULT_CSS],
            font_config=font_config
        )
        
        logger.info(f"✅ تم إنشاء ملف PDF متعدد التقارير: {output_path}")
        return output_path
        
    except TemplateNotFound:
        logger.error(f"❌ لم يتم العثور على القالب: {template_name}")
        raise RuntimeError(f"❌ لم يتم العثور على القالب: {template_name}")
    except Exception as e:
        logger.error(f"❌ فشل إنشاء ملف PDF: {str(e)}")
        raise RuntimeError(f"❌ فشل إنشاء ملف PDF: {e}")


# ============================================================
# 🧾 دوال مساعدة إضافية
# ============================================================

def get_available_templates() -> list:
    """
    Get list of available HTML templates.
    
    Returns:
        list: List of template filenames
    """
    try:
        templates = []
        for file in os.listdir(TEMPLATE_DIR):
            if file.endswith('.html'):
                templates.append(file)
        return sorted(templates)
    except Exception as e:
        logger.error(f"❌ فشل قراءة القوالب: {e}")
        return []


def validate_template(template_name: str) -> bool:
    """
    Check if a template exists.
    
    Args:
        template_name: Name of the template to check
    
    Returns:
        bool: True if template exists, False otherwise
    """
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    return os.path.exists(template_path)


def get_pdf_info(pdf_path: str) -> Dict[str, Any]:
    """
    Get information about a generated PDF file.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        dict: PDF information (size, creation time, etc.)
    """
    try:
        if not os.path.exists(pdf_path):
            return {'error': 'File not found'}
        
        stats = os.stat(pdf_path)
        return {
            'file_path': pdf_path,
            'file_name': os.path.basename(pdf_path),
            'size_bytes': stats.st_size,
            'size_mb': round(stats.st_size / (1024 * 1024), 2),
            'created_at': datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            'modified_at': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        }
    except Exception as e:
        logger.error(f"❌ فشل قراءة معلومات PDF: {e}")
        return {'error': str(e)}


def clean_old_pdfs(days: int = 30) -> int:
    """
    Delete PDF files older than specified days.
    
    Args:
        days: Delete files older than this many days (default: 30)
    
    Returns:
        int: Number of files deleted
    """
    try:
        deleted_count = 0
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        
        for file in os.listdir(OUTPUT_DIR):
            if file.endswith('.pdf'):
                file_path = os.path.join(OUTPUT_DIR, file)
                if os.path.getmtime(file_path) < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"🗑️ تم حذف ملف قديم: {file}")
        
        logger.info(f"✅ تم حذف {deleted_count} ملف PDF قديم")
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ فشل تنظيف الملفات القديمة: {e}")
        return 0


# ============================================================
# 🧾 تصدير الدوال الرئيسية
# ============================================================

__all__ = [
    'generate_pdf_report',
    'generate_all_reports_pdf',
    'generate_pdf_reports',
    'get_available_templates',
    'validate_template',
    'get_pdf_info',
    'clean_old_pdfs',
]