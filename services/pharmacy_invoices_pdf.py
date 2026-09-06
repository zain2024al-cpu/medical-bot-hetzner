# services/pharmacy_invoices_pdf.py
# 🧾 مسير الفواتير — PDF منظَّم بالتاريخ.
#
# ✅ نفس أسلوب services/pharmacy_evacuation_pdf.py المُثبت، ونفس مصدر
# الصفوف (`pharmacy_evacuation_service.get_evacuation_ledger_rows`) —
# فلا يتباعد المسيران في قواعد الفلترة (المحذوف ناعماً) ولا في مصدر
# التاريخ.
#
# **ما يميّزه عن مسير الإخلاء**: ذاك ورقة صرف بصافي المبلغ فقط؛ وهذا
# يعرض **تفصيل الفاتورة** — الإجمالي والخصم ونسبته والصافي — ويُجمِّع
# الصفوف **بيومها** بإجمالي لكل يوم، لأن السؤال المالي يُطرَح عادةً
# «كم يوم كذا؟» لا «كم الفترة كلها؟» وحدها.
#
# ⚠️ **اتجاه الأعمدة**: reportlab لا يعكس أعمدة RTL — تُعرَّف معكوسة
# صراحةً ليظهر "م" في أقصى اليمين.

from __future__ import annotations

import io
import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts"))

# الخط المضمَّن أولاً — هو الوحيد الموجود على الخادم (Linux).
_FONT_CANDIDATES = [
    (os.path.join(_FONTS_DIR, "Arabic-Regular.ttf"), "PhInvAr"),
    ("C:\\Windows\\Fonts\\arial.ttf", "Arial"),
    ("C:\\Windows\\Fonts\\tahoma.ttf", "Tahoma"),
]
_FONT_BOLD_CANDIDATES = [
    (os.path.join(_FONTS_DIR, "Arabic-Bold.ttf"), "PhInvArBd"),
    ("C:\\Windows\\Fonts\\arialbd.ttf", "ArialBd"),
]

# العناوين بترتيب القراءة (يمين ← يسار)؛ تُعكَس عند البناء.
_HEADERS = ["م", "المريض", "رقم الفاتورة", "بند الصرف",
            "الإجمالي", "الخصم %", "قيمة الخصم", "الصافي"]
_WIDTH_SHARES = [0.05, 0.26, 0.13, 0.19, 0.095, 0.075, 0.095, 0.10]

_AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
            "الجمعة", "السبت", "الأحد"]


def _num(v) -> str:
    """مبلغ بلا كسور عشرية — نفس عرض مسير الإخلاء."""
    try:
        return f"{float(v or 0):,.0f}"
    except (TypeError, ValueError):
        return "0"


def _pct(v) -> str:
    try:
        f = float(v or 0)
    except (TypeError, ValueError):
        return "—"
    if f <= 0:
        return "—"
    return f"{f:g}%"


def group_by_day(rows: list[dict]) -> list[tuple]:
    """[(اليوم، صفوفه، إجمالي صافيه), ...] مرتّبة تصاعدياً بالتاريخ."""
    buckets: dict[date, list[dict]] = {}
    for r in rows:
        d = r.get("date")
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except ValueError:
                d = None
        buckets.setdefault(d, []).append(r)

    out = []
    # ⚠️ ما لا تاريخ له يُوضَع آخراً لا يُحذَف: إسقاطه صامتاً يُنقِص
    # الإجمالي فلا يطابق ما في النظام، والفرق المالي لا يُغتفَر.
    for d in sorted((k for k in buckets if k is not None)):
        chunk = buckets[d]
        out.append((d, chunk, sum(float(x.get("net_amount") or 0) for x in chunk)))
    if None in buckets:
        chunk = buckets[None]
        out.append((None, chunk, sum(float(x.get("net_amount") or 0) for x in chunk)))
    return out


def build_invoices_pdf(rows: list[dict], start_date: date, end_date: date) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    from services.pdf_arabic import ar, pick_font

    FN = pick_font(_FONT_CANDIDATES)
    FB = pick_font(_FONT_BOLD_CANDIDATES, fallback=FN)

    page = landscape(A4)
    margin = 1.2 * cm
    content_w = page[0] - 2 * margin
    col_w = [content_w * s for s in reversed(_WIDTH_SHARES)]

    head = ParagraphStyle("h", fontName=FB, fontSize=9, alignment=TA_CENTER,
                          textColor=colors.HexColor("#1F3864"), leading=12)
    cell = ParagraphStyle("c", fontName=FN, fontSize=8.5, alignment=TA_CENTER, leading=11)
    cell_r = ParagraphStyle("cr", fontName=FN, fontSize=8.5, alignment=TA_RIGHT, leading=11)
    net_st = ParagraphStyle("nt", parent=cell, fontName=FB,
                            textColor=colors.HexColor("#1F3864"))
    day_st = ParagraphStyle("d", fontName=FB, fontSize=10.5, alignment=TA_RIGHT,
                            textColor=colors.HexColor("#1F3864"), leading=15)
    ttl = ParagraphStyle("t", fontName=FB, fontSize=15, alignment=TA_CENTER,
                         textColor=colors.HexColor("#1F3864"), leading=20)
    sub = ParagraphStyle("s", fontName=FN, fontSize=9, alignment=TA_CENTER,
                         textColor=colors.HexColor("#666666"), leading=13)
    tot_st = ParagraphStyle("tt", fontName=FB, fontSize=11, alignment=TA_CENTER,
                            textColor=colors.HexColor("#1F3864"), leading=15)

    def P(txt, st=cell):
        return Paragraph(ar(txt), st)

    period = (start_date.isoformat() if start_date == end_date
              else f"{start_date.isoformat()}  ←  {end_date.isoformat()}")

    story = [
        Paragraph(ar("🧾 مسير الفواتير — الصيدلية"), ttl),
        Spacer(1, 0.12 * cm),
        Paragraph(ar(f"الفترة: {period}  ·  عدد الفواتير: {len(rows)}"
                     f"  ·  تاريخ الطباعة: {date.today().isoformat()}"), sub),
        Spacer(1, 0.35 * cm),
    ]

    grand = 0.0
    if not rows:
        story.append(Paragraph(ar("لا توجد فواتير في هذه الفترة."), sub))
    else:
        header = [P(h, head) for h in reversed(_HEADERS)]
        n = 0
        for day, chunk, day_total in group_by_day(rows):
            grand += day_total
            label = (f"{_AR_DAYS[day.weekday()]}  {day.isoformat()}"
                     if day else "بلا تاريخ مسجَّل")
            story.append(Paragraph(ar(f"📅 {label}   —   {len(chunk)} فاتورة"), day_st))
            story.append(Spacer(1, 0.12 * cm))

            data = [header]
            for r in chunk:
                n += 1
                data.append([
                    P(_num(r.get("net_amount")), net_st),
                    P(_num(r.get("discount_amount"))),
                    P(_pct(r.get("discount_percent"))),
                    P(_num(r.get("invoice_total"))),
                    P(str(r.get("expense_item") or "—"), cell_r),
                    P(str(r.get("invoice_number") or "—")),
                    P(str(r.get("name") or "—"), cell_r),
                    P(str(n)),
                ])
            # صف إجمالي اليوم — الصافي في عموده لا في خانة معلّقة
            total_row = [P(_num(day_total), net_st)] + [P("")] * 6 + [P("")]
            total_row[4] = P("إجمالي اليوم", net_st)
            data.append(total_row)

            t = Table(data, colWidths=col_w, hAlign="CENTER", repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F6FC")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9BA5B4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.45 * cm))

        story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph(
            ar(f"الإجمالي العام للفترة:  {_num(grand)}"), tot_st))

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(FN, 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawRightString(page[0] - margin, 0.7 * cm, ar(f"صفحة {doc_.page}"))
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=1.4 * cm,
                            title="مسير الفواتير", author="Pharmacy")
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
