# services/pharmacy_evacuation_pdf.py
# PDF لـ"🖨️ طباعة مسير إخلاء الأدوية والمستلزمات الطبية".
#
# نفس الأسلوب المُثبت في services/data_analysis_pdf.py: reportlab مباشر +
# arabic_reshaper + python-bidi للنص العربي RTL، مع تقسيم صريح لكل 15 صفاً
# في جدول منفصل (وليس الاعتماد على repeatRows التلقائي) لضمان 15 صفاً
# بالضبط لكل صفحة وترقيم متصل للعمود "م".
#
# ✅ ملاحظة مهمة حول اتجاه الجدول: reportlab لا يعكس ترتيب الأعمدة تلقائياً
# لمستندات RTL — hAlign يُحاذي الجدول كَكُتلة فقط، لكن الأعمدة داخله
# تُرسَم من اليسار لليمين بنفس ترتيب القائمة المُعطاة. لذلك يجب تعريف
# الأعمدة بترتيب معكوس صراحة (التاريخ أولاً... حتى "م" أخيراً) حتى يظهر
# "م" في أقصى اليمين كما يُقرأ طبيعياً بالعربية.
#
# ✅ ملاحظة توازن الجدول: عرض الأعمدة الآن يُحسب دائماً من CONTENT_WIDTH
# (عرض الصفحة ناقص الهامشين) بدل قيم ثابتة قد تتجاوز المساحة المتاحة —
# هذا هو السبب الفعلي الذي كان يجعل الجدول يبدو "غير متوازن"/ملتصقاً
# بحافة الصفحة سابقاً (كان مجموع الأعمدة 19.5 سم بينما المساحة المتاحة
# بين الهامشين كانت 18 سم فقط).

from __future__ import annotations

import io
import logging
import os
from datetime import date, datetime

logger = logging.getLogger(__name__)

_FONT_CANDIDATES = [
    ("C:\\Windows\\Fonts\\arial.ttf",    "Arial"),   # ✅ نفس خط ملف Excel المرجعي بالضبط
    ("C:\\Windows\\Fonts\\tahoma.ttf",   "Tahoma"),
    ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", "NotoAr"),
]
_FONT_BOLD_CANDIDATES = [
    ("C:\\Windows\\Fonts\\arialbd.ttf",  "ArialBd"),
    ("C:\\Windows\\Fonts\\tahomabd.ttf", "TahomaBd"),
]

_ROWS_PER_PAGE = 15

# ✅ نِسَب عرض الأعمدة المطلوبة (بالترتيب المنطقي: م/المبلغ/الاسم/رقم
# الفاتورة/بند الصرف/البيان/التاريخ) — تُطبَّق لاحقاً على الترتيب
# المعكوس فعلياً في الرسم. مجموعها 100%. مُعدَّلة قليلاً عن الاقتراح
# الأصلي (بصلاحية "تعديل النسب إذا احتاج التصميم") بعد اختبار فعلي:
# "التاريخ" و"المبلغ" كانا يلتفّان بشكل قبيح منتصف الرقم لضيق العرض.
_COL_PERCENTAGES = {
    "م": 0.05,
    "المبلغ": 0.15,
    "الاسم": 0.26,
    "رقم الفاتورة": 0.13,
    "بند الصرف": 0.11,
    "البيان": 0.16,
    "التاريخ": 0.14,
}

_MARGIN_CM = 2.0  # هوامش متساوية يميناً ويساراً — مساحة طباعة احترافية


def _pick_font(candidates: list[tuple[str, str]], fallback: str = "Helvetica") -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path, alias in candidates:
        if os.path.isfile(path):
            try:
                pdfmetrics.registerFont(TTFont(alias, path))
                return alias
            except Exception:
                continue
    return fallback


def _ar(text) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text or "")))
    except Exception:
        return str(text or "")


def _colors():
    from reportlab.lib import colors
    return {
        "primary":   colors.HexColor("#1565C0"),
        "light_bg":  colors.HexColor("#F0F4F8"),
        "grid":      colors.HexColor("#CCCCCC"),  # ✅ نفس لون حدود الجدول في Excel المرجعي
        "text_dark": colors.HexColor("#1A237E"),
        "text_gray": colors.HexColor("#777777"),  # ✅ نفس لون سطر "الفترة" في Excel المرجعي
        "white":     colors.white,
    }


def build_evacuation_pdf(rows: list[dict], start_date: date, end_date: date) -> io.BytesIO:
    """
    rows: [{"amount": float, "name": str, "invoice_number": str,
             "expense_item": str, "statement": str, "date": date}, ...]
    مرتبة مسبقاً بالترتيب النهائي المطلوب (لا تُعاد فرزتها هنا).
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable,
    )

    C = _colors()
    FN = _pick_font(_FONT_CANDIDATES)
    FNB = _pick_font(_FONT_BOLD_CANDIDATES, FN)

    margin = _MARGIN_CM * cm
    content_width = A4[0] - (2 * margin)  # ✅ مصدر واحد للحقيقة لعرض كل العناصر أدناه

    def S(name, **kw):
        kw.setdefault("fontName", FN)
        return ParagraphStyle(name, **kw)

    ST = {
        "body":   S("bd",  fontSize=11, leading=15, alignment=TA_CENTER, textColor=C["text_dark"]),
        "th":     S("th",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["white"], fontName=FNB),
        "td_c":   S("tdc", fontSize=8,  leading=11, alignment=TA_CENTER, textColor=C["text_dark"]),
        "total_lbl": S("totl", fontSize=11, leading=14, alignment=TA_CENTER, textColor=C["white"], fontName=FNB),
        "total_val": S("totv", fontSize=11, leading=14, alignment=TA_CENTER, textColor=C["white"], fontName=FNB),
        "footer": S("ft",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FNB),
    }

    def P(txt, style_key) -> Paragraph:
        return Paragraph(_ar(txt), ST[style_key])

    # ── شريط الرأس (مرة واحدة أول الوثيقة) ────────────────────────────────────
    class EvacuationHeaderBand(Flowable):
        def __init__(self):
            Flowable.__init__(self)
            self.width, self.height = content_width, 5.8 * cm

        def draw(self):
            c = self.canv

            # بسم الله الرحمن الرحيم — خط أكبر ومرفوعة لأعلى، توسيط تام (لا تتغير)
            # ✅ نفس لون العنوان الرئيسي بالضبط (1565C0) — مطابق لملف Excel المرجعي
            # حيث يستخدم الحقلان نفس درجة الأزرق (وليس لونَين مختلفَين).
            c.setFont(FNB, 18)
            c.setFillColor(C["primary"])
            c.drawCentredString(self.width / 2, self.height - 0.6 * cm, _ar("بسم الله الرحمن الرحيم"))

            # العنوان الرئيسي — يبقى في المنتصف، خط واضح وكبير (لا يتغير)
            c.setFont(FNB, 19)
            c.setFillColor(C["primary"])
            c.drawCentredString(self.width / 2, self.height - 2.3 * cm, _ar("مسير إخلاء الأدوية والمستلزمات الطبية"))

            # صف واحد مظلَّل يجمع الحقول الثلاثة (تُملأ يدوياً — لا تُعبَّأ برمجياً أبداً)
            band_top = self.height - 3.2 * cm
            band_h = 1.1 * cm
            c.setFillColor(C["light_bg"])
            c.rect(0, band_top - band_h, self.width, band_h, fill=1, stroke=0)
            text_y = band_top - band_h / 2 - 0.15 * cm
            c.setFont(FN, 10)
            c.setFillColor(C["text_dark"])
            c.drawRightString(self.width - 0.4 * cm, text_y, _ar("رقم سند الصرف: ____________"))
            c.drawCentredString(self.width / 2, text_y, _ar("رقم القيد: ____________"))

            # ✅ "تاريخ تسليم المسير: 20__م / __ / __" — لا تُمرَّر كنص واحد عبر
            # _ar(): خوارزمية bidi تُعيد ترتيب سلسلة أرقام "20" ضمن سياق
            # عربي محيط بها، فينتقل "20" لنهاية الحقل الرقمي بدل بدايته
            # (تأكَّدتُ من هذا مباشرة). الحل: رسم التسمية والقالب الرقمي
            # كنصّين منفصلين متجاورين، فيبقى القالب الرقمي بترتيبه الصحيح.
            # حرف "م" (رمز التقويم الميلادي) يُرسَم هنا كجزء من القالب مباشرة
            # (وليس عبر _ar()) لأنه يقف منفرداً بلا حروف عربية مجاورة تحتاج
            # وصلاً، فيظهر بشكله المنفصل الصحيح دون أي حاجة لإعادة التشكيل.
            date_placeholder = "20__م / __ / __"
            date_label = _ar("تاريخ تسليم المسير: ")
            placeholder_w = c.stringWidth(date_placeholder, FN, 10)
            zone_x = 0.4 * cm
            c.drawString(zone_x, text_y, date_placeholder)
            c.drawString(zone_x + placeholder_w, text_y, date_label)

    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(C["text_gray"])
        canvas.setFont(FN, 8)
        canvas.drawRightString(w - 1.8 * cm, 0.7 * cm, _ar(f"صفحة {doc.page}"))
        canvas.drawString(1.8 * cm, 0.7 * cm, _ar(datetime.utcnow().strftime("%Y-%m-%d")))
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    story = []

    story.append(EvacuationHeaderBand())
    story.append(Spacer(1, 0.6 * cm))

    if not rows:
        story.append(P("لا توجد بيانات مطابقة لمعايير البحث المحددة.", "body"))
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        buf.seek(0)
        return buf

    # ترقيم "م" مسبقاً على كامل البيانات — يبقى متصلاً عبر كل الصفحات
    for i, r in enumerate(rows, start=1):
        r["_row_number"] = i

    # ✅ الأعمدة مُعرَّفة هنا بترتيب معكوس (التاريخ أولاً ... م أخيراً) حتى
    # يظهر "م" في أقصى يمين الصفحة كما يُقرأ طبيعياً بالعربية — العمود
    # الأخير في هذه القائمة = العمود الأيمن على الصفحة. النِّسَب مأخوذة من
    # _COL_PERCENTAGES ومُطبَّقة على content_width فتُجمَع دائماً إلى نفس
    # عرض الصفحة المتاح تماماً (لا التصاق بالحواف ولا تجاوز للهامش).
    REVERSED_LABELS = ["التاريخ", "البيان", "بند الصرف", "رقم الفاتورة", "الاسم", "المبلغ", "م"]
    HEADER_ROW = [P(lbl, "th") for lbl in REVERSED_LABELS]
    col_widths = [content_width * _COL_PERCENTAGES[lbl] for lbl in REVERSED_LABELS]
    AMOUNT_COL_IDX = REVERSED_LABELS.index("المبلغ")

    chunks = [rows[i:i + _ROWS_PER_PAGE] for i in range(0, len(rows), _ROWS_PER_PAGE)]
    for chunk_idx, chunk in enumerate(chunks):
        table_data = [HEADER_ROW]
        for r in chunk:
            date_str = r["date"].strftime("%Y/%m/%d") if isinstance(r["date"], date) else str(r["date"])
            table_data.append([
                P(date_str, "td_c"),
                P(r["statement"], "td_c"),
                P(r["expense_item"], "td_c"),
                P(r["invoice_number"], "td_c"),
                P(r["name"], "td_c"),
                P(f'{r["amount"]:.2f}', "td_c"),
                P(str(r["_row_number"]), "td_c"),
            ])
        t = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C["primary"]),
            # ✅ بلا تظليل متبادل بين الصفوف — نفس مظهر Excel المرجعي (صفوف بيضاء
            # صرفة مفصولة بخطوط شبكة رفيعة فقط، بدون تلوين متبادل).
            ("BACKGROUND", (0, 1), (-1, -1), C["white"]),
            ("GRID", (0, 0), (-1, -1), 0.4, C["grid"]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        if chunk_idx < len(chunks) - 1:
            story.append(PageBreak())

    # ── إجمالي المبلغ — القيمة تحت عمود "المبلغ" فقط، بنفس عرض الجدول كاملاً،
    # وبنفس أسلوب صف الإجمالي في Excel (خانة القيمة + تسمية ممتدة) ──────────
    total_amount = sum(r["amount"] for r in rows)
    story.append(Spacer(1, 0.35 * cm))
    total_row = [""] * len(col_widths)
    total_row[0] = P("إجمالي المبلغ", "total_lbl")
    total_row[AMOUNT_COL_IDX] = P(f'{total_amount:,.2f}', "total_val")
    total_table = Table([total_row], colWidths=col_widths, hAlign="CENTER")
    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C["primary"]),
        ("SPAN", (0, 0), (AMOUNT_COL_IDX - 1, 0)),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("ALIGN", (AMOUNT_COL_IDX, 0), (AMOUNT_COL_IDX, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(total_table)

    # ── صف تذييل التوقيعات (مرة واحدة، آخر الوثيقة، فارغ دائماً) ──────────────
    # ✅ الترتيب معكوس هنا صراحة (نفس سبب عكس أعمدة الجدول أعلاه): يُرسَم
    # من اليسار لليمين بترتيب القائمة، فـ"مستلم العهدة" آخر القائمة كي
    # يظهر في أقصى يمين الصفحة كأول عنصر يُقرأ.
    # ✅ خط تسليم متقطّع كنصّ داخل نفس الفقرة (سطر ثانٍ عبر <br/>) بدل خط
    # Border — نفس أسلوب ملف Excel المرجعي بالضبط. الشرطات لا تُمرَّر عبر
    # _ar() لأنها محايدة أصلاً (لا حروف عربية فيها لتُعاد تشكيلها).
    story.append(Spacer(1, 1.3 * cm))
    footer_labels = ["مسؤول العمليات", "المسؤول المالي", "المراجعة", "مستلم العهدة"]
    dash_counts = {"مستلم العهدة": 23, "المراجعة": 20, "المسؤول المالي": 24, "مسؤول العمليات": 24}

    def _footer_cell(label: str) -> Paragraph:
        return Paragraph(f"{_ar(label)}<br/>{'-' * dash_counts[label]}", ST["footer"])

    footer_table = Table(
        [[_footer_cell(lbl) for lbl in footer_labels]],
        colWidths=[content_width / 4] * 4, hAlign="CENTER",
    )
    footer_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(footer_table)

    for r in rows:
        r.pop("_row_number", None)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(f"[pharmacy_evacuation_pdf] built  rows={len(rows)}  size={buf.getbuffer().nbytes:,}")
    return buf
