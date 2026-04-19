# ================================================
# لصق تقرير جاهز (نص واحد) → حفظ مباشر — للأدمن فقط (زر من /admin)
# ================================================
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.shared_auth import is_admin
from db.models import Report, _now_ist_naive
from db.session import SessionLocal
from services.paste_report_parser import (
    MAX_BULK_PASTE_REPORTS,
    merge_report_date_with_visit_time,
    parse_full_report_text,
    split_bulk_report_texts,
)
from services.paste_entity_resolve import resolve_patient_hospital_dept_ids
from services.translators_service import (
    resolve_translator_for_report,
    sync_reports_translator_ids,
    sync_reports_translator_names,
)

logger = logging.getLogger(__name__)

WAIT_PASTE = 0


async def start_paste_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    if not user or not is_admin(user.id):
        if query:
            try:
                await query.edit_message_text("🚫 هذا الإجراء **للأدمن فقط**.", parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
        elif update.message:
            await update.message.reply_text("🚫 هذا الإجراء للأدمن فقط.")
        return ConversationHandler.END

    text = (
        "📋 **إرسال تقرير جاهز (أدمن)**\n\n"
        "• **تقرير واحد:** الصق القالب كاملاً — يُحفظ مباشرة.\n"
        "• **عدة تقارير:** الصقها في **رسالة واحدة**؛ يُفصل تلقائياً عند "
        "«🆕 تقرير جديد» أو عند تكرار سطر **التاريخ:** (نفس منطق المجموعة).\n\n"
        f"حد أقصى **{MAX_BULK_PASTE_REPORTS}** تقريراً لكل رسالة.\n\n"
        "أرسل /cancel للإلغاء."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="paste_report:cancel")]])
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await query.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    return WAIT_PASTE


def _save_paste_fields_to_db(session, user, fields: dict, report_date, visit_time):
    """يُنشئ تقريراً ويُرجع الكائن بعد commit + refresh."""
    tname_raw = (fields.get("translator_name") or "").strip() or None
    if tname_raw:
        tid, tname = resolve_translator_for_report(session, tname_raw)
    else:
        sender_name = (user.full_name or user.first_name or "").strip()
        if sender_name:
            tid, tname = resolve_translator_for_report(session, sender_name)
        else:
            tid, tname = None, str(user.id)

    pid, hid, did = resolve_patient_hospital_dept_ids(
        session,
        fields.get("patient_name"),
        fields.get("hospital_name"),
        fields.get("department"),
    )

    rep = Report(
        translator_id=tid,
        translator_name=tname,
        submitted_by_user_id=user.id,
        patient_id=pid,
        hospital_id=hid,
        department_id=did,
        patient_name=fields.get("patient_name"),
        hospital_name=fields.get("hospital_name"),
        department=fields.get("department"),
        doctor_name=fields.get("doctor_name"),
        medical_action=fields.get("medical_action"),
        complaint_text=fields.get("complaint_text") or "",
        case_status=fields.get("case_status"),
        doctor_decision=fields.get("doctor_decision"),
        room_number=fields.get("room_number"),
        followup_date=fields.get("followup_date"),
        followup_reason=fields.get("followup_reason"),
        report_date=report_date,
        visit_time=visit_time,
        status="active",
        created_at=datetime.utcnow(),
    )
    session.add(rep)
    session.commit()
    session.refresh(rep)
    return rep


async def receive_pasted_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("⚠️ أرسل النص فقط (التقرير بالصيغة المطلوبة).")
        return WAIT_PASTE

    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.effective_message.reply_text("🚫 غير مصرّح.")
        return ConversationHandler.END

    raw = update.message.text.strip()
    chunks = split_bulk_report_texts(raw)
    status_msg = None
    if len(chunks) > 1:
        status_msg = await update.message.reply_text(
            f"⏳ جاري حفظ **{len(chunks)}** تقرير...",
            parse_mode=ParseMode.MARKDOWN,
        )

    saved_ids: list[int] = []
    parse_errors: list[tuple[int, str]] = []
    save_errors: list[tuple[int, str]] = []
    warn_samples: list[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        try:
            fields, warnings = parse_full_report_text(chunk)
        except ValueError as e:
            parse_errors.append((idx, str(e)[:220]))
            continue

        report_date = fields.get("report_date") or _now_ist_naive()
        visit_time = fields.get("visit_time")
        merged_dt = merge_report_date_with_visit_time(report_date, visit_time)
        if merged_dt:
            report_date = merged_dt

        session = SessionLocal()
        try:
            rep = _save_paste_fields_to_db(session, user, fields, report_date, visit_time)
            saved_ids.append(rep.id)
            if warnings:
                for w in warnings[:2]:
                    warn_samples.append(f"#{idx}: {w}")
        except Exception as e:
            session.rollback()
            logger.exception("paste_full_report save failed idx=%s", idx)
            save_errors.append((idx, str(e)[:220]))
        finally:
            session.close()

    await asyncio.to_thread(sync_reports_translator_ids)
    await asyncio.to_thread(sync_reports_translator_names)

    no_tid_count = 0
    if saved_ids:
        s2 = SessionLocal()
        try:
            no_tid_count = (
                s2.query(Report)
                .filter(Report.id.in_(saved_ids), Report.translator_id.is_(None))
                .count()
            )
        finally:
            s2.close()

    warn_link = ""
    if no_tid_count and saved_ids:
        warn_link = (
            f"\n⚠️ **{no_tid_count}** تقريراً دون ربط بمترجم في الدليل — "
            "لن تُحسب في **تقييم المترجمين** حتى تُصحّح الأسماء.\n"
        )

    lines: list[str] = []
    if saved_ids:
        lo, hi = min(saved_ids), max(saved_ids)
        if len(saved_ids) == 1:
            lines.append(f"✅ **تم حفظ التقرير** — رقم التقرير: `{lo}`")
        else:
            lines.append(f"✅ **تم حفظ {len(saved_ids)} تقريراً** — الأرقام من `{lo}` إلى `{hi}`")
    else:
        lines.append("❌ **لم يُحفظ أي تقرير.**")

    if parse_errors:
        lines.append("\n**أخطاء تحليل:**")
        for i, msg in parse_errors[:12]:
            lines.append(f"• الجزء {i}: {msg}")
        if len(parse_errors) > 12:
            lines.append(f"• … و **{len(parse_errors) - 12}** أخرى")

    if save_errors:
        lines.append("\n**أخطاء حفظ:**")
        for i, msg in save_errors[:12]:
            lines.append(f"• الجزء {i}: {msg}")
        if len(save_errors) > 12:
            lines.append(f"• … و **{len(save_errors) - 12}** أخرى")

    if warn_samples:
        lines.append("\n**عيّنة تحذيرات التحليل:**")
        lines.extend(f"• {w}" for w in warn_samples[:8])

    body = "\n".join(lines) + warn_link
    if len(body) > 3900:
        body = body[:3880] + "\n…"

    if status_msg:
        try:
            await status_msg.edit_text(body, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(body, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(body, parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END


async def cancel_paste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("✅ تم الإلغاء.")
    return ConversationHandler.END


async def cancel_paste_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    return ConversationHandler.END


def register(app):
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_paste_report, pattern=r"^admin:paste_full_report$"),
            MessageHandler(
                filters.ChatType.PRIVATE & filters.TEXT & filters.Regex(r"^📋 لصق تقرير جاهز\s*$"),
                start_paste_report,
            ),
        ],
        states={
            WAIT_PASTE: [
                CallbackQueryHandler(cancel_paste_callback, pattern=r"^paste_report:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pasted_report),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_paste),
            CallbackQueryHandler(cancel_paste_callback, pattern=r"^paste_report:cancel$"),
        ],
        name="admin_paste_full_report",
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("تم تسجيل لصق التقرير الجاهز للأدمن (admin:paste_full_report)")
