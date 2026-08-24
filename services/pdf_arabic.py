# services/pdf_arabic.py
# مصدر الحقيقة الوحيد لتهيئة النص العربي وخطوطه في كل مولّدات PDF.
#
# ⚠️ لماذا هذا الملف موجود:
# كانت `_ar` (إعادة تشكيل + bidi) مكرَّرة **ست مرات** بنسخ مستقلة في
# comprehensive_report_pdf / data_analysis_pdf / patient_report_pdf /
# pharmacy_evacuation_pdf / residency_case_pdf / healthcare.evaluation.
# pdf_builder، و`_ar_wrap` أربع مرات، و`_pick_font` خمس مرات — وتعليقات
# تلك الملفات نفسها تعترف بالنسخ ("نفس نمط ... في services/X.py").
#
# ولأنها نسخ مستقلة **تباعدت فعلاً**، وأُثبِت ذلك بمقارنة سلوكية على
# الدوال الحقيقية (لا نصّياً):
#   • `pdf_builder.py` كان يُخرِج كلمة "None" حرفياً للقيمة الفارغة
#     (`str(text)` بلا حارس) بينما الخمس الأخرى تُخرِج "" — أي أن كلمة
#     "None" كانت تُطبَع فعلياً داخل تقرير تقييم الرعاية الصحية.
#   • نطاق محارف العربية اختلف: ثلاث نسخ تفتقد كتلة
#     Arabic Extended-A (U+08A0–U+08FF) الموجودة في نسختين.
#
# هذا الملف يوحّد السلوك على **الأوسع والأسلم**: نطاق يشمل كل الكتل
# المعروفة، وحارس يمنع طباعة "None". النسخ القديمة بقيت كأغلفة رقيقة
# تستدعيه (نفس نمط الإصلاح في shared/text_safety.py) فلا تُلمَس مئات
# مواضع الاستدعاء.

import logging
import re

logger = logging.getLogger(__name__)

# ✅ الاتحاد الكامل لكل كتل المحارف العربية المستخدَمة في النسخ الست:
#   Arabic (0600–06FF) · Arabic Supplement (0750–077F)
#   Arabic Extended-A (08A0–08FF) · Presentation Forms A (FB50–FDFF)
#   Presentation Forms B (FE70–FEFF)
ARABIC_RE = re.compile(
    "[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]"
)


def ar(text) -> str:
    """يعيد تشكيل النص العربي ويعكس اتجاهه ليُعرَض صحيحاً في ReportLab.

    النص الخالي من العربية يُعاد كما هو (لا تشويه للإنجليزية/الأرقام).
    القيم الفارغة/None تُعيد "" — ولا تُطبَع كلمة "None" في المستند.
    """
    s = str(text) if text is not None else ""
    if not s or not ARABIC_RE.search(s):
        return s
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(s), base_dir="R")
    except Exception:
        # لا يجوز أن يُسقِط تعذّرُ التشكيل توليدَ المستند كاملاً
        logger.warning("[pdf_arabic] تعذّرت إعادة تشكيل النص — يُستخدَم كما هو", exc_info=True)
        return s


def ar_wrap(text, font_name: str, font_size: float, max_width_pts: float) -> str:
    """يقسّم النص إلى أسطر تناسب العرض المتاح **ثم** يعيد تشكيل كل سطر.

    ⚠️ الترتيب مقصود: لو تُرِك `Paragraph` يلفّ نصاً أُعيد ترتيبه بـbidi
    مسبقاً، لقُطِع في الموضع الخطأ وظهرت الأسطر مبعثرة. لذلك يُقاس العرض
    على الشكل النهائي (المُشكَّل) لكل سطر قبل اعتماده.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    s = str(text or "").strip()
    if not s:
        return ""

    words = s.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = current + [word]
        if stringWidth(ar(" ".join(candidate)), font_name, font_size) <= max_width_pts or not current:
            current = candidate
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))

    return "<br/>".join(ar(line) for line in lines)


def _is_path(x) -> bool:
    """هل هذا العنصر مسار ملف لا اسم خط؟"""
    return isinstance(x, str) and (
        "/" in x or "\\" in x or x.lower().endswith((".ttf", ".otf"))
    )


def pick_font(candidates: list, fallback: str = "Helvetica") -> str:
    """يسجّل أول خط متاح من القائمة في ReportLab ويعيد اسمه.

    candidates — [(مسار الملف, اسم الخط), ...] بترتيب الأفضلية.

    ⚠️ الترتيب يُستنتَج لا يُفترَض: كل القوائم الفعلية في المشروع
    `(مسار, اسم)`، لكن هذه الدالة كانت تفكّها `(اسم, مسار)` — فكانت
    تستدعي TTFont(<مسار tahoma.ttf>, "Tahoma") معكوسةً، أي "افتح ملفاً
    اسمه Tahoma"، فيفشل **كل** مرشَّح وتعود Helvetica التي لا تملك
    محارف عربية ⇒ **مربعات في كل ملفات PDF بلا استثناء**. الفشل كان
    صامتاً تماماً لأن الاستثناء يُبتلع في `continue`.

    الآن: يُكتشَف أيّ العنصرين مسار، فيعمل الترتيبان معاً — ويُسجَّل
    خطأ صريح عند السقوط لـ`fallback` بدل الصمت.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    tried = []
    for a, b in candidates:
        path, name = (a, b) if _is_path(a) else (b, a)
        try:
            pdfmetrics.registerFont(TTFont(name, path))
            return name
        except Exception as exc:
            tried.append(f"{name}({path}): {type(exc).__name__}")
            continue

    # لا يجوز أن يمرّ هذا بصمت — النتيجة مستند عربي غير مقروء
    logger.error(
        "[pdf_arabic] تعذّر تسجيل أي خط عربي — سيظهر النص مربعات! "
        "المحاولات: %s", " | ".join(tried) or "(قائمة فارغة)"
    )
    return fallback
