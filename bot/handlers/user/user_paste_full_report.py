# ================================================
# لصق تقرير جاهز (نص واحد) → حفظ مباشر — للأدمن فقط (زر من /admin)
# ================================================
from __future__ import annotations

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
from services.paste_report_parser import parse_full_report_text
from services.translators_service import resolve_translator_for_report

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
        "الصق الرسالة **كاملة** بنفس القالب (التاريخ، اسم المريض، المستشفى، …).\n\n"
        "بعد اللصق يُحفظ التقرير مباشرة كتقرير جديد.\n\n"
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


async def receive_pasted_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_message.reply_text("⚠️ أرسل النص فقط (التقرير بالصيغة المطلوبة).")
        return WAIT_PASTE

    user = update.effective_user
    if not user or not is_admin(user.id):
        await update.effective_message.reply_text("🚫 غير مصرّح.")
        return ConversationHandler.END

    raw = update.message.text.strip()
    try:
        fields, warnings = parse_full_report_text(raw)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\n\nجرّب مرة أخرى أو /cancel")
        return WAIT_PASTE

    report_date = fields.get("report_date") or _now_ist_naive()
    visit_time = fields.get("visit_time")

    session = SessionLocal()
    try:
        tname_raw = (fields.get("translator_name") or "").strip() or None
        if tname_raw:
            tid, tname = resolve_translator_for_report(session, tname_raw)
        else:
            sender_name = (user.full_name or user.first_name or "").strip()
            if sender_name:
                tid, tname = resolve_translator_for_report(session, sender_name)
            else:
                tid, tname = None, str(user.id)

        rep = Report(
            translator_id=tid,
            translator_name=tname,
            submitted_by_user_id=user.id,
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
        rid = rep.id
    except Exception as e:
        session.rollback()
        logger.exception("paste_full_report save failed")
        await update.message.reply_text(f"❌ فشل الحفظ: {str(e)[:350]}")
        return ConversationHandler.END
    finally:
        session.close()

    warn_txt = ""
    if warnings:
        warn_txt = "\n⚠️ " + "\n⚠️ ".join(warnings[:5])

    await update.message.reply_text(
        f"✅ **تم حفظ التقرير** — رقم التقرير: `{rid}`\n"
        f"{warn_txt}",
        parse_mode=ParseMode.MARKDOWN,
    )
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
