# modules/residency/flow.py
# معالِج كولباك "rn:" + استقبال الصورة الشخصية — المرحلة الأولى فقط.

import io
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module
from shared.calendar_picker import build_calendar

from modules.residency.constants import RN
from modules.residency.repository import get_pending_profiles, get_profile_by_id
from modules.residency.models import set_reminder_date, mark_submitted, save_photo
from modules.residency.views import build_pending_list, build_profile_detail, build_photo_prompt

logger = logging.getLogger(__name__)

_MODULE_KEY = "residency"
_CTX_WAITING_PHOTO = "_rn_waiting_photo"
_CTX_ACTIVE_REMINDER = "_rn_active_reminder"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


async def _show_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, kb = build_pending_list(get_pending_profiles())
    query = update.callback_query
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, profile_id: int) -> None:
    profile = get_profile_by_id(profile_id)
    if profile is None:
        await update.callback_query.edit_message_text("❌ لم يتم العثور على الملف.")
        return
    uid = update.effective_user.id if update.effective_user else 0
    text, kb = build_profile_detail(profile, is_admin=is_admin(uid))
    await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith(f"{RN}:"):
        return
    action = data[len(RN) + 1:]
    uid = query.from_user.id if query.from_user else 0

    if not query.from_user or not _is_authorized(uid):
        logger.warning(f"[residency.cb] blocked unauthorized user={uid}  action={action!r}")
        return

    if action == "list":
        context.user_data.pop(_CTX_WAITING_PHOTO, None)
        context.user_data.pop(_CTX_ACTIVE_REMINDER, None)
        await _show_list(update, context)
        return

    if action.startswith("view_"):
        context.user_data.pop(_CTX_WAITING_PHOTO, None)
        context.user_data.pop(_CTX_ACTIVE_REMINDER, None)
        profile_id = int(action[len("view_"):])
        await _show_detail(update, context, profile_id)
        return

    if action.startswith("photo_"):
        profile_id = int(action[len("photo_"):])
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.")
            return
        context.user_data[_CTX_WAITING_PHOTO] = profile_id
        text, kb = build_photo_prompt(profile)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action.startswith("remind_"):
        profile_id = int(action[len("remind_"):])
        context.user_data[_CTX_ACTIVE_REMINDER] = profile_id
        now = datetime.utcnow()
        text, kb = build_calendar(now.year, now.month, RN, back_callback=f"{RN}:view_{profile_id}")
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action.startswith("cal_"):
        profile_id = context.user_data.get(_CTX_ACTIVE_REMINDER)
        if not profile_id:
            await _show_list(update, context)
            return
        parts = action.split(":")
        sub = parts[0]
        if sub == "cal_noop":
            return
        if sub == "cal_pick":
            y, m, d = int(parts[1]), int(parts[2]), int(parts[3])
            date_iso = f"{y:04d}-{m:02d}-{d:02d}"
            set_reminder_date(profile_id, date_iso)
            context.user_data.pop(_CTX_ACTIVE_REMINDER, None)
            await _show_detail(update, context, profile_id)
            return
        if sub in ("cal_prev", "cal_next"):
            y, m = int(parts[1]), int(parts[2])
            text, kb = build_calendar(y, m, RN, back_callback=f"{RN}:view_{profile_id}")
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        return

    if action.startswith("submit_"):
        profile_id = int(action[len("submit_"):])
        if not is_admin(uid):
            await query.answer("🚫 هذا الزر للأدمن فقط.", show_alert=True)
            return
        mark_submitted(profile_id, performed_by=uid)
        await _show_list(update, context)
        return


async def _on_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile_id = context.user_data.get(_CTX_WAITING_PHOTO)
    if not profile_id:
        return
    if not update.message or not update.message.photo:
        return

    uid = update.effective_user.id if update.effective_user else 0
    if not _is_authorized(uid):
        return

    context.user_data.pop(_CTX_WAITING_PHOTO, None)

    file_id = update.message.photo[-1].file_id
    final_file_id = file_id
    try:
        from modules.residency.photo_processing import resize_to_4x6

        tg_file = await context.bot.get_file(file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)
        resized_bytes = resize_to_4x6(buf.read())

        sent = await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=io.BytesIO(resized_bytes),
            caption="🖼️ الصورة مضبوطة على مقاس 4×6",
        )
        final_file_id = sent.photo[-1].file_id
    except Exception as exc:
        logger.warning(f"[residency] photo resize failed, saving original: {exc}")

    save_photo(profile_id, final_file_id)

    profile = get_profile_by_id(profile_id)
    text, kb = build_profile_detail(profile, is_admin=is_admin(uid))
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def register_handlers(app) -> None:
    app.add_handler(CallbackQueryHandler(_dispatch_callback, pattern=r"^rn:"), group=20)
    app.add_handler(MessageHandler(filters.PHOTO, _on_photo_message), group=17)
    logger.info("[residency] flow handlers registered (rn: callbacks group 20, photo group 17)")
