# services/data_analysis_pdf.py
# PDF builder for the "📊 تحليل البيانات" (Data Analysis / BI) system.
#
# Same proven stack already used successfully today in
# services/comprehensive_report_pdf.py and services/patient_report_pdf.py:
# reportlab (direct, not HTML/Jinja2) + arabic_reshaper + python-bidi for
# correct Arabic RTL shaping, matplotlib for charts.
#
# Deliberately NOT reusing services/pdf_generator_enhanced.py (Jinja2 +
# WeasyPrint/HTML) — that stack is a different technology and was not
# verified to avoid Arabic character-breaking issues; this file follows
# the pattern already proven correct in this project today.
#
# Usage:
#   buf = build_analysis_pdf(
#       title="تحليل المستشفيات",
#       period_label="مايو 2026",
#       filters_summary={...},
#       stats={"إجمالي الحالات": 120, ...},
#       sections=[
#           {"type": "ranked_table", "title": "المستشفيات", "data": {"Apollo": 22, ...}, "chart": "bar"},
#           {"type": "cross_table", "title": "توزيع الإجراءات حسب القسم", "data": {"قسم": {"إجراء": 3}}},
#           {"type": "text", "title": "رؤى", "text": "..."},
#       ],
#   )

from __future__ import annotations

import io
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Font resolution (same candidates as comprehensive_report_pdf.py) ───────────

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
        "accent":    colors.HexColor("#0288D1"),
        "success":   colors.HexColor("#2E7D32"),
        "warning":   colors.HexColor("#B7950B"),
        "light_bg":  colors.HexColor("#F0F4F8"),
        "card_bg":   colors.HexColor("#FAFCFF"),
        "grid":      colors.HexColor("#D0D9E8"),
        "text_dark": colors.HexColor("#1A237E"),
        "text_gray": colors.HexColor("#546E7A"),
        "white":     colors.white,
    }


# ── Chart generators (same pattern as comprehensive_report_pdf.py) ─────────────

def _bar_chart(data: dict[str, int], title: str, color: str = "#1565C0") -> io.BytesIO | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import arabic_reshaper
        from bidi.algorithm import get_display

        if not data:
            return None
        items = sorted(data.items(), key=lambda x: -x[1])[:12]
        labels = [get_display(arabic_reshaper.reshape(k)) for k, _ in items]
        values = [v for _, v in items]

        fig, ax = plt.subplots(figsize=(10, max(3, len(items) * 0.5)))
        bars = ax.barh(labels, values, color=color, edgecolor="white", height=0.7)
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
        logger.warning(f"[data_analysis_pdf] bar chart failed: {exc}")
        return None


def _pie_chart(data: dict[str, int], title: str) -> io.BytesIO | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import arabic_reshaper
        from bidi.algorithm import get_display

        if not data or sum(data.values()) == 0:
            return None
        items = sorted(data.items(), key=lambda x: -x[1])[:8]
        labels = [get_display(arabic_reshaper.reshape(f"{k} ({v})")) for k, v in items]
        values = [v for _, v in items]
        palette = ["#1565C0", "#2E7D32", "#B7950B", "#922B21", "#7D3C98",
                   "#117A65", "#D35400", "#1A5276"]

        fig, ax = plt.subplots(figsize=(5.5, 4.5))
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, autopct="%1.0f%%",
            colors=palette[:len(values)], startangle=140, pctdistance=0.75,
            textprops={"fontsize": 7},
        )
        for at in autotexts:
            at.set_fontsize(7)
            at.set_color("white")
        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as exc:
        logger.warning(f"[data_analysis_pdf] pie chart failed: {exc}")
        return None


# ── Main API ──────────────────────────────────────────────────────────────────

def build_analysis_pdf(
    title: str,
    period_label: str,
    filters_summary: dict,
    stats: dict[str, int | str],
    sections: list[dict],
) -> io.BytesIO:
    """
    Build a professional Arabic RTL PDF for any data-analysis type.

    title           — e.g. "تحليل المستشفيات"
    period_label    — human-readable period string
    filters_summary — {"hospitals": [...]|None, "departments": [...]|None,
                        "doctors": [...]|None, "actions": [...]|None,
                        "generated_at": datetime}
                       None/empty list → "الكل" for that dimension.
    stats           — flat {label: value} dict for the executive-summary cards
                       (e.g. {"إجمالي الحالات": 120, "المرضى": 45, ...})
    sections        — ordered list of content blocks, each a dict with "type":
        {"type": "ranked_table", "title": str, "data": dict[str,int],
         "chart": "bar"|"pie"|None, "columns": (name_col, count_col)}
        {"type": "cross_table", "title": str, "data": dict[str, dict[str,int]],
         "col1_title": str, "col2_title": str, "top_n": int}
        {"type": "text", "title": str, "text": str}
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, Image, Flowable,
        )
    except ImportError as e:
        logger.error(f"[data_analysis_pdf] reportlab missing: {e}")
        raise

    C = _colors()
    FN = _pick_font(_FONT_CANDIDATES)
    FNB = _pick_font(_FONT_BOLD_CANDIDATES, FN)

    def S(name, **kw):
        if "fontName" not in kw:
            kw["fontName"] = FN
        return ParagraphStyle(name, **kw)

    ST = {
        "cover_title": S("ct",  fontSize=22, leading=28, alignment=TA_CENTER, textColor=C["white"], fontName=FNB),
        "section":     S("sec", fontSize=13, leading=18, alignment=TA_RIGHT,  textColor=C["primary"], fontName=FNB, spaceBefore=10, spaceAfter=4),
        "body":        S("bd",  fontSize=10, leading=14, alignment=TA_RIGHT,  textColor=C["text_dark"]),
        "small":       S("sm",  fontSize=8,  leading=11, alignment=TA_RIGHT,  textColor=C["text_gray"]),
        "th":          S("th",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["white"], fontName=FNB),
        "td_r":        S("tdr", fontSize=8,  leading=11, alignment=TA_RIGHT,  textColor=C["text_dark"]),
        "td_c":        S("tdc", fontSize=8,  leading=11, alignment=TA_CENTER, textColor=C["text_dark"]),
        "stat_label":  S("sl",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_gray"]),
        "stat_value":  S("sv",  fontSize=18, leading=22, alignment=TA_CENTER, textColor=C["primary"], fontName=FNB),
    }

    def P(txt, style_key) -> Paragraph:
        return Paragraph(_ar(txt), ST[style_key])

    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(C["primary"])
        canvas.rect(0, h - 1.3 * cm, w, 1.3 * cm, fill=1, stroke=0)
        canvas.setFillColor(C["white"])
        canvas.setFont(FNB, 10)
        canvas.drawCentredString(w / 2, h - 0.85 * cm, _ar(f"تحليل البيانات — {title}"))
        canvas.setFillColor(C["primary"])
        canvas.rect(0, 0, w, 0.7 * cm, fill=1, stroke=0)
        canvas.setFillColor(C["white"])
        canvas.setFont(FN, 7)
        canvas.drawString(1 * cm, 0.2 * cm, _ar(datetime.utcnow().strftime("%Y-%m-%d")))
        canvas.drawCentredString(w / 2, 0.2 * cm, _ar("سري — للاستخدام الطبي الداخلي"))
        canvas.drawRightString(w - 1 * cm, 0.2 * cm, _ar(f"صفحة {doc.page}"))
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.5 * cm,
    )
    story = []

    # ── Cover page ──────────────────────────────────────────────────────────
    class CoverBand(Flowable):
        def __init__(self, title, period_label):
            Flowable.__init__(self)
            self.width, self.height = 540, 120
            self.title, self.period_label = title, period_label

        def draw(self):
            self.canv.setFillColor(C["primary"])
            self.canv.roundRect(0, 0, self.width, self.height, 10, stroke=0, fill=1)
            self.canv.setFillColor(C["white"])
            self.canv.setFont(FNB, 20)
            self.canv.drawRightString(self.width - 15, self.height - 38, _ar(self.title))
            self.canv.setFont(FN, 11)
            self.canv.setFillColor(C["light_bg"])
            self.canv.drawRightString(self.width - 15, 18, _ar(f"الفترة: {self.period_label}"))

    story.append(CoverBand(title, period_label))
    story.append(Spacer(1, 0.4 * cm))

    # ── Filters used (معايير البحث) ────────────────────────────────────────
    gen_at = filters_summary.get("generated_at") or datetime.utcnow()
    story.append(P("معايير البحث", "section"))
    crit_lines = [
        f"تاريخ إنشاء التقرير: {gen_at.strftime('%Y-%m-%d %H:%M')}",
        f"الفترة: {period_label}",
        "المستشفيات: " + ("، ".join(filters_summary.get("hospitals") or []) or "جميع المستشفيات"),
        "الأقسام: " + ("، ".join(filters_summary.get("departments") or []) or "جميع الأقسام"),
        "الأطباء: " + ("، ".join(filters_summary.get("doctors") or []) or "جميع الأطباء"),
        "أنواع الإجراءات: " + ("، ".join(filters_summary.get("actions") or []) or "جميع الأنواع"),
    ]
    crit_table = Table([[P(line, "body")] for line in crit_lines], colWidths=[18 * cm], hAlign="RIGHT")
    crit_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C["light_bg"]),
        ("GRID", (0, 0), (-1, -1), 0.4, C["grid"]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(crit_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Executive summary (stat cards) ─────────────────────────────────────
    if stats:
        story.append(P("الملخص التنفيذي", "section"))
        items = list(stats.items())
        row_size = 5
        for i in range(0, len(items), row_size):
            chunk = items[i:i + row_size]
            flat = [Table([[P(label, "stat_label")], [P(str(val), "stat_value")]], hAlign="CENTER")
                    for label, val in chunk]
            t = Table([flat], colWidths=[18 * cm / len(chunk)] * len(chunk), hAlign="CENTER")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), C["card_bg"]),
                ("GRID", (0, 0), (-1, -1), 0.5, C["grid"]),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2 * cm))

    # ── Dynamic sections ────────────────────────────────────────────────────
    def _ranked_table_section(sec: dict):
        data: dict[str, int] = sec["data"]
        title_txt = sec["title"]
        col1, col2 = sec.get("columns", ("الاسم", "عدد الحالات"))
        story.append(Spacer(1, 0.3 * cm))
        story.append(P(title_txt, "section"))
        if not data:
            story.append(P("لا توجد بيانات.", "body"))
            return
        total = sum(data.values()) or 1
        rows = [[P(col1, "th"), P(col2, "th"), P("النسبة", "th")]]
        for name, cnt in list(data.items())[:20]:
            pct = f"{cnt / total * 100:.1f}%"
            rows.append([P(name, "td_r"), P(str(cnt), "td_c"), P(pct, "td_c")])
        t = Table(rows, colWidths=[10 * cm, 4 * cm, 4 * cm], hAlign="RIGHT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C["primary"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
            ("GRID", (0, 0), (-1, -1), 0.4, C["grid"]),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

        chart_kind = sec.get("chart")
        if chart_kind == "bar":
            buf_chart = _bar_chart(data, title_txt)
        elif chart_kind == "pie":
            buf_chart = _pie_chart(data, title_txt)
        else:
            buf_chart = None
        if buf_chart:
            img = Image(buf_chart, width=15 * cm, height=max(4 * cm, min(12 * cm, len(data) * 0.5 * cm)))
            img.hAlign = "CENTER"
            story.append(Spacer(1, 0.3 * cm))
            story.append(img)

    def _cross_table_section(sec: dict):
        data: dict[str, dict[str, int]] = sec["data"]
        title_txt = sec["title"]
        col1_title = sec.get("col1_title", "التصنيف")
        col2_title = sec.get("col2_title", "التفصيل")
        top_n = sec.get("top_n", 3)
        story.append(Spacer(1, 0.3 * cm))
        story.append(P(title_txt, "section"))
        if not data:
            story.append(P("لا توجد بيانات.", "body"))
            return
        rows = [[P(col1_title, "th"), P(col2_title, "th"), P("العدد", "th")]]
        for v1, inner in list(data.items())[:15]:
            for v2, cnt in list(inner.items())[:top_n]:
                rows.append([P(v1, "td_r"), P(v2, "td_r"), P(str(cnt), "td_c")])
        t = Table(rows, colWidths=[6 * cm, 9 * cm, 3 * cm], hAlign="RIGHT", repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C["primary"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
            ("GRID", (0, 0), (-1, -1), 0.4, C["grid"]),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)

    def _text_section(sec: dict):
        story.append(Spacer(1, 0.3 * cm))
        story.append(P(sec["title"], "section"))
        for line in str(sec.get("text", "")).split("\n"):
            if line.strip():
                story.append(P(line, "body"))

    has_content = False
    for sec in sections:
        stype = sec.get("type")
        if stype == "ranked_table":
            if sec.get("data"):
                has_content = True
            _ranked_table_section(sec)
        elif stype == "cross_table":
            if sec.get("data"):
                has_content = True
            _cross_table_section(sec)
        elif stype == "text":
            has_content = True
            _text_section(sec)

    if not has_content and not stats:
        story.append(PageBreak())
        story.append(P("لا توجد بيانات مطابقة لمعايير البحث المحددة.", "body"))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(f"[data_analysis_pdf] built  title={title!r}  size={buf.getbuffer().nbytes:,}")
    return buf
