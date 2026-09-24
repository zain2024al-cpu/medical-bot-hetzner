# services/arrival_documents_pdf.py
# 📄 تجميع وثائق دفعة وصول (جوازات · تأشيرات · تذاكر · إقامات) في ملف
# PDF واحد منظَّم — بدل صور متفرّقة تُنشَر فرادى في المجموعة.
#
# ⚠️ **لماذا ملف واحد لا صور فرادى**: كانت كل وثيقة تُرسَل مستقلة
# فتضيع بين رسائل النصّ والألبوم في المجموعة — عشرات الإشعارات لدفعة
# واحدة. نفس المشكلة التي حُلَّت لصور فواتير الصيدلية
# (`pharmacy_invoice_images_pdf.py`) — هذا الملف نفس الحلّ.
#
# ⚠️ **«بلا فراغات»** (طلب المستخدم صراحةً بعد أول نسخة من هذا الملف):
# النسخة الأولى رسمت كل وثيقة على صفحة **عمودية** ثابتة بمقاس A4. أغلب
# وثائق السفر (جواز · تأشيرة · بطاقة) عريضة أفقياً، فحين تُحصَر عرضاً في
# صفحة طويلة يبقى أكثر من نصف ارتفاعها أبيض خالياً — فراغ حقيقي لا خطأ
# عرض. الحلّ هنا: **اتجاه الصفحة يتبع شكل الصورة نفسها**، لا مقاساً
# ثابتاً — أفقية لوثيقة عريضة، عمودية لوثيقة طويلة، وبينهما يُختار ما
# يُظهر الصورة أكبر فعلياً (قياساً لا تخميناً، انظر `_best_orientation`).
# وصفحة الغلاف صارت **فهرساً** حقيقياً (شخص × نوع وثيقة) بدل أسطر معلّقة
# فوق صفحة خالية.
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

# ألوان ثابتة — نفس هوية بقية مولّدات PDF في المشروع (نمط "#1F3864" الأزرق
# الرسمي في residency_case_pdf.py وpharmacy_invoices_pdf.py وغيرها).
_NAVY = "#1F3864"
_GRAY_BORDER = "#9BA5B4"
_GRAY_TEXT = "#666666"
_ROW_ALT = "#F2F6FC"
_RED = "#B00020"
_WHITE = "#FFFFFF"

# تسميات أعمدة الفهرس — نفس ترتيب DOC_TYPE_ORDER في group_documents.py.
# ⚠️ بلا إيموجي هنا: `ar()` يحذفه من نص الـPDF دائماً (لا خط على الخادم
# يملك محارف الإيموجي)، فإدراجه في عرض عمود ضيّق يُنتج عموداً بلا عنوان.
_DOC_TYPE_COLS = [
    ("passport", "جواز"), ("visa", "تأشيرة"),
    ("tickets", "تذاكر"), ("residence", "إقامة"),
]

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
    """ينزّل كل الوثائق. يُرجِع ([{"data", "person_label", "doc_key",
    "doc_label", "caption"}, ...], عدد ما تعذّر تنزيله).

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
        items.append({
            "data": data,
            "person_label": doc.get("person_label", "") or "—",
            "doc_key": doc.get("doc_key", ""),
            "doc_label": doc.get("doc_label", "") or "—",
            "caption": doc.get("caption", "") or "—",
        })
    return items, failed


def _chunks(items: list[dict]) -> list[list[dict]]:
    """يقسّم الوثائق على ملفات لا يتجاوز أيٌّ منها حدّ الرفع.

    ⚠️ التقسيم **لا يقطع فهرس الغلاف عن صوره**: كل ملف فرعي يبني فهرسه
    الخاص من الأشخاص/الوثائق الموجودة فيه فقط (انظر `_build_one`)، فلا
    يُشير فهرسٌ إلى صفحة في ملف آخر.
    """
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


def _best_orientation(iw: float, ih: float, margin: float, header_h: float,
                      footer_h: float, gap: float):
    """يختار اتجاه الصفحة (عمودي/أفقي) الذي يُظهر هذه الصورة **أكبر
    فعلياً** — قياساً بمساحة العرض الناتجة، لا تخميناً بعتبة ثابتة.

    ⚠️ هذا هو حلّ «الفراغات»: صورة عريضة (جواز/تذكرة) على صفحة طويلة
    ثابتة تُحصَر عرضاً ويبقى نصف الارتفاع أبيض؛ نفس الصورة على صفحة
    عريضة تكاد تملأها. المقارنة تُحسَب لا تُفترَض لأن بعض الوثائق شبه
    مربعة ولا تتبع قاعدة ثابتة.
    """
    from reportlab.lib.pagesizes import A4, landscape

    best = None
    for w, h in (A4, landscape(A4)):
        avail_w = w - 2 * margin
        avail_h = h - header_h - footer_h - 2 * gap
        scale = min(avail_w / iw, avail_h / ih)
        area = (iw * scale) * (ih * scale)
        if best is None or area > best[0]:
            best = (area, (w, h), scale)
    return best[1], best[2]


def _index_rows(items: list[dict]) -> list[dict]:
    """صفّ واحد لكل شخص بترتيب أول ظهوره، وأعلام ما يملك من أنواع الوثائق.

    ⚠️ لا يعتمد على تفكيك نصّ `caption`: يُبنى من `person_label`/`doc_key`
    التركيبيَّين القادمين من `group_documents.py` — فتغيّر صياغة الوصف
    لاحقاً لا يكسر الفهرس.
    """
    order: list[str] = []
    has: dict[str, set[str]] = {}
    for it in items:
        pl = it["person_label"]
        if pl not in has:
            has[pl] = set()
            order.append(pl)
        if it["doc_key"]:
            has[pl].add(it["doc_key"])
    return [{"person_label": pl, "keys": has[pl]} for pl in order]


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

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)

    _draw_cover(c, FN, FB, items, batch_label, part, parts)

    margin = 1.0 * cm
    header_h = 1.55 * cm
    footer_h = 0.9 * cm
    gap = 0.35 * cm

    for i, it in enumerate(items, start=1):
        header_line = ar(f"{it['person_label']}  —  {it['doc_label']}")

        try:
            img = ImageReader(io.BytesIO(it["data"]))
            iw, ih = img.getSize()
        except Exception as exc:
            logger.warning(f"[arrival_docs_pdf] تعذّر رسم وثيقة {it['caption']}: {exc}")
            img, iw, ih = None, None, None

        if img is not None:
            (page_w, page_h), scale = _best_orientation(iw, ih, margin, header_h, footer_h, gap)
        else:
            page_w, page_h, scale = A4[0], A4[1], None
        c.setPageSize((page_w, page_h))

        # شريط رأس مصمَّت — لا نصّ عائم فوق فراغ: العنوان والصورة كتلة واحدة.
        c.setFillColor(colors.HexColor(_NAVY))
        c.rect(0, page_h - header_h, page_w, header_h, stroke=0, fill=1)
        c.setFont(FB, 12)
        c.setFillColor(colors.HexColor(_WHITE))
        c.drawCentredString(page_w / 2, page_h - header_h / 2 - 0.14 * cm, header_line)

        avail_w = page_w - 2 * margin
        avail_h = page_h - header_h - footer_h - 2 * gap
        top = page_h - header_h - gap

        if img is not None:
            w, h = iw * scale, ih * scale
            x = (page_w - w) / 2
            y = top - avail_h + (avail_h - h) / 2
            c.setFillColor(colors.white)
            c.setStrokeColor(colors.HexColor(_GRAY_BORDER))
            c.rect(x - 0.05 * cm, y - 0.05 * cm, w + 0.1 * cm, h + 0.1 * cm, stroke=1, fill=0)
            c.drawImage(img, x, y, width=w, height=h, preserveAspectRatio=True, anchor="c")
        else:
            c.setFont(FN, 11)
            c.setFillColor(colors.HexColor(_RED))
            c.drawCentredString(page_w / 2, top - avail_h / 2, ar("⚠️ تعذّر عرض هذه الوثيقة"))

        c.setStrokeColor(colors.HexColor(_GRAY_BORDER))
        c.line(margin, footer_h, page_w - margin, footer_h)
        c.setFont(FN, 8)
        c.setFillColor(colors.HexColor(_GRAY_TEXT))
        c.drawRightString(page_w - margin, footer_h - 0.45 * cm,
                          ar(f"{i} / {len(items)}"))
        c.drawString(margin, footer_h - 0.45 * cm, ar(batch_label))
        c.showPage()

    c.save()
    buf.seek(0)
    return buf


def _draw_cover(c, FN: str, FB: str, items: list[dict], batch_label: str,
                part: int, parts: int) -> None:
    """صفحة غلاف **مفيدة**: عنوان + فهرس (شخص × نوع وثيقة) — لا أسطر
    معلّقة فوق صفحة خالية. يتجاوز الفهرس صفحة واحدة إن كثر الأشخاص
    (`_draw_index_table` تفتح صفحات متابعة بنفسها، لا حذف صفوف)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    from services.pdf_arabic import ar

    W, H = A4
    margin = 1.4 * cm
    band_h = 2.4 * cm

    c.setFillColor(colors.HexColor(_NAVY))
    c.rect(0, H - band_h, W, band_h, stroke=0, fill=1)
    c.setFont(FB, 18)
    c.setFillColor(colors.HexColor(_WHITE))
    c.drawCentredString(W / 2, H - band_h / 2 - 0.2 * cm, ar("📎 وثائق دفعة الوصول"))

    y = H - band_h - 0.9 * cm
    c.setFont(FN, 11)
    c.setFillColor(colors.HexColor(_GRAY_TEXT))
    c.drawCentredString(W / 2, y, ar(batch_label))
    y -= 0.65 * cm
    meta = f"عدد الوثائق: {len(items)}"
    if parts > 1:
        meta += f"   ·   الجزء {part} من {parts}"
    meta += f"   ·   تاريخ الإنشاء: {date.today().isoformat()}"
    c.drawCentredString(W / 2, y, ar(meta))
    y -= 1.0 * cm

    rows = _index_rows(items)
    if rows:
        c.setFont(FB, 13)
        c.setFillColor(colors.HexColor(_NAVY))
        c.drawRightString(W - margin, y, ar("فهرس الأشخاص والوثائق"))
        y -= 0.75 * cm
        _draw_index_table(c, FN, FB, rows, margin, y)
    c.showPage()


def _draw_index_table(c, FN: str, FB: str, rows: list[dict], margin: float, y_start: float) -> None:
    """جدول فهرس بسيط، RTL: «#» فالاسم على اليمين، وأنواع الوثائق تعقبها
    يساراً. يفتح صفحات متابعة بنفسها إن لم تتّسع كل الصفوف في صفحة —
    لا صفّ يُحذَف بصمت لضيق المساحة (نفس درس تصفيح قوائم الإقامات)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    from services.pdf_arabic import ar

    W, H = A4
    row_h = 0.85 * cm
    footer_reserve = 1.2 * cm
    table_w = W - 2 * margin
    # الأعمدة visually من اليسار لليمين: أنواع الوثائق ثم الاسم ثم "#"
    # — فيكون "#" أول ما تقرؤه عين عربية تبدأ من اليمين.
    num_w = 1.0 * cm
    doc_w = (table_w - num_w) * 0.14
    name_w = table_w - num_w - doc_w * len(_DOC_TYPE_COLS)

    def _header(y_top: float) -> float:
        c.setFillColor(colors.HexColor(_NAVY))
        c.rect(margin, y_top - row_h, table_w, row_h, stroke=0, fill=1)
        c.setFont(FB, 9.5)
        c.setFillColor(colors.HexColor(_WHITE))
        x = margin + table_w
        c.drawRightString(x - 0.2 * cm, y_top - row_h / 2 - 0.12 * cm, ar("#"))
        x -= num_w
        c.drawRightString(x - 0.2 * cm, y_top - row_h / 2 - 0.12 * cm, ar("الاسم"))
        x -= name_w
        for _key, label in _DOC_TYPE_COLS:
            c.drawCentredString(x - doc_w / 2, y_top - row_h / 2 - 0.12 * cm, ar(label))
            x -= doc_w
        return y_top - row_h

    y = _header(y_start)
    n = 0
    for row in rows:
        if y - row_h < footer_reserve:
            c.showPage()
            y = H - 1.4 * cm
            c.setFont(FB, 12)
            c.setFillColor(colors.HexColor(_NAVY))
            c.drawRightString(W - margin, y, ar("فهرس الأشخاص والوثائق — تابع"))
            y -= 0.75 * cm
            y = _header(y)

        n += 1
        bg = _ROW_ALT if n % 2 == 0 else _WHITE
        c.setFillColor(colors.HexColor(bg))
        c.rect(margin, y - row_h, table_w, row_h, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor(_GRAY_BORDER))
        c.rect(margin, y - row_h, table_w, row_h, stroke=1, fill=0)

        x = margin + table_w
        c.setFont(FN, 9)
        c.setFillColor(colors.HexColor(_GRAY_TEXT))
        c.drawRightString(x - 0.2 * cm, y - row_h / 2 - 0.1 * cm, str(n))
        x -= num_w
        c.setFont(FN, 9.5)
        c.setFillColor(colors.black)
        c.drawRightString(x - 0.25 * cm, y - row_h / 2 - 0.1 * cm, ar(row["person_label"]))
        x -= name_w
        for key, _label in _DOC_TYPE_COLS:
            # ⚠️ علامة **مرسومة** لا محرف نصّي: تحقّقنا أن U+2713 (✓) غائب
            # عن الخط العربي المضمَّن — كانت سترتسم مربّعاً فارغاً بالضبط
            # كما يحدث مع الإيموجي (نفس السبب الذي جعل `ar()` تحذفه دائماً).
            # دائرة مصمَتة/مجوَّفة تُرسَم بخطوط المتّجه وحدها، بلا اعتماد
            # على تغطية أي خط.
            cx, cy = x - doc_w / 2, y - row_h / 2 - 0.05 * cm
            r = 0.14 * cm
            if key in row["keys"]:
                c.setFillColor(colors.HexColor(_NAVY))
                c.circle(cx, cy, r, stroke=0, fill=1)
            else:
                c.setStrokeColor(colors.HexColor(_GRAY_BORDER))
                c.setLineWidth(0.6)
                c.circle(cx, cy, r, stroke=1, fill=0)
            x -= doc_w
        y -= row_h


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
