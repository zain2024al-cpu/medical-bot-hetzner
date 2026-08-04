# services/residency_archive_pdf.py
# PDF لأرشيف الإقامات — المرضى ومرافقوهم مع تواريخ انتهاء الإقامة والجواز.
#
# نفس الأسلوب المُثبت نجاحه في services/pharmacy_evacuation_pdf.py:
#   reportlab مباشرةً + arabic_reshaper + python-bidi، وخط عربي **مضمَّن مع
#   المشروع** (assets/fonts) لا خط نظام — خطوط النظام غير موجودة على
#   السيرفر فتسقط لـHelvetica وتظهر كل العربية مربعات.
#
# ⚠️ لا WeasyPrint هنا عمداً: يعتمد مكتبات نظام (libpango) تعطّلت فعلياً
# على السيرفر، وreportlab بايثون خالص.
#
# ⚠️ reportlab لا يعكس ترتيب الأعمدة تلقائياً في المستندات العربية — يجب
# تعريف الأعمدة **بترتيب معكوس صراحةً** ليظهر "م" أقصى اليمين كما يُقرأ.

from __future__ import annotations

import io
import logging
import os
import re
from datetime import date

logger = logging.getLogger(__name__)

_ARABIC_RE = re.compile("[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts"))

_FONT_CANDIDATES = [
    (os.path.join(_FONTS_DIR, "Arabic-Regular.ttf"), "ResArFont"),
    ("C:\\Windows\\Fonts\\arial.ttf",  "Arial"),
    ("C:\\Windows\\Fonts\\tahoma.ttf", "Tahoma"),
]
_FONT_BOLD_CANDIDATES = [
    (os.path.join(_FONTS_DIR, "Arabic-Bold.ttf"), "ResArFontBd"),
    ("C:\\Windows\\Fonts\\arialbd.ttf", "ArialBd"),
]

_MARGIN_CM = 1.5
_ROWS_PER_PAGE = 22

# ألوان مطابقة لملف Excel — نفس المفتاح البصري في المخرجين
_C_EXPIRED = "#FFCDD2"
_C_URGENT  = "#FFE0B2"
_C_SOON    = "#FFF9C4"


def _pick_font(candidates, fallback="Helvetica") -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    for path, alias in candidates:
        if os.path.isfile(path):
            try:
                pdfmetrics.registerFont(TTFont(alias, path))
                return alias
            except Exception:
                continue
    logger.warning("[residency_pdf] no Arabic font found — Arabic will render as boxes")
    return fallback


def _ar(text) -> str:
    """reshape+bidi للنص العربي فقط؛ التواريخ والأرقام تُعاد كما هي."""
    s = str(text if text is not None else "")
    if not _ARABIC_RE.search(s):
        return s
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


def build_archive_pdf(rows: list[dict]) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    from services.residency_archive_excel import _fmt, _days_text

    font   = _pick_font(_FONT_CANDIDATES)
    font_b = _pick_font(_FONT_BOLD_CANDIDATES, fallback=font)

    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=_MARGIN_CM * cm, rightMargin=_MARGIN_CM * cm,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm,
        title="Residency Archive",
    )
    content_w = page[0] - 2 * _MARGIN_CM * cm

    title_style = ParagraphStyle("t", fontName=font_b, fontSize=17,
                                 alignment=TA_CENTER, textColor=colors.HexColor("#424242"),
                                 leading=22)
    sub_style   = ParagraphStyle("s", fontName=font, fontSize=9.5,
                                 alignment=TA_CENTER, textColor=colors.HexColor("#616161"),
                                 leading=14)

    # ✅ الترتيب المنطقي ثم يُعكَس عند الرسم (انظر ملاحظة الرأس)
    headers_logical = ["م", "الاسم", "الصفة", "رقم الإقامة",
                       "انتهاء الإقامة", "المتبقّي", "انتهاء الجواز", "المتبقّي"]
    pct_logical     = [0.05, 0.26, 0.08, 0.13, 0.12, 0.12, 0.12, 0.12]

    headers = list(reversed(headers_logical))
    widths  = [p * content_w for p in reversed(pct_logical)]

    story = [
        Paragraph(_ar("أرشيف الإقامات — المرضى والمرافقون"), title_style),
        Spacer(1, 0.15 * cm),
        Paragraph(
            _ar(f"تاريخ التصدير: {date.today().strftime('%d/%m/%Y')}   •   "
                f"الإجمالي: {len(rows)} شخص"),
            sub_style,
        ),
        Spacer(1, 0.4 * cm),
    ]

    cell = ParagraphStyle("c", fontName=font, fontSize=8.5, alignment=TA_CENTER, leading=11)
    cell_b = ParagraphStyle("cb", fontName=font_b, fontSize=8.5, alignment=TA_CENTER, leading=11)

    chunks = [rows[i:i + _ROWS_PER_PAGE] for i in range(0, len(rows), _ROWS_PER_PAGE)] or [[]]

    for ci, chunk in enumerate(chunks):
        data = [[Paragraph(_ar(h), cell_b) for h in headers]]
        styles = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

        for ri, row in enumerate(chunk, start=1):
            res_txt, res_c = _days_text(row["res_expiry"])
            pas_txt, pas_c = _days_text(row["pas_expiry"])
            name = ("↳ " + row["name"]) if row["is_comp"] else row["name"]

            logical = [
                str(row["seq"]), name, row["role"], row["res_number"],
                _fmt(row["res_expiry"]), res_txt, _fmt(row["pas_expiry"]), pas_txt,
            ]
            st = cell if row["is_comp"] else cell_b
            data.append([Paragraph(_ar(v), st) for v in reversed(logical)])

            # مواضع أعمدة "المتبقّي" بعد العكس (الفهرس المنطقي 5 و7)
            n = len(headers_logical)
            col_res = n - 1 - 5
            col_pas = n - 1 - 7
            for col, c in ((col_res, res_c), (col_pas, pas_c)):
                if c:
                    hexmap = {"FFCDD2": _C_EXPIRED, "FFE0B2": _C_URGENT, "FFF9C4": _C_SOON}
                    styles.append(("BACKGROUND", (col, ri), (col, ri),
                                   colors.HexColor(hexmap.get(c, "#FFFFFF"))))
            if row["is_comp"]:
                styles.append(("TEXTCOLOR", (0, ri), (-1, ri), colors.HexColor("#555555")))

        t = Table(data, colWidths=widths, repeatRows=1, hAlign="CENTER")
        t.setStyle(TableStyle(styles))
        story.append(t)
        if ci < len(chunks) - 1:
            story.append(PageBreak())

    # مفتاح الألوان
    story.append(Spacer(1, 0.4 * cm))
    legend = Table(
        [[Paragraph(_ar(t_), cell) for t_ in reversed(
            ["مفتاح الألوان:", "منتهية", "خلال 30 يوم", "خلال 90 يوم"])]],
        colWidths=[3.2 * cm] * 4, hAlign="CENTER",
    )
    legend.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(_C_SOON)),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor(_C_URGENT)),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor(_C_EXPIRED)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(legend)

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor("#9E9E9E"))
        canvas.drawCentredString(page[0] / 2, 0.6 * cm, str(doc_.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    logger.info(f"[residency.archive_pdf] built  rows={len(rows)}  pages={len(chunks)}")
    return buf


def build_residency_archive_pdf() -> tuple[io.BytesIO | None, int]:
    """(الملف, عدد الأشخاص) — (None, 0) إن كان الأرشيف فارغاً."""
    from services.residency_archive_excel import collect_archive_rows
    rows = collect_archive_rows()
    if not rows:
        return None, 0
    return build_archive_pdf(rows), len(rows)
