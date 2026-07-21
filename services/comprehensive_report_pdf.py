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


def _ar_wrap(text, font_name: str, font_size: float, max_width_pts: float) -> str:
    """يلفّ النص يدوياً كلمة-كلمة ضمن العرض المتاح، ثم يُطبِّق reshape+bidi على
    كل سطر منجَز على حدة — يمنع تكسّر نص مختلط عربي/إنجليزي طويل (مثل اسم
    عملية بالإنجليزي داخل قرار الطبيب) عند لف Paragraph التلقائي لسلسلة
    أُعيد ترتيبها بصرياً بالفعل (نفس الإصلاح في services/patient_report_pdf.py
    وservices/pharmacy_evacuation_pdf.py)."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    s = str(text or "").strip()
    if not s:
        return ""

    words = s.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = current + [word]
        shaped_candidate = _ar(" ".join(candidate))
        w = stringWidth(shaped_candidate, font_name, font_size)
        if w <= max_width_pts or not current:
            current = candidate
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))

    return "<br/>".join(_ar(line) for line in lines)


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
    filters_summary: dict | None = None,
) -> io.BytesIO:
    """
    Build a comprehensive PDF report covering all cases in a date range.

    reports — list of report dicts from get_reports()
    stats   — dict from compute_stats()
    period_label — human-readable period string
    filters_summary — optional dict describing the applied filters, rendered
        as a "معايير البحث" section on the first page. Shape:
        {
            "hospitals":   list[str] | None,   # None/empty → "جميع المستشفيات"
            "departments": list[str] | None,
            "doctors":     list[str] | None,
            "actions":     list[str] | None,
        }
        Backward compatible: omitting this parameter entirely reproduces the
        exact previous PDF output (no filters section rendered).
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, Image, HRFlowable, Flowable,
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

    def P_wrap(txt, style_key, max_width_pts) -> Paragraph:
        """مثل P، لكن يلفّ يدوياً قبل reshape/bidi — للخلايا المعرَّضة لنص
        طويل مختلط عربي/إنجليزي (تفاصيل الحالة، اسم العملية بالإنجليزي)."""
        style = ST[style_key]
        usable_width = max(max_width_pts - 8, 20)
        wrapped = _ar_wrap(txt, style.fontName, style.fontSize, usable_width)
        return Paragraph(wrapped, style)

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
    class CoverBand(Flowable):
        def __init__(self, period_label):
            Flowable.__init__(self)
            self.width = 540
            self.height = 120
            self.period_label = period_label

        def draw(self):
            self.canv.setFillColor(C["primary"])
            self.canv.roundRect(0, 0, self.width, self.height, 10, stroke=0, fill=1)
            self.canv.setFillColor(C["white"])
            self.canv.setFont(FNB, 20)
            self.canv.drawRightString(self.width - 15, self.height - 38, _ar("التقرير الشامل"))
            self.canv.setFont(FN, 11)
            self.canv.setFillColor(C["light_bg"])
            self.canv.drawRightString(self.width - 15, 18, _ar(f"الفترة: {self.period_label}"))

    story.append(CoverBand(period_label))
    story.append(Spacer(1, 0.4 * cm))

    # ── Search criteria (معايير البحث) ────────────────────────────────────────
    # ✅ يظهر فقط عند تمرير filters_summary — التوليد القديم بدون هذا المعامل
    # ينتج نفس الملف السابق تماماً بدون أي تغيير.
    if filters_summary is not None:
        story.append(P("معايير البحث", "section"))
        gen_at = filters_summary.get("generated_at") or datetime.utcnow()
        crit_lines = [
            f"تاريخ إنشاء التقرير: {gen_at.strftime('%Y-%m-%d %H:%M')}",
            f"الفترة: {period_label}",
            "المستشفيات: " + ("، ".join(filters_summary.get("hospitals") or []) or "جميع المستشفيات"),
            "الأقسام: " + ("، ".join(filters_summary.get("departments") or []) or "جميع الأقسام"),
            "الأطباء: " + ("، ".join(filters_summary.get("doctors") or []) or "جميع الأطباء"),
            "أنواع الإجراءات: " + ("، ".join(filters_summary.get("actions") or []) or "جميع الأنواع"),
        ]
        crit_rows = [[P(line, "body")] for line in crit_lines]
        crit_table = Table(crit_rows, colWidths=[18 * cm], hAlign="RIGHT")
        crit_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C["light_bg"]),
            ("GRID",          (0, 0), (-1, -1), 0.4, C["grid"]),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(crit_table)
        story.append(Spacer(1, 0.4 * cm))

    # ── Summary stats ─────────────────────────────────────────────────────────
    # ✅ معكوسة عمداً: آخر عنصر بالقائمة = الأقصى يميناً — "إجمالي الحالات"
    # يظهر أولاً (أقصى اليمين) كأهم رقم تنفيذي (نفس مبدأ services/patient_report_pdf.py).
    stat_rows = [[
        [P("الإجراءات",            "stat_label"), P(str(stats["unique_actions"]),     "stat_value")],
        [P("الأقسام",              "stat_label"), P(str(stats["unique_depts"]),       "stat_value")],
        [P("المستشفيات",          "stat_label"), P(str(stats["unique_hospitals"]),   "stat_value")],
        [P("المرضى",              "stat_label"), P(str(stats["unique_patients"]),     "stat_value")],
        [P("إجمالي الحالات",      "stat_label"), P(str(stats["total"]),               "stat_value")],
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

    # Hospitals table — ✅ معكوسة: "المستشفى" يظهر أقصى اليمين
    story.append(P("المستشفيات", "section"))
    hosp_rows = [[P("عدد الحالات", "th"), P("المستشفى", "th")]]
    for h, cnt in hosp_counts.items():
        hosp_rows.append([P(str(cnt), "td_c"), P(h, "td_r")])
    ht = Table(hosp_rows, colWidths=[3 * cm, 13 * cm], hAlign="RIGHT")
    ht.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
        ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",          (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.3 * cm))

    # Departments table — ✅ معكوسة: "القسم" يظهر أقصى اليمين
    story.append(P("الأقسام", "section"))
    dept_rows = [[P("عدد الحالات", "th"), P("القسم", "th")]]
    for d, cnt in list(dept_counts.items())[:15]:
        dept_rows.append([P(str(cnt), "td_c"), P(d, "td_r")])
    dt = Table(dept_rows, colWidths=[3 * cm, 13 * cm], hAlign="RIGHT")
    dt.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
        ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",          (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(dt)
    story.append(Spacer(1, 0.3 * cm))

    # Actions table — ✅ معكوسة: "نوع الإجراء" يظهر أقصى اليمين
    story.append(P("الإجراءات", "section"))
    act_rows = [[P("النسبة", "th"), P("عدد الحالات", "th"), P("نوع الإجراء", "th")]]
    total = stats["total"] or 1
    for a, cnt in list(action_counts.items())[:15]:
        pct = f"{cnt / total * 100:.1f}%"
        act_rows.append([P(pct, "td_c"), P(str(cnt), "td_c"), P(a, "td_r")])
    at = Table(act_rows, colWidths=[3 * cm, 3 * cm, 10 * cm], hAlign="RIGHT")
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

    # ── Case-by-case detail table ─────────────────────────────────────────────
    # ✅ لا يُعرض هنا كل حالة على حدة — الجداول/الرسوم أعلاه (المستشفيات/
    # الأقسام/الإجراءات مع النسب + الرسوم البيانية) تكفي كملخص إحصائي لكل
    # الحالات الروتينية. يبقى الكشف الكامل فقط لأهم نوعين إكلينيكياً: "عملية"
    # (مع اسمها بالإنجليزي) و"استشارة أخيرة" — أحداث نادرة الحدوث ومهمة تستحق
    # التفصيل الكامل، بعكس المتابعات الروتينية المتكررة.
    def _trunc(text: str, n: int) -> str:
        text = (text or "").strip()
        return text if len(text) <= n else text[: n - 1].rstrip() + "…"

    def _extract_op_name_en(doctor_decision: str) -> str:
        dd = doctor_decision or ""
        if "اسم العملية بالإنجليزي:" not in dd:
            return ""
        try:
            rest = dd.split("اسم العملية بالإنجليزي:", 1)[1]
            for sep in ("\n\n", "ملاحظات:", "الفحوصات"):
                if sep in rest:
                    rest = rest.split(sep, 1)[0]
            return rest.strip()
        except Exception:
            return ""

    _FULL_DETAIL_ACTIONS = {"عملية", "استشارة أخيرة"}
    detail_reports = [r for r in reports if (r.get("medical_action") or "").strip() in _FULL_DETAIL_ACTIONS]

    story.append(PageBreak())
    story.append(P("تفاصيل الحالات — العمليات والاستشارات الأخيرة", "section"))

    if detail_reports:
        for action in sorted(_FULL_DETAIL_ACTIONS):
            action_reps = [r for r in detail_reports if (r.get("medical_action") or "").strip() == action]
            if not action_reps:
                continue
            is_operation = action == "عملية"

            story.append(Spacer(1, 0.3 * cm))
            story.append(P(f"● {action}  ({len(action_reps)} حالة)", "section"))

            header_row = [
                P("التاريخ",  "th"), P("المريض",   "th"), P("المستشفى", "th"),
                P("القسم",    "th"), P("الطبيب",   "th"),
            ]
            if is_operation:
                header_row.append(P("اسم العملية بالإنجليزي", "th"))
            header_row.append(P("تفاصيل الحالة", "th"))
            detail_rows = [header_row]

            # ✅ عرض الأعمدة قبل بناء الصفوف — P_wrap يحتاجه لتحديد نقاط اللف
            # الصحيحة (نفس سبب استخدامه: نص مختلط عربي/إنجليزي طويل يُفسِد
            # لفّه التلقائي إن مرّ عبر reshape+bidi قبل اللف اليدوي).
            # ⚠️ المجموع يجب ألا يتجاوز عرض المحتوى المتاح (17.4سم مع هوامش
            # 1.8سم) — عمود "اسم العملية بالإنجليزي" الإضافي كان يدفع
            # المجموع لأكثر من ذلك فيفيض الجدول خارج هامش الصفحة.
            if is_operation:
                col_widths = [1.8*cm, 2.4*cm, 2.4*cm, 2*cm, 2*cm, 2.2*cm, 4.5*cm]
            else:
                col_widths = [1.8*cm, 2.4*cm, 2.4*cm, 2*cm, 2*cm, 6.7*cm]
            opname_w, decision_w = (col_widths[5] if is_operation else None), col_widths[-1]

            for r in sorted(action_reps, key=lambda x: x.get("report_date") or date.min):
                row = [
                    P(_fmt_date(r.get("report_date")),           "td_c"),
                    P(_trunc(r.get("patient_name", ""), 20),      "td_r"),
                    P(_trunc(r.get("hospital_name", ""), 20),     "td_r"),
                    P(_trunc(r.get("department", ""), 18),        "td_r"),
                    P(_trunc(r.get("doctor_name", ""), 16),       "td_r"),
                ]
                if is_operation:
                    row.append(P_wrap(_extract_op_name_en(r.get("doctor_decision")) or "—", "td_r", opname_w))
                row.append(P_wrap(r.get("doctor_decision") or "", "td_r", decision_w))
                detail_rows.append(row)

            # ✅ عكس كل الأعمدة دفعة واحدة — "التاريخ" ينتهي أقصى اليمين
            # (نفس مبدأ العكس المطبَّق على كل جداول هذا الملف).
            detail_rows = [list(reversed(row)) for row in detail_rows]
            col_widths = list(reversed(col_widths))

            detail_table = Table(
                detail_rows,
                colWidths=col_widths,
                hAlign="CENTER",
                repeatRows=1,
            )
            detail_table.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
                ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING",     (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
                ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
                ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ]))
            story.append(detail_table)
    else:
        story.append(P("لا توجد عمليات أو استشارات أخيرة ضمن هذه الفترة/المعايير.", "body"))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(
        f"[comprehensive_pdf] built  reports={len(reports)}  "
        f"patients={stats['unique_patients']}  size={buf.getbuffer().nbytes:,}"
    )
    return buf
