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
# فتسقط لـHelvetica وتظهر العربية مربعات).
#
# ⚠️ **حزمة وثائق لا تقرير بيانات**: الطلب صراحةً تحويل الملف من جداول
# بيانات (حالة/تواريخ/سجل أحداث) إلى عرض **صور الوثائق نفسها** — جواز
# وتأشيرة وإقامة (آخر نسخة مرفوعة لا كل النسخ التاريخية — والعمود نفسه
# `latest_residency_file_id` لا يخزّن غيرها أصلاً) وفورم C، ثم نفس المجموعة
# لكل مرافق بالترتيب. جدول بيانات المرافقين وسجل الأحداث حُذفا من هذا
# الملف تحديداً لأنهما ليسا "وثائق" — إن احتاجهما المستخدم لاحقاً فمكانهما
# شاشة تفصيل الملف داخل البوت لا هذا الملف.
#
# ⚠️ لا إيموجي في نصوص PDF: الخط العربي المضمَّن نصّي بلا حروف تصويرية،
# وreportlab لا يرسم إيموجي ملوَّنة أصلاً — ظهرت ستكون مربعات فارغة. كل
# النصوص هنا عربية/إنجليزية صرفة، مطابقةً لعرف بقية ملفات هذا المشروع.

from __future__ import annotations

import io
import logging
from datetime import date

logger = logging.getLogger(__name__)

_MARGIN_CM = 1.6
# أقصى ارتفاع لصورة وثيقة واحدة — يكفي لصورة واضحة وقابلة للقراءة دون أن
# تفرض صفحة إضافية لكل وثيقة بمفردها.
_MAX_IMG_HEIGHT_CM = 9.5
# لا تكبير مفرط لصورة صغيرة الدقة أصلاً (تظهر مبكسلة)
_MAX_UPSCALE = 3.0


def _prepare_image_flowable(raw: bytes, max_width_pt: float, max_height_pt: float):
    """
    يحوّل بايتات صورة خامة (من تيليجرام) إلى Image جاهزة للإدراج في PDF.

    يصحّح دوران الهاتف عبر بيانات EXIF (الصور المرفوعة من الجوال كثيراً ما
    تصل بدوران خاطئ بصرياً رغم أنها "معتدلة" في بياناتها الوصفية)، ويحسب
    مقاساً يحافظ على النسبة الأصلية ويملأ المساحة المتاحة بلا تمدّد يشوّه
    محتوى الوثيقة.
    """
    from PIL import Image as PILImage, ImageOps
    from reportlab.platypus import Image as RLImage

    im = PILImage.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")

    w, h = im.size
    scale = min(max_width_pt / w, max_height_pt / h, _MAX_UPSCALE)
    draw_w, draw_h = w * scale, h * scale

    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88)
    out.seek(0)
    return RLImage(out, width=draw_w, height=draw_h)


def build_profile_pdf(*, profile, companions, images: dict[str, bytes]) -> bytes:
    """
    يبني حزمة PDF لوثائق مريض ومرافقيه.

    ``images`` قاموس ``file_id → bytes`` تحمّله الطبقة المستدعية مسبقاً
    (I/O شبكي async عبر بوت تيليجرام) — هذه الدالة متزامنة صرفة (بناء PDF
    حسابي)، فلا تحتاج ولا تعرف شيئاً عن كائن البوت.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, KeepTogether, PageBreak,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    from services.residency_archive_pdf import (
        _pick_font, _ar, _FONT_CANDIDATES, _FONT_BOLD_CANDIDATES,
    )

    font   = _pick_font(_FONT_CANDIDATES)
    font_b = _pick_font(_FONT_BOLD_CANDIDATES, fallback=font)

    buf = io.BytesIO()
    page = A4
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=_MARGIN_CM * cm, rightMargin=_MARGIN_CM * cm,
        topMargin=1.3 * cm, bottomMargin=1.3 * cm,
        title=f"Residency documents — {profile.name}",
    )
    W = page[0] - 2 * _MARGIN_CM * cm
    max_img_h = _MAX_IMG_HEIGHT_CM * cm

    title  = ParagraphStyle("t", fontName=font_b, fontSize=16, alignment=TA_CENTER,
                            textColor=colors.HexColor("#424242"), leading=21)
    sub    = ParagraphStyle("s", fontName=font, fontSize=9, alignment=TA_CENTER,
                            textColor=colors.HexColor("#757575"), leading=13)
    person = ParagraphStyle("p", fontName=font_b, fontSize=13, alignment=TA_RIGHT,
                            textColor=colors.HexColor("#263238"), leading=18)
    doclbl = ParagraphStyle("d", fontName=font_b, fontSize=10, alignment=TA_RIGHT,
                            textColor=colors.HexColor("#546E7A"), leading=14)
    body   = ParagraphStyle("b", fontName=font, fontSize=9.5, alignment=TA_RIGHT, leading=14)

    def _doc_block(label_ar: str, file_id: str):
        raw = images.get(file_id) if file_id else None
        if not raw:
            return None
        try:
            img = _prepare_image_flowable(raw, W, max_img_h)
        except Exception:
            logger.warning(
                f"[residency.profile_pdf] تعذّرت معالجة صورة"
                f"  label={label_ar!r}  file_id={file_id!r}"
            )
            return None
        # ✅ KeepTogether يمنع فصل التسمية عن صورتها عبر فاصل صفحة — أهم من
        # فصل الصورة نفسها لأنها لا تنقسم أصلاً على أكثر من صفحة.
        return KeepTogether([
            Paragraph(_ar(label_ar), doclbl),
            Spacer(1, 0.15 * cm),
            img,
            Spacer(1, 0.5 * cm),
        ])

    def _person_section(name: str, docs: list[tuple[str, str]], *, is_companion: bool) -> list:
        header = ("المرافق: " if is_companion else "المريض: ") + (name or "—")
        blocks = [Paragraph(_ar(header), person), Spacer(1, 0.3 * cm)]
        found_any = False
        for label, fid in docs:
            block = _doc_block(label, fid)
            if block:
                blocks.append(block)
                found_any = True
        if not found_any:
            blocks.append(Paragraph(_ar("لا توجد وثائق مرفوعة."), body))
        return blocks

    story = [
        Paragraph(_ar("حزمة وثائق الإقامة"), title),
        Spacer(1, 0.1 * cm),
        Paragraph(_ar(f"تاريخ الإصدار: {date.today().strftime('%d/%m/%Y')}"), sub),
        Spacer(1, 0.7 * cm),
    ]

    people: list[tuple[str, list[tuple[str, str]], bool]] = [(
        profile.name,
        [
            ("جواز السفر",                    profile.passport_file_id),
            ("التأشيرة",                       profile.visa_file_id),
            ("الإقامة (آخر نسخة مرفوعة)",      profile.latest_residency_file_id),
            ("فورم C (وثيقة عائلية واحدة)",    getattr(profile, "form_c_file_id", "")),
        ],
        False,
    )]
    for c in companions:
        people.append((
            c.name,
            [
                ("جواز السفر",               c.passport_file_id),
                ("التأشيرة",                  c.visa_file_id),
                ("الإقامة (آخر نسخة مرفوعة)", c.latest_residency_file_id),
            ],
            True,
        ))

    for i, (name, docs, is_comp) in enumerate(people):
        if i > 0:
            story.append(PageBreak())
        story += _person_section(name, docs, is_companion=is_comp)

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor("#9E9E9E"))
        canvas.drawCentredString(page[0] / 2, 0.7 * cm, str(doc_.page))
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    out = buf.getvalue()
    logger.info(
        f"[residency.profile_pdf] built  name={profile.name!r}  bytes={len(out)}"
        f"  people={len(people)}  images_available={len(images)}"
    )
    return out
