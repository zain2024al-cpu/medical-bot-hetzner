# ================================================
# استعادة تقارير: Excel/CSV/JSON (أرشيف كامل) أو SQLite (مع اختيار فترة)
# ================================================
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from datetime import date, datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
from services.reports_recovery_service import (
    merge_reports_from_csv,
    merge_reports_from_excel,
    merge_reports_from_json_full,
    merge_reports_from_sqlite,
    safe_unlink,
)

logger = logging.getLogger(__name__)

(WAIT_FILE, CHOOSE_RANGE) = range(2)


def _period_presets():
    """فترات يناير/فبراير لسنة التقويم الحالية (مثال 2026)."""
    y = date.today().year
    return {
        "jan": (datetime(y, 1, 1), datetime(y, 2, 1), f"يناير {y}"),
        "feb": (datetime(y, 2, 1), datetime(y, 3, 1), f"فبراير {y}"),
        "janfeb": (datetime(y, 1, 1), datetime(y, 3, 1), f"يناير + فبراير {y}"),
    }


async def start_recovery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    user = update.effective_user
    if not user or not is_admin(user.id):
        if query:
            await query.edit_message_text("🚫 للأدمن فقط.")
        return ConversationHandler.END

    context.user_data.pop("recovery_file_path", None)
    context.user_data.pop("recovery_file_ext", None)

    text = (
        "📥 **استعادة تقارير من ملف خارجي**\n\n"
        "أرسل **ملفاً واحداً** كمستند:\n\n"
        "• **Excel** (`.xlsx`) أو **CSV** (`.csv`) أو **JSON** كامل — "
        "يُستورد **كل الصفوف** مباشرة إلى قاعدة البيانات (مناسب لأرشيف يناير/فبراير أو أي فترة).\n"
        "• أو نسخة **SQLite** (`.db` / `.sqlite`) — ثم تختار **فترة يناير / فبراير / الاثنين** "
        "حسب `report_date` أو `created_at`.\n\n"
        "⚠️ تُنشأ **صفوف جديدة** (بدون الاحتفاظ برقم id القديم). يُفضّل `/backup` قبل الاستيراد.\n\n"
        "أو اضغط إلغاء."
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ إلغاء", callback_data="recovery:cancel")]]
    )
    if query:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return WAIT_FILE


def _suffix_for_recovery(fname: str) -> Optional[str]:
    n = (fname or "").lower()
    if n.endswith(".xlsx"):
        return ".xlsx"
    if n.endswith(".csv"):
        return ".csv"
    if n.endswith(".json"):
        return ".json"
    if n.endswith(".db") or n.endswith(".sqlite"):
        return ".db"
    return None


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.document:
        await update.effective_message.reply_text(
            "⚠️ أرسل **ملفاً** كمستند (.xlsx / .csv / .json / .db)."
        )
        return WAIT_FILE

    doc = update.message.document
    fname = doc.file_name or ""
    suffix = _suffix_for_recovery(fname)
    if not suffix:
        await update.message.reply_text(
            "⚠️ المسموح: `.xlsx` أو `.csv` أو `.json` (أرشيف كامل) أو `.db` / `.sqlite`.\n"
            "ملفات `.xls` القديمة: احفظها كـ **Excel xlsx** من Excel."
        )
        return WAIT_FILE

    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    fd, tmp_path = tempfile.mkstemp(prefix="recovery_", suffix=suffix)
    os.close(fd)

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(tmp_path)
    except Exception as e:
        safe_unlink(tmp_path)
        await update.message.reply_text(f"❌ فشل تنزيل الملف: {str(e)[:200]}")
        return ConversationHandler.END

    # أرشيف كامل: استيراد فوري دون اختيار فترة
    if suffix in (".xlsx", ".csv", ".json"):
        await update.message.reply_text("⏳ جاري استيراد الأرشيف إلى قاعدة البيانات ...")

        def _run_full():
            if suffix == ".xlsx":
                return merge_reports_from_excel(tmp_path, clear_fks=True)
            if suffix == ".csv":
                return merge_reports_from_csv(tmp_path, clear_fks=True)
            return merge_reports_from_json_full(tmp_path, clear_fks=True)

        try:
            inserted, skipped, errors = await asyncio.to_thread(_run_full)
            err_tail = ""
            if errors:
                err_tail = "\n⚠️ أخطاء (أول 3):\n" + "\n".join(errors[:3])
            await update.message.reply_text(
                f"✅ **انتهى استيراد الأرشيف**\n\n"
                f"➕ **مُدرج:** {inserted}\n"
                f"⏭️ **تُجاهل (فارغ أو بدون تاريخ):** {skipped}\n"
                f"{err_tail}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.exception("recovery full import failed")
            await update.message.reply_text(f"❌ فشل الاستيراد: {str(e)[:400]}")
        finally:
            safe_unlink(tmp_path)

        return ConversationHandler.END

    # SQLite: اختيار فترة (يناير/فبراير/...)
    context.user_data["recovery_file_path"] = tmp_path
    context.user_data["recovery_file_ext"] = ".db"

    presets = _period_presets()
    jan_s, jan_e, jan_l = presets["jan"]
    feb_s, feb_e, feb_l = presets["feb"]
    both_s, both_e, both_l = presets["janfeb"]

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"📅 {jan_l}", callback_data="recovery:range:jan"),
                InlineKeyboardButton(f"📅 {feb_l}", callback_data="recovery:range:feb"),
            ],
            [InlineKeyboardButton(f"📅 {both_l}", callback_data="recovery:range:janfeb")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="recovery:cancel")],
        ]
    )

    await update.message.reply_text(
        f"✅ تم استلام ملف SQLite.\n\nاختر الفترة الزمنية لاستيراد التقارير "
        f"(حسب `report_date` أو `created_at`):\n\n"
        f"• `{jan_s.date()}` → `{jan_e.date()}` (يناير)\n"
        f"• `{feb_s.date()}` → `{feb_e.date()}` (فبراير)\n"
        f"• أو الاثنين معاً حتى `{both_e.date()}`.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN,
    )
    return CHOOSE_RANGE


async def choose_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "recovery:cancel":
        safe_unlink(context.user_data.get("recovery_file_path"))
        context.user_data.pop("recovery_file_path", None)
        await query.edit_message_text("✅ تم الإلغاء.")
        return ConversationHandler.END

    if not query.data.startswith("recovery:range:"):
        return CHOOSE_RANGE

    key = query.data.split(":")[-1]
    presets = _period_presets()
    if key == "jan":
        start, end, label = presets["jan"]
    elif key == "feb":
        start, end, label = presets["feb"]
    elif key == "janfeb":
        start, end, label = presets["janfeb"]
    else:
        await query.edit_message_text("❌ خيار غير معروف.")
        return ConversationHandler.END

    path = context.user_data.get("recovery_file_path")
    ext = context.user_data.get("recovery_file_ext")
    if not path or not os.path.isfile(path):
        await query.edit_message_text("❌ الملف غير متوفر. ابدأ من جديد.")
        return ConversationHandler.END

    await query.edit_message_text(f"⏳ جاري الاستيراد — **{label}** ...", parse_mode=ParseMode.MARKDOWN)

    try:

        def _run_sqlite():
            return merge_reports_from_sqlite(path, start, end, clear_fks=True)

        inserted, skipped, errors = await asyncio.to_thread(_run_sqlite)

        err_tail = ""
        if errors:
            err_tail = "\n⚠️ أخطاء (أول 3):\n" + "\n".join(errors[:3])

        await query.message.reply_text(
            f"✅ **انتهى الاستيراد**\n\n"
            f"📌 الفترة: {label}\n"
            f"➕ **مُدرج:** {inserted}\n"
            f"⏭️ **خارج النطاق (تُجاهل):** {skipped}\n"
            f"{err_tail}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.exception("recovery failed")
        await query.message.reply_text(f"❌ فشل الاستيراد: {str(e)[:400]}")
    finally:
        safe_unlink(path)
        context.user_data.pop("recovery_file_path", None)
        context.user_data.pop("recovery_file_ext", None)

    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    safe_unlink(context.user_data.get("recovery_file_path"))
    context.user_data.pop("recovery_file_path", None)
    context.user_data.pop("recovery_file_ext", None)
    if update.message:
        await update.message.reply_text("✅ تم الإلغاء.")
    return ConversationHandler.END


async def cancel_recovery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        safe_unlink(context.user_data.get("recovery_file_path"))
        context.user_data.pop("recovery_file_path", None)
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    return ConversationHandler.END


def register(app):
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_recovery_callback, pattern=r"^admin:reports_recovery$"),
        ],
        states={
            WAIT_FILE: [
                CallbackQueryHandler(cancel_recovery, pattern=r"^recovery:cancel$"),
                MessageHandler(filters.Document.ALL, receive_file),
            ],
            CHOOSE_RANGE: [
                CallbackQueryHandler(choose_range, pattern=r"^recovery:range:"),
                CallbackQueryHandler(cancel_recovery, pattern=r"^recovery:cancel$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_cmd),
            CallbackQueryHandler(cancel_recovery, pattern=r"^recovery:cancel$"),
        ],
        name="admin_reports_recovery",
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("تم تسجيل استعادة التقارير (admin:reports_recovery)")
