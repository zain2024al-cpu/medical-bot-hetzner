# services/patient_report_pdf.py
# PDF generator for patient medical history reports.
# Called from bot/handlers/admin/admin_patient_report.py.
#
# Usage:
#   buf = build_patient_pdf(patient, reports, dept_filter, period_label)
#   → io.BytesIO ready for bot.send_document()

from __future__ import annotations

import io
import logging
import os
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Font resolution (same strategy as admin_evaluation.py) ───────────────────

_FONT_CANDIDATES = [
    ("C:\\Windows\\Fonts\\tahoma.ttf",   "Tahoma"),
    ("C:\\Windows\\Fonts\\arial.ttf",    "Arial"),
    ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", "NotoAr"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu"),
    # Project-bundled font (assets/fonts/Arabic-Regular.ttf copied from Arial)
    (
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Arabic-Regular.ttf")),
        "ArabicReg",
    ),
]

_FONT_BOLD_CANDIDATES = [
    ("C:\\Windows\\Fonts\\tahomabd.ttf", "TahomaBd"),
    ("C:\\Windows\\Fonts\\arialbd.ttf",  "ArialBd"),
    (
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Arabic-Bold.ttf")),
        "ArabicBold",
    ),
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
    كل سطر منجَز على حدة (لا على النص الكامل قبل اللف).

    ✅ بدون هذا: نص مختلط عربي/إنجليزي طويل (مثل "تفاصيل العملية: ...
    اسم العملية بالإنجليزي: Appendectomy") يُمرَّر لـ Paragraph بعد
    reshape+bidi على السلسلة الكاملة، فيلفّه Paragraph تلقائياً بعد إعادة
    الترتيب البصري — يقطعها في نقطة خاطئة فيظهر النص مبعثَراً/بترتيب
    خاطئ (نفس الخلل الذي أُصلِح سابقاً في services/pharmacy_evacuation_pdf.py)."""
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


# ── Color palette ─────────────────────────────────────────────────────────────

def _colors():
    from reportlab.lib import colors
    return {
        "primary":    colors.HexColor("#1565C0"),
        "accent":     colors.HexColor("#0288D1"),
        "success":    colors.HexColor("#2E7D32"),
        "warning":    colors.HexColor("#F57F17"),
        "danger":     colors.HexColor("#C62828"),
        "light_bg":   colors.HexColor("#F0F4F8"),
        "card_bg":    colors.HexColor("#FAFCFF"),
        "grid":       colors.HexColor("#D0D9E8"),
        "text_dark":  colors.HexColor("#1A237E"),
        "text_gray":  colors.HexColor("#546E7A"),
        "white":      colors.white,
        "black":      colors.black,
    }


# ── Matplotlib chart ──────────────────────────────────────────────────────────

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

        fig, ax = plt.subplots(figsize=(8, max(3, len(items) * 0.5)))
        bars = ax.barh(labels, values, color="#1565C0", edgecolor="white", height=0.65)
        for bar, v in zip(bars, values):
            ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                    str(v), va="center", fontsize=9, color="#333")
        ax.set_xlim(0, max(values) * 1.2 if values else 1)
        ax.invert_yaxis()
        ax.set_xlabel("")
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
        logger.warning(f"[patient_pdf] chart generation failed: {exc}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def build_patient_pdf(
    patient: dict,
    reports: list[dict],
    dept_filter: list[str] | None,
    period_label: str,
    healthcare_records: list[dict] | None = None,
) -> io.BytesIO:
    """
    Build a professional Arabic PDF report for a single patient.

    patient  — {name, file_number, nationality, disease, phone, ...}
    reports  — list of report dicts from DB
    dept_filter — None = all depts, list = specific depts selected
    period_label — human-readable period string for the header
    healthcare_records — سجلات وحدة الرعاية الصحية (اختياري)، من
        services/healthcare_records_repository.py:get_healthcare_records_for_patient —
        [{"type", "type_label", "date", "department", "description",
          "specialist_name", "notes"}, ...]. إذا كانت فارغة/None، لا يُضاف
        أي قسم إضافي (سلوك الدالة بلا تغيير عن السابق).
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm, mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, Image, HRFlowable, KeepTogether,
        )
        from reportlab.platypus.flowables import Flowable
    except ImportError as e:
        logger.error(f"[patient_pdf] reportlab not available: {e}")
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
        "cover_title":  S("ct",  fontSize=22, leading=28, alignment=TA_CENTER, textColor=C["white"],    fontName=FNB),
        "cover_sub":    S("cs",  fontSize=12, leading=16, alignment=TA_CENTER, textColor=C["light_bg"]),
        "section":      S("sec", fontSize=13, leading=18, alignment=TA_RIGHT,  textColor=C["primary"],  fontName=FNB, spaceBefore=10, spaceAfter=4),
        "body":         S("bd",  fontSize=10, leading=14, alignment=TA_RIGHT,  textColor=C["black"]),
        "small":        S("sm",  fontSize=8,  leading=11, alignment=TA_RIGHT,  textColor=C["text_gray"]),
        "th":           S("th",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["white"],    fontName=FNB),
        "td_r":         S("tdr", fontSize=8,  leading=11, alignment=TA_RIGHT,  textColor=C["black"]),
        "td_c":         S("tdc", fontSize=8,  leading=11, alignment=TA_CENTER, textColor=C["black"]),
        "stat_label":   S("sl",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_gray"]),
        "stat_value":   S("sv",  fontSize=18, leading=22, alignment=TA_CENTER, textColor=C["primary"],  fontName=FNB),
        "footer":       S("ft",  fontSize=7,  leading=10, alignment=TA_CENTER, textColor=C["text_gray"]),
    }

    def P(txt, style_key) -> Paragraph:
        return Paragraph(_ar(txt), ST[style_key])

    def P_wrap(txt, style_key, max_width_pts) -> Paragraph:
        """مثل P، لكن يلفّ يدوياً قبل reshape/bidi — للخلايا المعرَّضة لنص
        طويل مختلط عربي/إنجليزي (قرار الطبيب، الشكوى، اسم العملية بالإنجليزي)."""
        style = ST[style_key]
        usable_width = max(max_width_pts - 8, 20)
        wrapped = _ar_wrap(txt, style.fontName, style.fontSize, usable_width)
        return Paragraph(wrapped, style)

    # ── Canvas callbacks (header/footer on every page) ─────────────────────
    patient_name = patient.get("name", "—")

    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        # Top bar
        canvas.setFillColor(C["primary"])
        canvas.rect(0, h - 1.3 * cm, w, 1.3 * cm, fill=1, stroke=0)
        canvas.setFillColor(C["white"])
        canvas.setFont(FNB, 9)
        canvas.drawCentredString(w / 2, h - 0.85 * cm, _ar(f"التقرير الطبي — {patient_name}"))
        # Footer
        canvas.setFillColor(C["primary"])
        canvas.rect(0, 0, w, 0.7 * cm, fill=1, stroke=0)
        canvas.setFillColor(C["white"])
        canvas.setFont(FN, 7)
        canvas.drawString(1 * cm, 0.2 * cm, _ar(datetime.utcnow().strftime("%Y-%m-%d")))
        canvas.drawCentredString(w / 2, 0.2 * cm, _ar("سري — للاستخدام الطبي الداخلي"))
        canvas.drawRightString(w - 1 * cm, 0.2 * cm, _ar(f"صفحة {doc.page}"))
        canvas.restoreState()

    # ── Buffer + document ─────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=2.2 * cm, bottomMargin=1.5 * cm,
    )

    story = []

    # ── Aggregate data ────────────────────────────────────────────────────────
    total = len(reports)
    hospitals = sorted({r.get("hospital_name", "") for r in reports if r.get("hospital_name")})
    depts_in  = sorted({r.get("department", "") for r in reports if r.get("department")})

    action_counts: dict[str, int] = defaultdict(int)
    action_reports: dict[str, list[dict]] = defaultdict(list)
    for r in reports:
        a = (r.get("medical_action") or "غير محدد").strip()
        action_counts[a] += 1
        action_reports[a].append(r)

    dates = [r.get("report_date") for r in reports if r.get("report_date")]
    first_dt = min(dates) if dates else None
    last_dt  = max(dates) if dates else None

    def _fd(d) -> str:
        if d is None: return "—"
        return d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)

    # ── COVER ─────────────────────────────────────────────────────────────────
    from reportlab.platypus.flowables import Flowable as _F
    from reportlab.lib.units import cm as _cm

    class CoverBand(_F):
        def __init__(self):
            super().__init__()
            self.width  = 540
            self.height = 120

        def draw(self):
            c = self.canv
            c.setFillColor(C["primary"])
            c.roundRect(0, 0, self.width, self.height, 10, stroke=0, fill=1)
            # Accent strip
            c.setFillColor(C["accent"])
            c.roundRect(0, 0, self.width, 8, 0, stroke=0, fill=1)
            # Title
            c.setFillColor(C["white"])
            c.setFont(FNB, 20)
            c.drawRightString(self.width - 15, self.height - 38, _ar("التقرير الطبي الشامل للمريض"))
            # Subtitle
            c.setFont(FN, 11)
            c.setFillColor(C["light_bg"])
            c.drawRightString(self.width - 15, self.height - 58, _ar(patient_name))
            c.setFont(FN, 9)
            c.drawRightString(self.width - 15, 18, _ar(f"الفترة: {period_label}"))

    story.append(CoverBand())
    story.append(Spacer(1, 0.4 * cm))

    # ── مربع الصورة الشخصية (فارغ — يُلصَق يدوياً) + الاسم والفترة فقط ─────────
    # ✅ بلا بيانات شخصية تفصيلية (رقم ملف/جنسية/حالة مرضية/هاتف) بناءً على
    # طلب صريح — الاسم والفترة فقط، مع مربع فارغ 4×6 سم للصورة الشخصية.
    class PhotoBox(_F):
        def __init__(self, w=4 * cm, h=6 * cm):
            super().__init__()
            self.width = w
            self.height = h

        def draw(self):
            c = self.canv
            c.setStrokeColor(C["grid"])
            c.setLineWidth(1)
            c.rect(0, 0, self.width, self.height, fill=0, stroke=1)
            c.setFillColor(C["text_gray"])
            c.setFont(FN, 8)
            c.drawCentredString(self.width / 2, self.height / 2 + 4, _ar("الصورة"))
            c.drawCentredString(self.width / 2, self.height / 2 - 8, _ar("الشخصية"))

    # ✅ عمود القيمة أولاً ثم التسمية — آخر عمود بالقائمة = الأقصى يميناً
    # (reportlab يرسم الأعمدة من اليسار لليمين بترتيب القائمة المُعطاة، فلا
    # بد من هذا الترتيب المعكوس صراحة ليُقرأ "الاسم:" ثم القيمة من اليمين
    # لليسار كما يُقرأ العربي طبيعياً — نفس مبدأ services/pharmacy_evacuation_pdf.py).
    name_period_table = Table(
        [
            [P(patient_name, "body"),  P("الاسم:",   "td_r")],
            [P(period_label, "body"), P("الفترة:", "td_r")],
        ],
        colWidths=[9 * cm, 3 * cm], hAlign="RIGHT",
    )
    name_period_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C["card_bg"]),
        ("GRID",          (0, 0), (-1, -1), 0.4, C["grid"]),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))

    # ✅ مربع الصورة أخيراً بالقائمة = الأقصى يميناً في الصف الخارجي
    header_row_table = Table(
        [[name_period_table, PhotoBox()]],
        colWidths=[12 * cm, 4 * cm], hAlign="RIGHT",
    )
    header_row_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN",  (1, 0), (1, 0), "CENTER"),
    ]))
    story.append(header_row_table)
    story.append(Spacer(1, 0.5 * cm))

    # ── Summary stat cards ────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=C["grid"], spaceAfter=4))
    story.append(P("الملخص التنفيذي", "section"))

    # ✅ معكوسة عمداً: آخر عنصر بالقائمة = الأقصى يميناً (نفس مبدأ عكس
    # الأعمدة في كل جداول هذا التقرير) — "إجمالي التقارير" يظهر أولاً
    # (أقصى اليمين) كأهم رقم تنفيذي.
    stat_data = [[
        [P(str(len(depts_in)),   "stat_value"), P("الأقسام",            "stat_label")],
        [P(str(len(action_counts)), "stat_value"), P("أنواع الإجراءات", "stat_label")],
        [P(str(len(hospitals)),  "stat_value"), P("المستشفيات",         "stat_label")],
        [P(str(total),           "stat_value"), P("إجمالي التقارير",   "stat_label")],
    ]]
    flat_stat = []
    for cell_list in stat_data[0]:
        flat_stat.append(Table([[cell_list[0]], [cell_list[1]]], hAlign="CENTER"))

    stat_table = Table([flat_stat], colWidths=[4 * cm] * 4, hAlign="CENTER")
    stat_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), C["card_bg"]),
        ("GRID",        (0, 0), (-1, -1), 0.5, C["grid"]),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(stat_table)
    story.append(Spacer(1, 0.3 * cm))

    # Period — ✅ معكوس: "أول تقرير" يظهر أولاً (أقصى اليمين) ثم قيمته، تليها
    # "آخر تقرير" ثم قيمتها يساراً — بترتيب قراءة عربي طبيعي من اليمين لليسار.
    period_data = [
        [P(_fd(last_dt), "body"), P("آخر تقرير:", "td_r"),
         P(_fd(first_dt), "body"), P("أول تقرير:", "td_r")],
    ]
    pt = Table(period_data, colWidths=[5 * cm, 3 * cm, 5 * cm, 3 * cm], hAlign="RIGHT")
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C["light_bg"]),
        ("GRID",       (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",      (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(pt)

    # ── Action-type bar chart ─────────────────────────────────────────────────
    if len(action_counts) > 1:
        story.append(Spacer(1, 0.5 * cm))
        story.append(P("توزيع الإجراءات", "section"))
        chart_buf = _action_bar_chart(dict(action_counts), FN)
        if chart_buf:
            chart_h = min(10 * cm, max(3 * cm, len(action_counts) * 0.55 * cm))
            img = Image(chart_buf, width=15 * cm, height=chart_h)
            img.hAlign = "CENTER"
            story.append(img)

    # ── Action summary table ──────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(P("جدول ملخص الإجراءات", "section"))
    # ✅ معكوسة: "نوع الإجراء" (العمود الأساسي) يظهر أقصى اليمين
    act_rows = [[P("النسبة", "th"), P("عدد التقارير", "th"), P("نوع الإجراء", "th")]]
    for action, cnt in sorted(action_counts.items(), key=lambda x: -x[1]):
        pct = f"{cnt / total * 100:.1f}%" if total else "—"
        act_rows.append([
            P(pct, "td_c"),
            P(str(cnt), "td_c"),
            P(action, "td_r"),
        ])
    act_table = Table(act_rows, colWidths=[3 * cm, 3 * cm, 10 * cm], hAlign="RIGHT")
    act_table.setStyle(TableStyle([
        ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
        ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
        ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
        ("LEFTPADDING",    (0, 0), (-1, -1), 6),
    ]))
    story.append(act_table)

    # ── Hospitals list ────────────────────────────────────────────────────────
    if hospitals:
        story.append(Spacer(1, 0.4 * cm))
        story.append(P("المستشفيات المزارة", "section"))
        # ✅ معكوسة: "المستشفى" يظهر أقصى اليمين
        hosp_rows = [[P("عدد الزيارات", "th"), P("المستشفى", "th")]]
        hosp_counts = defaultdict(int)
        for r in reports:
            h = r.get("hospital_name", "")
            if h:
                hosp_counts[h] += 1
        for h, cnt in sorted(hosp_counts.items(), key=lambda x: -x[1]):
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

    def _extract_op_name_en(doctor_decision: str) -> str:
        """يستخرج اسم العملية بالإنجليزي من doctor_decision — لا عمود مخصَّص
        له في Report (نفس نمط استخراجه في user_reports_edit.py عند التعديل)."""
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

    # ── سجلات الرعاية الصحية — إحصائيات + رسم بياني فقط (بلا جدول تفصيلي) ─────
    if healthcare_records:
        hc_counts: dict[str, int] = defaultdict(int)
        for rec in healthcare_records:
            hc_counts[rec["type_label"]] += 1
        hc_total = len(healthcare_records)

        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width="100%", thickness=1, color=C["grid"], spaceAfter=4))
        story.append(P("سجلات الرعاية الصحية", "section"))

        # ✅ معكوسة: "النوع" يظهر أقصى اليمين
        hc_rows = [[P("النسبة", "th"), P("العدد", "th"), P("النوع", "th")]]
        for type_label, cnt in sorted(hc_counts.items(), key=lambda x: -x[1]):
            pct = f"{cnt / hc_total * 100:.1f}%" if hc_total else "—"
            hc_rows.append([P(pct, "td_c"), P(str(cnt), "td_c"), P(type_label, "td_r")])
        hc_table = Table(hc_rows, colWidths=[3 * cm, 3 * cm, 10 * cm], hAlign="RIGHT")
        hc_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  C["primary"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
            ("GRID",           (0, 0), (-1, -1), 0.4, C["grid"]),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",     (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 6),
            ("LEFTPADDING",    (0, 0), (-1, -1), 6),
        ]))
        story.append(hc_table)

        if len(hc_counts) > 1:
            chart_buf = _action_bar_chart(dict(hc_counts), FN)
            if chart_buf:
                story.append(Spacer(1, 0.3 * cm))
                chart_h = min(8 * cm, max(3 * cm, len(hc_counts) * 0.6 * cm))
                img = Image(chart_buf, width=15 * cm, height=chart_h)
                img.hAlign = "CENTER"
                story.append(img)

    # ── تفاصيل التقارير — تُعرَض أخيراً في التقرير ─────────────────────────────
    # ✅ الكشف الكامل بكل التقارير يبقى فقط لأهم نوعين إكلينيكياً (عمليات
    # ونادرة الحدوث): "عملية" (مع اسمها بالإنجليزي) و"استشارة أخيرة". بقية
    # الأنواع الروتينية تظهر ملخَّصة إحصائياً أعلاه فقط، مع عرض آخر تقرير
    # لكل نوع هنا للسياق — بلا تكرار القائمة الكاملة.
    _FULL_DETAIL_ACTIONS = {"عملية", "استشارة أخيرة"}

    story.append(PageBreak())
    story.append(P("تفاصيل التقارير حسب نوع الإجراء", "section"))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C["primary"], spaceAfter=6))

    for action, reps in sorted(action_reports.items(), key=lambda x: -len(x[1])):
        count = len(reps)
        sorted_reps = sorted(reps, key=lambda x: x.get("report_date") or date.min)
        show_full = action in _FULL_DETAIL_ACTIONS
        display_reps = sorted_reps if show_full else [sorted_reps[-1]]
        note_suffix = "" if show_full else "  — آخر تقرير فقط"

        section_block = [
            Spacer(1, 0.4 * cm),
            P(f"● {action}  ({count} تقرير{note_suffix})", "section"),
            HRFlowable(width="100%", thickness=0.8, color=C["accent"], spaceAfter=4),
        ]

        is_operation = action == "عملية"
        header_row = [
            P("#",             "th"),
            P("التاريخ",       "th"),
            P("المستشفى / القسم", "th"),
            P("الطبيب",        "th"),
            P("الشكوى",        "th"),
        ]
        if is_operation:
            header_row.append(P("اسم العملية بالإنجليزي", "th"))
        header_row += [P("القرار الطبي", "th"), P("المتابعة", "th")]

        # ✅ عرض الأعمدة يُحسَب هنا (قبل بناء الصفوف) لأن P_wrap يحتاجه لتحديد
        # نقاط اللف الصحيحة — نفس سبب استخدام P_wrap أصلاً: خلايا "الشكوى"/
        # "القرار الطبي"/"اسم العملية بالإنجليزي" قد تحوي نصاً طويلاً مختلط
        # عربي/إنجليزي يُفسِد التفافه التلقائي إن مرّ عبر reshape+bidi قبل اللف.
        # ⚠️ مجموع الأعمدة يجب ألا يتجاوز عرض المحتوى المتاح (17.4سم مع هوامش
        # 1.8سم يميناً ويساراً) — عمود "اسم العملية بالإنجليزي" الإضافي كان
        # يدفع المجموع لأكثر من ذلك فيفيض الجدول خارج هامش الصفحة اليسار.
        if is_operation:
            col_widths = [0.6*cm, 2.2*cm, 2.6*cm, 2*cm, 2.4*cm, 2.2*cm, 2.6*cm, 1.6*cm]
        else:
            col_widths = [0.6*cm, 2.2*cm, 3.2*cm, 2.3*cm, 3*cm, 3*cm, 1.7*cm]
        complaint_w, opname_w, decision_w = col_widths[4], (col_widths[5] if is_operation else None), col_widths[-2]

        rows = [header_row]
        for idx, r in enumerate(display_reps, 1):
            hosp = r.get("hospital_name", "")
            dept = r.get("department", "")
            location = hosp + ("\n" + dept if dept else "")
            followup  = _fd(r.get("followup_date"))

            row = [
                P(str(idx),       "td_c"),
                P(_fd(r.get("report_date")), "td_c"),
                P(location,       "td_r"),
                P(r.get("doctor_name", "—"), "td_r"),
                P_wrap(r.get("complaint_text") or "", "td_r", complaint_w),
            ]
            if is_operation:
                row.append(P_wrap(_extract_op_name_en(r.get("doctor_decision")) or "—", "td_r", opname_w))
            row += [
                P_wrap(r.get("doctor_decision") or "", "td_r", decision_w),
                P(followup if followup != "—" else "", "td_c"),
            ]
            rows.append(row)

        # ✅ عكس كل الأعمدة (رأس + كل الصفوف + العرض) دفعة واحدة — يضمن ظهور
        # "#" أقصى اليمين (نفس مبدأ "م" في services/pharmacy_evacuation_pdf.py)
        # بدل بنائها معكوسة يدوياً عمود عمود (عرضة للخطأ).
        rows = [list(reversed(row)) for row in rows]
        col_widths = list(reversed(col_widths))

        detail_table = Table(
            rows,
            colWidths=col_widths,
            hAlign="RIGHT",
            repeatRows=1,
        )
        detail_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  C["accent"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
            ("GRID",           (0, 0), (-1, -1), 0.3, C["grid"]),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",     (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
            ("WORDWRAP",       (0, 0), (-1, -1), True),
        ]))

        story += section_block + [detail_table]

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(
        f"[patient_pdf] built  patient={patient.get('name')!r}"
        f"  reports={total}  size={buf.getbuffer().nbytes:,} bytes"
    )
    return buf
