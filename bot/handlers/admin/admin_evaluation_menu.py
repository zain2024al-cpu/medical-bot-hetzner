# bot/handlers/admin/admin_evaluation_menu.py
#
# قائمة التقييم - توحيد خيارات التقييم المختلفة
# يفتح قائمة بخيارين:
# 1. تقييم المترجمين
# 2. تقرير تقييم الرعاية الصحية

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler,
    filters
)

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

# ── States ─────────────────────────────────────────────────────────────────────
(
    MENU,
) = range(1)

_PFX = "eval_menu"


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """Evaluation menu options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقييم المترجمين", callback_data=f"{_PFX}:translators")],
        [InlineKeyboardButton("📊 تقرير تقييم الرعاية الصحية", callback_data=f"{_PFX}:healthcare")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_evaluation_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Show evaluation menu."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()

    try:
        await update.message.reply_text(
            "📊 *قائمة التقييم*\n\n"
            "اختر نوع التقييم المطلوب:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[eval_menu] Failed to show menu: {exc}")

    return MENU


async def handle_menu_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle evaluation choice - delegate to appropriate handler."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    if data == f"{_PFX}:translators":
        # Delegate to translator evaluation
        # We simulate pressing the original button by calling the handler directly
        from bot.handlers.admin.admin_evaluation import start_evaluation
        await start_evaluation(update, context)
        return ConversationHandler.END

    if data == f"{_PFX}:healthcare":
        # Delegate to healthcare evaluation
        # Get the healthcare evaluation handler from modules
        try:
            from modules.healthcare.evaluation.flow import handle_callback
            await handle_callback(update, context)
        except ImportError:
            try:
                await query.edit_message_text("❌ نظام تقييم الرعاية الصحية غير متاح.")
            except Exception:
                pass
        return ConversationHandler.END

    return MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel handler."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register evaluation menu handler."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^📊 التقييم$"),
                start_evaluation_menu,
            ),
        ],
        states={
            MENU: [
                CallbackQueryHandler(handle_menu_choice, pattern=rf"^{_PFX}:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="evaluation_menu_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(conv)
    logger.info("[eval_menu] ConversationHandler registered for evaluation menu")
