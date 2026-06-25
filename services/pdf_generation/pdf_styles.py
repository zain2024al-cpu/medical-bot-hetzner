# ================================================
# services/pdf_generation/pdf_styles.py
# 🎨 أنماط وألوان التقارير
# ================================================

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm, inch
# define pt locally (1 point)
pt = 1.0
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ========================================
# تسجيل الخطوط العربية
# ========================================

def setup_arabic_fonts():
    """إعداد الخطوط العربية"""
    font_candidates = [
        ("C:\\Windows\\Fonts\\tahoma.ttf", "Tahoma"),
        ("C:\\Windows\\Fonts\\tahomabd.ttf", "TahomaBd"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuBd"),
    ]
    
    for font_path, font_name in font_candidates:
        if os.path.isfile(font_path):
            try:
                if "Bold" in font_name or "bd" in font_path.lower():
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                else:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
            except:
                pass


# ========================================
# الألوان
# ========================================

class PDFColors:
    """لوحة الألوان الموحدة"""
    
    PRIMARY = colors.HexColor("#1565C0")           # أزرق داكن
    ACCENT = colors.HexColor("#0288D1")            # أزرق فاتح
    SUCCESS = colors.HexColor("#2E7D32")           # أخضر
    WARNING = colors.HexColor("#F57F17")           # برتقالي
    DANGER = colors.HexColor("#C62828")            # أحمر
    
    LIGHT_BG = colors.HexColor("#F0F4F8")          # خلفية فاتحة
    CARD_BG = colors.HexColor("#FAFCFF")           # خلفية البطاقة
    GRID = colors.HexColor("#D0D9E8")              # خطوط الجدول
    
    TEXT_DARK = colors.HexColor("#1A237E")         # نص داكن
    TEXT_GRAY = colors.HexColor("#546E7A")         # نص رمادي
    
    WHITE = colors.white
    BLACK = colors.black


# ========================================
# أنماط الفقرات
# ========================================

def get_styles():
    """الحصول على أنماط الفقرات"""
    
    styles = getSampleStyleSheet()
    
    # عنوان رئيسي
    styles.add(ParagraphStyle(
        name='ArabicTitle',
        fontSize=28,
        leading=36,
        textColor=PDFColors.PRIMARY,
        fontName='Tahoma',
        alignment=2,  # RTL
        spaceAfter=12,
        bold=True,
    ))
    
    # عنوان فرعي
    styles.add(ParagraphStyle(
        name='ArabicHeading',
        fontSize=20,
        leading=24,
        textColor=PDFColors.PRIMARY,
        fontName='Tahoma',
        alignment=2,  # RTL
        spaceAfter=10,
        bold=True,
    ))
    
    # عنوان قسم
    styles.add(ParagraphStyle(
        name='ArabicSubHeading',
        fontSize=14,
        leading=18,
        textColor=PDFColors.ACCENT,
        fontName='Tahoma',
        alignment=2,  # RTL
        spaceAfter=8,
        bold=True,
    ))
    
    # نص عادي
    styles.add(ParagraphStyle(
        name='ArabicBody',
        fontSize=12,
        leading=16,
        textColor=PDFColors.TEXT_DARK,
        fontName='Tahoma',
        alignment=2,  # RTL
        spaceAfter=6,
    ))
    
    # نص صغير
    styles.add(ParagraphStyle(
        name='ArabicSmall',
        fontSize=10,
        leading=12,
        textColor=PDFColors.TEXT_GRAY,
        fontName='Tahoma',
        alignment=2,  # RTL
        spaceAfter=4,
    ))
    
    return styles


# ========================================
# إعدادات PDF
# ========================================

class PDFConfig:
    """إعدادات PDF"""
    
    # حجم الصفحة (A4 بالمليمتر)
    PAGE_WIDTH = 210 * mm
    PAGE_HEIGHT = 297 * mm
    
    # الهوامش
    MARGIN_TOP = 20 * mm
    MARGIN_BOTTOM = 15 * mm
    MARGIN_LEFT = 20 * mm
    MARGIN_RIGHT = 20 * mm
    
    # حجم المحتوى
    CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    CONTENT_HEIGHT = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    
    # الجداول
    TABLE_HEADER_HEIGHT = 30 * pt
    TABLE_ROW_HEIGHT = 25 * pt
    MAX_ROWS_PER_PAGE = 25
    
    # الرسوم البيانية
    CHART_WIDTH = 7 * inch  # 7 inches
    CHART_HEIGHT = 4.5 * inch
    
    # الفاصل بين الأقسام
    SECTION_SPACING = 12 * pt
    
    # رقم الصفحات
    SHOW_PAGE_NUMBERS = True
    SHOW_HEADERS = True
    SHOW_FOOTERS = True


# لا توجد حاجة لتحويلات إضافية
