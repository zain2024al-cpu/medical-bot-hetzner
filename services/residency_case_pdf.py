# services/residency_case_pdf.py
# PDF لـ"🖨️ طباعة ملف الحالة" — ملف واحد منظّم يجمع المريض وكل مرافقيه:
# بيانات أساسية + صورة شخصية + حالة الإقامة الحالية + آخر إصدار (تاريخه
# وملفه) + وثائقه المستقلة، ثم جدول ملخّص في النهاية.
#
# ✅ دالة نقية متزامنة بلا أي استدعاء Telegram/DB داخلها — تستقبل قاموس
# `case` جاهزاً (بايتات الصور/الملفات مُنزَّلة مسبقاً من المتصل غير
# المتزامن في modules/residency/flow.py عبر bot.get_file+download_to_memory)
# لتشغيلها بأمان داخل asyncio.to_thread دون تعارض حلقات الأحداث.
#
# نفس نمط النص العربي السليم المُثبَت في services/pharmacy_evacuation_pdf.py
# (reshape+bidi صريح + خط عربي حقيقي مسجَّل)، مُعاد كتابته هنا محلياً
# استقلالاً لكل ملف PDF كما جرت العادة في هذا المشروع.
#
# ✅ الصورة الشخصية/ملف الإصدار/كل وثيقة قد تصل صورة أو ملف PDF حقيقي
# (Form C الرسمية غالباً PDF) — تُصنَّف بايتات كل مرفق فعلياً
# (_classify_attachment)، فالصور تُضمَّن مباشرة داخل النص، وملفات PDF
# الحقيقية تُدمَج كصفحات كاملة في نهاية الملف عبر pypdf (نفس نمط
# bot/handlers/admin/admin_patient_attachments_bundle.py) بدل إسقاطها.

from __future__ import annotations

import io
import logging
import os
import re

logger = logging.getLogger(__name__)

# ✅ نمط محارف العربية انتقل إلى services/pdf_arabic.py::ARABIC_RE
# (كان معرَّفاً هنا بنسخة مستقلة تباعدت عن البقية).

_HERE = os.path.dirname(os.path.abspath(__file__))
_FONTS_DIR = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts"))

_FONT_CANDIDATES = [
    ("C:\\Windows\\Fonts\\arial.ttf", "Arial"),
    ("C:\\Windows\\Fonts\\tahoma.ttf", "Tahoma"),
    (os.path.join(_FONTS_DIR, "Arabic-Regular.ttf"), "ResCaseArFont"),
]
_FONT_BOLD_CANDIDATES = [
    ("C:\\Windows\\Fonts\\arialbd.ttf", "ArialBd"),
    ("C:\\Windows\\Fonts\\tahomabd.ttf", "TahomaBd"),
    (os.path.join(_FONTS_DIR, "Arabic-Bold.ttf"), "ResCaseArFontBd"),
]

_MARGIN_CM = 2.0


def _pick_font(candidates: list[tuple[str, str]], fallback: str = "Helvetica") -> str:
    """غلاف رقيق حول services/pdf_arabic.py::pick_font — المصدر الموحّد.
    قوائم الخطوط (_FONT_CANDIDATES) تبقى في كل ملف كما هي."""
    from services.pdf_arabic import pick_font as _shared_pick_font
    return _shared_pick_font(candidates, fallback)


def _ar(text) -> str:
    """غلاف رقيق حول services/pdf_arabic.py::ar — المصدر الموحّد.
    (كانت نسخة مستقلة؛ انظر شرح سبب التوحيد في ذلك الملف.)"""
    from services.pdf_arabic import ar as _shared_ar
    return _shared_ar(text)


def _ar_wrap(text, font_name: str, font_size: float, max_width_pts: float) -> str:
    """غلاف رقيق حول services/pdf_arabic.py::ar_wrap — المصدر الموحّد."""
    from services.pdf_arabic import ar_wrap as _shared_ar_wrap
    return _shared_ar_wrap(text, font_name, font_size, max_width_pts)


def _colors():
    from reportlab.lib import colors
    return {
        "primary":   colors.HexColor("#424242"),
        "light_bg":  colors.HexColor("#F0F0F0"),
        "grid":      colors.HexColor("#CCCCCC"),
        "text_dark": colors.HexColor("#212121"),
        "text_gray": colors.HexColor("#777777"),
        "white":     colors.white,
        "frame":     colors.HexColor("#333333"),
    }


def _classify_attachment(data: bytes | None) -> str:
    """يفرّق بين ملف PDF حقيقي (يُدمَج كصفحات كاملة لاحقاً — Form C
    الرسمية غالباً PDF لا صورة) وصورة (تُضمَّن مباشرة داخل النص) وأي نوع
    آخر غير مدعوم للمعاينة داخل هذا الملف. لا يعتمد على امتداد الملف
    (غير متوفر أصلاً من Telegram file_id) بل على محتوى البايتات نفسها."""
    if not data:
        return "none"
    if data[:5] == b"%PDF-":
        return "pdf"
    try:
        from reportlab.lib.utils import ImageReader

        reader = ImageReader(io.BytesIO(data))
        iw, ih = reader.getSize()
        if iw and ih:
            return "image"
    except Exception:
        pass
    return "unknown"


def _embed_image(img_bytes: bytes, max_w_pts: float, max_h_pts: float):
    """يبني عنصر Image محافِظاً على نسبة الأبعاد ضمن الحد الأقصى
    المُعطى، أو None إن تعذّرت قراءة البايتات فعلياً رغم تصنيفها صورة."""
    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.platypus import Image

        reader = ImageReader(io.BytesIO(img_bytes))
        iw, ih = reader.getSize()
        if not iw or not ih:
            return None
        scale = min(max_w_pts / iw, max_h_pts / ih, 1.0)
        return Image(io.BytesIO(img_bytes), width=iw * scale, height=ih * scale)
    except Exception as exc:
        logger.warning(f"[residency_case_pdf] embed image failed: {exc}")
        return None


def build_case_pdf(case: dict) -> io.BytesIO:
    """
    case = {
        "root_id": int, "case_no": str, "patient_name": str,
        "companion_count": int, "created_at": str,
        "people": [
            {
                "name": str, "role": str,               # "المريض" | "مرافق"
                "status_text": str,                       # نص الحالة الجاهز (أيقونة + تسمية)
                "photo_bytes": bytes | None,               # None = فئة "الصورة الشخصية" غير مطلوبة
                "expiry_date": str,                        # قد تكون فارغة (معلومة نصّية دائماً)
                "arrival_docs": {                            # مفاتيح المطلوب فقط منها — الغائب لا يُعرَض إطلاقاً
                    "passport": bytes | None, "visa": bytes | None, "tickets": bytes | None,
                },
                "residence_doc": {                           # None = فئة "صورة الإقامة" غير مطلوبة
                    "source": "من الوصول" | "إصدار رسمي" | None,  # None = مطلوبة لكن لا مصدر لدى الشخص
                    "date": str, "file_bytes": bytes | None,
                } | None,
                "documents": [{"label": str, "file_bytes": bytes | None}],
            }, ...
        ],
    }
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
    )

    C = _colors()
    FN = _pick_font(_FONT_CANDIDATES)
    FNB = _pick_font(_FONT_BOLD_CANDIDATES, FN)

    margin = _MARGIN_CM * cm
    content_width = A4[0] - (2 * margin)

    def S(name, **kw):
        kw.setdefault("fontName", FN)
        return ParagraphStyle(name, **kw)

    ST = {
        "title":  S("title", fontSize=17, leading=22, alignment=TA_CENTER, textColor=C["primary"], fontName=FNB),
        "h2":     S("h2",    fontSize=13, leading=17, alignment=TA_RIGHT,  textColor=C["primary"], fontName=FNB),
        "body":   S("body",  fontSize=10, leading=15, alignment=TA_RIGHT,  textColor=C["text_dark"]),
        "body_b": S("bodyb", fontSize=10, leading=15, alignment=TA_RIGHT,  textColor=C["text_dark"], fontName=FNB),
        "th":     S("th",    fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_dark"], fontName=FNB),
        "td_c":   S("tdc",   fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_dark"]),
        "note":   S("note",  fontSize=9,  leading=12, alignment=TA_CENTER, textColor=C["text_gray"]),
    }

    def P(txt, style_key="body") -> Paragraph:
        return Paragraph(_ar(txt), ST[style_key])

    def P_wrap(txt, style_key, max_width_pts) -> Paragraph:
        style = ST[style_key]
        usable_width = max(max_width_pts - 10, 20)
        wrapped = _ar_wrap(txt, style.fontName, style.fontSize, usable_width)
        return Paragraph(wrapped, style)

    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4
        frame_margin = 0.5 * cm
        canvas.setStrokeColor(C["frame"])
        canvas.setLineWidth(0.6)
        canvas.rect(frame_margin, frame_margin, w - 2 * frame_margin, h - 2 * frame_margin, fill=0, stroke=1)
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

    # ── رأس ملف الحالة ────────────────────────────────────────────────────────
    story.append(P("🏠 ملف الحالة", "title"))
    story.append(Spacer(1, 0.3 * cm))
    header_lines = [
        f"رقم الحالة: {case.get('case_no', '')}",
        f"اسم المريض: {case.get('patient_name', '')}",
        f"عدد المرافقين: {case.get('companion_count', 0)}",
        f"تاريخ الإصدار: {case.get('created_at', '')}",
    ]
    for line in header_lines:
        story.append(P(line, "body_b"))
    story.append(Spacer(1, 0.4 * cm))

    people = case.get("people", [])
    photo_max = (4.5 * cm, 4.5 * cm)
    # ✅ ارتفاع الحد الأقصى كان 9سم فقط — صغير جداً لصور المستندات
    # الرأسية (جواز/تأشيرة/إقامة المصوَّرة بالهاتف عادة طولية)، فيقيّدها
    # الارتفاع القصير فتظهر ضيقة جداً مقارنة بعرض الصفحة المتاح (شكوى
    # "المقاسات صغيرة وبقية الصفحة فاضية"). رُفِع لقرابة ارتفاع الصفحة
    # القابل للطباعة فعلياً حتى تستغل الصور الطولية عرض الصفحة كاملاً.
    file_max = (content_width * 0.95, 22 * cm)

    # ✅ كل ملف/وثيقة يتبيّن أنه PDF حقيقي (Form C الرسمية غالباً PDF لا
    # صورة) لا يمكن تضمينه كـImage داخل النص المتدفّق — يُجمَع هنا ليُدمَج
    # كصفحات كاملة في نهاية الملف (بعد صفحة فاصلة تُعرِّف صاحبه ونوعه)،
    # بدل إسقاطه بصمت كما كان يحدث سابقاً.
    pdf_attachments: list[tuple[str, bytes]] = []

    def _attachment_flowables(label: str, data: bytes | None, person_name: str):
        kind = _classify_attachment(data)
        if kind == "none":
            return [P(f"- {label}: لا يوجد ملف مرفوع بعد.", "note")]
        if kind == "image":
            img = _embed_image(data, *file_max)
            if img is not None:
                img.hAlign = "RIGHT"
                return [P(f"- {label} ✅", "body"), img]
            return [P(f"- {label} ✅ (تعذّر عرض الصورة)", "note")]
        if kind == "pdf":
            pdf_attachments.append((f"{person_name} — {label}", data))
            return [P(f"- {label} ✅ (ملف PDF — الصفحات مرفقة في نهاية هذا الملف)", "body")]
        return [P(f"- {label} ✅ (نوع ملف غير مدعوم للمعاينة هنا — راجعه داخل البوت)", "note")]

    for person in people:
        block = []
        block.append(P(f"👤 {person['name']} — {person['role']}", "h2"))
        block.append(Spacer(1, 0.15 * cm))

        img = _embed_image(person.get("photo_bytes"), *photo_max) if person.get("photo_bytes") else None
        if img is not None:
            img.hAlign = "RIGHT"
            block.append(img)
            block.append(Spacer(1, 0.15 * cm))

        block.append(P(f"الحالة الحالية: {person.get('status_text', '')}", "body"))
        if person.get("expiry_date"):
            block.append(P(f"تاريخ انتهاء الإقامة الحالية: {person['expiry_date']}", "body"))

        # ✅ إقامة واحدة فقط تُطبَع — الأحدث زمنياً أياً كان مصدرها (وصول
        # أو إصدار رسمي لاحق)، بطلب المستخدم صراحةً؛ لا تُعرَض الاثنتان
        # معاً أبداً. `residence_doc is None` = الفئة غير مطلوبة أصلاً.
        residence_doc = person.get("residence_doc")
        if residence_doc is not None:
            block.append(Spacer(1, 0.1 * cm))
            block.append(P("🪪 صورة الإقامة:", "body_b"))
            if residence_doc.get("source"):
                block.append(P(f"المصدر: {residence_doc['source']}  —  التاريخ: {residence_doc.get('date', '')}", "body"))
                block.extend(_attachment_flowables("صورة الإقامة", residence_doc.get("file_bytes"), person["name"]))
            else:
                block.append(P("لا توجد إقامة مرفوعة.", "note"))

        # ✅ وثائق "🛬 الوصول" (جواز/تأشيرة/تذاكر) — مصدر مستقل تماماً عن
        # res_documents، مفاتيح غائبة = فئتها غير مطلوبة فلا يُعرَض سطرها.
        arrival_docs = person.get("arrival_docs") or {}
        if arrival_docs:
            block.append(Spacer(1, 0.15 * cm))
            block.append(P("📎 وثائق الوصول:", "body_b"))
            _ARRIVAL_LABELS = [("passport", "جواز السفر"), ("visa", "التأشيرة"), ("tickets", "التذاكر")]
            for key, label in _ARRIVAL_LABELS:
                if key in arrival_docs:
                    block.extend(_attachment_flowables(label, arrival_docs.get(key), person["name"]))

        block.append(Spacer(1, 0.15 * cm))
        docs = person.get("documents", [])
        block.append(P(f"📄 الوثائق ({len(docs)}):", "body_b"))
        if not docs:
            block.append(P("لا توجد وثائق مضافة.", "note"))
        else:
            for d in docs:
                block.extend(_attachment_flowables(d["label"], d.get("file_bytes"), person["name"]))

        story.append(KeepTogether(block))
        story.append(Spacer(1, 0.5 * cm))

    # ── جدول ملخّص ────────────────────────────────────────────────────────────
    story.append(P("📊 ملخّص الحالة", "h2"))
    story.append(Spacer(1, 0.2 * cm))

    REVERSED_LABELS = ["عدد الوثائق", "آخر إصدار", "حالة الإقامة", "الصفة", "الشخص"]
    col_pct = {"عدد الوثائق": 0.15, "آخر إصدار": 0.2, "حالة الإقامة": 0.25, "الصفة": 0.15, "الشخص": 0.25}
    header_row = [P(lbl, "th") for lbl in REVERSED_LABELS]
    col_widths = [content_width * col_pct[lbl] for lbl in REVERSED_LABELS]

    table_data = [header_row]
    for person in people:
        _rdoc = person.get("residence_doc")
        last_issue = (_rdoc.get("date") if _rdoc and _rdoc.get("source") else None) or "—"
        table_data.append([
            P(str(len(person.get("documents", []))), "td_c"),
            P(last_issue, "td_c"),
            P(person.get("status_text", ""), "td_c"),
            P(person["role"], "td_c"),
            P_wrap(person["name"], "td_c", col_widths[-1]),
        ])

    t = Table(table_data, colWidths=col_widths, hAlign="CENTER", repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C["light_bg"]),
        ("BACKGROUND", (0, 1), (-1, -1), C["white"]),
        ("GRID", (0, 0), (-1, -1), 0.4, C["grid"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)

    if not pdf_attachments:
        logger.info(f"[residency_case_pdf] built  root_id={case.get('root_id')}  people={len(people)}  size={buf.getbuffer().nbytes:,}  pdf_attachments=0")
        return buf

    # ── دمج صفحات مرفقات PDF الحقيقية في نهاية الملف ──────────────────────────
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas as canvas_mod

    def _divider_page_bytes(label: str) -> bytes:
        dbuf = io.BytesIO()
        c = canvas_mod.Canvas(dbuf, pagesize=A4)
        w, h = A4
        c.setFont(FNB, 15)
        c.setFillColor(C["primary"])
        c.drawCentredString(w / 2, h / 2 + 0.4 * cm, _ar("📎 مرفق"))
        c.setFont(FN, 12)
        c.setFillColor(C["text_dark"])
        c.drawCentredString(w / 2, h / 2 - 0.4 * cm, _ar(label))
        c.showPage()
        c.save()
        dbuf.seek(0)
        return dbuf.getvalue()

    writer = PdfWriter()
    for page in PdfReader(buf).pages:
        writer.add_page(page)

    for label, raw in pdf_attachments:
        for page in PdfReader(io.BytesIO(_divider_page_bytes(label))).pages:
            writer.add_page(page)
        try:
            for page in PdfReader(io.BytesIO(raw)).pages:
                writer.add_page(page)
        except Exception as exc:
            logger.warning(f"[residency_case_pdf] failed to merge pdf attachment {label!r}: {exc}")
            for page in PdfReader(io.BytesIO(_divider_page_bytes(f"{label} — تعذّر فتح الملف"))).pages:
                writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    logger.info(f"[residency_case_pdf] built  root_id={case.get('root_id')}  people={len(people)}  size={out.getbuffer().nbytes:,}  pdf_attachments={len(pdf_attachments)}")
    return out
