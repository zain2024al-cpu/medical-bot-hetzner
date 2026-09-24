# services/arrival_documents_pdf.py
# 📄 تجميع وثائق دفعة وصول (جوازات · تأشيرات · تذاكر · إقامات) في ملف
# PDF واحد منظَّم — بدل صور متفرّقة تُنشَر فرادى في المجموعة.
#
# ⚠️ **لماذا ملف واحد لا صور فرادى**: كانت كل وثيقة تُرسَل مستقلة
# (`send_photo`/`send_document`) فتضيع بين رسائل النصّ والألبوم في
# المجموعة — عشرات الإشعارات لدفعة واحدة، ومَن يفتح المجموعة بعد ساعة
# يجد صوراً مبعثرة بلا ترتيب واضح. نفس المشكلة التي حُلَّت لصور فواتير
# الصيدلية (`pharmacy_invoice_images_pdf.py`) — هذا الملف نفس الحلّ.
#
# ⚠️ **الصور مخزَّنة في تليجرام بـ`file_id` لا في القرص**، فالتجميع
# يتطلّب **تنزيلها** — وهو ما يجعل الدالة الأولى `async` بخلاف بقية
# مولّدات PDF المتزامنة.

from __future__ import annotations

import io
import logging
from datetime import date

logger = logging.getLogger(__name__)

# ⚠️ حدّ رفع الملفات للبوت في تليجرام ≈ ٥٠ ميجابايت. يُقسَّم الناتج قبل
# بلوغه بهامش، وإلا فشل الإرسال **بعد** تنزيل كل الوثائق — أطول عملية في
# التدفّق تضيع كاملةً في آخر خطوة.
_MAX_BYTES_PER_FILE = 18 * 1024 * 1024

_HERE_FONTS = None


def _fonts():
    import os
    global _HERE_FONTS
    if _HERE_FONTS is None:
        here = os.path.dirname(os.path.abspath(__file__))
        d = os.path.normpath(os.path.join(here, "..", "assets", "fonts"))
        _HERE_FONTS = (
            [(os.path.join(d, "Arabic-Regular.ttf"), "ArrDocAr"),
             ("C:\\Windows\\Fonts\\arial.ttf", "Arial")],
            [(os.path.join(d, "Arabic-Bold.ttf"), "ArrDocArBd"),
             ("C:\\Windows\\Fonts\\arialbd.ttf", "ArialBd")],
        )
    return _HERE_FONTS


async def collect_document_bytes(documents: list[dict], bot) -> tuple[list[dict], int]:
    """ينزّل كل الوثائق. يُرجِع ([{"data", "caption"}, ...], عدد ما تعذّر تنزيله).

    ⚠️ فشل وثيقة **لا يُسقِط الباقي**: `file_id` قد يبطل في تليجرام مع
    الوقت، فتوقّف العملية كلها بسبب ملف واحد قديم يعني ألّا يصل شيء أبداً.
    تُحصى المتعذّرة وتُعلَن للمُدخِل بدل أن تُبتلَع.
    """
    items: list[dict] = []
    failed = 0
    for doc in documents:
        fid = doc.get("file_id")
        if not fid:
            continue
        try:
            f = await bot.get_file(fid)
            data = bytes(await f.download_as_bytearray())
        except Exception as exc:
            failed += 1
            logger.warning(f"[arrival_docs_pdf] تعذّر تنزيل {str(fid)[:18]}…: {exc}")
            continue
        items.append({"data": data, "caption": doc.get("caption", "") or "—"})
    return items, failed


def _chunks(items: list[dict]) -> list[list[dict]]:
    """يقسّم الوثائق على ملفات لا يتجاوز أيٌّ منها حدّ الرفع."""
    out, cur, size = [], [], 0
    for it in items:
        n = len(it["data"])
        if cur and size + n > _MAX_BYTES_PER_FILE:
            out.append(cur)
            cur, size = [], 0
        cur.append(it)
        size += n
    if cur:
        out.append(cur)
    return out or [[]]


def _build_one(items: list[dict], batch_label: str, part: int, parts: int) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdfcanvas

    from services.pdf_arabic import ar, pick_font

    reg, bold = _fonts()
    FN = pick_font(reg)
    FB = pick_font(bold, fallback=FN)

    W, H = A4
    margin = 1.2 * cm
    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)

    # صفحة غلاف — تُعرّف الملف عند فتحه أو حفظه ورقياً، بدل صفحات بلا هوية.
    c.setFont(FB, 17)
    c.setFillColor(colors.HexColor("#1F3864"))
    c.drawCentredString(W / 2, H - 4 * cm, ar("📎 وثائق دفعة الوصول"))
    c.setFont(FN, 11)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(W / 2, H - 5.2 * cm, ar(batch_label))
    c.drawCentredString(W / 2, H - 6.0 * cm, ar(f"عدد الوثائق: {len(items)}"))
    if parts > 1:
        c.drawCentredString(W / 2, H - 6.8 * cm, ar(f"الجزء {part} من {parts}"))
    c.drawCentredString(W / 2, H - 7.6 * cm,
                        ar(f"تاريخ الإنشاء: {date.today().isoformat()}"))
    c.showPage()

    for i, it in enumerate(items, start=1):
        c.setFont(FB, 12)
        c.setFillColor(colors.HexColor("#1F3864"))
        c.drawRightString(W - margin, H - margin - 0.2 * cm, ar(f"{i}. {it['caption']}"))
        c.setStrokeColor(colors.HexColor("#9BA5B4"))
        c.line(margin, H - margin - 0.55 * cm, W - margin, H - margin - 0.55 * cm)

        top = H - margin - 0.9 * cm
        avail_w = W - 2 * margin
        avail_h = top - margin - 0.6 * cm
        try:
            img = ImageReader(io.BytesIO(it["data"]))
            iw, ih = img.getSize()
            # ⚠️ النسبة محفوظة: تمديد الصورة لملء الصفحة يشوّه أرقام
            # الجواز/التأشيرة فتصير غير مقروءة — والغرض كلّه قراءتها.
            scale = min(avail_w / iw, avail_h / ih)
            w, h = iw * scale, ih * scale
            c.drawImage(img, (W - w) / 2, top - h, width=w, height=h,
                        preserveAspectRatio=True, anchor="n")
        except Exception as exc:
            logger.warning(f"[arrival_docs_pdf] تعذّر رسم وثيقة {it['caption']}: {exc}")
            c.setFont(FN, 11)
            c.setFillColor(colors.HexColor("#B00020"))
            c.drawCentredString(W / 2, top - 3 * cm, ar("⚠️ تعذّر عرض هذه الوثيقة"))

        c.setFont(FN, 8)
        c.setFillColor(colors.HexColor("#888888"))
        c.drawRightString(W - margin, 0.7 * cm, ar(f"صفحة {c.getPageNumber()}"))
        c.showPage()

    c.save()
    buf.seek(0)
    return buf


async def build_arrival_documents_pdfs(documents: list[dict], bot, batch_label: str
                                       ) -> tuple[list[io.BytesIO], int, int]:
    """يُرجِع (الملفات، عدد الوثائق المُدرَجة، عدد المتعذّرة)."""
    items, failed = await collect_document_bytes(documents, bot)
    groups = _chunks(items)
    files = [_build_one(g, batch_label, i + 1, len(groups))
             for i, g in enumerate(groups)]
    logger.info(f"[arrival_docs_pdf] {len(items)} وثيقة في {len(files)} ملف "
                f"(تعذّر {failed})")
    return files, len(items), failed
