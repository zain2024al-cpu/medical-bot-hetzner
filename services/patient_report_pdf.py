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
    # ✅ الخط المرفَق مع المشروع مضمون الوجود على أي سيرفر (جزء من الـ repo)
    # ومؤكَّد أنه يعرض العربي بشكل صحيح (اختُبر فعلياً مع matplotlib أيضاً) —
    # يجب تجربته قبل خطوط النظام (NotoNaskh/DejaVu) التي قد تكون غير مثبَّتة
    # على الخادم، أو مثبَّتة لكن بدعم عربي ضعيف (DejaVu Sans تحديداً لا يدعم
    # أشكال العرض العربية Presentation Forms بشكل كامل، وهذا ما كان يسبب
    # ظهور تسميات الرسم البياني مشوَّهة رغم إصلاح استخدام matplotlib للخط).
    (
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Arabic-Regular.ttf")),
        "ArabicReg",
    ),
    ("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", "NotoAr"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu"),
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


# ✅ الرسوم البيانية تُرسَم مباشرة عبر reportlab (Flowable مخصَّصة، انظر
# _HBarChart داخل build_patient_pdf) بدل matplotlib. matplotlib+freetype على
# السيرفر الفعلي يطبِّق تشكيلاً/ترتيباً تلقائياً إضافياً للنص العربي (عبر
# raqm/HarfBuzz إن كان مفعَّلاً في بنية matplotlib المثبَّتة) فوق التشكيل
# اليدوي الذي نطبِّقه (arabic_reshaper + get_display) — هذه المعالجة
# المزدوجة تنتج نصاً مشوَّهاً، وهي بيئة-محدَّدة (ظهرت على السيرفر الفعلي رغم
# نجاح نفس الكود محلياً على Windows). بما أن reportlab يُستخدم بالفعل بنجاح
# مثبَّت عبر كل هذا الملف لعرض العربي بشكل صحيح ومتّسق، رسم الأشرطة والنصوص
# به مباشرة يُلغي هذا الخلل نهائياً بدل ملاحقة إعدادات matplotlib بيئة بيئة.


# ── Public API ────────────────────────────────────────────────────────────────

def build_patient_pdf(
    patient: dict,
    reports: list[dict],
    dept_filter: list[str] | None,
    period_label: str,
    healthcare_records: list[dict] | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> io.BytesIO:
    """
    Build a professional Arabic PDF report for a single patient.

    patient  — {name, file_number, nationality, disease, phone, ...}
    reports  — list of report dicts from DB
    dept_filter — None = all depts, list = specific depts selected
    period_label — human-readable period string for the header (e.g. "آخر 3 أشهر")
    healthcare_records — سجلات وحدة الرعاية الصحية (اختياري)، من
        services/healthcare_records_repository.py:get_healthcare_records_for_patient —
        [{"type", "type_label", "date", "department", "description",
          "specialist_name", "notes"}, ...]. إذا كانت فارغة/None، لا يُضاف
        أي قسم إضافي (سلوك الدالة بلا تغيير عن السابق).
    period_start / period_end — تواريخ الفترة الفعلية (اختياري) لعرضها بجانب
        period_label في سطر الفترة أعلى التقرير (مثال: "آخر 3 أشهر — من
        23/04/2026 إلى 22/07/2026"). إن لم تُمرَّر، يُعرض period_label وحده.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm, mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            PageBreak, HRFlowable, KeepTogether,
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

    def P_field(label, txt, style_key, max_width_pts) -> Paragraph:
        """حقل نصي مستقل (تسمية: قيمة) خارج أي جدول — على عكس خلية جدول،
        هذا الـ Paragraph قابل للانقسام تلقائياً بين صفحتين إن طال (Platypus
        يدعم split() للفقرات)، فلا يمكن أن يسبّب LayoutError مهما طال النص
        (وهو ما كان يحدث سابقاً عندما كان النص الطويل محشوراً داخل خلية جدول
        واحدة غير قابلة للانقسام)."""
        style = ST[style_key]
        usable_width = max(max_width_pts - 8, 20)
        value = str(txt or "").strip() or "—"
        combined = f"{label}:  {value}"
        wrapped = _ar_wrap(combined, style.fontName, style.fontSize, usable_width)
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
    content_width_pts = A4[0] - doc.leftMargin - doc.rightMargin

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

    def _fd(d) -> str:
        if d is None: return "—"
        return d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)

    # ── رأس التقرير: بلا صندوق أزرق كبير ──────────────────────────────────────
    # ✅ إزالة الصندوق الأزرق الكبير (CoverBand) وجدول الاسم/الفترة المكرر
    # بناءً على طلب صريح: "المربع الأزرق كبير جدا لا داعي له" + "الجدول الذي
    # فيه الاسم والفترة مكرر مرة ثانية" (كان يكرر ما يعرضه الصندوق الأزرق).
    # الشكل الجديد: سطر باسم المريض، سطر "التقرير الطبي الشامل" تحته، سطر
    # الفترة تحته (تُدمَج فيه period_label الجاهزة مع تواريخ البداية/النهاية
    # الفعلية إن تُوفِّرت)، والصورة الشخصية أعلى الصفحة على اليسار (بدل
    # اليمين/تحت الجدول كما كانت) — كل ذلك بلا أي خلفية ملوّنة.
    from reportlab.platypus.flowables import Flowable as _F

    class PhotoBox(_F):
        def __init__(self, w=2.6 * cm, h=3.4 * cm):
            super().__init__()
            self.width = w
            self.height = h

        def draw(self):
            c = self.canv
            c.setStrokeColor(C["grid"])
            c.setLineWidth(1)
            c.rect(0, 0, self.width, self.height, fill=0, stroke=1)
            c.setFillColor(C["text_gray"])
            c.setFont(FN, 6.5)
            c.drawCentredString(self.width / 2, self.height / 2 + 3, _ar("الصورة"))
            c.drawCentredString(self.width / 2, self.height / 2 - 6, _ar("الشخصية"))

    class _HBarChart(_F):
        """رسم بياني بالأشرطة الأفقية يُرسَم مباشرة عبر reportlab (بلا
        matplotlib) — يضمن نفس عرض العربي الصحيح والمتّسق المستخدَم في بقية
        هذا المستند، ويتجنّب خلل التشكيل المزدوج المحتمل مع matplotlib على
        بعض بيئات الخادم (انظر التعليق أعلى تعريف build_patient_pdf)."""
        def __init__(self, items, width, row_h=0.6 * cm, label_w=5.2 * cm):
            super().__init__()
            self.items = items[:12]
            self.width = width
            self.row_h = row_h
            self.label_w = label_w
            self.height = max(len(self.items), 1) * row_h

        def draw(self):
            c = self.canv
            if not self.items:
                return
            max_v = max(v for _, v in self.items) or 1
            bar_area_w = self.width - self.label_w - 0.3 * cm
            for i, (label, value) in enumerate(self.items):
                row_top = self.height - i * self.row_h
                bar_h = self.row_h * 0.6
                y = row_top - self.row_h + (self.row_h - bar_h) / 2
                bar_len = (value / max_v) * bar_area_w
                bar_x_left = bar_area_w - bar_len
                c.setFillColor(C["primary"])
                c.rect(bar_x_left, y, bar_len, bar_h, fill=1, stroke=0)
                c.setFillColor(C["text_gray"])
                c.setFont(FN, 8)
                c.drawRightString(bar_x_left - 4, y + bar_h / 2 - 3, str(value))
                c.setFillColor(C["black"])
                c.setFont(FN, 8)
                c.drawString(bar_area_w + 6, y + bar_h / 2 - 3, _ar(label))
            c.setStrokeColor(C["grid"])
            c.setLineWidth(0.6)
            c.line(bar_area_w, 0, bar_area_w, self.height)

    if period_start and period_end:
        period_line_text = f"الفترة: {period_label} — من {_fd(period_start)} إلى {_fd(period_end)}"
    else:
        period_line_text = f"الفترة: {period_label}"

    name_style     = S("name_ttl", fontSize=17, leading=21, alignment=TA_RIGHT, textColor=C["text_dark"], fontName=FNB)
    subtitle_style = S("subttl",   fontSize=12, leading=16, alignment=TA_RIGHT, textColor=C["primary"],   fontName=FNB)
    period_style   = S("prdline",  fontSize=9.5, leading=13, alignment=TA_RIGHT, textColor=C["text_gray"])

    text_stack = [
        Paragraph(_ar(patient_name), name_style),
        Paragraph(_ar("التقرير الطبي الشامل"), subtitle_style),
        Paragraph(_ar(period_line_text), period_style),
    ]

    # ✅ الصورة أولاً بالقائمة = أقصى اليسار (بعكس بقية جداول هذا الملف التي
    # تُعكَس عمداً لتصبح RTL — هنا نريد LEFT فعلاً، فلا نعكس الترتيب).
    header_table = Table(
        [[PhotoBox(), text_stack]],
        colWidths=[3.4 * cm, content_width_pts - 3.4 * cm],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
        ("ALIGN",        (0, 0), (0, 0),   "CENTER"),
        ("ALIGN",        (1, 0), (1, 0),   "RIGHT"),
        ("LEFTPADDING",  (0, 0), (0, 0),   0),
        ("RIGHTPADDING", (1, 0), (1, 0),   0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.4 * cm))

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
    # ✅ حُذف سطر "أول تقرير/آخر تقرير" بناءً على طلب صريح — لا داعي له.

    # ── توزيع الإجراءات: الجدول أولاً ثم الرسم البياني ────────────────────────
    # ✅ ترتيب صريح بناءً على طلب المستخدم: يبدأ الجدول ثم يليه الرسم البياني
    # (بدل الرسم البياني أولاً كما كان). معكوسة: "نوع الإجراء" يظهر أقصى اليمين.
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
    story.append(Spacer(1, 0.4 * cm))
    # ✅ العنوان والجدول معاً (KeepTogether) — كان يظهر العنوان في أسفل صفحة
    # والجدول بأكمله في الصفحة التالية، وهو خطأ فادح بحسب المستخدم صراحة.
    story.append(KeepTogether([P("جدول ملخص الإجراءات", "section"), act_table]))

    if len(action_counts) > 1:
        chart_items = sorted(action_counts.items(), key=lambda x: -x[1])
        chart = _HBarChart(chart_items, width=content_width_pts)
        chart.hAlign = "RIGHT"
        # ✅ العنوان والرسم يبقيان معاً على نفس الصفحة (KeepTogether) —
        # بدل احتمال أن يظهر العنوان في أسفل صفحة والرسم في التي تليها.
        story.append(Spacer(1, 0.5 * cm))
        story.append(KeepTogether([P("توزيع الإجراءات", "section"), chart]))

    # ── Hospitals list ────────────────────────────────────────────────────────
    if hospitals:
        story.append(Spacer(1, 0.4 * cm))
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
        story.append(KeepTogether([P("المستشفيات المزارة", "section"), ht]))

    # ── إحصائيات حسب القسم ونوع الإجراء معاً ─────────────────────────────────
    # ✅ جدول تقاطعي (Pivot): يجيب على "كم إجراء من كل نوع صدر عن كل قسم" —
    # بخلاف جدول "ملخص الإجراءات" أعلاه الذي يُظهر نوع الإجراء وحده بلا ربطه
    # بالقسم. يُبنى فقط إن وُجد قسم واحد على الأقل ضمن التقارير.
    dept_action_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in reports:
        dept = (r.get("department") or "").strip()
        if not dept:
            continue
        a = (r.get("medical_action") or "غير محدد").strip()
        dept_action_counts[dept][a] += 1

    if dept_action_counts:
        action_names = sorted(action_counts.keys())
        dept_col_w  = 3.2 * cm
        total_col_w = 1.6 * cm
        action_col_w = max((content_width_pts - dept_col_w - total_col_w) / len(action_names), 0.9 * cm)

        # ✅ رأس مبني منطقياً (القسم أولاً) ثم يُعكَس دفعة واحدة أدناه —
        # نفس أسلوب جدول تفاصيل التقارير (info_table) لضمان "القسم" أقصى اليمين.
        header_row = [P("القسم", "th")] + [P(a, "th") for a in action_names] + [P("الإجمالي", "th")]
        rows = [header_row]
        for dept in sorted(dept_action_counts.keys()):
            counts = dept_action_counts[dept]
            dept_total = sum(counts.values())
            row = [P(dept, "td_r")] + [P(str(counts.get(a, 0)), "td_c") for a in action_names] + [P(str(dept_total), "td_c")]
            rows.append(row)

        col_totals = [sum(dept_action_counts[d].get(a, 0) for d in dept_action_counts) for a in action_names]
        grand_total = sum(col_totals)
        rows.append(
            [P("الإجمالي", "td_r")] + [P(str(c), "td_c") for c in col_totals] + [P(str(grand_total), "td_c")]
        )

        rows = [list(reversed(row)) for row in rows]
        col_widths = list(reversed([dept_col_w] + [action_col_w] * len(action_names) + [total_col_w]))

        dept_action_table = Table(rows, colWidths=col_widths, hAlign="RIGHT", repeatRows=1)
        dept_action_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),   C["primary"]),
            ("BACKGROUND",     (0, -1), (-1, -1), C["light_bg"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2),  [C["white"], C["light_bg"]]),
            ("GRID",           (0, 0), (-1, -1),  0.3, C["grid"]),
            ("ALIGN",          (0, 0), (-1, -1),  "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1),  "MIDDLE"),
            ("FONTNAME",       (0, -1), (-1, -1), FNB),
            ("TOPPADDING",     (0, 0), (-1, -1),  4),
            ("BOTTOMPADDING",  (0, 0), (-1, -1),  4),
            ("RIGHTPADDING",   (0, 0), (-1, -1),  3),
            ("LEFTPADDING",    (0, 0), (-1, -1),  3),
        ]))
        story.append(Spacer(1, 0.4 * cm))
        story.append(KeepTogether([P("إحصائيات حسب القسم ونوع الإجراء", "section"), dept_action_table]))

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
        story.append(KeepTogether([P("سجلات الرعاية الصحية", "section"), hc_table]))

        if len(hc_counts) > 1:
            hc_chart_items = sorted(hc_counts.items(), key=lambda x: -x[1])
            hc_chart = _HBarChart(hc_chart_items, width=content_width_pts)
            hc_chart.hAlign = "RIGHT"
            story.append(Spacer(1, 0.3 * cm))
            story.append(hc_chart)

    # ── تفاصيل التقارير — تُعرَض أخيراً في التقرير ─────────────────────────────
    # ✅ هذا القسم يقتصر حصراً على نوعين بناءً على طلب صريح: "استشارة مع قرار
    # عملية" و"استشارة أخيرة" — بقية الأنواع لا تظهر هنا إطلاقاً (لا حتى
    # بصيغة "آخر تقرير فقط")، فهي معروضة إحصائياً فقط في الجداول أعلاه.
    # ⚠️ الاسم الفعلي في قاعدة البيانات هو "استشارة مع قرار عملية" (بلا الـ
    # "ال" التعريف) — وليس "عملية" وحدها، وهي نوع منفصل تماماً في البيانات
    # الحقيقية (رصدنا كليهما ظاهرين كنوعين مستقلين في تقرير مريض فعلي).
    _FULL_DETAIL_ACTIONS = {"استشارة مع قرار عملية", "استشارة أخيرة"}

    story.append(PageBreak())
    story.append(P("تفاصيل التقارير حسب نوع الإجراء", "section"))
    story.append(HRFlowable(width="100%", thickness=1.5, color=C["primary"], spaceAfter=6))

    detail_actions = {a: reps for a, reps in action_reports.items() if a in _FULL_DETAIL_ACTIONS}
    for action, reps in sorted(detail_actions.items(), key=lambda x: -len(x[1])):
        count = len(reps)
        sorted_reps = sorted(reps, key=lambda x: x.get("report_date") or date.min)
        display_reps = sorted_reps

        section_block = [
            Spacer(1, 0.4 * cm),
            P(f"● {action}  ({count} تقرير)", "section"),
            HRFlowable(width="100%", thickness=0.8, color=C["accent"], spaceAfter=4),
        ]

        is_operation = action == "استشارة مع قرار عملية"

        # ✅ جدول موجز آمن (حقول قصيرة فقط: #/تاريخ/مستشفى/طبيب/متابعة) — بلا
        # أي نص حر طويل، فلا يمكن أن يفيض عن ارتفاع الصفحة إطلاقاً. النصوص
        # الحرة (الشكوى/القرار الطبي/اسم العملية) تُعرض تحته كفقرات مستقلة
        # (انظر P_field) بدل حشرها في خلية جدول — لأن خلية جدول واحدة غير
        # قابلة للانقسام بين صفحتين، فنص حر طويل جداً فيها كان يسبب
        # LayoutError (تعطّل فعلي شوهد في سجلات الإنتاج: خلية بارتفاع 710
        # نقطة لا تتسع في صفحة كاملة). الفقرة المستقلة قابلة للانقسام تلقائياً
        # بين الصفحات مهما طال النص، فتُلغي هذا الخطر نهائياً.
        header_row = [
            P("#",       "th"),
            P("التاريخ", "th"),
            P("المستشفى / القسم", "th"),
            P("الطبيب",  "th"),
            P("المتابعة", "th"),
        ]
        col_widths = [0.8*cm, 2.4*cm, 5*cm, 3.5*cm, 2.5*cm]

        rows = [header_row]
        for idx, r in enumerate(display_reps, 1):
            hosp = r.get("hospital_name", "")
            dept = r.get("department", "")
            location = hosp + ("\n" + dept if dept else "")
            followup  = _fd(r.get("followup_date"))
            rows.append([
                P(str(idx),       "td_c"),
                P(_fd(r.get("report_date")), "td_c"),
                P(location,       "td_r"),
                P(r.get("doctor_name", "—"), "td_r"),
                P(followup if followup != "—" else "—", "td_c"),
            ])

        # ✅ عكس كل الأعمدة (رأس + كل الصفوف + العرض) دفعة واحدة — يضمن ظهور
        # "#" أقصى اليمين (نفس مبدأ "م" في services/pharmacy_evacuation_pdf.py)
        # بدل بنائها معكوسة يدوياً عمود عمود (عرضة للخطأ).
        rows = [list(reversed(row)) for row in rows]
        col_widths = list(reversed(col_widths))

        info_table = Table(
            rows,
            colWidths=col_widths,
            hAlign="RIGHT",
            repeatRows=1,
        )
        info_table.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  C["accent"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["white"], C["light_bg"]]),
            ("GRID",           (0, 0), (-1, -1), 0.3, C["grid"]),
            ("ALIGN",          (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",         (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",     (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 3),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 4),
            ("LEFTPADDING",    (0, 0), (-1, -1), 4),
        ]))

        story += section_block + [info_table]

        # ── تفاصيل نصية حرة لكل تقرير — فقرات مستقلة قابلة للانقسام بين
        # الصفحات (بلا حد أقصى آمن لطول النص، بعكس خلية الجدول أعلاه) ────────
        for idx, r in enumerate(display_reps, 1):
            detail_block = [
                Spacer(1, 0.25 * cm),
                P(f"● تقرير رقم {idx} — {_fd(r.get('report_date'))}", "small"),
                P_field("الشكوى", r.get("complaint_text"), "td_r", content_width_pts),
            ]
            if is_operation:
                detail_block.append(
                    P_field("اسم العملية بالإنجليزي", _extract_op_name_en(r.get("doctor_decision")), "td_r", content_width_pts)
                )
            detail_block.append(P_field("القرار الطبي", r.get("doctor_decision"), "td_r", content_width_pts))
            story += detail_block

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(
        f"[patient_pdf] built  patient={patient.get('name')!r}"
        f"  reports={total}  size={buf.getbuffer().nbytes:,} bytes"
    )
    return buf
