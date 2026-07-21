# services/residency_pdf_builder.py
"""
Generates a "Patient Document Package" PDF for a residency profile.

Layout
------
  Page 1  — Patient data table
  Page 2  — Companions grid table (if any)
  Page 3  — History log (if any)
  Pages … — Document images: patient (passport / visa / residence)
             then each companion (passport / visa / residence)

WeasyPrint on Linux / Docker (production).
fpdf2 fallback on Windows (dev) — text only, no images.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = str(BASE_DIR / "templates")

# ── WeasyPrint availability ────────────────────────────────────────────────────
if sys.platform.startswith("win"):
    WEASYPRINT_AVAILABLE = False
    logger.info("[residency_pdf] Windows detected — WeasyPrint disabled, using fpdf2 fallback")
else:
    try:
        from weasyprint import HTML as _WP_HTML
        WEASYPRINT_AVAILABLE = True
    except Exception as e:
        # ✅ Exception كاملة وليس ImportError فقط — نقص مكتبة نظام (libpango)
        # يرمي OSError، وكان يتسرّب ويُسقط استيراد الوحدة.
        WEASYPRINT_AVAILABLE = False
        _WP_HTML = None
        logger.warning(f"[residency_pdf] WeasyPrint not available ({type(e).__name__}: {e})")


# ── Display helpers ────────────────────────────────────────────────────────────

def _fmt_date(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return s or "—"


def _days_remaining(s: str | None) -> str:
    if not s:
        return "—"
    try:
        d    = datetime.strptime(s[:10], "%Y-%m-%d").date()
        diff = (d - date.today()).days
        if diff < 0:
            return f"منتهية منذ {abs(diff)} يوم"
        if diff == 0:
            return "تنتهي اليوم"
        return f"{diff} يوم"
    except Exception:
        return "—"


def _status_label(s: str | None) -> str:
    mapping = {
        "active":            "نشطة",
        "expiring":          "قريبة الانتهاء",
        "renewal_submitted": "تم التقديم",
        "issued":            "تم الإصدار",
        "dependent_pending": "مرافق معلق",
        "expired":           "منتهية",
    }
    return mapping.get(s or "", s or "—")


# ── Telegram image download ────────────────────────────────────────────────────

async def _download_data_uri(bot, file_id: str) -> str | None:
    """
    Download a Telegram file and return a data URI string
    (e.g. "data:image/jpeg;base64,…") or None on failure.
    """
    if not file_id:
        return None
    try:
        tg_file = await bot.get_file(file_id)
        buf     = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)
        raw   = buf.read()
        # Detect image format from magic bytes
        mime  = "image/png" if raw[:4] == b"\x89PNG" else "image/jpeg"
        b64   = base64.b64encode(raw).decode()
        return f"data:{mime};base64,{b64}"
    except Exception as exc:
        logger.warning(f"[residency_pdf] image download failed  file_id={file_id!r}: {exc}")
        return None


async def _collect_images(bot, profile, companions: list) -> dict[str, str | None]:
    """
    Concurrently download all document images.
    Keys: "p_passport", "p_visa", "p_residence",
          "c_{id}_passport", "c_{id}_visa", "c_{id}_residence"
    Values: data URI strings or None.
    """
    keys:  list[str]   = []
    coros: list        = []

    # Patient documents
    keys.append("p_passport");  coros.append(_download_data_uri(bot, profile.passport_file_id or ""))
    keys.append("p_visa");       coros.append(_download_data_uri(bot, profile.visa_file_id or ""))
    keys.append("p_residence");  coros.append(_download_data_uri(bot, profile.latest_residency_file_id or ""))

    # Companion documents
    for c in companions:
        keys.append(f"c_{c.id}_passport");  coros.append(_download_data_uri(bot, c.passport_file_id or ""))
        keys.append(f"c_{c.id}_visa");       coros.append(_download_data_uri(bot, c.visa_file_id or ""))
        keys.append(f"c_{c.id}_residence");  coros.append(_download_data_uri(bot, c.latest_residency_file_id or ""))

    results = await asyncio.gather(*coros, return_exceptions=True)
    images: dict[str, str | None] = {}
    for k, r in zip(keys, results):
        images[k] = r if isinstance(r, str) else None

    logger.debug(f"[residency_pdf] images collected: {sum(v is not None for v in images.values())}/{len(images)}")
    return images


# ── HTML rendering ─────────────────────────────────────────────────────────────

def _build_context(profile, companions: list, history: list, images: dict) -> dict:
    p_data = {
        "name":             profile.name or "—",
        "residency_number": profile.residency_number or "—",
        "status":           _status_label(profile.status),
        "expiry_date":      _fmt_date(profile.expiry_date),
        "days_remaining":   _days_remaining(profile.expiry_date),
        "comp_count":       len(companions),
        "notes":            profile.notes or "",
    }

    c_list = []
    for c in companions:
        c_list.append({
            "id":               c.id,
            "name":             c.name or "—",
            "residency_number": c.residency_number or "—",
            "status":           _status_label(c.status),
            "expiry_date":      _fmt_date(c.expiry_date),
            "days_remaining":   _days_remaining(c.expiry_date),
        })

    h_list = []
    for h in history:
        date_part = (h.created_at or "")[:10]
        comp_tag  = " (مرافق)" if h.companion_id else ""
        h_list.append({
            "label": f"{h.action_label}{comp_tag}",
            "date":  date_part,
        })

    return {
        "profile":      p_data,
        "companions":   c_list,
        "history":      h_list,
        "images":       images,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _render_html(profile, companions: list, history: list, images: dict) -> str:
    env      = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("residency_patient_package.html")
    ctx      = _build_context(profile, companions, history, images)
    return template.render(**ctx)


# ── WeasyPrint (Linux / production) ───────────────────────────────────────────

def _weasyprint_to_pdf(html: str) -> bytes:
    return _WP_HTML(string=html, base_url=TEMPLATE_DIR).write_pdf()


# ── fpdf2 fallback (Windows / dev) ────────────────────────────────────────────

def _fpdf2_fallback(profile, companions: list, history: list) -> bytes:
    """
    Text-only PDF via fpdf2 + arabic_reshaper.
    Images are omitted in this mode.
    """
    from fpdf import FPDF
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        def ar(text: str) -> str:
            return get_display(arabic_reshaper.reshape(str(text)))
    except ImportError:
        def ar(text: str) -> str:  # type: ignore[misc]
            return str(text)

    # Try to find a Unicode font that supports Arabic on Windows
    font_candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]
    font_path: str | None = None
    for fp in font_candidates:
        if Path(fp).exists():
            font_path = fp
            break

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()

    if font_path:
        pdf.add_font("ArabicFont", "", font_path, uni=True)
        main_font = "ArabicFont"
    else:
        main_font = "Helvetica"

    # ── Page 1: Patient data ──────────────────────────────────────────────────
    pdf.set_font(main_font, size=15)
    pdf.cell(0, 10, ar("ملف إقامة المريض"), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font(main_font, size=10)
    rows = [
        ("الاسم",             profile.name or "—"),
        ("رقم الإقامة",       profile.residency_number or "—"),
        ("الحالة",            _status_label(profile.status)),
        ("تاريخ الانتهاء",   _fmt_date(profile.expiry_date)),
        ("الأيام المتبقية",  _days_remaining(profile.expiry_date)),
        ("عدد المرافقين",    str(len(companions))),
    ]
    for label, value in rows:
        pdf.set_fill_color(244, 246, 249)
        pdf.cell(60, 8, ar(value), align="R", border=1)
        pdf.cell(60, 8, ar(label), align="R", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    # ── Page 2: Companions ───────────────────────────────────────────────────
    if companions:
        pdf.add_page()
        pdf.set_font(main_font, size=14)
        pdf.cell(0, 10, ar(f"المرافقون ({len(companions)})"), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font(main_font, size=9)
        # Header
        headers = ["الحالة", "الأيام المتبقية", "تاريخ الانتهاء", "رقم الإقامة", "الاسم"]
        col_w   = [28, 30, 30, 34, 52]
        pdf.set_fill_color(26, 58, 92)
        pdf.set_text_color(255, 255, 255)
        for h_text, w in zip(headers, col_w):
            pdf.cell(w, 8, ar(h_text), align="C", border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        for i, c in enumerate(companions):
            pdf.set_fill_color(248, 249, 252) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            vals = [
                _status_label(c.status),
                _days_remaining(c.expiry_date),
                _fmt_date(c.expiry_date),
                c.residency_number or "—",
                c.name or "—",
            ]
            for val, w in zip(vals, col_w):
                pdf.cell(w, 7, ar(val), align="R", border=1, fill=True)
            pdf.ln()

    # ── Page 3: History ──────────────────────────────────────────────────────
    if history:
        pdf.add_page()
        pdf.set_font(main_font, size=14)
        pdf.cell(0, 10, ar("سجل الأحداث"), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_font(main_font, size=9)
        pdf.set_fill_color(26, 58, 92)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(35, 8, ar("التاريخ"), align="C", border=1, fill=True)
        pdf.cell(139, 8, ar("الحدث"), align="C", border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        for i, h in enumerate(history):
            comp_tag  = " (مرافق)" if h.companion_id else ""
            label_txt = f"{h.action_label}{comp_tag}"
            date_txt  = (h.created_at or "")[:10]
            pdf.set_fill_color(248, 249, 252) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(35,  7, ar(date_txt),  align="C", border=1, fill=True)
            pdf.cell(139, 7, ar(label_txt), align="R", border=1, fill=True)
            pdf.ln()

    pdf.set_y(-25)
    pdf.set_font(main_font, size=8)
    pdf.set_text_color(150, 150, 150)
    note = ar("* الوثائق (صور الجوازات والتأشيرات) غير متاحة في وضع Windows — استخدم بيئة Linux للحصول على الملف الكامل.")
    pdf.multi_cell(0, 5, note, align="R")

    return bytes(pdf.output())


# ── Public API ─────────────────────────────────────────────────────────────────

async def build_residency_pdf(
    *,
    bot,
    profile,
    companions: list,
    history:    list,
) -> bytes:
    """
    Build a full PDF document package for the given residency profile.

    - Downloads all Telegram document images concurrently (Linux path only).
    - Renders the Jinja2 HTML template.
    - Converts to PDF bytes via WeasyPrint (Linux) or fpdf2 (Windows).

    Returns raw PDF bytes.
    """
    if WEASYPRINT_AVAILABLE:
        images    = await _collect_images(bot, profile, companions)
        html      = _render_html(profile, companions, history, images)
        loop      = asyncio.get_running_loop()
        pdf_bytes = await loop.run_in_executor(None, _weasyprint_to_pdf, html)
        logger.info(
            f"[residency_pdf] WeasyPrint OK"
            f"  profile_id={profile.id}  size={len(pdf_bytes):,} bytes"
        )
    else:
        loop      = asyncio.get_running_loop()
        pdf_bytes = await loop.run_in_executor(
            None, _fpdf2_fallback, profile, companions, history
        )
        logger.info(
            f"[residency_pdf] fpdf2 fallback OK"
            f"  profile_id={profile.id}  size={len(pdf_bytes):,} bytes"
        )

    return pdf_bytes
