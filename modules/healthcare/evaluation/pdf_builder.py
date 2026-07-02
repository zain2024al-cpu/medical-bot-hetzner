# modules/healthcare/evaluation/pdf_builder.py
# Professional Arabic RTL PDF report for a single healthcare specialist.
#
# Stack:
#   reportlab   — layout engine (Platypus)
#   arabic_reshaper + python-bidi — proper Arabic shaping & direction
#   matplotlib  — bar/pie charts embedded as images
#
# Usage:
#   buf = build_evaluation_pdf(data)   → io.BytesIO ready for bot.send_document()

from __future__ import annotations

import io
import os
import logging
import tempfile
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ── Font paths ────────────────────────────────────────────────────────────────

_HERE       = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR  = os.path.normpath(os.path.join(_HERE, "..", "..", "..", "assets", "fonts"))
_FONT_REG   = os.path.join(_FONTS_DIR, "Arabic-Regular.ttf")
_FONT_BOLD  = os.path.join(_FONTS_DIR, "Arabic-Bold.ttf")

# fallback to system Arial on Windows
if not os.path.isfile(_FONT_REG):
    _FONT_REG = "C:/Windows/Fonts/arial.ttf"
if not os.path.isfile(_FONT_BOLD):
    _FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"


# ── Arabic text helper ────────────────────────────────────────────────────────

def _ar(text: str) -> str:
    """Reshape + apply bidi so ReportLab renders Arabic correctly (RTL)."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


# ── Color palette ─────────────────────────────────────────────────────────────

from reportlab.lib import colors

C_PRIMARY   = colors.HexColor("#1B4F8A")   # deep blue
C_ACCENT    = colors.HexColor("#2E86C1")   # mid blue
C_LIGHT_BG  = colors.HexColor("#EBF5FB")  # pale blue background
C_SUCCESS   = colors.HexColor("#1E8449")   # green
C_WARNING   = colors.HexColor("#B7950B")   # amber
C_DANGER    = colors.HexColor("#922B21")   # red
C_GRAY      = colors.HexColor("#566573")   # gray text
C_BORDER    = colors.HexColor("#AED6F1")   # table border
C_ROW_ALT   = colors.HexColor("#F2F9FF")   # alternating table row
C_WHITE     = colors.white
C_BLACK     = colors.black


# ── ReportLab setup ───────────────────────────────────────────────────────────

from reportlab.pdfbase            import pdfmetrics
from reportlab.pdfbase.ttfonts    import TTFont
from reportlab.lib.pagesizes      import A4
from reportlab.lib.units          import cm, mm
from reportlab.lib.styles         import ParagraphStyle
from reportlab.lib.enums          import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus           import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image, KeepTogether,
)
from reportlab.platypus.flowables import Flowable

_fonts_registered = False

def _register_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    try:
        pdfmetrics.registerFont(TTFont("ArabicReg",  _FONT_REG))
        pdfmetrics.registerFont(TTFont("ArabicBold", _FONT_BOLD))
        _fonts_registered = True
        logger.debug(f"[pdf_builder] fonts registered  reg={_FONT_REG}")
    except Exception as exc:
        logger.error(f"[pdf_builder] font registration failed: {exc}")


# ── Paragraph styles ──────────────────────────────────────────────────────────

def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title", fontName="ArabicBold", fontSize=22, leading=28,
            alignment=TA_CENTER, textColor=C_WHITE, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="ArabicReg", fontSize=13, leading=18,
            alignment=TA_CENTER, textColor=C_WHITE, spaceAfter=2,
        ),
        "section": ParagraphStyle(
            "section", fontName="ArabicBold", fontSize=13, leading=18,
            alignment=TA_RIGHT, textColor=C_PRIMARY, spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", fontName="ArabicReg", fontSize=10, leading=14,
            alignment=TA_RIGHT, textColor=C_BLACK,
        ),
        "small": ParagraphStyle(
            "small", fontName="ArabicReg", fontSize=8, leading=12,
            alignment=TA_RIGHT, textColor=C_GRAY,
        ),
        "stat_label": ParagraphStyle(
            "stat_label", fontName="ArabicReg", fontSize=9, leading=12,
            alignment=TA_CENTER, textColor=C_GRAY,
        ),
        "stat_value": ParagraphStyle(
            "stat_value", fontName="ArabicBold", fontSize=20, leading=24,
            alignment=TA_CENTER, textColor=C_PRIMARY,
        ),
        "table_header": ParagraphStyle(
            "table_header", fontName="ArabicBold", fontSize=9, leading=12,
            alignment=TA_CENTER, textColor=C_WHITE,
        ),
        "table_cell": ParagraphStyle(
            "table_cell", fontName="ArabicReg", fontSize=8, leading=11,
            alignment=TA_RIGHT, textColor=C_BLACK,
        ),
        "table_cell_c": ParagraphStyle(
            "table_cell_c", fontName="ArabicReg", fontSize=8, leading=11,
            alignment=TA_CENTER, textColor=C_BLACK,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="ArabicReg", fontSize=7, leading=10,
            alignment=TA_CENTER, textColor=C_GRAY,
        ),
    }


# ── Custom flowable: colored stat card ───────────────────────────────────────

class StatCard(Flowable):
    """A small colored box showing a number + label."""
    def __init__(self, value: str, label: str, color=None, width=3.8*cm, height=2.2*cm):
        super().__init__()
        self.value  = value
        self.label  = label
        self.color  = color or C_PRIMARY
        self.width  = width
        self.height = height

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(self.color)
        c.roundRect(0, 0, self.width, self.height, 4*mm, fill=1, stroke=0)
        # Value
        c.setFillColor(C_WHITE)
        c.setFont("ArabicBold", 18)
        c.drawCentredString(self.width / 2, self.height * 0.45, self.value)
        # Label
        c.setFont("ArabicReg", 8)
        c.drawCentredString(self.width / 2, self.height * 0.18, _ar(self.label))


# ── Cover page ────────────────────────────────────────────────────────────────

class _CoverCanvas:
    """Mixin for the first page: dark gradient header."""
    pass


def _on_first_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    # Header block
    canvas.setFillColor(C_PRIMARY)
    canvas.rect(0, h - 8*cm, w, 8*cm, fill=1, stroke=0)
    # Accent strip
    canvas.setFillColor(C_ACCENT)
    canvas.rect(0, h - 8.3*cm, w, 0.3*cm, fill=1, stroke=0)
    _draw_footer(canvas, doc)
    canvas.restoreState()


def _on_later_pages(canvas, doc):
    canvas.saveState()
    w, h = A4
    # Thin header bar
    canvas.setFillColor(C_PRIMARY)
    canvas.rect(0, h - 1.5*cm, w, 1.5*cm, fill=1, stroke=0)
    canvas.setFillColor(C_WHITE)
    canvas.setFont("ArabicBold", 9)
    canvas.drawCentredString(w / 2, h - 1.0*cm, _ar(f"تقرير تقييم الأداء — {doc._eval_specialist}"))
    _draw_footer(canvas, doc)
    canvas.restoreState()


def _draw_footer(canvas, doc):
    w, _ = A4
    canvas.setFillColor(C_PRIMARY)
    canvas.rect(0, 0, w, 0.8*cm, fill=1, stroke=0)
    canvas.setFillColor(C_WHITE)
    canvas.setFont("ArabicReg", 7)
    date_str = _ar(datetime.utcnow().strftime("%Y-%m-%d"))
    canvas.drawString(1*cm, 0.25*cm, date_str)
    canvas.drawCentredString(w / 2, 0.25*cm, _ar("نظام الرعاية الصحية — سري وللاستخدام الداخلي"))
    canvas.drawRightString(w - 1*cm, 0.25*cm, _ar(f"صفحة {doc.page}"))


# ── Chart generators ──────────────────────────────────────────────────────────

def _bar_chart(data: dict[str, int], title: str, color: str = "#2E86C1") -> io.BytesIO:
    """Horizontal bar chart → PNG bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import arabic_reshaper
    from bidi.algorithm import get_display

    if not data:
        return None

    labels = [get_display(arabic_reshaper.reshape(k)) for k in data.keys()]
    values = list(data.values())

    fig, ax = plt.subplots(figsize=(7, max(2, len(labels) * 0.45)))
    bars = ax.barh(labels, values, color=color, edgecolor="white", height=0.6)

    # Value labels
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                str(v), va="center", fontsize=8, color="#333")

    ax.set_xlim(0, max(values) * 1.2 if values else 1)
    ax.invert_yaxis()
    ax.set_xlabel("")
    ax.set_title(get_display(arabic_reshaper.reshape(title)), fontsize=10, pad=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=8)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _pie_chart(data: dict[str, int], title: str) -> io.BytesIO:
    """Pie chart → PNG bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import arabic_reshaper
    from bidi.algorithm import get_display

    if not data or sum(data.values()) == 0:
        return None

    labels = [get_display(arabic_reshaper.reshape(f"{k} ({v})")) for k, v in data.items()]
    values = list(data.values())
    palette = ["#2E86C1", "#1E8449", "#B7950B", "#922B21", "#7D3C98",
               "#117A65", "#D35400", "#1A5276"]

    fig, ax = plt.subplots(figsize=(5, 4))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct="%1.0f%%",
        colors=palette[:len(values)],
        startangle=140, pctdistance=0.75,
        textprops={"fontsize": 7},
    )
    for at in autotexts:
        at.set_fontsize(7)
        at.set_color("white")
    ax.set_title(get_display(arabic_reshaper.reshape(title)), fontsize=10, pad=8)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _activity_chart(cases_by_date: dict[str, int]) -> io.BytesIO:
    """Bar chart of daily case counts over the period."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not cases_by_date:
        return None

    dates  = sorted(cases_by_date.keys())
    counts = [cases_by_date[d] for d in dates]

    # Shorten labels
    short = [d[5:] for d in dates]   # "MM-DD"

    fig, ax = plt.subplots(figsize=(max(6, len(dates) * 0.4), 3))
    ax.bar(range(len(dates)), counts, color="#2E86C1", edgecolor="white", width=0.7)
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(short, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("الحالات", fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=8)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Main builder ──────────────────────────────────────────────────────────────

def build_evaluation_pdf(data) -> io.BytesIO:
    """
    Build a professional Arabic RTL PDF evaluation report.
    Returns an io.BytesIO buffer ready for bot.send_document().
    """
    from .repository import EvaluationData
    assert isinstance(data, EvaluationData)

    _register_fonts()
    S = _styles()
    w_page, h_page = A4
    margin = 1.8 * cm

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=9 * cm,   # space for header on page 1
        bottomMargin=1.5 * cm,
    )
    doc._eval_specialist = data.specialist_name   # used by header/footer

    story = []

    # ── 1. Cover content (inside the header area, drawn by canvas) ────────────
    period_str = _ar(
        f"{data.period_start.strftime('%Y/%m/%d')} — {data.period_end.strftime('%Y/%m/%d')}"
    )
    story.append(Spacer(1, -5.5 * cm))   # pull up into the blue header zone
    story.append(Paragraph(_ar("تقرير تقييم الأداء الصحي"), S["title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(_ar(data.specialist_name), S["subtitle"]))
    story.append(Paragraph(_ar(f"الفترة: {period_str}"), S["subtitle"]))
    story.append(Spacer(1, 5.5 * cm))   # push back down

    # ── 2. Executive summary — stat cards ────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=6))
    story.append(Paragraph(_ar("الملخص التنفيذي"), S["section"]))

    doc_pct = (
        int(data.cases_with_images / data.total_cases * 100)
        if data.total_cases else 0
    )
    avg_per_day = (
        f"{data.total_cases / max(data.active_days, 1):.1f}"
        if data.total_cases else "0"
    )

    cards = [
        (str(data.total_cases),      "إجمالي الحالات",    C_PRIMARY),
        (str(data.woundcare_count),  "مجارحة",             C_ACCENT),
        (str(data.followup_count),   "معاينة",             C_SUCCESS),
        (str(data.medication_count), "صيدلية",             C_WARNING),
        (str(data.supplies_count),   "مستلزمات",           C_DANGER),
    ]
    card_row = [[StatCard(v, l, c) for v, l, c in cards]]
    card_table = Table(card_row, colWidths=[3.8 * cm] * 5, hAlign="CENTER")
    card_table.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER")]))
    story.append(card_table)
    story.append(Spacer(1, 0.4 * cm))

    # Secondary stats
    sec_data = [
        [
            _p(_ar("أيام النشاط"),          S["stat_label"]),
            _p(_ar("متوسط الحالات / يوم"),  S["stat_label"]),
            _p(_ar("مرضى فريدون"),           S["stat_label"]),
            _p(_ar("نسبة التوثيق"),          S["stat_label"]),
        ],
        [
            _p(_ar(str(data.active_days)),     S["stat_value"]),
            _p(_ar(avg_per_day),               S["stat_value"]),
            _p(_ar(str(data.unique_patients)), S["stat_value"]),
            _p(_ar(f"{doc_pct}%"),             S["stat_value"]),
        ],
    ]
    sec_table = Table(sec_data, colWidths=[4.3 * cm] * 4, hAlign="CENTER")
    sec_table.setStyle(TableStyle([
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("BACKGROUND", (0,0), (-1,0),  C_LIGHT_BG),
        ("GRID",       (0,0), (-1,-1), 0.5, C_BORDER),
        ("ROUNDEDCORNERS", [3*mm]),
    ]))
    story.append(sec_table)

    # ── 3. Service mix pie chart ──────────────────────────────────────────────
    service_mix = {k: v for k, v in {
        "مجارحة":    data.woundcare_count,
        "معاينة":    data.followup_count,
        "صيدلية":   data.medication_count,
        "مستلزمات": data.supplies_count,
    }.items() if v > 0}

    if len(service_mix) > 1:
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(_ar("توزيع الخدمات"), S["section"]))
        pie_buf = _pie_chart(service_mix, "توزيع الخدمات")
        if pie_buf:
            img = Image(pie_buf, width=9*cm, height=7*cm)
            img.hAlign = "CENTER"
            story.append(img)

    # ── 4. Departments table ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph(_ar("الأقسام الطبية"), S["section"]))

    if data.department_counts:
        dept_rows = [[
            _p(_ar("القسم"),         S["table_header"]),
            _p(_ar("عدد الحالات"),   S["table_header"]),
            _p(_ar("النسبة"),        S["table_header"]),
        ]]
        total = sum(data.department_counts.values())
        for i, (dept, cnt) in enumerate(data.department_counts.items()):
            pct = f"{cnt/total*100:.1f}%" if total else "—"
            bg  = C_ROW_ALT if i % 2 == 0 else C_WHITE
            dept_rows.append([
                _p(_ar(dept), S["table_cell"]),
                _p(str(cnt),  S["table_cell_c"]),
                _p(pct,       S["table_cell_c"]),
            ])
        dept_table = _make_table(dept_rows, [10*cm, 3.5*cm, 3.5*cm])
        story.append(dept_table)

        # Bar chart
        chart_buf = _bar_chart(data.department_counts, "الأقسام الطبية")
        if chart_buf:
            story.append(Spacer(1, 0.4*cm))
            img = Image(chart_buf, width=15*cm, height=min(12*cm, max(3*cm, len(data.department_counts)*0.55*cm)))
            img.hAlign = "CENTER"
            story.append(img)
    else:
        story.append(Paragraph(_ar("لا توجد بيانات أقسام."), S["body"]))

    # ── 4.5 Specialist breakdown (comprehensive report only) ──────────────────
    # ✅ تظهر فقط في التقرير الشامل (أكثر من صحي واحد في البيانات) —
    # في تقرير الصحي الفردي يكون specialist_counts دائماً عنصراً واحداً.
    if len(data.specialist_counts) > 1:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(_ar("التوزيع حسب الصحي"), S["section"]))

        spec_rows = [[
            _p(_ar("الصحي"),         S["table_header"]),
            _p(_ar("عدد الحالات"),   S["table_header"]),
            _p(_ar("النسبة"),        S["table_header"]),
        ]]
        spec_total = sum(data.specialist_counts.values())
        for spec_name, cnt in data.specialist_counts.items():
            pct = f"{cnt/spec_total*100:.1f}%" if spec_total else "—"
            spec_rows.append([
                _p(_ar(spec_name), S["table_cell"]),
                _p(str(cnt),       S["table_cell_c"]),
                _p(pct,            S["table_cell_c"]),
            ])
        story.append(_make_table(spec_rows, [10*cm, 3.5*cm, 3.5*cm]))

        spec_chart_buf = _bar_chart(data.specialist_counts, "التوزيع حسب الصحي", color="#1E8449")
        if spec_chart_buf:
            story.append(Spacer(1, 0.4*cm))
            img = Image(
                spec_chart_buf, width=15*cm,
                height=min(12*cm, max(3*cm, len(data.specialist_counts)*0.55*cm)),
            )
            img.hAlign = "CENTER"
            story.append(img)

    # ── 5. Documentation analysis ─────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(_ar("تحليل التوثيق"), S["section"]))

    doc_rows = [
        [_p(_ar("البيان"), S["table_header"]), _p(_ar("القيمة"), S["table_header"])],
        [_p(_ar("حالات موثقة بصور"),   S["table_cell"]),
         _p(str(data.cases_with_images),    S["table_cell_c"])],
        [_p(_ar("حالات بدون صور"),     S["table_cell"]),
         _p(str(data.cases_without_images), S["table_cell_c"])],
        [_p(_ar("إجمالي الصور المرفوعة"), S["table_cell"]),
         _p(str(data.total_images),         S["table_cell_c"])],
        [_p(_ar("نسبة التوثيق"),       S["table_cell"]),
         _p(_ar(_doc_quality_label(doc_pct)), S["table_cell_c"])],
    ]
    story.append(_make_table(doc_rows, [12*cm, 5*cm]))

    # ── 6. Activity analysis ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph(_ar("تحليل النشاط"), S["section"]))

    first_s = data.first_case_dt.strftime("%Y-%m-%d") if data.first_case_dt else "—"
    last_s  = data.last_case_dt.strftime("%Y-%m-%d")  if data.last_case_dt  else "—"
    total_days = (data.period_end - data.period_start).days + 1

    act_rows = [
        [_p(_ar("البيان"), S["table_header"]), _p(_ar("القيمة"), S["table_header"])],
        [_p(_ar("أول حالة"),         S["table_cell"]), _p(_ar(first_s), S["table_cell_c"])],
        [_p(_ar("آخر حالة"),         S["table_cell"]), _p(_ar(last_s),  S["table_cell_c"])],
        [_p(_ar("أيام النشاط الفعلي"), S["table_cell"]),
         _p(f"{data.active_days} / {total_days}", S["table_cell_c"])],
        [_p(_ar("مرضى فريدون"),      S["table_cell"]), _p(str(data.unique_patients), S["table_cell_c"])],
        [_p(_ar("مرضى بزيارات متعددة"), S["table_cell"]), _p(str(data.repeat_patients), S["table_cell_c"])],
    ]
    story.append(_make_table(act_rows, [12*cm, 5*cm]))

    # Daily activity chart
    if data.cases_by_date:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(_ar("توزيع الحالات حسب التاريخ"), S["section"]))
        act_buf = _activity_chart(data.cases_by_date)
        if act_buf:
            img = Image(act_buf, width=16*cm, height=5*cm)
            img.hAlign = "CENTER"
            story.append(img)

    # Weekday distribution
    if data.cases_by_weekday:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(_ar("توزيع الحالات حسب أيام الأسبوع"), S["section"]))
        wd_buf = _bar_chart(data.cases_by_weekday, "النشاط الأسبوعي", "#1E8449")
        if wd_buf:
            img = Image(wd_buf, width=12*cm, height=5*cm)
            img.hAlign = "CENTER"
            story.append(img)

    # ── 7. Woundcare phase breakdown ──────────────────────────────────────────
    if data.phase_counts:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(_ar("مراحل المجارحة"), S["section"]))
        phase_rows = [[_p(_ar("المرحلة"), S["table_header"]), _p(_ar("عدد الحالات"), S["table_header"])]]
        for i, (ph, cnt) in enumerate(sorted(data.phase_counts.items(), key=lambda x: -x[1])):
            bg = C_ROW_ALT if i % 2 == 0 else C_WHITE
            phase_rows.append([_p(_ar(ph), S["table_cell"]), _p(str(cnt), S["table_cell_c"])])
        story.append(_make_table(phase_rows, [12*cm, 5*cm]))

    # ── 8. Medication dispense source breakdown ───────────────────────────────
    if data.dispense_source_counts:
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(_ar("مصادر صرف الأدوية"), S["section"]))
        disp_buf = _pie_chart(data.dispense_source_counts, "مصادر الصرف")
        if disp_buf:
            img = Image(disp_buf, width=8*cm, height=6*cm)
            img.hAlign = "CENTER"
            story.append(img)

    # ── 9. Case details table ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph(_ar("تفاصيل الحالات"), S["section"]))

    if data.cases:
        detail_rows = [[
            _p(_ar("التاريخ"),      S["table_header"]),
            _p(_ar("المريض"),       S["table_header"]),
            _p(_ar("الخدمة"),       S["table_header"]),
            _p(_ar("القسم"),        S["table_header"]),
            _p(_ar("التفاصيل"),     S["table_header"]),
            _p(_ar("صور"),          S["table_header"]),
        ]]
        for i, row in enumerate(data.cases):
            date_s = row.created_at.strftime("%Y-%m-%d") if row.created_at else "—"
            depts  = ", ".join(row.departments[:2]) if row.departments else "—"
            detail = row.detail if isinstance(row.detail, str) else (row.detail[0] if row.detail else "—")
            bg     = C_ROW_ALT if i % 2 == 0 else C_WHITE
            detail_rows.append([
                _p(_ar(date_s),              S["table_cell_c"]),
                _p(_ar(row.patient_name[:18]), S["table_cell"]),
                _p(_ar(row.service_label),   S["table_cell_c"]),
                _p(_ar(depts[:20]),          S["table_cell"]),
                _p(_ar(str(detail)[:20]),    S["table_cell"]),
                _p(str(row.image_count),     S["table_cell_c"]),
            ])

        detail_table = _make_table(
            detail_rows,
            [2.5*cm, 4*cm, 2.2*cm, 4*cm, 3.3*cm, 1.3*cm],
            row_colors=True,
        )
        story.append(detail_table)
    else:
        story.append(Paragraph(_ar("لا توجد حالات في هذه الفترة."), S["body"]))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)
    buf.seek(0)
    logger.info(
        f"[pdf_builder] PDF built"
        f"  specialist={data.specialist_name!r}"
        f"  cases={data.total_cases}"
        f"  size={buf.getbuffer().nbytes:,} bytes"
    )
    return buf


# ── Utility helpers ───────────────────────────────────────────────────────────

def _p(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def _make_table(rows, col_widths, row_colors: bool = False) -> Table:
    t = Table(rows, colWidths=col_widths, repeatRows=1, hAlign="CENTER")
    style_cmds = [
        ("BACKGROUND",  (0, 0), (-1, 0),  C_PRIMARY),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  C_WHITE),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_BORDER),
        ("FONTNAME",    (0, 0), (-1, 0),  "ArabicBold"),
        ("FONTSIZE",    (0, 0), (-1, 0),  9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_ROW_ALT]),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t


def _doc_quality_label(pct: int) -> str:
    if pct >= 80:
        return f"{pct}% — ممتاز ✓"
    if pct >= 50:
        return f"{pct}% — جيد"
    return f"{pct}% — يحتاج تحسين"
