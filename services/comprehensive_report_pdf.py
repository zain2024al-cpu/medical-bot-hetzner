# services/comprehensive_report_pdf.py
# Comprehensive PDF report builder for all cases in a date range.
#
# Usage:
#   reports = await get_reports(start, end)
#   stats = compute_stats(reports)
#   pdf_buf = build_comprehensive_pdf(reports, stats, period_label)

from __future__ import annotations

import io
import logging
import os
from collections import defaultdict
from datetime import date, datetime

logger = logging.getLogger(__name__)

# ── Font resolution ───────────────────────────────────────────────────────────

_FONT_CANDIDATES = [
    ("C:\\Windows\\Fonts\\tahoma.ttf",   "Tahoma"),
    ("C:\\Windows\\Fonts\\arial.ttf",    "Arial"),
    ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", "NotoAr"),
]

_FONT_BOLD_CANDIDATES = [
    ("C:\\Windows\\Fonts\\tahomabd.ttf", "TahomaBd"),
    ("C:\\Windows\\Fonts\\arialbd.ttf",  "ArialBd"),
]


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


def _ar(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text or "")))
    except Exception:
        return str(text or "")


def _colors():
    from reportlab.lib import colors
    return {
        "primary":    colors.HexColor("#1565C0"),
        "accent":     colors.HexColor("#0288D1"),
        "success":    colors.HexColor("#2E7D32"),
        "light_bg":   colors.HexColor("#F0F4F8"),
        "card_bg":    colors.HexColor("#FAFCFF"),
        "grid":       colors.HexColor("#D0D9E8"),
        "text_dark":  colors.HexColor("#1A237E"),
        "text_gray":  colors.HexColor("#546E7A"),
        "white":      colors.white,
    }


def _fmt_date(d) -> str:
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _action_bar_chart(action_counts: dict[str, int], font_name: str) -> io.BytesIO | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import arabic_reshaper
        from bidi.algorithm import get_display

        if not action_counts:
            return None

        items = sorted(action_counts.items(), key=lambda x: -x[1])[:12]
        labels = [get_display(arabic_reshaper.reshape(k)) for k, _ in items]
        values = [v for _, v in items]

        fig, ax = plt.subplots(figsize=(10, max(3, len(items) * 0.5)))
        bars = ax.barh(labels, values, color="#1565C0", edgecolor="white", height=0.7)
        for bar, v in zip(bars, values):
            ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                    str(v), va="center", fontsize=9, color="#333")
        ax.set_xlim(0, max(values) * 1.2 if values else 1)
        ax.invert_yaxis()
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="y", labelsize=8)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as exc:
        logger.warning(f"[comprehensive_pdf] chart failed: {exc}")
        return None


def _date_line_chart(date_counts: dict[date, int], font_name: str) -> io.BytesIO | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime

        if not date_counts:
            return None

        dates = sorted(date_counts.keys())
        counts = [date_counts[d] for d in dates]

        fig, ax = plt.subplots(figsize=(12, 3.5))
        ax.plot(dates, counts, marker="o", color="#1565C0", linewidth=2, markersize=5)
        ax.fill_between(dates, counts, alpha=0.2, color="#1565C0")
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        plt.xticks(rotation=45)
        ax.set_ylabel("عدد الحالات", fontsize=10)
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as exc:
        logger.warning(f"[comprehensive_pdf] date chart failed: {exc}")
        return None


# ── Main API ──────────────────────────────────────────────────────────────────

def build_comprehensive_pdf(
    reports: list[dict],
    stats: dict,
    period_label: str,
) -> io.BytesIO:
    """
    Build a comprehensive PDF report covering all cases in a date range.

    reports — list of report dicts from get_reports()
    stats   — dict from compute_stats()
    period_label — human-readable period string
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, Image, HRFlowable,
        )
    except ImportError as e:
        logger.error(f"[comprehensive_pdf] reportlab missing: {e}")
        raise

    C   = _colors()
    FN  = _pick_font(_FONT_CANDIDATES)
    FNB = _pick_font(_FONT_BOLD_CANDIDATES, FN)

    # ── Styles ────────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()

    def S(name, **kw):
        # Use FN as default fontName, but allow override via kw
        if "fontName" not in kw:
            kw["fontName"] = FN
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    ST = {
        "cover_title":  S("ct",  fontSize=24, leading=32, alignment=TA_CENTER, textColor=C["white"],    fontName=FNB),
        "section":      S("sec", fontSize=13, leading=18, alignment=TA_RIGHT,  textColor=C["primary"],  fontName=FNB, spaceBefore=10, spaceAfter=4),
        "body":         S("bd",  fontSize=10, leading=14, alignment=TA_RIGHT,  textColor=C["text_dark"]),
        "small":        S("sm",  fontSize=8,  leading=11, alignment=TA_RIGHT,  textColor=C["text_gray"]),
        "th":           S("th",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["white"],    fontName=FNB),
        "td_r":         S("tdr", fontSize=8,  leading=11, alignment=TA_RIGHT,  textColor=C["text_dark"]),
        "td_c":         S("tdc", fontSize=8,  leading=11, alignment=TA_CENTER, textColor=C["text_dark"]),
        "stat_label":   S("sl",  fontSize=10, leading=14, alignment=TA_CENTER, textColor=C["text_gray"]),
        "stat_value":   S("sv",  fontSize=20, leading=26, alignment=TA_CENTER, textColor=C["primary"],  fontName=FNB),
    }

    def P(txt, style_key) -> Paragraph:
        return Paragraph(_ar(txt), ST[style_key])

    # ── Header/footer on each page ────────────────────────────────────────────
    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        # Top
        canvas.setFillColor(C["primary"])
        canvas.rect(0, h - 1.3 * cm, w, 1.3 * cm, fill=1, stroke=0)
        canvas.setFillColor(C["white"])
        canvas.setFont(FNB, 10)
        canvas.drawCentredString(w / 2, h - 0.85 * cm, _ar("التقرير الشامل للحالات الطبية"))
        # Footer
        canvas.setFillColor(C["primary"])
        canvas.rect(0, 0, w, 0.7 * cm, fill=1, stroke=0)
        canvas.setFillColor(C["white"])
        canvas.setFont(FN, 7)
        canvas.drawString(1 * cm, 0.2 * cm, _ar(datetime.utcnow().strftime("%Y-%m-%d")))
        canvas.drawCentredString(w / 2, 0.2 * cm, _ar("سري — للاستخدام الطبي الداخلي"))
        canvas.drawRightString(w - 1 * cm, 0.2 * cm, _ar(f"صفحة {doc.page}"))
        canvas.restoreState()

    # ── Build ─────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.5 * cm,
    )
    story = []

    # Cover
    class CoverBand:
        def __init__(self):
            self.width, self.height = 540, 120

        def drawOn(self, canvas, x, y):
            canvas.setFillColor(C["primary"])
            canvas.roundRect(x, y, self.width, self.height, 10, stroke=0, fill=1)
            canvas.setFillColor(C["white"])
            canvas.setFont(FNB, 20)
            canvas.drawRightString(x + self.width - 15, y + self.height - 38, _ar("التقرير الشامل"))
            canvas.setFont(FN, 11)
            canvas.setFillColor(C["light_bg"])
            canvas.drawRightString(x + self.width - 15, y + 18, _ar(f"الفترة: {period_label}"))

    story.append(CoverBand())
    story.append(Spacer(1, 0.4 * cm))

    # ── Summary stats ─────────────────────────────────────────────────────────
    stat_rows = [[
        [P("إجمالي الحالات",      "stat_label"), P(str(stats["total"]),               "stat_value")],
        [P("المرضى",              "stat_label"), P(str(stats["unique_patients"]),     "stat_value")],
        [P("المستشفيات",          "stat_label"), P(str(stats["unique_hospitals"]),   "stat_value")],
        [P("الأقسام",              "stat_label"), P(str(stats["unique_depts"]),       "stat_value")],
        [P("الإجراءات",            "stat_label"), P(str(stats["unique_actions"]),     "stat_value")],
    ]]
    flat_stat = []
    for cell_pair in stat_rows[0]:
        flat_stat.append(Table([[cell_pair[0]], [cell_pair[1]]], hAlign="CENTER"))

    stat_table = Table([flat_stat], colWidths=[4 * cm] * 5, hAlign="CENTER")
    stat_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, -1), C["card_bg"]),
        ("GRID",           (0, 0), (-1, -1), 0.5, C["grid"]),
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Aggregations ──────────────────────────────────────────────────────────
    from .reports_repository import (
        aggregate_by_hospital, aggregate_by_department,
        aggregate_by_action, aggregate_by_date,
    )

    hosp_counts = aggregate_by_hospital(reports)
    dept_counts = aggregate_by_department(reports)
    action_counts = aggregate_by_action(reports)
    date_counts = aggregate_by_date(reports)

    # Hospitals table
    story.append(P("المستشفيات", "section"))
    hosp_rows = [[P("المستشفى", "th"), P("عدد الحالات", "th")]]
    for h, cnt in hosp_counts.items():
        hosp_rows.append([P(h, "td_r"), P(str(cnt), "td_c")])
    ht = Table(hosp_rows, colWidths=[13 * cm, 3 * cm], hAlign="RIGHT")
    ht.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
        ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",          (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.3 * cm))

    # Departments table
    story.append(P("الأقسام", "section"))
    dept_rows = [[P("القسم", "th"), P("عدد الحالات", "th")]]
    for d, cnt in list(dept_counts.items())[:15]:
        dept_rows.append([P(d, "td_r"), P(str(cnt), "td_c")])
    dt = Table(dept_rows, colWidths=[13 * cm, 3 * cm], hAlign="RIGHT")
    dt.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
        ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",          (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(dt)
    story.append(Spacer(1, 0.3 * cm))

    # Actions table
    story.append(P("الإجراءات", "section"))
    act_rows = [[P("نوع الإجراء", "th"), P("عدد الحالات", "th"), P("النسبة", "th")]]
    total = stats["total"] or 1
    for a, cnt in list(action_counts.items())[:15]:
        pct = f"{cnt / total * 100:.1f}%"
        act_rows.append([P(a, "td_r"), P(str(cnt), "td_c"), P(pct, "td_c")])
    at = Table(act_rows, colWidths=[10 * cm, 3 * cm, 3 * cm], hAlign="RIGHT")
    at.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
        ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
    ]))
    story.append(at)

    # ── Charts ────────────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(P("الرسوم البيانية", "section"))

    # Action chart
    chart_buf = _action_bar_chart(action_counts, FN)
    if chart_buf:
        img = Image(chart_buf, width=15 * cm, height=max(4 * cm, len(action_counts) * 0.5 * cm))
        img.hAlign = "CENTER"
        story.append(Spacer(1, 0.3 * cm))
        story.append(P("توزيع الإجراءات", "section"))
        story.append(img)

    # Date chart
    if len(date_counts) > 1:
        date_buf = _date_line_chart(date_counts, FN)
        if date_buf:
            img = Image(date_buf, width=15 * cm, height=4 * cm)
            img.hAlign = "CENTER"
            story.append(Spacer(1, 0.3 * cm))
            story.append(P("التوزيع الزمني", "section"))
            story.append(img)

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(
        f"[comprehensive_pdf] built  reports={len(reports)}  "
        f"patients={stats['unique_patients']}  size={buf.getbuffer().nbytes:,}"
    )
    return buf
