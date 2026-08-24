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
from datetime import date, datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.handlers.admin.decorators import require_admin
from shared.selectors.patient_selector import selector as patient_selector
from shared.selectors import result_router
from shared.files.filename_builder import build_medical_pdf_filename

logger = logging.getLogger(__name__)

# تاريخ إضافة نظام تتبع المرفقات الطبية (medical_attachment_files) — أي
# تقرير أقدم من هذا التاريخ لا يمكن أن يكون له سجل مرفق حتى لو أُرسل فعلاً
# للمجموعة وقتها، لأن جدول التتبع نفسه لم يكن موجوداً بعد.
_ATTACHMENT_TRACKING_START = date(2026, 7, 4)


def _as_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None

_RKEY_PATIENT = "admin.patient_attachments.patient"

# بادئة كولباك شاشة الفترة (شاشة جديدة بين اختيار المريض والتجميع)
_PFX = "pattach"

# مفاتيح انتقالية في user_data — لا تعيش بعد انتهاء التجميع
_CTX_PID   = "_pattach_pid"
_CTX_NAME  = "_pattach_name"
_CTX_START = "_pattach_start"   # تاريخ البداية بعد اختياره من التقويم

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
        logger.debug("تم تجاهل استثناء في show_patient_selector", exc_info=True)
    await patient_selector.enter(
        update, context, return_to=_RKEY_PATIENT,
        # ✅ نفس منطق «👤 تقرير مريض»: شاشة إخراج لا إدخال.
        include_archived=True,
    )


# ── شاشة الفترة (كل الفترة / من → إلى) ───────────────────────────────────────
# ⚠️ قبل هذه الشاشة كان اختيار المريض يبدأ التجميع فوراً لكل تاريخه الطبي،
# فمريض بعشرات الزيارات يُنتِج ملفاً ضخماً بلا وسيلة لحصره. الآن يختار
# الأدمن: كل الفترة (السلوك القديم) أو مدى محدَّد بتاريخين.

def _period_kb(patient_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 كل الفترة",
                              callback_data=f"{_PFX}:all:{patient_id}")],
        [InlineKeyboardButton("📆 من → إلى (تحديد بالتاريخ)",
                              callback_data=f"{_PFX}:custom:{patient_id}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


async def _show_period_menu(update, context, patient_id: int, patient_name: str) -> None:
    await patient_selector.respond(
        update,
        f"📎 *كل مرفقات المريض*\n"
        f"👤 {patient_name}\n\n"
        f"📅 اختر الفترة:",
        reply_markup=_period_kb(patient_id),
        parse_mode=ParseMode.MARKDOWN,
    )


def _fmt(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


async def _show_calendar(query, context, step: str, year: int, month: int,
                         patient_id: int) -> None:
    """`step` = "start" أو "end" — يحدّد عنوان الشاشة ووجهة الاختيار."""
    from shared.calendar_picker import build_calendar

    title = "📆 *تاريخ البداية*" if step == "start" else "📆 *تاريخ النهاية*"
    extra = ""
    if step == "end":
        extra = f"\n_البداية:_ {_fmt(context.user_data.get(_CTX_START))}"

    text, kb = build_calendar(
        year, month, _PFX, f"{_PFX}:custom:{patient_id}", quick_jump=True,
    )
    await query.edit_message_text(
        f"{title}{extra}\n\n{text}", reply_markup=kb, parse_mode=ParseMode.MARKDOWN,
    )


@require_admin
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """كل كولباكات `pattach:` — الفترة والتقويم."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    action = (query.data or "")[len(_PFX) + 1:]
    ud = context.user_data

    if action == "cancel":
        ud.clear()
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_callback", exc_info=True)
        return

    if action == "cal_noop":
        return

    patient_id = ud.get(_CTX_PID)
    patient_name = ud.get(_CTX_NAME) or ""

    # 🔒 تحصين ضد فقدان user_data (إعادة تشغيل البوت، أو ضغط زر قديم):
    # مُعرّف المريض مضمَّن في كولباك `all:`/`custom:` فيُستعاد منه، والاسم
    # من قاعدة البيانات. بدون هذا كان الزر يصمت بلا أي تفسير — نفس صنف
    # العطل الذي عولج في اختيار البحث inline.
    if not patient_id and ":" in action:
        try:
            patient_id = int(action.split(":")[1])
            ud[_CTX_PID] = patient_id
        except (ValueError, IndexError):
            patient_id = None
    if patient_id and not patient_name:
        from db.session import SessionLocal
        from db.models import Patient
        with SessionLocal() as _s:
            row = _s.query(Patient).filter_by(id=patient_id).first()
            patient_name = row.full_name if row else ""
        ud[_CTX_NAME] = patient_name
    if not patient_id:
        await query.edit_message_text(
            "⚠️ انتهت الجلسة. اختر المريض من جديد.",
        )
        return

    # كل الفترة — السلوك السابق تماماً (بلا أي قيد تاريخي)
    if action.startswith("all:"):
        ud.pop(_CTX_START, None)
        await _build_and_send(update, context, patient_id, patient_name,
                              None, None, "كل الفترة")
        return

    # بدء التحديد بالتاريخ: تقويم البداية
    if action.startswith("custom:"):
        ud.pop(_CTX_START, None)
        today = date.today()
        await _show_calendar(query, context, "start", today.year, today.month, patient_id)
        return

    # تنقّل التقويم — الخطوة مُستنتَجة من وجود تاريخ البداية
    if action.startswith(("cal_prev:", "cal_next:", "cal_yprev:", "cal_ynext:")):
        parts = action.split(":")
        step = "end" if ud.get(_CTX_START) else "start"
        await _show_calendar(query, context, step, int(parts[1]), int(parts[2]), patient_id)
        return

    if action.startswith(("cal_years:", "cal_yearpage:")):
        from shared.calendar_picker import build_year_picker
        text, kb = build_year_picker(int(action.split(":")[1]), _PFX,
                                     f"{_PFX}:custom:{patient_id}")
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    if action.startswith("cal_setyear:"):
        from shared.calendar_picker import build_month_picker
        text, kb = build_month_picker(int(action.split(":")[1]), _PFX,
                                      f"{_PFX}:custom:{patient_id}")
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    if action.startswith("cal_setmonth:"):
        parts = action.split(":")
        step = "end" if ud.get(_CTX_START) else "start"
        await _show_calendar(query, context, step, int(parts[1]), int(parts[2]), patient_id)
        return

    if action.startswith("cal_pick:"):
        parts = action.split(":")
        picked = date(int(parts[1]), int(parts[2]), int(parts[3]))

        if not ud.get(_CTX_START):
            ud[_CTX_START] = picked
            await _show_calendar(query, context, "end", picked.year, picked.month, patient_id)
            return

        start = ud.pop(_CTX_START)
        end = picked
        # ✅ ترتيب متسامح: لو اختار الأدمن النهاية قبل البداية تُبدَّلان بدل
        # أن يُنتِج المدى صفر نتائج بلا تفسير.
        if end < start:
            start, end = end, start
        await _build_and_send(update, context, patient_id, patient_name,
                              start, end, f"{_fmt(start)} → {_fmt(end)}")
        return


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
    # ⚠️ نفس ملاحظة admin_patient_report_v2: الاختيار من البحث inline يصل
    # عبر رسالة نصّية، فـ`update.callback_query` تكون None هنا.
    query = update.callback_query

    if result.cancelled:
        await patient_selector.respond(update, "✅ تم الإلغاء.")
        return

    patient_id = result.id
    patient_name = result.name

    # ✅ لم يعد التجميع يبدأ هنا — يمرّ أولاً بشاشة اختيار الفترة.
    context.user_data[_CTX_PID] = patient_id
    context.user_data[_CTX_NAME] = patient_name
    await _show_period_menu(update, context, patient_id, patient_name)


async def _build_and_send(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    patient_id: int, patient_name: str,
    start: date | None, end: date | None, period_label: str,
) -> None:
    """يجمّع مرفقات المريض ضمن المدى المطلوب ويرسلها.

    start/end = None ⇒ كل الفترة (السلوك السابق حرفياً، بلا أي فلترة).
    """
    query = update.callback_query

    await patient_selector.respond(
        update, f"⏳ جارٍ تجميع مرفقات *{patient_name}*...\n📅 {period_label}",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        from services.medical_attachment_files_service import (
            get_medical_attachment_files_for_patient,
            get_reports_with_paper_report_for_patient,
        )

        attachments = await asyncio.to_thread(get_medical_attachment_files_for_patient, patient_id)
        paper_reports = await asyncio.to_thread(get_reports_with_paper_report_for_patient, patient_id)

        # ✅ الفلترة بالمدى تُطبَّق على **المصدرين معاً** — لو فُلترت
        # المرفقات وحدها لأصبح تنبيه "تقارير بلا مرفق" يحصي تقارير خارج
        # الفترة المطلوبة أصلاً، فيبدو التنبيه خاطئاً.
        # المرفق بلا تاريخ يُستبعَد من المدى المحدَّد (لا يمكن التحقق منه)
        # لكنه يبقى في "كل الفترة".
        if start is not None and end is not None:
            def _within(row) -> bool:
                d = _as_date(row.get("report_date"))
                return d is not None and start <= d <= end

            attachments = [a for a in attachments if _within(a)]
            paper_reports = [r for r in paper_reports if _within(r)]

        reports_covered = {a["report_id"] for a in attachments}
        missing_reports = [r for r in paper_reports if r["report_id"] not in reports_covered]
        missing_count = len(missing_reports)

        gap_note = ""
        if missing_reports:
            missing_dates = [_as_date(r.get("report_date")) for r in missing_reports]
            before_tracking = [d for d in missing_dates if d and d < _ATTACHMENT_TRACKING_START]
            after_tracking = [d for d in missing_dates if d and d >= _ATTACHMENT_TRACKING_START]
            undated = [d for d in missing_dates if d is None]

            lines = [f"⚠️ {missing_count} تقرير مؤكَّد عليه \"يوجد تقرير طبي\" بلا أي مرفق فعلي مسجَّل:"]
            if before_tracking:
                lines.append(
                    f"• {len(before_tracking)} منها أقدم من {_ATTACHMENT_TRACKING_START} "
                    f"(تاريخ بدء تسجيل المرفقات) — طبيعي أن يكون بلا سجل، الملف أُرسل للمجموعة "
                    f"وقتها لكن نظام التسجيل نفسه لم يكن موجوداً بعد."
                )
            if after_tracking:
                lines.append(
                    f"• ⚠️ {len(after_tracking)} منها بتاريخ {_ATTACHMENT_TRACKING_START} أو بعده — "
                    f"هذا فشل فعلي وقت النشر، راجع \"📋 تقارير ناقصة المرفقات\" لمعرفة أيها بالضبط."
                )
            if undated:
                lines.append(f"• {len(undated)} منها بلا تاريخ معروف.")
            gap_note = "\n" + "\n".join(lines)

        if not attachments:
            text = (f"⚠️ لا توجد مرفقات طبية للمريض *{patient_name}*\n"
                    f"📅 ضمن: {period_label}")
            if gap_note:
                text += f"\n\n{gap_note.strip()}"
            try:
                await patient_selector.respond(update, text, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                logger.debug("تم تجاهل استثناء في _on_patient_selected", exc_info=True)
            return

        pdf_buf, page_count, leftovers = await _build_combined_pdf(context.bot, attachments)
        chat_id = update.effective_chat.id

        if pdf_buf is not None:
            filename = build_medical_pdf_filename(
                patient_name=patient_name,
                workflow_type="المرفقات" if start else "كل_المرفقات",
            )
            caption = (
                f"📎 *المرفقات الطبية*\n"
                f"👤 {patient_name}\n"
                f"📅 {period_label}\n"
                f"📄 {page_count} صفحة — من {len(attachments)} مرفق ({len(reports_covered)} تقرير)"
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

        if gap_note:
            await context.bot.send_message(
                chat_id=chat_id,
                text=gap_note.strip(),
                parse_mode=ParseMode.MARKDOWN,
            )

        try:
            if query is not None:
                await query.delete_message()
        except Exception:
            logger.debug("تم تجاهل استثناء في _on_patient_selected", exc_info=True)

        logger.info(
            f"[patient_attachments_bundle] patient_id={patient_id}  period={period_label!r}  "
            f"total={len(attachments)}  merged_pages={page_count}  leftovers={len(leftovers)}  "
            f"paper_reports={len(paper_reports)}  reports_covered={len(reports_covered)}  missing={missing_count}"
        )

    except Exception:
        logger.exception("[patient_attachments_bundle] فشل تجميع المرفقات")
        try:
            await patient_selector.respond(update, "❌ حدث خطأ أثناء تجميع المرفقات.")
        except Exception:
            logger.debug("تم تجاهل استثناء في _on_patient_selected", exc_info=True)

    finally:
        context.user_data.clear()


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """تسجيل مسار result_router فقط — لا توجد أزرار/CallbackQueryHandler
    إضافية لهذه الميزة بعد اختيار المريض (كل شيء يتم تلقائياً)."""
    result_router.register(_RKEY_PATIENT, _on_patient_selected)
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=rf"^{_PFX}:"))
    logger.info(
        "[patient_attachments_bundle] result_router route + "
        f"CallbackQueryHandler('^{_PFX}:') registered"
    )
