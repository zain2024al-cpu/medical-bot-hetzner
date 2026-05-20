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
#   async def _on_patient_selected(patient: PatientRecord | None, update, context):
#       if patient is None:
#           ...  # user pressed back / cancelled
#       else:
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
#   sel_pat:back          — user cancelled; route None to the caller
#
# ── IDX snapshot protocol ─────────────────────────────────────────────────────
#   Snapshot (ordered name list) is written at render time.
#   If snapshot is missing at idx-consume time (session was cleared),
#   re-render the list rather than resolving against a stale index.

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from ._data import fetch_all, lookup_by_name, PatientRecord
from ._session import PatientSelectorState, save as _save, load as _load, clear as _clear
from ._view import CB, build_list, build_empty, build_confirmation, build_error
from shared.selectors import result_router

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

async def enter(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    return_to: str,
    search_query: str = "",
    page: int = 0,
) -> None:
    """
    Open the patient selector.

    return_to   — result_router key registered by the calling module
    search_query — pre-filter (usually empty on first open)
    page        — starting page (usually 0)

    Fetches patient list from DB, saves session state, and renders the
    list screen.  All further interaction is handled by handle_callback().
    """
    records = await asyncio.get_event_loop().run_in_executor(
        None, fetch_all
    )
    names = [r.name for r in records]

    state = PatientSelectorState(
        return_to=return_to,
        page=page,
        search_query=search_query,
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
    Registered as a CallbackQueryHandler in group 0.
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

def register_handler(app) -> None:
    """
    Register the sel_pat:* CallbackQueryHandler with PTB.

    Call once at app startup, after all ConversationHandlers are registered.
    Group 1 is used so ConversationHandlers in group 0 are not interfered with.
    """
    app.add_handler(
        CallbackQueryHandler(handle_callback, pattern=rf"^{CB}:"),
        group=1,
    )
    logger.info(f"[patient_selector] handler registered  pattern='^{CB}:'  group=1")


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _handle_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int,
) -> None:
    state = _load(context.user_data)
    if state is None:
        # Session lost — re-open from scratch with no return_to context
        logger.warning("[patient_selector] session lost in _handle_list — re-fetching")
        records = await asyncio.get_event_loop().run_in_executor(None, fetch_all)
        state = PatientSelectorState(
            return_to="",
            page=page,
            snapshot=[r.name for r in records],
        )
        _save(context.user_data, state)

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

    # ── IDX snapshot protocol: missing snapshot → re-render, never resolve ────
    if state is None or not state.snapshot:
        logger.warning(
            "[patient_selector] snapshot missing at idx-consume time — re-rendering list"
        )
        records = await asyncio.get_event_loop().run_in_executor(None, fetch_all)
        state = PatientSelectorState(
            return_to=state.return_to if state else "",
            page=0,
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

    await result_router.route(return_to, record, update, context)


async def _handle_back(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    state = _load(context.user_data)
    return_to = state.return_to if state else ""
    _clear(context.user_data)

    logger.info(f"[patient_selector] cancelled  return_to={return_to!r}")
    await result_router.route(return_to, None, update, context)


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
