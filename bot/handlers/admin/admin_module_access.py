# bot/handlers/admin/admin_module_access.py
# Admin-only tools for activating / deactivating platform modules per user.
#
# Callback prefix: "amod"
# Patterns:
#   amod:list:<tg_user_id>               — show module list for a user
#   amod:grant:<tg_user_id>:<module_key> — grant a module
#   amod:revoke:<tg_user_id>:<module_key>— revoke a module

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

CB = "amod"


# ── Keyboard builders ─────────────────────────────────────────────────────────

def _module_list_kb(tg_user_id: int, active_modules: list[str]) -> InlineKeyboardMarkup:
    """Toggle keyboard: one row per registered module + back button."""
    from core.routing.registry import registry

    rows: list[list[InlineKeyboardButton]] = []
    for mod in registry.all_modules():
        is_active = mod in active_modules
        icon = "✅" if is_active else "❌"
        action = "revoke" if is_active else "grant"
        rows.append([
            InlineKeyboardButton(
                f"{icon} {mod}",
                callback_data=f"{CB}:{action}:{tg_user_id}:{mod}",
            )
        ])

    # Back button goes to admin_users_management user-detail view.
    # admin_users_management uses DB row id in its callbacks, but here we only
    # have tg_user_id — so we route back to the home screen instead.
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="aum:home")])
    return InlineKeyboardMarkup(rows)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def show_user_modules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    amod:list:<tg_user_id>
    Display module activation status for a user with toggle buttons.
    """
    query = update.callback_query
    if not query:
        return

    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer("🚫 غير مسموح", show_alert=True)
        return

    await query.answer()

    try:
        parts = query.data.split(":")
        # amod:list:<tg_user_id>
        tg_user_id = int(parts[2])
    except (IndexError, ValueError):
        await query.answer("⚠️ بيانات غير صحيحة", show_alert=True)
        return

    from core.access.access_service import get_user_modules
    active = get_user_modules(tg_user_id)

    text = (
        f"🔑 *إدارة الوصول*\n\n"
        f"المستخدم: `{tg_user_id}`\n"
        f"الوحدات النشطة: {len(active)}\n\n"
        f"اضغط على وحدة لتفعيلها أو إلغاء تفعيلها:"
    )
    try:
        await query.edit_message_text(
            text,
            reply_markup=_module_list_kb(tg_user_id, active),
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.warning(f"show_user_modules edit failed: {exc}")


async def handle_module_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    amod:grant:<tg_user_id>:<module_key>
    amod:revoke:<tg_user_id>:<module_key>
    Grant or revoke a module, then refresh the module list view.
    """
    query = update.callback_query
    if not query:
        return

    user = update.effective_user
    if not user or not is_admin(user.id):
        await query.answer("🚫 غير مسموح", show_alert=True)
        return

    try:
        parts = query.data.split(":")
        action = parts[1]          # "grant" or "revoke"
        tg_user_id = int(parts[2])
        module_key = parts[3]
    except (IndexError, ValueError):
        await query.answer("⚠️ بيانات غير صحيحة", show_alert=True)
        return

    from core.access.access_service import grant_module, revoke_module, get_user_modules

    admin_id = user.id
    if action == "grant":
        changed = grant_module(tg_user_id, module_key, granted_by=admin_id)
        msg = f"✅ تم تفعيل '{module_key}'" if changed else f"ℹ️ '{module_key}' نشط بالفعل"
    elif action == "revoke":
        changed = revoke_module(tg_user_id, module_key, revoked_by=admin_id)
        msg = f"❌ تم إلغاء '{module_key}'" if changed else f"ℹ️ '{module_key}' غير نشط أصلاً"
    else:
        await query.answer("⚠️ إجراء غير معروف", show_alert=True)
        return

    await query.answer(msg, show_alert=False)

    # Refresh the module list
    active = get_user_modules(tg_user_id)
    text = (
        f"🔑 *إدارة الوصول*\n\n"
        f"المستخدم: `{tg_user_id}`\n"
        f"الوحدات النشطة: {len(active)}\n\n"
        f"اضغط على وحدة لتفعيلها أو إلغاء تفعيلها:"
    )
    try:
        await query.edit_message_text(
            text,
            reply_markup=_module_list_kb(tg_user_id, active),
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.warning(f"handle_module_toggle refresh failed: {exc}")


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    app.add_handler(
        CallbackQueryHandler(show_user_modules, pattern=rf"^{CB}:list:"),
        group=1,
    )
    app.add_handler(
        CallbackQueryHandler(handle_module_toggle, pattern=rf"^{CB}:(grant|revoke):"),
        group=1,
    )
    logger.info("[admin_module_access] registered")
