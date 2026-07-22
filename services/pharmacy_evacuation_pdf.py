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
import re
from datetime import date

logger = logging.getLogger(__name__)

# نطاقات يونيكود العربية (الأساسية + الملحقة + أشكال العرض) — أي نص لا
# يحتوي ولو حرفاً واحداً من هذه النطاقات لا علاقة له بإعادة التشكيل/bidi
# إطلاقاً (تواريخ، أرقام فواتير، مبالغ، رموز، نص لاتيني).
_ARABIC_RE = re.compile(
    "[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]"
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVAL_FONTS_DIR = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts"))

_FONT_CANDIDATES = [
    ("C:\\Windows\\Fonts\\arial.ttf",    "Arial"),   # ✅ نفس خط ملف Excel المرجعي بالضبط (على ويندوز فقط)
    ("C:\\Windows\\Fonts\\tahoma.ttf",   "Tahoma"),
    # ✅ خط عربي مضمَّن مع المشروع — يعمل فعلياً على السيرفر (Linux)، بعكس
    # مسار Noto السابق الذي لم يكن مثبَّتاً أصلاً فتسقط الخطوط لـ Helvetica
    # (بلا أي دعم للعربية) فتظهر كل النصوص كمربعات.
    (os.path.join(_EVAL_FONTS_DIR, "Arabic-Regular.ttf"), "EvacArFont"),
]
_FONT_BOLD_CANDIDATES = [
    ("C:\\Windows\\Fonts\\arialbd.ttf",  "ArialBd"),
    ("C:\\Windows\\Fonts\\tahomabd.ttf", "TahomaBd"),
    (os.path.join(_EVAL_FONTS_DIR, "Arabic-Bold.ttf"), "EvacArFontBd"),
]

# ✅ عمود "التاريخ" حصراً يستخدم نفس الخط المُثبَت نجاحه في تقرير تقييم
# المترجمين (modules/healthcare/evaluation/pdf_builder.py) — خط عربي مخصّص
# مضمَّن، وليس خط النظام Arial/Tahoma المستخدَم لبقية أعمدة هذا الجدول.
_DATE_FONT_CANDIDATES = [
    (os.path.join(_EVAL_FONTS_DIR, "Arabic-Regular.ttf"), "EvacDateFont"),
    ("C:\\Windows\\Fonts\\arial.ttf", "Arial"),
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
    """يُطبِّق reshape+bidi على النص العربي فقط. أي نص لا يحتوي ولو حرفاً
    عربياً واحداً (تاريخ، رقم فاتورة، مبلغ، رمز، نص لاتيني) يُعاد كما هو
    دون أي معالجة — فلا يخضع لإعادة ترتيب bidi إطلاقاً، مهما كان شكله."""
    s = str(text or "")
    if not _ARABIC_RE.search(s):
        return s
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


def _ar_wrap(text, font_name: str, font_size: float, max_width_pts: float) -> str:
    """يلفّ النص يدوياً كلمة-كلمة ضمن العرض المتاح، ثم يُطبِّق reshape+bidi
    على كل سطر مُنجَز على حدة (لا على النص الكامل قبل اللف).

    ✅ سبب وجود هذه الدالة: لو مُرِّر نص عربي طويل عبر _ar() ثم دخل داخل
    Paragraph من reportlab، فإن Paragraph يلفّه تلقائياً بعد إعادة الترتيب
    البصري (bidi) — أي أنه يقطع سلسلة نصية أُعيد ترتيبها أصلاً لتُقرأ من
    اليمين لليسار، فيقع القطع في نقطة خاطئة بصرياً، مما يُظهر النص وكأنه
    "منعكس" أو "ناقص" (أعمدة الاسم/البيان تحديداً، لأنها الأطول محتوى).
    الحل: اللف يتم هنا على النص الأصلي (بترتيب القراءة الطبيعي) *قبل* أي
    reshape/bidi، ثم يُعاد تشكيل وترتيب كل سطر مكتمل بمفرده، فيبقى كل سطر
    وحدة بصرية سليمة ومستقلة."""
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
        "primary":   colors.HexColor("#424242"),  # ✅ رمادي غامق بدل الأزرق (رأس الجدول/العنوان/شريط الإجمالي)
        "light_bg":  colors.HexColor("#F0F0F0"),
        "grid":      colors.HexColor("#CCCCCC"),  # ✅ نفس لون حدود الجدول في Excel المرجعي
        "text_dark": colors.HexColor("#212121"),  # ✅ رمادي شبه أسود بدل الأزرق الغامق (نص الجدول)
        "text_gray": colors.HexColor("#777777"),  # ✅ نفس لون سطر "الفترة" في Excel المرجعي
        "white":     colors.white,
        "frame":     colors.HexColor("#333333"),  # إطار الصفحة — رمادي غامق جداً وهادئ
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
        KeepTogether,
    )

    C = _colors()
    FN = _pick_font(_FONT_CANDIDATES)
    FNB = _pick_font(_FONT_BOLD_CANDIDATES, FN)
    # ✅ عمود "التاريخ" فقط — نفس خط تقرير تقييم المترجمين المُثبَت نجاحه
    FN_DATE = _pick_font(_DATE_FONT_CANDIDATES, FN)

    margin = _MARGIN_CM * cm
    content_width = A4[0] - (2 * margin)  # ✅ مصدر واحد للحقيقة لعرض كل العناصر أدناه

    def S(name, **kw):
        kw.setdefault("fontName", FN)
        return ParagraphStyle(name, **kw)

    ST = {
        "body":   S("bd",  fontSize=11, leading=15, alignment=TA_CENTER, textColor=C["text_dark"]),
        # ✅ صف الرأس بيج فاتح (light_bg) بنص داكن — بدل الخلفية الداكنة/النص الأبيض.
        "th":     S("th",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FNB),
        "td_c":   S("tdc", fontSize=8,  leading=11, alignment=TA_CENTER, textColor=C["text_dark"]),
        # ✅ نفس نمط "td_c" تماماً، فقط بخط عمود التاريخ المطابق لتقرير
        # تقييم المترجمين (FN_DATE بدل FN) — بقية الأعمدة لم تتغيّر إطلاقاً.
        "td_date": S("tdd", fontSize=8, leading=11, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FN_DATE),
        # ✅ صف الإجمالي بيج فاتح (light_bg) بنص داكن — بدل الخلفية الداكنة/النص الأبيض.
        "total_lbl": S("totl", fontSize=11, leading=14, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FNB),
        "total_val": S("totv", fontSize=11, leading=14, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FNB),
        "footer": S("ft",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FNB),
    }

    def P(txt, style_key) -> Paragraph:
        return Paragraph(_ar(txt), ST[style_key])

    def P_wrap(txt, style_key, max_width_pts) -> Paragraph:
        """مثل P تماماً، لكن يستخدم _ar_wrap للأعمدة المعرَّضة لنص طويل
        (الاسم/البيان) لمنع تكسّر النص عند التفاف Paragraph التلقائي."""
        style = ST[style_key]
        # ✅ خصم الحشوة الأفقية للخلية (RIGHTPADDING+LEFTPADDING = 5+5) حتى
        # يُقاس العرض المتاح للنص فعلياً، لا عرض العمود كاملاً.
        usable_width = max(max_width_pts - 10, 20)
        wrapped = _ar_wrap(txt, style.fontName, style.fontSize, usable_width)
        return Paragraph(wrapped, style)

    # ── شريط الرأس (مرة واحدة أول الوثيقة) ────────────────────────────────────
    class EvacuationHeaderBand(Flowable):
        def __init__(self):
            Flowable.__init__(self)
            # ✅ خُفِّض من 5.8cm — كان يترك ~1.5cm فراغاً فارغاً أسفل الشريط
            # المظلَّل بلا داعٍ. هذا التخفيض جزء من مجموعة تعديلات لضمان بقاء
            # كل "مسير" (جدول + إجمالي + تذييل توقيعات) على صفحة واحدة دائماً
            # حتى عند التفاف خلايا "البيان"/"الاسم" لعدة أسطر — بدل أن يفيض
            # تذييل التوقيعات وحده لصفحة جديدة شبه فارغة.
            self.width, self.height = content_width, 4.6 * cm

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

            # ✅ خطوط كتابة حقيقية (canvas.line) بدل underscore/dash: الشرطة
            # السفلية "_" حرف نصّي عادي — بعضها لا يظهر بمحاذاة صحيحة مع خط
            # عربي مُعاد تشكيله (يرتفع/ينخفض عن خط الأساس حسب الخط المُستخدَم)،
            # بينما الخط المرسوم كائن رسومي مستقل تماماً عن النص، فيظهر بمحاذاة
            # ثابتة ونظيفة دائماً بصرف النظر عن الخط.
            def blank_line(x_left: float, width_pt: float, y: float) -> None:
                c.saveState()
                c.setStrokeColor(C["text_dark"])
                c.setLineWidth(0.7)
                y_line = y - 0.08 * cm
                c.line(x_left, y_line, x_left + width_pt, y_line)
                c.restoreState()

            def group_width(parts) -> float:
                total = 0.0
                for kind, val in parts:
                    total += c.stringWidth(val, FN, 10) if kind == "text" else val
                return total

            def rtl_group(parts, right_x: float, y: float) -> None:
                """يرسم عناصر بترتيب القراءة من اليمين لليسار: أول عنصر
                بالقائمة يُرسَم أقصى اليمين (right_x)، وكل عنصر تالٍ يسار
                سابقه مباشرة. parts: [("text", s)] أو [("blank", width_pt)]."""
                cursor_right = right_x
                for kind, val in parts:
                    w = c.stringWidth(val, FN, 10) if kind == "text" else val
                    if kind == "text":
                        c.drawString(cursor_right - w, y, val)
                    else:
                        blank_line(cursor_right - w, w, y)
                    cursor_right -= w

            BLANK_W = 2.4 * cm

            sanad_parts = [("text", _ar("رقم سند الصرف:")), ("blank", BLANK_W)]
            rtl_group(sanad_parts, self.width - 0.4 * cm, text_y)

            qaid_parts = [("text", _ar("رقم القيد:")), ("blank", BLANK_W)]
            qw = group_width(qaid_parts)
            rtl_group(qaid_parts, self.width / 2 + qw / 2, text_y)

            # ✅ "تاريخ تسليم المسير: 20[خط] / [خط] / [خط]" — "20" فقط نصّ
            # ظاهر (بادئة السنة)، بلا أي حرف "م"، والفراغات الثلاثة (آخر
            # رقمين من السنة/الشهر/اليوم) خطوط حقيقية للكتابة اليدوية.
            # القيمة كلها تُرسَم كوحدة LTR واحدة (نفس أسلوب الإصدار السابق)
            # ثم التسمية بعدها منفصلة — لا يمر أيٌّ منهما عبر _ar() هنا لأن
            # "20"/"/" لا تحتاج أي إعادة تشكيل أو ترتيب bidi.
            date_value_parts = [
                ("text", "20"), ("blank", 0.55 * cm),
                ("text", "/"), ("blank", 0.55 * cm),
                ("text", "/"), ("blank", 0.55 * cm),
            ]
            zone_x = 0.4 * cm
            cursor = zone_x
            for kind, val in date_value_parts:
                if kind == "text":
                    c.drawString(cursor, text_y, val)
                    cursor += c.stringWidth(val, FN, 10)
                else:
                    blank_line(cursor, val, text_y)
                    cursor += val
            c.drawString(cursor, text_y, _ar("تاريخ تسليم المسير: "))

    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        # ✅ إطار احترافي خفيف يحيط الصفحة من الداخل (canvas.rect، وليس حدود
        # جدول) — يُرسَم عند 0.5سم من حافة الصفحة، أي بعيداً تماماً عن هامش
        # المحتوى الفعلي (2سم) بفارق 1.5سم لا يلمس أبداً العنوان/الجدول/
        # التوقيعات، وبفارق ~0.2سم فقط عن رقم الصفحة (يبقى رقم الصفحة داخل
        # الإطار كما في النماذج الرسمية، دون ملامسته). هوامش المحتوى نفسها
        # (margin/content_width) لم تتغيّر إطلاقاً.
        frame_margin = 0.5 * cm
        canvas.setStrokeColor(C["frame"])
        canvas.setLineWidth(0.6)
        canvas.rect(
            frame_margin, frame_margin,
            w - 2 * frame_margin, h - 2 * frame_margin,
            fill=0, stroke=1,
        )
        canvas.setFillColor(C["text_gray"])
        canvas.setFont(FN, 8)
        canvas.drawRightString(w - 1.8 * cm, 0.7 * cm, _ar(f"صفحة {doc.page}"))
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )
    story = []

    if not rows:
        story.append(EvacuationHeaderBand())
        story.append(Spacer(1, 0.3 * cm))
        story.append(P("لا توجد بيانات مطابقة لمعايير البحث المحددة.", "body"))
        doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
        buf.seek(0)
        return buf

    # ✅ الأعمدة مُعرَّفة هنا بترتيب معكوس (التاريخ أولاً ... م أخيراً) حتى
    # يظهر "م" في أقصى يمين الصفحة كما يُقرأ طبيعياً بالعربية — العمود
    # الأخير في هذه القائمة = العمود الأيمن على الصفحة. النِّسَب مأخوذة من
    # _COL_PERCENTAGES ومُطبَّقة على content_width فتُجمَع دائماً إلى نفس
    # عرض الصفحة المتاح تماماً (لا التصاق بالحواف ولا تجاوز للهامش).
    REVERSED_LABELS = ["التاريخ", "البيان", "بند الصرف", "رقم الفاتورة", "الاسم", "المبلغ", "م"]
    HEADER_ROW = [P(lbl, "th") for lbl in REVERSED_LABELS]
    col_widths = [content_width * _COL_PERCENTAGES[lbl] for lbl in REVERSED_LABELS]
    AMOUNT_COL_IDX = REVERSED_LABELS.index("المبلغ")
    # ✅ عرضا عمودي "الاسم" و"البيان" تحديداً — أطول الأعمدة محتوى وأكثرها
    # عرضة للف التلقائي، لذا يُمرَّران لـ P_wrap لضمان لف يدوي سليم.
    NAME_COL_W = col_widths[REVERSED_LABELS.index("الاسم")]
    STATEMENT_COL_W = col_widths[REVERSED_LABELS.index("البيان")]

    # ✅ كل مجموعة من 15 صفاً = "مسير" مستقل: رأس خاص به، جدول خاص به،
    # وتذييل توقيعات خاص به. الترقيم "م" يبدأ من 1 في كل مسير جديد (وليس
    # مستمراً عبر كل المسيرات) لأن كل مسير وثيقة رسمية مستقلة بذاتها.
    # ✅ الإجمالي (المبلغ) استثناء متعمَّد: يظهر مرة واحدة فقط، في آخر صفحة
    # من الفترة المطبوعة بأكملها — وليس إجمالياً جزئياً مكرَّراً في كل صفحة
    # (بقرار المستخدم صراحةً؛ سابقاً كان كل مسير/صفحة يعرض إجمالي صفوفه فقط).
    grand_total = sum(r["amount"] for r in rows)
    chunks = [rows[i:i + _ROWS_PER_PAGE] for i in range(0, len(rows), _ROWS_PER_PAGE)]
    for chunk_idx, chunk in enumerate(chunks):
        story.append(EvacuationHeaderBand())
        story.append(Spacer(1, 0.3 * cm))

        table_data = [HEADER_ROW]
        for row_num, r in enumerate(chunk, start=1):
            # ✅ نفس تنسيق strftime ("%Y-%m-%d") ونفس نمط الخط المستخدَمين في
            # عمود التاريخ بتقرير تقييم المترجمين (modules/healthcare/
            # evaluation/pdf_builder.py) تحديداً — بقية الأعمدة لم تتغيّر.
            date_str = r["date"].strftime("%Y-%m-%d") if isinstance(r["date"], date) else str(r["date"])
            table_data.append([
                P(date_str, "td_date"),
                P_wrap(r["statement"], "td_c", STATEMENT_COL_W),
                P(r["expense_item"], "td_c"),
                P(r["invoice_number"], "td_c"),
                P_wrap(r["name"], "td_c", NAME_COL_W),
                P(f'{r["amount"]:.2f}', "td_c"),
                P(str(row_num), "td_c"),
            ])
        # ✅ تعبئة الأسطر المتبقية فارغة حتى يظهر كل مسير بـ15 سطراً دائماً
        # (شكل نموذج ورقي ثابت)، حتى لو كان عدد الصفوف الفعلية أقل — رقم
        # "م" يستمر بالعدّ على الأسطر الفارغة أيضاً، وبقية الأعمدة فارغة.
        for blank_row_num in range(len(chunk) + 1, _ROWS_PER_PAGE + 1):
            table_data.append(["", "", "", "", "", "", P(str(blank_row_num), "td_c")])
        t = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
        t.setStyle(TableStyle([
            # ✅ صف الرأس بيج فاتح بدل الرمادي الداكن (نفس شريط سند الصرف).
            ("BACKGROUND", (0, 0), (-1, 0), C["light_bg"]),
            # ✅ بلا تظليل متبادل بين الصفوف — نفس مظهر Excel المرجعي (صفوف بيضاء
            # صرفة مفصولة بخطوط شبكة رفيعة فقط، بدون تلوين متبادل).
            ("BACKGROUND", (0, 1), (-1, -1), C["white"]),
            ("GRID", (0, 0), (-1, -1), 0.4, C["grid"]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # ✅ خُفِّضت الحشوة الرأسية من 5 إلى 3 (جزء من تعديلات "صفحة واحدة
            # لكل مسير" — توفّر ~2.3سم عبر 16 صفاً، بلا أثر يُذكر على القراءة).
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ]))

        # ── إجمالي المبلغ — يظهر فقط في آخر صفحة من كامل الفترة المطبوعة ─────
        is_last_chunk = chunk_idx == len(chunks) - 1
        total_table = None
        if is_last_chunk:
            total_row = [""] * len(col_widths)
            total_row[0] = P("إجمالي المبلغ", "total_lbl")
            total_row[AMOUNT_COL_IDX] = P(f'{grand_total:,.2f}', "total_val")
            total_table = Table([total_row], colWidths=col_widths, hAlign="CENTER")
            total_table.setStyle(TableStyle([
                # ✅ صف الإجمالي بيج فاتح بدل الرمادي الداكن (نفس شريط سند الصرف).
                ("BACKGROUND", (0, 0), (-1, -1), C["light_bg"]),
                ("SPAN", (0, 0), (AMOUNT_COL_IDX - 1, 0)),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("ALIGN", (AMOUNT_COL_IDX, 0), (AMOUNT_COL_IDX, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ]))

        # ── تذييل توقيعات هذا المسير ─────────────────────────────────────────
        # ✅ الترتيب معكوس هنا صراحة (نفس سبب عكس أعمدة الجدول أعلاه): يُرسَم
        # من اليسار لليمين بترتيب القائمة، فـ"مستلم العهدة" آخر القائمة كي
        # يظهر في أقصى يمين الصفحة كأول عنصر يُقرأ.
        # ✅ خط توقيع حقيقي (LINEBELOW) بدل شرطات نصّية "----": ReportLab يرسم
        # هذا الخط عبر canvas.line داخلياً، وهو كائن رسومي مستقل تماماً عن
        # النص — يظهر دائماً بمحاذاة نظيفة وثابتة بصرف النظر عن الخط المُستخدَم،
        # بعكس شرطات "-" النصّية التي قد لا تتناسق مع نص عربي مُعاد تشكيله.
        footer_labels = ["مسؤول العمليات", "المسؤول المالي", "المراجعة", "مستلم العهدة"]
        # ✅ ارتفاعا الصفّين خُفِّضا قليلاً (0.8→0.65، 1.2→0.9) — جزء من تعديلات
        # "صفحة واحدة لكل مسير"؛ يبقى سطر التوقيع اليدوي بمساحة كافية للكتابة.
        footer_table = Table(
            [[P(lbl, "footer") for lbl in footer_labels], ["", "", "", ""]],
            colWidths=[content_width / 4] * 4, hAlign="CENTER", rowHeights=[0.65 * cm, 0.9 * cm],
        )
        footer_table.setStyle(TableStyle([
            ("LINEBELOW", (0, 1), (-1, 1), 1.0, C["text_dark"]),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))

        # ✅ KeepTogether يمنع reportlab من تقسيم صفوف الجدول تلقائياً منتصف
        # الصفحة عندما يتجاوز ارتفاعها المساحة المتبقية (يحدث عند وجود خلية
        # بنص ملتفّ لعدة أسطر) — بدلاً من ذلك يُنقَل الجدول كاملاً لصفحة
        # جديدة، فيبقى كل مسير (حتى 15 صفاً) وحدة واحدة متماسكة لا تتجزأ.
        # ✅ الفراغات بين الجدول/الإجمالي/التذييل خُفِّضت (جزء من تعديلات
        # "صفحة واحدة لكل مسير" — راجع الملاحظة عند KeepTogether أعلاه).
        story.append(KeepTogether(t))
        if total_table is not None:
            story.append(Spacer(1, 0.2 * cm))
            story.append(total_table)
        story.append(Spacer(1, 0.6 * cm))
        story.append(footer_table)

        if chunk_idx < len(chunks) - 1:
            story.append(PageBreak())

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    logger.info(f"[pharmacy_evacuation_pdf] built  rows={len(rows)}  size={buf.getbuffer().nbytes:,}")
    return buf
