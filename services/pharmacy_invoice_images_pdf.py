# services/pharmacy_invoice_images_pdf.py
# 📸 تجميع **صور الفواتير المرفوعة** في ملف PDF قابل للطباعة.
#
# يختلف عن services/pharmacy_invoices_pdf.py: ذاك جدول أرقام، وهذا
# الصور نفسها — صفحة لكل صورة برأس يعرّفها (المريض · التاريخ · رقم
# الفاتورة)، وإلا صارت أوراقاً بلا هوية عند الطباعة.
#
# ⚠️ الصور مخزَّنة في تليجرام بـ`file_id` لا في القرص، فالتجميع يتطلّب
# **تنزيلها** — وهو ما يجعل هذه الدالة `async` بخلاف بقية مولّدات PDF.

from __future__ import annotations

import io
import json
import logging
from datetime import date

logger = logging.getLogger(__name__)

# ⚠️ حدّ رفع الملفات للبوت في تليجرام ≈ ٥٠ ميجابايت. يُقسَّم الناتج قبل
# بلوغه بهامش، وإلا فشل الإرسال **بعد** تنزيل كل الصور — أطول عملية في
# التدفّق تضيع كاملةً في آخر خطوة.
_MAX_BYTES_PER_FILE = 18 * 1024 * 1024

_AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
            "الجمعة", "السبت", "الأحد"]

_HERE_FONTS = None


def _fonts():
    import os
    global _HERE_FONTS
    if _HERE_FONTS is None:
        here = os.path.dirname(os.path.abspath(__file__))
        d = os.path.normpath(os.path.join(here, "..", "assets", "fonts"))
        _HERE_FONTS = (
            [(os.path.join(d, "Arabic-Regular.ttf"), "PhImgAr"),
             ("C:\\Windows\\Fonts\\arial.ttf", "Arial")],
            [(os.path.join(d, "Arabic-Bold.ttf"), "PhImgArBd"),
             ("C:\\Windows\\Fonts\\arialbd.ttf", "ArialBd")],
        )
    return _HERE_FONTS


def _ids_of(row) -> list[str]:
    """معرّفات صور صفّ واحد — تتحمّل التالف بدل أن تُسقِط العملية."""
    raw = row.get("image_file_ids") or "[]"
    try:
        ids = json.loads(raw) if isinstance(raw, str) else list(raw or [])
    except (ValueError, TypeError):
        logger.warning(f"[invoice_images] JSON تالف للصفّ {row.get('invoice_number')}")
        return []
    return [str(i) for i in ids if i]


def count_images(rows: list[dict]) -> int:
    return sum(len(_ids_of(r)) for r in rows)


async def collect_images(rows: list[dict], bot) -> tuple[list[dict], int]:
    """ينزّل كل الصور. يُرجِع (العناصر، عدد ما تعذّر تنزيله).

    ⚠️ فشل صورة **لا يُسقِط الباقي**: `file_id` قد يبطل في تليجرام مع
    الوقت، فتوقّف العملية كلها بسبب صورة واحدة قديمة يعني ألّا يُطبَع شيء
    أبداً. تُحصى المتعذّرة وتُعلَن للمستخدم بدل أن تُبتلَع.
    """
    items: list[dict] = []
    failed = 0
    for r in rows:
        for fid in _ids_of(r):
            try:
                f = await bot.get_file(fid)
                data = bytes(await f.download_as_bytearray())
            except Exception as exc:
                failed += 1
                logger.warning(f"[invoice_images] تعذّر تنزيل {str(fid)[:18]}…: {exc}")
                continue
            items.append({
                "data": data,
                "patient": str(r.get("name") or "—"),
                "invoice": str(r.get("invoice_number") or "—"),
                "date": r.get("date"),
                "expense_item": str(r.get("expense_item") or "—"),
            })
    return items, failed


def _chunks(items: list[dict]) -> list[list[dict]]:
    """يقسّم الصور على ملفات لا يتجاوز أيٌّ منها حدّ الرفع."""
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


def _build_one(items: list[dict], start_date: date, end_date: date,
               part: int, parts: int) -> io.BytesIO:
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

    period = (start_date.isoformat() if start_date == end_date
              else f"{start_date.isoformat()}  ←  {end_date.isoformat()}")

    # صفحة غلاف — تُعرّف الملف عند طباعته وحفظه ورقياً
    c.setFont(FB, 17)
    c.setFillColor(colors.HexColor("#1F3864"))
    c.drawCentredString(W / 2, H - 4 * cm, ar("📸 صور فواتير الصيدلية"))
    c.setFont(FN, 11)
    c.setFillColor(colors.HexColor("#444444"))
    c.drawCentredString(W / 2, H - 5.2 * cm, ar(f"الفترة: {period}"))
    c.drawCentredString(W / 2, H - 6.0 * cm, ar(f"عدد الصور: {len(items)}"))
    if parts > 1:
        c.drawCentredString(W / 2, H - 6.8 * cm, ar(f"الجزء {part} من {parts}"))
    c.drawCentredString(W / 2, H - 7.6 * cm,
                        ar(f"تاريخ الطباعة: {date.today().isoformat()}"))
    c.showPage()

    for i, it in enumerate(items, start=1):
        d = it.get("date")
        dlabel = (f"{_AR_DAYS[d.weekday()]} {d.isoformat()}"
                  if hasattr(d, "weekday") else "—")

        c.setFont(FB, 11)
        c.setFillColor(colors.HexColor("#1F3864"))
        c.drawRightString(W - margin, H - margin - 0.2 * cm,
                          ar(f"{i}. {it['patient']}"))
        c.setFont(FN, 9)
        c.setFillColor(colors.HexColor("#555555"))
        c.drawRightString(W - margin, H - margin - 0.95 * cm,
                          ar(f"فاتورة: {it['invoice']}   ·   {it['expense_item']}   ·   {dlabel}"))
        c.setStrokeColor(colors.HexColor("#9BA5B4"))
        c.line(margin, H - margin - 1.25 * cm, W - margin, H - margin - 1.25 * cm)

        top = H - margin - 1.6 * cm
        avail_w = W - 2 * margin
        avail_h = top - margin - 0.6 * cm
        try:
            img = ImageReader(io.BytesIO(it["data"]))
            iw, ih = img.getSize()
            # ⚠️ النسبة محفوظة: تمديد الصورة لملء الصفحة يشوّه أرقام
            # الفاتورة فتصير غير مقروءة — والغرض كلّه قراءتها.
            scale = min(avail_w / iw, avail_h / ih)
            w, h = iw * scale, ih * scale
            c.drawImage(img, (W - w) / 2, top - h, width=w, height=h,
                        preserveAspectRatio=True, anchor="n")
        except Exception as exc:
            logger.warning(f"[invoice_images] تعذّر رسم صورة {it['invoice']}: {exc}")
            c.setFont(FN, 11)
            c.setFillColor(colors.HexColor("#B00020"))
            c.drawCentredString(W / 2, top - 3 * cm, ar("⚠️ تعذّر عرض هذه الصورة"))

        c.setFont(FN, 8)
        c.setFillColor(colors.HexColor("#888888"))
        c.drawRightString(W - margin, 0.7 * cm, ar(f"صفحة {c.getPageNumber()}"))
        c.showPage()

    c.save()
    buf.seek(0)
    return buf


async def build_invoice_images_pdfs(rows: list[dict], bot,
                                    start_date: date, end_date: date
                                    ) -> tuple[list[io.BytesIO], int, int]:
    """يُرجِع (الملفات، عدد الصور المُدرَجة، عدد المتعذّرة)."""
    items, failed = await collect_images(rows, bot)
    groups = _chunks(items)
    files = [_build_one(g, start_date, end_date, i + 1, len(groups))
             for i, g in enumerate(groups)]
    logger.info(f"[invoice_images] {len(items)} صورة في {len(files)} ملف "
                f"(تعذّر {failed})")
    return files, len(items), failed
