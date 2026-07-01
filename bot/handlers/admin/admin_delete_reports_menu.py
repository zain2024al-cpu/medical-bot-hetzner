# bot/handlers/admin/admin_delete_reports_menu.py
#
# قائمة حذف التقارير الموحدة
# تتيح حذف:
# - تقارير المترجمين (User Reports)
# - تقارير الرعاية الصحية (Healthcare Reports)
# - تقارير الخدمات العامة (General Services Reports)

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
    SHOW_MENU,
) = range(1)

_PFX = "del_menu"


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """Delete menu options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍⚕️ تقارير المترجمين", callback_data=f"{_PFX}:translators")],
        [InlineKeyboardButton("🏥 تقارير الرعاية الصحية", callback_data=f"{_PFX}:healthcare")],
        [InlineKeyboardButton("🛠️ تقارير الخدمات العامة", callback_data=f"{_PFX}:services")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_delete_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Show delete menu."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()

    try:
        await update.message.reply_text(
            "🗑️ *حذف التقارير*\n\n"
            "اختر نوع التقارير المراد حذفها:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Failed to show menu: {exc}")

    return SHOW_MENU


async def handle_menu_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle delete choice - delegate to appropriate handler."""
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

    # Mark which type of reports to delete
    if data == f"{_PFX}:translators":
        context.user_data["_delete_type"] = "translators"
        type_label = "تقارير المترجمين"
    elif data == f"{_PFX}:healthcare":
        context.user_data["_delete_type"] = "healthcare"
        type_label = "تقارير الرعاية الصحية"
    elif data == f"{_PFX}:services":
        context.user_data["_delete_type"] = "services"
        type_label = "تقارير الخدمات العامة"
    else:
        return SHOW_MENU

    # Show confirmation message and delegate to appropriate handler
    try:
        await query.edit_message_text(
            f"جاري تحميل {type_label}...",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

    # Delegate to the appropriate delete handler
    if context.user_data.get("_delete_type") == "translators":
        from bot.handlers.admin.admin_delete_reports import start_delete_reports as delete_translators
        await delete_translators(update, context)
    elif context.user_data.get("_delete_type") == "healthcare":
        await _delete_healthcare_reports(update, context)
    elif context.user_data.get("_delete_type") == "services":
        await _delete_services_reports(update, context)

    return ConversationHandler.END


async def _delete_healthcare_reports(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete healthcare reports."""
    query = update.callback_query
    try:
        await query.edit_message_text(
            "🏥 *حذف تقارير الرعاية الصحية*\n\n"
            "اختر السنة أولاً:",
        )
    except Exception:
        pass

    # TODO: Implement healthcare reports deletion interface
    # This will be similar to the translator reports deletion
    # but for healthcare module's report tables
    logger.info("[del_menu] Healthcare reports deletion not yet implemented")


async def _delete_services_reports(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete general services reports."""
    query = update.callback_query
    try:
        await query.edit_message_text(
            "🛠️ *حذف تقارير الخدمات العامة*\n\n"
            "اختر السنة أولاً:",
        )
    except Exception:
        pass

    # TODO: Implement general services reports deletion interface
    # This will be similar to the translator reports deletion
    # but for general services module's report tables
    logger.info("[del_menu] Services reports deletion not yet implemented")


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
    """Register delete reports menu handler."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^🗑️ حذف التقارير$"),
                start_delete_reports_menu,
            ),
        ],
        states={
            SHOW_MENU: [
                CallbackQueryHandler(handle_menu_choice, pattern=rf"^{_PFX}:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="delete_reports_menu_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(conv)
    logger.info("[del_menu] ConversationHandler registered for delete menu")
