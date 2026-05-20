# shared/uploads/collector.py
# Public API for the reusable upload collector engine.
#
# ── How to use from any module ────────────────────────────────────────────────
#
#   from shared.uploads import collector as uploads
#   from shared.uploads import UploadedFile, UploadResult
#   from shared.result_router import register
#
#   # 1. Register completion handler once at startup:
#   register("healthcare.wounds.images", _on_images_ready)
#
#   # 2. Open the collector from any handler:
#   await uploads.open(
#       update, context,
#       title="ارفع صور الجرح",
#       return_to="healthcare.wounds.images",
#       allowed_types=["photo"],
#       min_files=1,
#       max_files=5,
#   )
#
#   # 3. Receive result:
#   async def _on_images_ready(result: UploadResult, update, context):
#       if result.cancelled:
#           ...
#       else:
#           for f in result.files:
#               raw = await context.bot.get_file(f.file_id)
#               ...
#
# ── Registration ──────────────────────────────────────────────────────────────
#
#   # Once at app startup (after all ConversationHandlers):
#   uploads.register_handler(app)
#
# ── Handler groups ────────────────────────────────────────────────────────────
#
#   group -1  MessageHandler(PHOTO | Document.ALL) — file capture
#             Raises ApplicationHandlerStop when upload session is active,
#             so ConversationHandlers in group 0 never see upload messages.
#
#   group  1  CallbackQueryHandler(^upl:) — confirm / cancel / remove / noop
#
# ── Callback protocol ─────────────────────────────────────────────────────────
#
#   upl:confirm     — confirm collection, route UploadResult.confirmed()
#   upl:cancel      — cancel, route UploadResult.cancelled_result()
#   upl:rm:{idx}    — remove file at index idx from collection
#   upl:noop        — display-only button (counter)
#
# ── Session safety ────────────────────────────────────────────────────────────
#
#   On session loss (key missing): route cancelled_result().
#   The upload system stores only Telegram file_id references, not raw bytes,
#   so there is nothing to recover — the caller must restart the upload.

import logging
from typing import Optional

from telegram import Update, Message
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from ._models import UploadedFile, UploadResult
from ._session import UploadSession, save as _save, load as _load, clear as _clear
from ._validation import validate_incoming
from ._view import (
    CB,
    build_waiting, build_collecting, build_min_warning,
    build_session_lost, build_error,
)
from shared.result_router import route as _route

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

async def open(
    update:           Update,
    context:          ContextTypes.DEFAULT_TYPE,
    *,
    title:            str,
    return_to:        str,
    icon:             str        = "📎",
    allowed_types:    list[str]  | None = None,
    min_files:        int        = 0,
    max_files:        int        = 0,
    max_file_size_mb: int        = 0,
    preloaded_files:  list[UploadedFile] | None = None,
) -> None:
    """
    Open the upload collector screen.

    title            — Arabic screen title shown in the header
    return_to        — result_router key registered by the calling module
    icon             — emoji shown in the header (default 📎)
    allowed_types    — list of "photo", "document", "pdf", "image_document"
                       default: ["photo", "document"]
    min_files        — minimum files required to confirm (0 = no minimum)
    max_files        — maximum files allowed (0 = no limit)
    max_file_size_mb — max document size in MB (0 = no limit; photos are
                       always Telegram-compressed server-side)
    preloaded_files  — files to show as already collected (e.g. editing existing)
    """
    if allowed_types is None:
        allowed_types = ["photo", "document"]

    collected = [f.to_dict() for f in (preloaded_files or [])]
    seen_ids  = [f.file_unique_id for f in (preloaded_files or [])]

    session = UploadSession(
        return_to=        return_to,
        title=            title,
        icon=             icon,
        allowed_types=    allowed_types,
        min_files=        min_files,
        max_files=        max_files,
        max_file_size_mb= max_file_size_mb,
        collected=        collected,
        seen_unique_ids=  seen_ids,
    )

    logger.info(
        f"[uploads] open  return_to={return_to!r}  types={allowed_types}"
        f"  min={min_files}  max={max_files}  preloaded={len(collected)}"
    )

    msg = await _send_initial(update, context, session)
    if msg:
        session.ui_message_id = msg.message_id
        session.ui_chat_id    = msg.chat.id

    _save(context.user_data, session)


async def handle_message(
    update:  Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Handle incoming photo / document messages while an upload session is active.

    Registered as MessageHandler in group -1 (before ConversationHandlers).
    When the upload session is active, this handler consumes the update and
    raises ApplicationHandlerStop so group-0 ConversationHandlers never see it.
    When there is no active upload session, the function returns None and the
    update propagates normally.
    """
    from telegram.ext import ApplicationHandlerStop

    session = _load(context.user_data)
    if session is None:
        return   # no active session — let other handlers process normally

    msg = update.message
    if not msg:
        return

    # Try to extract a file from this message
    file_info = _extract_file(msg, session.allowed_types)

    if file_info is None:
        # Message matched our filter (photo/document) but doesn't fit
        # allowed_types — show a gentle rejection and stop propagation.
        try:
            await msg.reply_text("⚠️ نوع الملف غير مدعوم في هذه العملية.")
        except Exception:
            pass
        raise ApplicationHandlerStop

    uploaded_file, is_photo = file_info

    # Validate against session constraints
    error = validate_incoming(
        mime_type=       uploaded_file.mime_type,
        file_size=       uploaded_file.file_size,
        file_unique_id=  uploaded_file.file_unique_id,
        is_photo=        is_photo,
        is_document=     not is_photo,
        allowed_types=   session.allowed_types,
        max_file_size_mb=session.max_file_size_mb,
        max_files=       session.max_files,
        current_count=   session.count,
        seen_unique_ids= session.seen_unique_ids,
    )

    if error:
        if error.code != "duplicate":  # duplicate is silently discarded
            try:
                await msg.reply_text(error.message)
            except Exception:
                pass
        else:
            logger.debug(
                f"[uploads] duplicate discarded  unique_id={uploaded_file.file_unique_id!r}"
            )
        raise ApplicationHandlerStop

    # Accept the file
    session.collected.append(uploaded_file.to_dict())
    session.seen_unique_ids.append(uploaded_file.file_unique_id)
    _save(context.user_data, session)

    logger.info(
        f"[uploads] file accepted  type={'photo' if is_photo else 'document'}"
        f"  size={uploaded_file.file_size}  total={session.count}"
    )

    await _render(update, context, session)
    raise ApplicationHandlerStop   # prevent ConversationHandlers from also seeing this


async def handle_callback(
    update:  Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Dispatch upl:* callback queries.
    Registered as CallbackQueryHandler in group 1.
    """
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    if not data.startswith(f"{CB}:"):
        return

    action = data[len(CB) + 1:]   # strip "upl:"

    if action == "noop":
        return

    if action == "cancel":
        await _handle_cancel(update, context)

    elif action == "confirm":
        await _handle_confirm(update, context)

    elif action.startswith("rm:"):
        try:
            idx = int(action.split(":", 1)[1])
        except (ValueError, IndexError):
            await _show_error(query, "رقم الملف غير صالح.")
            return
        await _handle_remove(update, context, idx)

    else:
        logger.warning(f"[uploads] unknown callback action: {action!r}")


def register_handler(app) -> None:
    """
    Register upload handlers with PTB. Call once at app startup.

    group -1  MessageHandler — captures photo/document messages while session is active.
              Must be before ConversationHandlers (group 0) so it can stop propagation.

    group  1  CallbackQueryHandler — handles upl:* button presses.
              Same group as patient_selector and multiselect.
    """
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND,
            handle_message,
        ),
        group=-1,
    )
    app.add_handler(
        CallbackQueryHandler(handle_callback, pattern=rf"^{CB}:"),
        group=1,
    )
    logger.info(
        f"[uploads] handlers registered"
        f"  msg=group:-1  cb=group:1  pattern='^{CB}:'"
    )


# ── Internal handlers ─────────────────────────────────────────────────────────

async def _handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = _load(context.user_data)

    if session is None:
        text, kb = build_session_lost()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    # Enforce minimum
    if session.min_files > 0 and session.count < session.min_files:
        state_dict = _session_as_raw(session)
        text, kb   = build_min_warning(state_dict, session.collected, session.min_files)
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    files     = session.get_files()
    return_to = session.return_to
    _clear(context.user_data)

    result = UploadResult.confirmed(files)
    logger.info(
        f"[uploads] confirmed  return_to={return_to!r}  count={len(files)}"
    )
    await _route(return_to, result, update, context)


async def _handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query     = update.callback_query
    session   = _load(context.user_data)
    return_to = session.return_to if session else ""
    _clear(context.user_data)

    logger.info(f"[uploads] cancelled  return_to={return_to!r}")
    if return_to:
        await _route(return_to, UploadResult.cancelled_result(), update, context)


async def _handle_remove(
    update:  Update,
    context: ContextTypes.DEFAULT_TYPE,
    idx:     int,
) -> None:
    query   = update.callback_query
    session = _load(context.user_data)

    if session is None:
        text, kb = build_session_lost()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    if idx < 0 or idx >= len(session.collected):
        logger.error(
            f"[uploads] rm idx={idx} out of range (len={len(session.collected)})"
        )
        await _show_error(query, "لم يُعثر على الملف. يرجى المحاولة مرة أخرى.")
        return

    removed = session.collected.pop(idx)
    unique_id = removed.get("file_unique_id", "")
    if unique_id in session.seen_unique_ids:
        session.seen_unique_ids.remove(unique_id)

    _save(context.user_data, session)
    logger.debug(
        f"[uploads] removed idx={idx}  unique_id={unique_id!r}"
        f"  remaining={session.count}"
    )

    await _render(update, context, session)


# ── Render helpers ────────────────────────────────────────────────────────────

async def _send_initial(
    update:  Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UploadSession,
) -> Optional[Message]:
    """Send or edit the initial upload screen. Returns the Message for ID tracking."""
    state_dict = _session_as_raw(session)
    if session.collected:
        text, kb = build_collecting(state_dict, session.collected)
    else:
        text, kb = build_waiting(state_dict)

    try:
        if update.callback_query:
            return await update.callback_query.edit_message_text(
                text, reply_markup=kb, parse_mode="Markdown"
            )
        return await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )
    except Exception as exc:
        logger.error(f"[uploads] could not send initial screen: {exc}")
        return None


async def _render(
    update:  Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: UploadSession,
) -> None:
    """
    Update the upload UI after a state change (file added, removed, etc.).

    Prefers editing the tracked UI message (ui_message_id). Falls back to
    sending a new message and updating the stored ID.
    """
    state_dict = _session_as_raw(session)
    if session.collected:
        text, kb = build_collecting(state_dict, session.collected)
    else:
        text, kb = build_waiting(state_dict)

    # Try editing the tracked message first
    if session.ui_message_id and session.ui_chat_id:
        try:
            await context.bot.edit_message_text(
                chat_id=    session.ui_chat_id,
                message_id= session.ui_message_id,
                text=       text,
                reply_markup=kb,
                parse_mode= "Markdown",
            )
            return
        except Exception as exc:
            logger.debug(f"[uploads] edit_message_text failed ({exc}) — sending new")

    # Fallback: send a new message and update the tracked ID
    try:
        msg = await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )
        session.ui_message_id = msg.message_id
        session.ui_chat_id    = msg.chat.id
        _save(context.user_data, session)
    except Exception as exc:
        logger.error(f"[uploads] could not render upload screen: {exc}")


async def _show_error(query, message: str) -> None:
    text, kb = build_error(message)
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


# ── File extraction ───────────────────────────────────────────────────────────

def _extract_file(
    msg:           Message,
    allowed_types: list[str],
) -> Optional[tuple[UploadedFile, bool]]:
    """
    Extract an UploadedFile from a photo or document message.

    Returns (UploadedFile, is_photo) or None if the message contains no
    extractable file that *could* match the allowed_types.

    Note: type validation against allowed_types happens in validate_incoming().
    Here we extract any photo or document, then let the validator decide.
    """
    # Telegram-compressed photo — always preferred over document for photos
    if msg.photo:
        best = msg.photo[-1]   # largest available resolution
        return UploadedFile(
            file_id=        best.file_id,
            file_unique_id= best.file_unique_id,
            mime_type=      "image/jpeg",   # Telegram always delivers JPEG
            file_size=      best.file_size or 0,
            width=          best.width,
            height=         best.height,
        ), True

    # Document (PDF, image-as-file, audio, video, etc.)
    if msg.document:
        doc  = msg.document
        mime = doc.mime_type or ""
        return UploadedFile(
            file_id=        doc.file_id,
            file_unique_id= doc.file_unique_id,
            mime_type=      mime,
            file_size=      doc.file_size or 0,
            file_name=      doc.file_name or "",
        ), False

    return None


# ── Utility ───────────────────────────────────────────────────────────────────

def _session_as_raw(session: UploadSession) -> dict:
    return {
        "return_to":        session.return_to,
        "title":            session.title,
        "icon":             session.icon,
        "allowed_types":    session.allowed_types,
        "min_files":        session.min_files,
        "max_files":        session.max_files,
        "max_file_size_mb": session.max_file_size_mb,
    }
