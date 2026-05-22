# shared/multiselect/engine.py
# Public API for the reusable multi-select engine.
#
# ── How to use from any module ────────────────────────────────────────────────
#
#   from shared.multiselect import engine as multiselect
#   from shared.multiselect import Option
#   from shared.result_router import register
#
#   PROCEDURE_OPTIONS = [
#       Option(id="debridement",   label="Debridement",    icon="🩹"),
#       Option(id="dressing",      label="Dressing Change", icon="🩺"),
#       Option(id="cultures",      label="Wound Culture",   icon="🧫"),
#   ]
#
#   # 1. Register completion handler once at startup:
#   register("healthcare.procedures", _on_procedures_selected)
#
#   # 2. Open the selector in a handler:
#   await multiselect.open(
#       update, context,
#       title="اختر الإجراءات",
#       options=PROCEDURE_OPTIONS,
#       return_to="healthcare.procedures",
#       icon="🩺",
#       min_select=1,
#   )
#
#   # 3. Receive result:
#   async def _on_procedures_selected(result: MultiSelectResult, update, context):
#       if result.cancelled:
#           ...
#       else:
#           chosen_ids = result.ids   # ["debridement", "dressing"]
#
# ── Registration ──────────────────────────────────────────────────────────────
#
#   # Once at app startup (after all ConversationHandlers):
#   multiselect.register_handler(app)
#
# ── Callback protocol ─────────────────────────────────────────────────────────
#
#   msel:tog:{idx}   — toggle option at snapshot index idx
#   msel:page:{n}    — navigate to page n (0-based)
#   msel:confirm     — confirm selection
#   msel:cancel      — cancel, route MultiSelectResult.cancelled_result()
#   msel:noop        — display-only button (counter)
#
# ── IDX snapshot protocol ─────────────────────────────────────────────────────
#   Options snapshot is written at open() time and stored in session.
#   Toggle callbacks resolve against snapshot[idx].
#   If snapshot is missing (session cleared): route None — the engine cannot
#   reconstruct caller-supplied options without the original call.

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from ._models import Option, MultiSelectResult
from ._session import MultiSelectState, save as _save, load as _load, clear as _clear
from ._view import CB, build_selection, build_min_warning, build_session_lost, build_error
from shared.result_router import route as _route

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

async def open(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    title: str,
    options: list[Option],
    return_to: str,
    icon: str = "☑️",
    page: int = 0,
    min_select: int = 0,
    max_select: int = 0,
    preselected_ids: list[str] | None = None,
    auto_confirm_ids: list[str] | None = None,
) -> None:
    """
    Open the multi-select engine for the given options.

    title            — Arabic screen title shown in the header
    options          — list of Option objects (caller-supplied, becomes snapshot)
    return_to        — result_router key registered by the calling module
    icon             — emoji shown in the header (default ☑️)
    page             — starting page (0-based, usually 0)
    min_select       — minimum selections required to confirm (0 = no min)
    max_select       — maximum selections allowed (0 = no max)
    preselected_ids  — ids to mark as already selected when the screen opens
    auto_confirm_ids — option ids that, when toggled ON, immediately auto-confirm
                       the multiselect (no manual ✅ needed). Use for 'أخرى'-style
                       options that should open a text-input prompt instantly.
    """
    if not options:
        logger.warning("[multiselect] open() called with empty options — routing cancelled")
        await _route(return_to, MultiSelectResult.cancelled_result(), update, context)
        return

    snapshot = [o.to_dict() for o in options]
    state = MultiSelectState(
        return_to=return_to,
        title=title,
        icon=icon,
        options=snapshot,
        selected_ids=set(preselected_ids or []),
        page=page,
        min_select=min_select,
        max_select=max_select,
        auto_confirm_ids=frozenset(auto_confirm_ids or []),
    )
    _save(context.user_data, state)

    logger.info(
        f"[multiselect] open  return_to={return_to!r}  options={len(options)}"
        f"  min={min_select}  max={max_select}"
    )
    await _render(update, context, state)


async def handle_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Dispatch msel:* callback queries.
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

    action = data[len(CB) + 1:]   # strip "msel:"

    if action == "noop":
        return  # counter display button — do nothing

    if action == "cancel":
        await _handle_cancel(update, context)

    elif action == "confirm":
        await _handle_confirm(update, context)

    elif action.startswith("tog:"):
        try:
            idx = int(action.split(":", 1)[1])
        except (ValueError, IndexError):
            await _show_error(query, "رقم الاختيار غير صالح.")
            return
        await _handle_toggle(update, context, idx)

    elif action.startswith("page:"):
        try:
            page = int(action.split(":", 1)[1])
        except (ValueError, IndexError):
            page = 0
        await _handle_page(update, context, page)

    else:
        logger.warning(f"[multiselect] unknown action: {action!r}")


def register_handler(app) -> None:
    """
    Register the msel:* CallbackQueryHandler with PTB.
    Call once at app startup, after all ConversationHandlers.
    Group 1 avoids interference with group 0 ConversationHandlers.
    """
    app.add_handler(
        CallbackQueryHandler(handle_callback, pattern=rf"^{CB}:"),
        group=1,
    )
    logger.info(f"[multiselect] handler registered  pattern='^{CB}:'  group=1")


# ── Internal handlers ─────────────────────────────────────────────────────────

async def _handle_toggle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    idx: int,
) -> None:
    query  = update.callback_query
    state  = _load(context.user_data)

    # Session lost — cannot recover without caller-supplied options
    if state is None or not state.options:
        await _show_session_lost(query)
        await _route_cancelled(update, context, return_to="")
        return

    # Validate index against snapshot
    if idx < 0 or idx >= len(state.options):
        logger.error(
            f"[multiselect] idx={idx} out of range "
            f"(snapshot len={len(state.options)})"
        )
        await _show_error(query, "الاختيار غير صالح. يرجى المحاولة مرة أخرى.")
        return

    opt_dict = state.options[idx]
    opt_id   = opt_dict["id"]

    if opt_id in state.selected_ids:
        # Deselect
        state.selected_ids.discard(opt_id)
        logger.debug(f"[multiselect] deselected id={opt_id!r}  idx={idx}")
        _save(context.user_data, state)
        await _render(update, context, state)
    else:
        # Select — enforce max_select
        if state.max_select > 0 and len(state.selected_ids) >= state.max_select:
            try:
                await query.answer(
                    f"⚠️ الحد الأقصى {state.max_select} خيارات",
                    show_alert=False,
                )
            except Exception:
                pass
            return   # do not re-render — nothing changed
        state.selected_ids.add(opt_id)
        logger.debug(f"[multiselect] selected id={opt_id!r}  idx={idx}")

        # Auto-confirm if this option is in auto_confirm_ids
        if state.auto_confirm_ids and opt_id in state.auto_confirm_ids:
            logger.debug(f"[multiselect] auto-confirm triggered for id={opt_id!r}")
            _save(context.user_data, state)
            await _handle_confirm(update, context)
            return

        _save(context.user_data, state)
        await _render(update, context, state)


async def _handle_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int,
) -> None:
    state = _load(context.user_data)
    if state is None or not state.options:
        await _show_session_lost(update.callback_query)
        return

    state.page = page
    _save(context.user_data, state)
    await _render(update, context, state)


async def _handle_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query
    state = _load(context.user_data)

    if state is None or not state.options:
        await _show_session_lost(query)
        await _route_cancelled(update, context, return_to="")
        return

    # Enforce minimum selection
    if state.min_select > 0 and len(state.selected_ids) < state.min_select:
        try:
            await query.answer(
                f"⚠️ يجب اختيار {state.min_select} على الأقل",
                show_alert=True,
            )
        except Exception:
            pass
        # Re-render with warning prepended
        state_dict = _state_as_raw(state)
        text, kb = build_min_warning(state_dict, state.selected_ids, state.min_select)
        await _edit_or_send(query, update, text, kb)
        return

    # Build result from selected ids
    id_to_opt = {o["id"]: o for o in state.options}
    selected_options = [
        Option.from_dict(id_to_opt[sid])
        for sid in state.selected_ids
        if sid in id_to_opt
    ]
    result    = MultiSelectResult.confirmed(selected_options)
    return_to = state.return_to

    _clear(context.user_data)

    logger.info(
        f"[multiselect] confirmed  return_to={return_to!r}"
        f"  selected={[o.id for o in selected_options]}"
    )
    await _route(return_to, result, update, context)


async def _handle_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query     = update.callback_query
    state     = _load(context.user_data)
    return_to = state.return_to if state else ""
    _clear(context.user_data)

    logger.info(f"[multiselect] cancelled  return_to={return_to!r}")
    if return_to:
        await _route(return_to, MultiSelectResult.cancelled_result(), update, context)
    else:
        await _show_session_lost(query)


# ── Render helpers ────────────────────────────────────────────────────────────

async def _render(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: MultiSelectState,
) -> None:
    state_dict = _state_as_raw(state)
    text, kb   = build_selection(state_dict, state.selected_ids)
    await _edit_or_send(update.callback_query, update, text, kb)


async def _edit_or_send(query, update, text: str, kb) -> None:
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception as exc:
        logger.debug(f"[multiselect] edit_message_text failed ({exc}) — sending new")
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[multiselect] could not send message: {exc}")


async def _show_session_lost(query) -> None:
    text, kb = build_session_lost()
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


async def _show_error(query, message: str) -> None:
    text, kb = build_error(message)
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


async def _route_cancelled(update, context, return_to: str) -> None:
    if return_to:
        await _route(return_to, MultiSelectResult.cancelled_result(), update, context)


def _state_as_raw(state: MultiSelectState) -> dict:
    """Convert MultiSelectState back to a dict for the view layer."""
    return {
        "return_to":       state.return_to,
        "title":           state.title,
        "icon":            state.icon,
        "options":         state.options,
        "page":            state.page,
        "min_select":      state.min_select,
        "max_select":      state.max_select,
        "auto_confirm_ids": list(state.auto_confirm_ids),
    }
