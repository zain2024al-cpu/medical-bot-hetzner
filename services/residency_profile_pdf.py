# services/residency_profile_pdf.py
# ملف PDF لمريض واحد ومرافقيه — يُفتح من زر «📄 ملف PDF» في تفصيل الملف.
#
# ⚠️ يحلّ محلّ services/residency_pdf_builder.py الذي كان **معطّلاً منذ
# إنشائه**: يعتمد قالب Jinja اسمه templates/residency_patient_package.html
# ومجلد templates/ غير موجود إطلاقاً في المشروع (TemplateNotFound)، فوق
# اعتماده على WeasyPrint الذي تعطّلت مكتبات نظامه (libpango) على السيرفر.
# الزر كان يعطي «❌ فشل إنشاء ملف PDF» في كل مرة.
#
# نفس مسار reportlab المُثبت في residency_archive_pdf.py، وبإعادة استخدام
# دوالّه: خط عربي **مضمَّن مع المشروع** (خطوط النظام غير موجودة على السيرفر
# فتسقط لـHelvetica وتظهر العربية مربعات)، وأعمدة **معكوسة صراحةً** لأن
# reportlab لا يعكس ترتيب الأعمدة تلقائياً في المستندات العربية.

from __future__ import annotations

import io
import logging
from datetime import date

logger = logging.getLogger(__name__)

_MARGIN_CM = 1.6


def _info_table(rows_logical, font, font_b, width):
    """جدول تسمية/قيمة — التسمية يميناً بعد العكس."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT
    from services.residency_archive_pdf import _ar

    lbl = ParagraphStyle("l", fontName=font_b, fontSize=9.5, alignment=TA_RIGHT, leading=13)
    val = ParagraphStyle("v", fontName=font,   fontSize=9.5, alignment=TA_RIGHT, leading=13)

    data = [list(reversed([Paragraph(_ar(a), lbl), Paragraph(_ar(b), val)]))
            for a, b in rows_logical]
    t = Table(data, colWidths=[width * 0.66, width * 0.34], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F7F7F7")),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def build_profile_pdf(*, profile, companions, history) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    from services.residency_archive_pdf import (
        _pick_font, _ar, _FONT_CANDIDATES, _FONT_BOLD_CANDIDATES,
    )
    from services.residency_archive_excel import _fmt, _days_text
    from modules.residency.views import format_status

    font   = _pick_font(_FONT_CANDIDATES)
    font_b = _pick_font(_FONT_BOLD_CANDIDATES, fallback=font)

    buf = io.BytesIO()
    page = A4
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=_MARGIN_CM * cm, rightMargin=_MARGIN_CM * cm,
        topMargin=1.3 * cm, bottomMargin=1.3 * cm,
        title=f"Residency — {profile.name}",
    )
    W = page[0] - 2 * _MARGIN_CM * cm

    title = ParagraphStyle("t", fontName=font_b, fontSize=16, alignment=TA_CENTER,
                           textColor=colors.HexColor("#424242"), leading=21)
    sub   = ParagraphStyle("s", fontName=font, fontSize=9, alignment=TA_CENTER,
                           textColor=colors.HexColor("#757575"), leading=13)
    head  = ParagraphStyle("h", fontName=font_b, fontSize=11.5, alignment=TA_RIGHT,
                           textColor=colors.HexColor("#37474F"), leading=16)
    cell  = ParagraphStyle("c", fontName=font, fontSize=8.5, alignment=TA_CENTER, leading=11)
    cellb = ParagraphStyle("cb", fontName=font_b, fontSize=8.5, alignment=TA_CENTER, leading=11)
    body  = ParagraphStyle("b", fontName=font, fontSize=9, alignment=TA_RIGHT, leading=13)

    res_txt, _ = _days_text(profile.expiry_date)
    story = [
        Paragraph(_ar("ملف إقامة"), title),
        Paragraph(_ar(profile.name or "—"), title),
        Spacer(1, 0.1 * cm),
        Paragraph(_ar(f"تاريخ الإصدار: {date.today().strftime('%d/%m/%Y')}"), sub),
        Spacer(1, 0.5 * cm),
        Paragraph(_ar("بيانات المريض"), head),
        Spacer(1, 0.15 * cm),
    ]

    info = [
        ("الاسم",            profile.name or "—"),
        ("رقم الإقامة",      profile.residency_number or "—"),
        ("الحالة",           format_status(profile.status)),
        ("انتهاء الإقامة",   _fmt(profile.expiry_date)),
        ("المتبقّي",          res_txt),
    ]
    pas = getattr(profile, "passport_expiry", "")
    if pas:
        pas_txt, _ = _days_text(pas)
        info += [("انتهاء الجواز", _fmt(pas)), ("المتبقّي على الجواز", pas_txt)]
    info.append(("عدد المرافقين", str(len(companions))))
    story += [_info_table(info, font, font_b, W), Spacer(1, 0.5 * cm)]

    # ── المرافقون ─────────────────────────────────────────────────────────────
    story.append(Paragraph(_ar(f"المرافقون ({len(companions)})"), head))
    story.append(Spacer(1, 0.15 * cm))
    if not companions:
        story.append(Paragraph(_ar("لا يوجد مرافقون مسجَّلون."), body))
    else:
        hdr = ["م", "الاسم", "رقم الإقامة", "انتهاء الإقامة", "المتبقّي", "الحالة"]
        pct = [0.06, 0.28, 0.18, 0.16, 0.16, 0.16]
        data = [[Paragraph(_ar(h), cellb) for h in reversed(hdr)]]
        for i, c in enumerate(companions, 1):
            txt, _c = _days_text(c.expiry_date)
            logical = [str(i), c.name or "—", c.residency_number or "—",
                       _fmt(c.expiry_date), txt, format_status(c.status)]
            data.append([Paragraph(_ar(v), cell) for v in reversed(logical)])
        t = Table(data, colWidths=[p * W for p in reversed(pct)], hAlign="CENTER")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEFF1")),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ── الوثائق ───────────────────────────────────────────────────────────────
    story.append(Paragraph(_ar("الوثائق المحفوظة"), head))
    story.append(Spacer(1, 0.15 * cm))
    tick = lambda v: "✔" if v else "—"
    story += [_info_table([
        ("الجواز",   tick(profile.passport_file_id)),
        ("التأشيرة", tick(profile.visa_file_id)),
        ("الإقامة",  tick(profile.latest_residency_file_id)),
        ("فورم C",   tick(getattr(profile, "form_c_file_id", ""))),
    ], font, font_b, W), Spacer(1, 0.5 * cm)]

    # ── السجل ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(_ar("سجل الأحداث"), head))
    story.append(Spacer(1, 0.15 * cm))
    if not history:
        story.append(Paragraph(_ar("لا توجد أحداث مسجَّلة."), body))
    else:
        hdr = ["التاريخ", "الحدث", "الحالة"]
        pct = [0.2, 0.55, 0.25]
        data = [[Paragraph(_ar(h), cellb) for h in reversed(hdr)]]
        for h in history[:40]:
            who = " (مرافق)" if h.companion_id else ""
            logical = [(h.created_at or "")[:10],
                       (h.action_label or "—") + who,
                       format_status(h.new_status)]
            data.append([Paragraph(_ar(v), cell) for v in reversed(logical)])
        t = Table(data, colWidths=[p * W for p in reversed(pct)],
                  repeatRows=1, hAlign="CENTER")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ECEFF1")),
            ("GRID",       (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t)

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor("#9E9E9E"))
        canvas.drawCentredString(page[0] / 2, 0.7 * cm, str(doc_.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    out = buf.getvalue()
    logger.info(f"[residency.profile_pdf] built  name={profile.name!r}  bytes={len(out)}")
    return out
