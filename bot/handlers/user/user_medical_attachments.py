# ================================================
# bot/handlers/user/user_medical_attachments.py
# 📎 إضافة مرفقات طبية لتقرير منشور
# ================================================

import calendar
import io
import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from db.session import SessionLocal
from db.models import Report
from config.settings import REPORTS_GROUP_ID, MEDICAL_REPORTS_GROUP_ID
from shared.files.filename_builder import build_medical_pdf_filename

logger = logging.getLogger(__name__)



async def _photos_to_pdf(bot, photo_file_ids: list) -> io.BytesIO | None:
    """
    تحميل الصور من Telegram، تمريرها عبر pipeline التحسين، ثم تحويلها إلى PDF.
    يرجع إلى التحويل المباشر إذا فشل pipeline.
    """
    # --- تحميل الصور الخام من Telegram ---
    raw_images: list[bytes] = []
    for file_id in photo_file_ids:
        try:
            tg_file = await bot.get_file(file_id)
            buf = io.BytesIO()
            await tg_file.download_to_memory(buf)
            raw_images.append(buf.getvalue())
        except Exception as img_err:
            logger.error(f"❌ فشل تحميل صورة {file_id}: {img_err}", exc_info=True)

    if not raw_images:
        return None

    # --- محاولة تشغيل pipeline التحسين ---
    try:
        from image_pipeline import run_pipeline_async
        pdf = await run_pipeline_async(raw_images)
        logger.info(f"✅ MA: pipeline نجح  pages={len(raw_images)}")
        return pdf
    except Exception as pipeline_err:
        logger.warning(f"⚠️ MA: pipeline فشل ({pipeline_err}) — fallback to direct conversion")

    # --- Fallback: تحويل مباشر بدون تحسين ---
    return _direct_convert(raw_images)


def _direct_convert(raw_images: list[bytes]) -> io.BytesIO | None:
    """تحويل مباشر بدون أي معالجة — نفس السلوك القديم."""
    try:
        import img2pdf
        from PIL import Image as PILImage

        img_buffers = []
        for raw in raw_images:
            try:
                pil_img = PILImage.open(io.BytesIO(raw))
                pil_img.load()
                if pil_img.format == "JPEG" and pil_img.mode == "RGB":
                    img_buffers.append(raw)
                else:
                    if pil_img.mode in ("RGBA", "P", "LA"):
                        pil_img = pil_img.convert("RGB")
                    jpeg_buf = io.BytesIO()
                    pil_img.save(jpeg_buf, format="JPEG", quality=95, subsampling=0)
                    img_buffers.append(jpeg_buf.getvalue())
            except Exception:
                continue

        if not img_buffers:
            return None
        return io.BytesIO(img2pdf.convert(img_buffers))

    except Exception as e:
        logger.error(f"❌ فشل التحويل المباشر: {e}", exc_info=True)
        return None


TZ = ZoneInfo("Asia/Riyadh")
REPORTS_PER_PAGE = 8

MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}
WEEKDAYS_AR = ["سبت", "أحد", "اثن", "ثلا", "أرب", "خمي", "جمع"]


def _build_ma_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now(TZ).date()

    keyboard = []
    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"ma_cal:prev:{year}-{month:02d}"),
        InlineKeyboardButton(f"{MONTH_NAMES_AR[month]} {year}", callback_data="ma_cal:noop"),
        InlineKeyboardButton("➡️", callback_data=f"ma_cal:next:{year}-{month:02d}"),
    ])
    keyboard.append([InlineKeyboardButton(d, callback_data="ma_cal:noop") for d in WEEKDAYS_AR])

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ma_cal:noop"))
            else:
                d = date(year, month, day)
                label = f"({day})" if d == today else str(day)
                row.append(InlineKeyboardButton(label, callback_data=f"ma_cal:day:{year}-{month:02d}-{day:02d}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="ma:back_list")])
    return InlineKeyboardMarkup(keyboard)


# ─────────────────────────────────────────────
# Entry point — يُستدعى من user_inline_menu.py
# ─────────────────────────────────────────────

async def start_medical_attachments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة الدخول: عرض تقارير اليوم"""
    query = update.callback_query
    if query:
        await query.answer()

    tg_id = update.effective_user.id
    context.user_data["ma_state"] = {}          # تنظيف أي جلسة سابقة
    context.user_data["ma_state"]["tg_id"] = tg_id

    await _show_today_reports(update, context, page=0)


# ─────────────────────────────────────────────
# عرض قائمة التقارير
# ─────────────────────────────────────────────

def _today_start_end():
    now = datetime.now(TZ)
    start = datetime(now.year, now.month, now.day, tzinfo=TZ)
    end   = start + timedelta(days=1)
    # تحويل لـ naive (قاعدة البيانات تخزن naive)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def _get_reports_for_date(tg_id: int, target_date: date):
    start = datetime(target_date.year, target_date.month, target_date.day)
    end   = start + timedelta(days=1)
    with SessionLocal() as s:
        rows = (
            s.query(Report)
            .filter(
                Report.submitted_by_user_id == tg_id,
                Report.created_at >= start,
                Report.created_at < end,
            )
            .order_by(Report.created_at.desc())
            .all()
        )
        # detach
        return [
            {
                "id": r.id,
                "patient_name": r.patient_name or "—",
                "hospital_name": r.hospital_name or "—",
                "department_name": r.department or "—",
                "translator_name": r.translator_name or "—",
                "medical_action": r.medical_action or "—",
                "created_at": r.created_at,
                "group_message_id": r.group_message_id,
            }
            for r in rows
        ]


async def _show_today_reports(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    tg_id = update.effective_user.id
    today = datetime.now(TZ).date()

    ma = context.user_data.setdefault("ma_state", {})
    target_date = ma.get("target_date", today)

    reports = _get_reports_for_date(tg_id, target_date)
    ma["reports"] = reports
    ma["page"]    = page

    date_label = "اليوم" if target_date == today else target_date.strftime("%Y-%m-%d")

    if not reports:
        text = f"📎 **المرفقات الطبية**\n\nلا توجد تقارير بتاريخ {date_label}."
        keyboard = [
            [InlineKeyboardButton("📅 تاريخ آخر", callback_data="ma:pick_date")],
        ]
    else:
        text = f"📎 **المرفقات الطبية**\n\nاختر التقرير الذي تريد إضافة مرفقات له:\n📅 {date_label} — {len(reports)} تقرير"

        total_pages = (len(reports) - 1) // REPORTS_PER_PAGE + 1
        start_i = page * REPORTS_PER_PAGE
        end_i   = start_i + REPORTS_PER_PAGE
        page_reports = reports[start_i:end_i]

        keyboard = []
        for r in page_reports:
            keyboard.append([
                InlineKeyboardButton(
                    f"👤 {r['patient_name']}",
                    callback_data=f"ma:select:{r['id']}"
                )
            ])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"ma:page:{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"ma:page:{page+1}"))
        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton("📅 تاريخ آخر", callback_data="ma:pick_date")])

    markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


# ─────────────────────────────────────────────
# Callback handler الرئيسي
# ─────────────────────────────────────────────

async def handle_ma_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data  # ma:xxx

    parts = data.split(":")

    # ─── رجوع للقائمة الرئيسية ───
    if parts[1] == "back_main":
        context.user_data.pop("ma_state", None)
        from bot.keyboards import reports_submenu
        await query.edit_message_text(
            "📝 **إدارة التقارير**\n\nاختر العملية المطلوبة:",
            reply_markup=reports_submenu(),
            parse_mode="Markdown"
        )
        return

    # ─── تغيير الصفحة ───
    if parts[1] == "page":
        page = int(parts[2])
        await _show_today_reports(update, context, page=page)
        return

    # ─── اختيار تاريخ آخر ───
    if parts[1] == "pick_date":
        now = datetime.now(TZ)
        ma = context.user_data.setdefault("ma_state", {})
        ma["cal_year"]  = now.year
        ma["cal_month"] = now.month
        markup = _build_ma_calendar(now.year, now.month)
        await query.edit_message_text(
            f"📅 **اختر التاريخ**\n\n{MONTH_NAMES_AR[now.month]} {now.year}",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    # ─── العودة لقائمة التقارير ───
    if parts[1] == "back_list":
        ma = context.user_data.get("ma_state", {})
        ma.pop("awaiting_date", None)
        await _show_today_reports(update, context, page=ma.get("page", 0))
        return

    # ─── اختيار تقرير ───
    if parts[1] == "select":
        report_id = int(parts[2])
        ma = context.user_data.setdefault("ma_state", {})
        ma["report_id"]    = report_id
        ma["attachments"]  = []
        ma["awaiting_date"] = False

        # جلب بيانات التقرير
        report = _get_report_by_id(report_id)
        if not report:
            await query.edit_message_text("❌ التقرير غير موجود.")
            return

        ma["report_info"] = report
        await _show_upload_prompt(query, context, report)
        return

    # ─── الانتهاء من الرفع ───
    if parts[1] == "done":
        await _publish_attachments(query, context)
        return

    # ─── إلغاء الرفع ───
    if parts[1] == "cancel":
        context.user_data.pop("ma_state", None)
        from bot.keyboards import reports_submenu
        await query.edit_message_text(
            "❌ تم الإلغاء.",
            reply_markup=reports_submenu(),
            parse_mode="Markdown"
        )
        return


async def _show_upload_prompt(query, context, report: dict):
    name = report["patient_name"]
    hospital = report["hospital_name"]
    dept = report["department_name"]
    translator = report["translator_name"]

    text = (
        f"📎 **إضافة مرفقات طبية**\n\n"
        f"👤 **المريض:** {name}\n"
        f"🏥 **المستشفى:** {hospital}\n"
        f"🏢 **القسم:** {dept}\n"
        f"👨‍💼 **المترجم:** {translator}\n\n"
        f"أرسل الصور أو الملفات أو الفيديوهات الآن.\n"
        f"عند الانتهاء اضغط **✅ تم الانتهاء**."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تم الانتهاء", callback_data="ma:done")],
        [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="ma:back_list")],
    ])
    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception:
        await query.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


# ─────────────────────────────────────────────
# معالجة الرسائل (صور / ملفات / فيديو)
# ─────────────────────────────────────────────

async def handle_ma_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التقويم — تنقل الأشهر واختيار اليوم"""
    query = update.callback_query
    await query.answer()
    data = query.data  # ma_cal:prev/next/day/noop:...

    parts = data.split(":")
    action = parts[1]

    if action == "noop":
        return

    ma = context.user_data.setdefault("ma_state", {})

    if action in ("prev", "next"):
        ym = parts[2]  # YYYY-MM
        year, month = int(ym[:4]), int(ym[5:7])
        if action == "prev":
            month -= 1
            if month == 0:
                month, year = 12, year - 1
        else:
            month += 1
            if month == 13:
                month, year = 1, year + 1
        ma["cal_year"]  = year
        ma["cal_month"] = month
        markup = _build_ma_calendar(year, month)
        await query.edit_message_text(
            f"📅 **اختر التاريخ**\n\n{MONTH_NAMES_AR[month]} {year}",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    if action == "day":
        ymd = parts[2]  # YYYY-MM-DD
        target = datetime.strptime(ymd, "%Y-%m-%d").date()
        ma["target_date"] = target
        await _show_today_reports(update, context, page=0)
        return


async def handle_ma_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الصور والملفات والفيديوهات"""
    ma = context.user_data.get("ma_state", {})

    if not ma.get("report_id"):
        return  # لم يختر تقريراً بعد

    msg = update.message
    attachments = ma.setdefault("attachments", [])

    if msg.photo:
        file_id   = msg.photo[-1].file_id
        file_type = "photo"
    elif msg.document:
        file_id   = msg.document.file_id
        file_type = "document"
    elif msg.video:
        file_id   = msg.video.file_id
        file_type = "video"
    else:
        return

    attachments.append({"file_id": file_id, "type": file_type})
    count = len(attachments)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ تم الانتهاء ({count} مرفق)", callback_data="ma:done")],
        [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="ma:back_list")],
    ])
    await msg.reply_text(
        f"✅ تم استلام المرفق ({count} حتى الآن). أرسل المزيد أو اضغط **تم الانتهاء**.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────
# النشر للمجموعة
# ─────────────────────────────────────────────

async def _publish_attachments(query, context):
    ma = context.user_data.get("ma_state", {})
    attachments = ma.get("attachments", [])
    report      = ma.get("report_info", {})

    if not attachments:
        await query.answer("⚠️ لم ترفع أي مرفقات بعد!", show_alert=True)
        return

    bot = context.bot
    group_id = MEDICAL_REPORTS_GROUP_ID or REPORTS_GROUP_ID

    if not group_id:
        await query.edit_message_text("❌ معرف المجموعة غير مضبوط في الإعدادات.")
        return

    name       = report.get("patient_name", "—")
    hospital   = report.get("hospital_name", "—")
    dept       = report.get("department_name", "—")
    translator = report.get("translator_name", "—")
    caption    = (
        f"📎 إضافة مرفقات طبية\n"
        f"👤 {name} | 🏥 {hospital} | 🏢 {dept} | 👨‍💼 {translator}"
    )

    try:
        from telegram import InputMediaDocument, InputMediaVideo, error as tg_error

        # إذا هاجرت المجموعة إلى supergroup، نحدث الـ group_id تلقائياً
        async def _send_with_migrate(coro_factory):
            nonlocal group_id
            try:
                return await coro_factory(group_id)
            except tg_error.ChatMigrated as e:
                group_id = e.new_chat_id
                logger.warning(f"⚠️ MA: المجموعة هاجرت، الـ ID الجديد: {group_id}")
                return await coro_factory(group_id)

        # فصل الصور عن باقي الملفات
        photo_ids  = [a["file_id"] for a in attachments if a["type"] == "photo"]
        other_atts = [a for a in attachments if a["type"] != "photo"]

        # ── الصور → PDF واحد بجودة أصلية ────────────────────────────────
        if photo_ids:
            logger.info(f"📸 MA: محاولة تحويل {len(photo_ids)} صورة إلى PDF")
            pdf_buf = await _photos_to_pdf(bot, photo_ids)
            logger.info(f"📄 MA: نتيجة _photos_to_pdf = {pdf_buf}")
            if pdf_buf:
                pdf_data = pdf_buf.read()
                logger.info(f"📄 MA: حجم PDF = {len(pdf_data)} bytes")
                _pdf_filename = build_medical_pdf_filename(
                    patient_name=name,
                    departments=dept,
                )
                def _make_pdf_buf():
                    b = io.BytesIO(pdf_data)
                    b.name = _pdf_filename
                    return b
                await _send_with_migrate(
                    lambda gid: bot.send_document(chat_id=gid, document=_make_pdf_buf(), caption=caption)
                )
                logger.info(f"✅ MA: تم إرسال {len(photo_ids)} صورة كـ PDF للمجموعة")
            else:
                logger.error("❌ MA: _photos_to_pdf أعادت None — يتم إرسال صور كـ fallback")
                from telegram import InputMediaPhoto
                if len(photo_ids) == 1:
                    pid = photo_ids[0]
                    await _send_with_migrate(
                        lambda gid: bot.send_photo(chat_id=gid, photo=pid, caption=caption)
                    )
                else:
                    media_group = [
                        InputMediaPhoto(media=fid, caption=(caption if i == 0 else None))
                        for i, fid in enumerate(photo_ids)
                    ]
                    await _send_with_migrate(
                        lambda gid: bot.send_media_group(chat_id=gid, media=media_group)
                    )

        # ── الفيديوهات والملفات → ترسل كما هي ──────────────────────────
        if other_atts:
            if len(other_atts) == 1:
                att = other_atts[0]
                first_cap = caption if not photo_ids else None
                if att["type"] == "document":
                    fid = att["file_id"]
                    await _send_with_migrate(
                        lambda gid: bot.send_document(chat_id=gid, document=fid, caption=first_cap)
                    )
                elif att["type"] == "video":
                    fid = att["file_id"]
                    await _send_with_migrate(
                        lambda gid: bot.send_video(chat_id=gid, video=fid, caption=first_cap)
                    )
            else:
                media_group = []
                for i, att in enumerate(other_atts):
                    cap = (caption if (i == 0 and not photo_ids) else None)
                    if att["type"] == "document":
                        media_group.append(InputMediaDocument(media=att["file_id"], caption=cap))
                    elif att["type"] == "video":
                        media_group.append(InputMediaVideo(media=att["file_id"], caption=cap))
                if media_group:
                    await _send_with_migrate(
                        lambda gid: bot.send_media_group(chat_id=gid, media=media_group)
                    )

        logger.info(f"✅ MA: نُشرت {len(attachments)} مرفقات للتقرير {report.get('id')} في المجموعة {group_id}")

        # تحديث has_paper_report = 1 حتى تُحتسب ضمن "تقارير طبية: نعم" في التقييم
        report_id = report.get("id")
        if report_id:
            try:
                with SessionLocal() as s:
                    r = s.query(Report).filter_by(id=report_id).first()
                    if r:
                        r.has_paper_report = 1
                        s.commit()
                        logger.info(f"✅ MA: تم تحديث has_paper_report=1 للتقرير #{report_id}")
            except Exception as db_err:
                logger.warning(f"⚠️ MA: فشل تحديث has_paper_report للتقرير #{report_id}: {db_err}")

        # تنظيف الجلسة
        context.user_data.pop("ma_state", None)

        await query.edit_message_text(
            f"✅ **تم النشر بنجاح**\n\n"
            f"تم إرسال {len(attachments)} مرفق(ات) للمجموعة.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"❌ MA: فشل النشر: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ فشل النشر: {e}\n\nيرجى المحاولة مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 إعادة المحاولة", callback_data="ma:done"),
                InlineKeyboardButton("❌ إلغاء", callback_data="ma:cancel"),
            ]])
        )


# ─────────────────────────────────────────────
# DB helper
# ─────────────────────────────────────────────

def _get_report_by_id(report_id: int):
    try:
        with SessionLocal() as s:
            r = s.query(Report).filter_by(id=report_id).first()
            if not r:
                return None
            return {
                "id": r.id,
                "patient_name": r.patient_name or "—",
                "hospital_name": r.hospital_name or "—",
                "department_name": r.department or "—",
                "translator_name": r.translator_name or "—",
                "medical_action": r.medical_action or "—",
                "group_message_id": r.group_message_id,
            }
    except Exception as e:
        logger.error(f"❌ MA: خطأ في جلب التقرير {report_id}: {e}")
        return None


# ─────────────────────────────────────────────
# تسجيل الـ handlers
# ─────────────────────────────────────────────

async def _entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """entry point من زر user_action:medical_attachments أو زر النص الثابت"""
    await start_medical_attachments(update, context)


def register(app):
    # زر Inline (من القوائم الداخلية) — group=-1 لضمان الأولوية على ConversationHandlers
    app.add_handler(CallbackQueryHandler(_entry_callback, pattern=r"^user_action:medical_attachments$"), group=-1)
    # زر النص الثابت في لوحة المستخدم
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Regex(r"^📎 المرفقات الطبية$"),
        _entry_callback
    ), group=-1)
    app.add_handler(CallbackQueryHandler(handle_ma_callback,  pattern=r"^ma:"),     group=-1)
    app.add_handler(CallbackQueryHandler(handle_ma_calendar,  pattern=r"^ma_cal:"), group=-1)
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.ALL | filters.VIDEO),
            handle_ma_media
        ),
        group=5,
    )
