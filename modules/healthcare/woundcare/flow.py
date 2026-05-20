# modules/healthcare/woundcare/flow.py
# Woundcare "Add Record" flow orchestrator.
#
# ── Flow overview ─────────────────────────────────────────────────────────────
#
#   1. Callback wca:start
#          └─ patient_selector.enter()         return_to="hc.woundcare.patient"
#
#   2. result_router → _on_patient()
#          └─ multiselect.open(WOUND_TYPES)    return_to="hc.woundcare.wound_type"
#
#   3. result_router → _on_wound_type()
#          └─ uploads.open(photos)             return_to="hc.woundcare.images"
#
#   4. result_router → _on_images()
#          └─ send notes prompt (inline keyboard: skip / cancel)
#             session.step = STEP_NOTES
#
#   5. MessageHandler (text, group 0) → _handle_notes_text()
#      OR Callback wca:skip_notes → _handle_skip_notes()
#          └─ show review screen
#             session.step = STEP_REVIEW
#
#   6. Callback wca:confirm → _handle_confirm()
#          └─ save_wound_record() → success screen
#
#   Any step: wca:cancel / result.cancelled → _cancel()
#   Any step: wca:edit_notes → re-enter notes step
#
# ── Handler groups ────────────────────────────────────────────────────────────
#
#   group  0  MessageHandler(TEXT, ~COMMAND) — notes text capture
#             Only acts when session.step == STEP_NOTES; otherwise no-op.
#
#   group  1  CallbackQueryHandler(^wca:|^hc:) — all inline button actions

import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from shared.multiselect import Option
from shared.result_router import register as _register_route
from shared.selectors.patient_selector import selector as patient_selector
from shared.multiselect import engine as multiselect
from shared.uploads import collector as uploads

from modules.healthcare.woundcare.session import (
    WoundcareAddSession,
    STEP_PATIENT, STEP_WOUND_TYPE, STEP_IMAGES, STEP_NOTES, STEP_REVIEW,
)
from modules.healthcare.woundcare.views import (
    HC, WCA,
    build_healthcare_menu, build_woundcare_menu,
    build_notes_prompt, build_review,
    build_success, build_cancelled, build_error,
)
from modules.healthcare.woundcare.models import save_wound_record

logger = logging.getLogger(__name__)


# ── Wound type catalogue ──────────────────────────────────────────────────────

WOUND_TYPE_OPTIONS: list[Option] = [
    Option(id="pressure",  label="جرح ضغط",        icon="🔴"),
    Option(id="diabetic",  label="جرح سكري",        icon="🟡"),
    Option(id="surgical",  label="جرح جراحي",       icon="🔧"),
    Option(id="burn",      label="حرق",             icon="🔥"),
    Option(id="traumatic", label="جرح رضحي",        icon="⚡"),
    Option(id="venous",    label="قرحة وريدية",      icon="💙"),
    Option(id="arterial",  label="قرحة شريانية",     icon="❤️"),
    Option(id="chronic",   label="جرح مزمن",        icon="⏳"),
]

_RKEY_PATIENT    = "hc.woundcare.patient"
_RKEY_WOUND_TYPE = "hc.woundcare.wound_type"
_RKEY_IMAGES     = "hc.woundcare.images"


# ── Step 1: start ─────────────────────────────────────────────────────────────

async def _start_add_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called from wca:start callback. Creates session and opens patient selector."""
    WoundcareAddSession.create(context.user_data)
    logger.info(
        f"[woundcare] add flow started  user={update.effective_user.id}"
    )
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


# ── Step 2: patient selected ──────────────────────────────────────────────────

async def _on_patient(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """result_router callback: patient selector completed."""
    if result is None or getattr(result, "cancelled", False):
        await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        session = WoundcareAddSession.create(context.user_data)

    patient = result.patient if hasattr(result, "patient") else result
    session.patient_id   = patient.id   if patient else None
    session.patient_name = patient.name if patient else ""
    session.step         = STEP_WOUND_TYPE
    session.save(context.user_data)

    logger.info(
        f"[woundcare] patient selected: {session.patient_name!r} id={session.patient_id}"
    )

    await multiselect.open(
        update, context,
        title="اختر نوع الجرح",
        options=WOUND_TYPE_OPTIONS,
        return_to=_RKEY_WOUND_TYPE,
        icon="🩹",
        min_select=1,
    )


# ── Step 3: wound type selected ───────────────────────────────────────────────

async def _on_wound_type(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """result_router callback: wound type multiselect completed."""
    if result.cancelled:
        await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.wound_type_ids    = result.ids
    session.wound_type_labels = result.labels
    session.step              = STEP_IMAGES
    session.save(context.user_data)

    logger.info(
        f"[woundcare] wound types selected: {result.ids}"
    )

    await uploads.open(
        update, context,
        title="ارفع صور الجرح",
        return_to=_RKEY_IMAGES,
        icon="📷",
        allowed_types=["photo", "image_document"],
        min_files=1,
        max_files=10,
    )


# ── Step 4: images collected ──────────────────────────────────────────────────

async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """result_router callback: upload collector completed."""
    if result.cancelled:
        await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.images = [f.to_dict() for f in result.files]
    session.step   = STEP_NOTES
    session.save(context.user_data)

    logger.info(
        f"[woundcare] images collected: {result.count}  patient={session.patient_name!r}"
    )

    text, kb = build_notes_prompt(session)
    try:
        await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )
    except Exception as exc:
        logger.error(f"[woundcare] could not send notes prompt: {exc}")


# ── Step 5a: notes text received ─────────────────────────────────────────────

async def _handle_notes_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    MessageHandler in group 0 — only acts when session.step == STEP_NOTES.
    Returns silently for all other text messages.
    """
    session = WoundcareAddSession.load(context.user_data)
    if session is None or session.step != STEP_NOTES:
        return  # not our turn

    notes = (update.message.text or "").strip()
    session.notes = notes
    session.step  = STEP_REVIEW
    session.save(context.user_data)

    logger.info(
        f"[woundcare] notes received  len={len(notes)}  patient={session.patient_name!r}"
    )

    text, kb = build_review(session)
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 5b: skip notes ───────────────────────────────────────────────────────

async def _handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.notes = ""
    session.step  = STEP_REVIEW
    session.save(context.user_data)

    text, kb = build_review(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )


# ── Step 5c: edit notes (from review screen) ─────────────────────────────────

async def _handle_edit_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.notes = ""
    session.step  = STEP_NOTES
    session.save(context.user_data)

    text, kb = build_notes_prompt(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )


# ── Step 6: confirm save ──────────────────────────────────────────────────────

async def _handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    try:
        saved = save_wound_record(
            patient_id=        session.patient_id,
            patient_name=      session.patient_name,
            wound_type_ids=    session.wound_type_ids,
            wound_type_labels= session.wound_type_labels,
            images=            session.images,
            notes=             session.notes,
            created_by=        update.effective_user.id if update.effective_user else None,
        )
    except Exception as exc:
        logger.error(f"[woundcare] DB save failed: {exc}")
        text, kb = build_error("فشل حفظ التقرير. يرجى المحاولة مرة أخرى.")
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    WoundcareAddSession.clear(context.user_data)

    logger.info(
        f"[woundcare] record saved id={saved.record_id}"
        f"  patient={saved.patient_name!r}"
    )

    text, kb = build_success(saved.record_id, saved.patient_name, saved.image_count)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )


# ── Cancellation ─────────────────────────────────────────────────────────────

async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    WoundcareAddSession.clear(context.user_data)
    text, kb = build_cancelled()
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    try:
        await update.effective_message.reply_text(
            text, reply_markup=kb, parse_mode="Markdown"
        )
    except Exception as exc:
        logger.error(f"[woundcare] could not send cancellation: {exc}")


# ── Main callback dispatcher ──────────────────────────────────────────────────

async def _handle_wca_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch wca:* callbacks."""
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    action = data[len(WCA) + 1:]   # strip "wca:"

    if action == "start":
        await _start_add_flow(update, context)

    elif action == "skip_notes":
        await _handle_skip_notes(update, context)

    elif action == "edit_notes":
        await _handle_edit_notes(update, context)

    elif action == "confirm":
        await _handle_confirm(update, context)

    elif action == "cancel":
        await _cancel(update, context)

    else:
        logger.warning(f"[woundcare] unknown wca action: {action!r}")


async def _handle_hc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatch hc:* callbacks (healthcare navigation)."""
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    action = data[len(HC) + 1:]   # strip "hc:"

    if action == "main":
        text, kb = build_healthcare_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(
                text, reply_markup=kb, parse_mode="Markdown"
            )

    elif action == "woundcare":
        text, kb = build_woundcare_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(
                text, reply_markup=kb, parse_mode="Markdown"
            )

    else:
        logger.warning(f"[woundcare] unknown hc action: {action!r}")


# ── Handler registration ──────────────────────────────────────────────────────

def register_result_routes() -> None:
    """
    Register result_router completion handlers.
    Must be called once at startup, before any flow can complete.
    """
    _register_route(_RKEY_PATIENT,    _on_patient)
    _register_route(_RKEY_WOUND_TYPE, _on_wound_type)
    _register_route(_RKEY_IMAGES,     _on_images)
    logger.info(
        f"[woundcare] result routes registered: "
        f"{_RKEY_PATIENT}, {_RKEY_WOUND_TYPE}, {_RKEY_IMAGES}"
    )


def register_handlers(app) -> None:
    """
    Register woundcare PTB handlers.

    group 0  — text MessageHandler (notes input, fires when no ConversationHandler matches)
    group 1  — CallbackQueryHandlers for wca:* and hc:* buttons
    """
    # Notes text input — group 0, AFTER ConversationHandlers
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            _handle_notes_text,
        ),
        group=0,
    )

    # wca:* callbacks
    app.add_handler(
        CallbackQueryHandler(_handle_wca_callback, pattern=rf"^{WCA}:"),
        group=1,
    )

    # hc:* navigation callbacks
    app.add_handler(
        CallbackQueryHandler(_handle_hc_callback, pattern=rf"^{HC}:"),
        group=1,
    )

    logger.info(
        "[woundcare] handlers registered  "
        "notes=group:0  wca=group:1  hc=group:1"
    )
