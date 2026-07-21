# bot/handlers/admin/admin_patient_attachments_bundle.py
#
# "📎 كل مرفقات مريض" — زر إضافي داخل "🖨️ طباعة التقارير": يختار الأدمن
# مريضاً من قائمة الأسماء (نفس patient_selector المشترك)، فيجمع البوت كل
# مرفقاته الطبية عبر كل تقاريره/زياراته في ملف PDF واحد مرتّب (صفحة لكل
# صورة، ودمج صفحات أي مستند PDF مرفوع). المرفقات التي لا يمكن دمجها ضمن
# PDF (فيديو/صوت/مستندات غير PDF) تُرسَل بعده كل واحدة على حِدة.
#
# ✅ بدون ConversationHandler (نفس نمط admin_patient_report_v2.py) —
# result_router لالتقاط اختيار المريض من patient_selector.

from __future__ import annotations

import asyncio
import io
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from shared.selectors.patient_selector import selector as patient_selector
from shared.selectors import result_router
from shared.files.filename_builder import build_medical_pdf_filename

logger = logging.getLogger(__name__)

_RKEY_PATIENT = "admin.patient_attachments.patient"

# امتدادات الصور التي تُضَمّ كصفحات — سواء وصلت بنوع "photo" أو كـ"document".
_MERGEABLE_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

_SEND_METHOD = {
    "photo": "send_photo",
    "video": "send_video",
    "audio": "send_audio",
    "voice": "send_voice",
}
_SEND_PARAM = {
    "photo": "photo",
    "video": "video",
    "audio": "audio",
    "voice": "voice",
}


# ── Entry: عرض منتقي المرضى ─────────────────────────────────────────────────

async def show_patient_selector(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


# ── تجميع المرفقات وبناء ملف PDF واحد ────────────────────────────────────────

def _label_for(att: dict) -> str:
    d = att.get("report_date")
    date_str = d.strftime("%d/%m/%Y") if d else "—"
    dept = att.get("department") or att.get("medical_action") or "—"
    return f"{date_str} — {dept}"


def _merge_downloaded_pages(items: list[tuple[dict, bytes, bool]]) -> tuple[io.BytesIO | None, int, list[dict]]:
    """الجزء الحسابي الثقيل فقط (تحويل صور→PDF ودمج الصفحات) — دالة متزامنة
    عادية تُشغَّل داخل asyncio.to_thread حتى لا تُجمِّد حلقة أحداث البوت
    الوحيدة (وبالتالي كل المستخدمين الآخرين) طوال مدة معالجة كل الصفحات."""
    from PIL import Image
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    page_count = 0
    failed: list[dict] = []

    for att, raw, is_image in items:
        try:
            if is_image:
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                page_buf = io.BytesIO()
                img.save(page_buf, format="PDF", resolution=150.0)
                page_buf.seek(0)
                reader = PdfReader(page_buf)
            else:
                reader = PdfReader(io.BytesIO(raw))

            for page in reader.pages:
                writer.add_page(page)
            page_count += len(reader.pages)
        except Exception:
            logger.exception(f"[patient_attachments_bundle] فشل دمج مرفق id={att.get('id')}")
            failed.append(att)

    if page_count == 0:
        return None, 0, failed

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out, page_count, failed


async def _build_combined_pdf(bot, attachments: list[dict]) -> tuple[io.BytesIO | None, int, list[dict]]:
    """يحمّل كل مرفق (I/O شبكي — يبقى async) ثم يدمجها ضمن ملف PDF واحد
    (صور كصفحات + صفحات أي مستند PDF مدمجة بترتيبها) عبر خيط منفصل. يعيد
    (الملف الناتج أو None عند عدم وجود أي صفحة قابلة للدمج، عدد الصفحات،
    والمرفقات التي تعذّر تحميلها/دمجها لتُرسَل لاحقاً كل واحد منها على حِدة)."""
    downloaded: list[tuple[dict, bytes, bool]] = []
    leftovers: list[dict] = []

    for att in attachments:
        file_type = att.get("file_type")
        file_name = (att.get("file_name") or "").lower()
        is_image = file_type == "photo" or (
            file_type == "document" and file_name.endswith(_MERGEABLE_IMAGE_EXT)
        )
        is_pdf_doc = file_type == "document" and file_name.endswith(".pdf")

        if not is_image and not is_pdf_doc:
            leftovers.append(att)
            continue

        try:
            tg_file = await bot.get_file(att["file_id"])
            raw = bytes(await tg_file.download_as_bytearray())
            downloaded.append((att, raw, is_image))
        except Exception:
            logger.exception(f"[patient_attachments_bundle] فشل تحميل مرفق id={att.get('id')}")
            leftovers.append(att)

    pdf_buf, page_count, merge_failed = await asyncio.to_thread(_merge_downloaded_pages, downloaded)
    leftovers.extend(merge_failed)
    return pdf_buf, page_count, leftovers


async def _send_leftover(bot, chat_id: int, att: dict) -> None:
    file_type = att.get("file_type")
    method_name = _SEND_METHOD.get(file_type, "send_document")
    param_name = _SEND_PARAM.get(file_type, "document")
    caption = f"📎 مرفق إضافي (تعذّر دمجه) — {_label_for(att)}"
    try:
        method = getattr(bot, method_name)
        await method(chat_id=chat_id, **{param_name: att["file_id"]}, caption=caption)
    except Exception:
        logger.exception(f"[patient_attachments_bundle] فشل إرسال مرفق منفصل id={att.get('id')}")


# ── نتيجة اختيار المريض ──────────────────────────────────────────────────────

async def _on_patient_selected(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query

    if result.cancelled:
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        return

    patient_id = result.id
    patient_name = result.name

    try:
        await query.edit_message_text(
            f"⏳ جارٍ تجميع مرفقات *{patient_name}*...", parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    try:
        from services.medical_attachment_files_service import get_medical_attachment_files_for_patient

        attachments = await asyncio.to_thread(get_medical_attachment_files_for_patient, patient_id)

        if not attachments:
            try:
                await query.edit_message_text(
                    f"⚠️ لا توجد مرفقات طبية مسجَّلة للمريض *{patient_name}*.",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass
            return

        pdf_buf, page_count, leftovers = await _build_combined_pdf(context.bot, attachments)
        chat_id = update.effective_chat.id

        if pdf_buf is not None:
            filename = build_medical_pdf_filename(patient_name=patient_name, workflow_type="كل_المرفقات")
            caption = (
                f"📎 *كل المرفقات الطبية*\n"
                f"👤 {patient_name}\n"
                f"📄 {page_count} صفحة — من {len(attachments)} مرفق"
            )
            await context.bot.send_document(
                chat_id=chat_id, document=pdf_buf, filename=filename,
                caption=caption, parse_mode=ParseMode.MARKDOWN,
            )

        if leftovers:
            note = (
                f"ℹ️ يوجد {len(leftovers)} مرفق إضافي (فيديو/صوت/مستند غير قابل للدمج) "
                f"سيُرسَل بشكل منفصل بعد هذه الرسالة:"
            )
            await context.bot.send_message(chat_id=chat_id, text=note)
            for att in leftovers:
                await _send_leftover(context.bot, chat_id, att)

        if pdf_buf is None and not leftovers:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ تعذّر تجهيز أي مرفق للمريض *{patient_name}*.",
                parse_mode=ParseMode.MARKDOWN,
            )

        try:
            await query.delete_message()
        except Exception:
            pass

        logger.info(
            f"[patient_attachments_bundle] patient_id={patient_id}  "
            f"total={len(attachments)}  merged_pages={page_count}  leftovers={len(leftovers)}"
        )

    except Exception:
        logger.exception("[patient_attachments_bundle] فشل تجميع المرفقات")
        try:
            await query.edit_message_text("❌ حدث خطأ أثناء تجميع المرفقات.")
        except Exception:
            pass

    finally:
        context.user_data.clear()


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """تسجيل مسار result_router فقط — لا توجد أزرار/CallbackQueryHandler
    إضافية لهذه الميزة بعد اختيار المريض (كل شيء يتم تلقائياً)."""
    result_router.register(_RKEY_PATIENT, _on_patient_selected)
    logger.info("[patient_attachments_bundle] result_router route registered")
