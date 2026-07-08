# shared/selectors/patient_selector/selector.py
# Public API for the reusable patient selector.
#
# ── How to open the selector from any module ─────────────────────────────────
#
#   from shared.selectors.patient_selector import selector as patient_selector
#   from shared.selectors.result_router import register
#
#   # 1. Register your completion handler once at startup:
#   register("mymodule.step.patient", _on_patient_selected)
#
#   # 2. Open the selector when the user needs to pick a patient:
#   await patient_selector.enter(update, context, return_to="mymodule.step.patient")
#
#   # 3. Your handler is called when the user picks or cancels:
#   async def _on_patient_selected(result: PatientSelectionResult, update, context):
#       if result.cancelled:
#           ...  # user pressed back / cancelled
#       else:
#           patient = result.patient
#           ...  # patient.id, patient.name are available
#
# ── Registration ──────────────────────────────────────────────────────────────
#
#   # Once at app startup (after all ConversationHandlers in group 0):
#   patient_selector.register_handler(app)
#
# ── Callback protocol ─────────────────────────────────────────────────────────
#
#   sel_pat:list:{page}   — show paginated list (page 0-based)
#   sel_pat:idx:{n}       — user selected patient at global index n in snapshot
#   sel_pat:back          — user cancelled; route PatientSelectionResult.cancelled_result()
#
# ── IDX snapshot protocol ─────────────────────────────────────────────────────
#   Snapshot (ordered name list) is written at render time.
#   If snapshot is missing at idx-consume time (session was cleared),
#   re-render the list rather than resolving against a stale index.
#
# ── Inline-search protocol ────────────────────────────────────────────────────
#   The "🔍 بحث" button in the patient list uses switch_inline_query_current_chat
#   so the user can search via the Telegram inline-query interface.  When the
#   user selects an inline result, Telegram sends a text message to the chat:
#       __PATIENT_SELECTED__:{patient_id}:{patient_name}
#   handle_inline_selection() (group 3 MessageHandler) receives this message,
#   checks that the patient-selector session is active, parses the patient,
#   deletes the raw marker message, and routes the result — exactly like a
#   direct button tap would do via handle_callback / _handle_selection.

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from ._data import fetch_all, lookup_by_name, PatientRecord, PatientSelectionResult
from ._session import PatientSelectorState, save as _save, load as _load, clear as _clear
from ._view import CB, build_list, build_empty, build_confirmation, build_error, build_session_lost
from shared.selectors import result_router

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

async def enter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    return_to: str,
    search_query: str = "",
    page: int = 0,
    include_pharmacy: bool = False,
) -> None:
    """
    Open the patient selector.

    return_to   — result_router key registered by the calling module
    search_query — pre-filter (usually empty on first open)
    page        — starting page (usually 0)
    include_pharmacy — True فقط لزرّي صرف الأدوية/المستلزمات الطبية:
                       يشمل مرضى "pharmacy_only" إضافةً لمرضى general.
                       الافتراضي False = مرضى general فقط (كل الشاشات الأخرى).

    Fetches patient list from DB, saves session state, and renders the
    list screen.  All further interaction is handled by handle_callback().
    """
    records = await asyncio.get_event_loop().run_in_executor(
        None, lambda: fetch_all(include_pharmacy=include_pharmacy)
    )
    names = [r.name for r in records]

    state = PatientSelectorState(
        return_to=return_to,
        page=page,
        search_query=search_query,
        include_pharmacy=include_pharmacy,
        snapshot=names,
    )
    _save(context.user_data, state)

    await _render_list(update, context, state)


# ── Callback handler ──────────────────────────────────────────────────────────

async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Dispatch sel_pat:* callback queries.
    Registered as a CallbackQueryHandler in group 1.
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

    action_part = data[len(CB) + 1:]  # strip "sel_pat:"

    # ── sel_pat:list:{page} ───────────────────────────────────────────────────
    if action_part.startswith("list:"):
        try:
            page = int(action_part.split(":", 1)[1])
        except (ValueError, IndexError):
            page = 0
        await _handle_list(update, context, page)

    # ── sel_pat:idx:{n} ───────────────────────────────────────────────────────
    elif action_part.startswith("idx:"):
        try:
            idx = int(action_part.split(":", 1)[1])
        except (ValueError, IndexError):
            await _show_error(query, "رقم الاختيار غير صالح.")
            return
        await _handle_selection(update, context, idx)

    # ── sel_pat:back ──────────────────────────────────────────────────────────
    elif action_part == "back":
        await _handle_back(update, context)

    else:
        logger.warning(f"[patient_selector] unknown action: {action_part!r}")


# ── Registration ──────────────────────────────────────────────────────────────

async def handle_inline_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Handle '__PATIENT_SELECTED__:{id}:{name}' text messages produced by the
    inline-query search when the user picks a result from the search dropdown.

    Registered in group 3 so it fires independently of the group-0 flow-text
    handlers (which already consumed the message in group 0 but silently did
    nothing because the session step is STEP_PATIENT at the time).

    Only acts when the patient selector session is active in user_data.
    Returns silently otherwise — allows the case-summary / translator
    ConversationHandlers to handle their own __PATIENT_SELECTED__ messages.
    """
    message = update.message
    if not message:
        return

    text = message.text or ""

    # Guard: only handle the inline-search protocol marker
    if not text.startswith("__PATIENT_SELECTED__:"):
        return

    # Guard: only act when our session is active (has a valid return_to)
    state = _load(context.user_data)
    if state is None or not state.return_to:
        return

    # Delete the raw marker message so it doesn't clutter the chat
    try:
        await message.delete()
    except Exception:
        pass

    # Parse  __PATIENT_SELECTED__:{id}:{name}
    try:
        parts = text.split(":", 2)
        patient_id_raw = int(parts[1]) if len(parts) > 1 else 0
        patient_name   = parts[2].strip() if len(parts) > 2 else ""
    except (ValueError, IndexError):
        logger.warning(f"[patient_selector] malformed inline selection: {text!r}")
        return

    if not patient_name or patient_name in ("خطأ", "لا يوجد"):
        logger.warning("[patient_selector] inline selection contained sentinel/error value")
        return

    # Build a PatientRecord — prefer to use the id from the message
    if patient_id_raw and patient_id_raw > 0:
        record: PatientRecord = PatientRecord(id=patient_id_raw, name=patient_name)
    else:
        # id=0 or missing — fall back to name-only DB lookup
        db_record = await asyncio.get_event_loop().run_in_executor(
            None, lookup_by_name, patient_name
        )
        record = db_record or PatientRecord(id=None, name=patient_name)

    return_to = state.return_to
    _clear(context.user_data)

    logger.info(
        f"[patient_selector] inline-selected patient={patient_name!r}"
        f" id={record.id}  return_to={return_to!r}"
    )

    await result_router.route(
        return_to,
        PatientSelectionResult.confirmed(record),
        update,
        context,
    )


def register_handler(app) -> None:
    """
    Register the sel_pat:* CallbackQueryHandler and the inline-search text
    handler with PTB.

    group 1 — CallbackQueryHandler for sel_pat:* (direct patient-button taps)
    group 3 — MessageHandler for __PATIENT_SELECTED__:* text messages produced
              when the user picks from an inline-query search result.
              Group 3 fires independently from the group-0 flow-text handlers so
              it is always reached even when a healthcare text handler also matches.

    Call once at app startup, after all ConversationHandlers are registered.
    """
    app.add_handler(
        CallbackQueryHandler(handle_callback, pattern=rf"^{CB}:"),
        group=1,
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^__PATIENT_SELECTED__:"),
            handle_inline_selection,
        ),
        group=3,
    )
    logger.info(
        f"[patient_selector] handlers registered"
        f"  callback=group:1 ('^{CB}:')  text=group:3 ('^__PATIENT_SELECTED__:')"
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _handle_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int,
) -> None:
    state = _load(context.user_data)
    if state is None:
        # Session lost (e.g. bot restart) — cannot recover return_to.
        # Show a clear "session expired" message rather than silently building
        # a broken state whose return_to="" would make patient selection a no-op.
        logger.warning("[patient_selector] session lost in _handle_list — showing session lost")
        await _show_session_lost(update.callback_query)
        return

    state.page = page
    _save(context.user_data, state)
    await _render_list(update, context, state)


async def _handle_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    idx: int,
) -> None:
    query = update.callback_query
    state = _load(context.user_data)

    # ── IDX snapshot protocol: missing session → session lost screen ─────────
    if state is None:
        # Session completely gone (bot restart / long idle).
        # Cannot recover return_to — show session-expired screen.
        logger.warning(
            "[patient_selector] session missing at idx-consume time — showing session lost"
        )
        await _show_session_lost(query)
        return

    # ── Snapshot gone but session still has return_to → safe to re-fetch ─────
    if not state.snapshot:
        logger.warning(
            "[patient_selector] snapshot empty at idx-consume time — re-fetching list"
        )
        # ✅ إعادة الجلب تحترم include_pharmacy الأصلي من الجلسة — حتى لا
        # يتسرب مريض pharmacy_only لشاشة غير مخوَّلة (أو يختفي من مخوَّلة)
        # أثناء إعادة البناء بعد فقدان الـsnapshot.
        _inc = state.include_pharmacy
        records = await asyncio.get_event_loop().run_in_executor(
            None, lambda: fetch_all(include_pharmacy=_inc)
        )
        state = PatientSelectorState(
            return_to=state.return_to,   # preserved from existing session
            page=0,
            include_pharmacy=_inc,
            snapshot=[r.name for r in records],
        )
        _save(context.user_data, state)
        await _render_list(update, context, state)
        return

    # Validate index
    if idx < 0 or idx >= len(state.snapshot):
        logger.error(
            f"[patient_selector] idx={idx} out of range (snapshot len={len(state.snapshot)})"
        )
        await _show_error(query, "الاختيار غير صالح، يرجى المحاولة مرة أخرى.")
        return

    name = state.snapshot[idx]

    # Show brief confirmation
    conf_text, conf_kb = build_confirmation(name)
    try:
        await query.edit_message_text(conf_text, reply_markup=conf_kb, parse_mode="Markdown")
    except Exception:
        pass

    # Resolve full record (with DB id) — runs in thread pool
    record: PatientRecord | None = await asyncio.get_event_loop().run_in_executor(
        None, lookup_by_name, name
    )
    if record is None:
        # Name exists in snapshot but not in DB (was deleted) — treat as name-only record
        record = PatientRecord(id=None, name=name)
        logger.warning(f"[patient_selector] name {name!r} not found in DB — using id=None")

    return_to = state.return_to
    _clear(context.user_data)

    logger.info(
        f"[patient_selector] selected patient={name!r} id={record.id}"
        f"  return_to={return_to!r}"
    )

    await result_router.route(
        return_to,
        PatientSelectionResult.confirmed(record),
        update,
        context,
    )


async def _handle_back(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    state = _load(context.user_data)
    return_to = state.return_to if state else ""
    _clear(context.user_data)

    if not return_to:
        logger.debug("[patient_selector] stale back callback with no return_to")
        await _show_session_lost(query)
        return

    logger.info(f"[patient_selector] cancelled  return_to={return_to!r}")
    await result_router.route(
        return_to,
        PatientSelectionResult.cancelled_result(),
        update,
        context,
    )


async def _render_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: PatientSelectorState,
) -> None:
    """Render the patient list screen (edit or send new message)."""
    names = state.snapshot

    if not names:
        text, kb = build_empty(state.search_query)
    else:
        text, kb = build_list(names, state.page, state.search_query)

    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.warning(f"[patient_selector] render failed ({exc}) — sending new message")
        try:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as exc2:
            logger.error(f"[patient_selector] could not send message: {exc2}")


async def _show_error(query, message: str) -> None:
    text, kb = build_error(message)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


async def _show_session_lost(query) -> None:
    text, kb = build_session_lost()
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
