# modules/healthcare/other/flow.py
# "Other" healthcare catch-all flow — 8-step workflow.

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from shared.result_router import register as _register_route
from shared.calendar_picker import build_calendar
from shared.selectors.patient_selector import selector as patient_selector
from shared.multiselect import engine as multiselect
from shared.uploads import collector as uploads

from modules.healthcare.other.session import (
    OtherHealthcareSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT, STEP_OPERATIONS, STEP_IMAGES,
    STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.healthcare.other.constants import ACTION_OPTIONS
from modules.healthcare.other.views import (
    HC, HCOTH,
    build_date_prompt, build_date_calendar_prompt,
    build_notes_prompt, build_specialist_prompt,
    build_review, build_success, build_cancelled, build_error,
)
from modules.healthcare.views import parse_date_input

logger = logging.getLogger(__name__)

_RKEY_PATIENT    = "hc.other.patient"
_RKEY_OPERATIONS = "hc.other.actions"
_RKEY_IMAGES     = "hc.other.images"

# ── Review edit routes ────────────────────────────────────────────────────────

_REVIEW_EDIT_ROUTES: dict[str, str] = {
    "edit_operations": STEP_OPERATIONS,
    "edit_images":     STEP_IMAGES,
    "edit_notes":      STEP_NOTES,
    "edit_specialist": STEP_SPECIALIST,
}


# ── _go_to_review ─────────────────────────────────────────────────────────────

async def _go_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.edit_from_review = False
    session.step             = STEP_REVIEW
    session.save(context.user_data)
    text, kb = build_review(session)
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── _route_to_edit_step ───────────────────────────────────────────────────────

async def _route_to_edit_step(
    session: "OtherHealthcareSession",
    step: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    from modules.healthcare.other.constants import ACTION_OPTIONS
    query = update.callback_query

    async def _safe_edit(text, kb):
        if query:
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
            except Exception:
                pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    if step == STEP_OPERATIONS:
        await multiselect.open(
            update, context,
            title="اختر نوع الإجراء",
            options=ACTION_OPTIONS,
            return_to=_RKEY_OPERATIONS,
            icon="📝", min_select=1,
            preselected_ids=session.operation_ids,
        )
    elif step == STEP_IMAGES:
        await uploads.open(
            update, context,
            title="ارفع صور / مستندات (اختياري)",
            return_to=_RKEY_IMAGES,
            icon="📎",
            allowed_types=["photo", "image_document"],
            min_files=0, max_files=10,
        )
    elif step == STEP_NOTES:
        text, kb = build_notes_prompt(session)
        await _safe_edit(text, kb)
    elif step == STEP_SPECIALIST:
        text, kb = build_specialist_prompt(session)
        await _safe_edit(text, kb)


# ── _open_edit_step ───────────────────────────────────────────────────────────

async def _open_edit_step(
    action: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    step = _REVIEW_EDIT_ROUTES.get(action)
    if step is None:
        return
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.edit_from_review = True
    session.step             = step
    session.save(context.user_data)
    await _route_to_edit_step(session, step, update, context)


async def _start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    OtherHealthcareSession.create(context.user_data)
    logger.info(f"[other_hc] flow started  user={update.effective_user.id}")
    text, kb = build_date_prompt()
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_date_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose today's date — advance to patient selector."""
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        session = OtherHealthcareSession.create(context.user_data)
    session.step = STEP_PATIENT
    session.save(context.user_data)
    logger.info(f"[other_hc] date confirmed (today)  user={update.effective_user.id}")
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


async def _handle_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose calendar date — show inline month calendar."""
    from datetime import datetime
    query = update.callback_query
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        session = OtherHealthcareSession.create(context.user_data)
    session.step = STEP_DATE_CUSTOM
    session.save(context.user_data)
    now = datetime.utcnow()
    text, kb = build_calendar(now.year, now.month, HCOTH, f"{HCOTH}:start")
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_cal_action(
    update: Update, context: ContextTypes.DEFAULT_TYPE, action: str
) -> None:
    """Handle cal_prev / cal_next / cal_pick / cal_noop calendar callbacks."""
    from datetime import datetime
    query = update.callback_query
    parts = action.split(":")
    kind  = parts[0]

    if kind == "cal_noop":
        return

    if kind in ("cal_prev", "cal_next"):
        y, m = int(parts[1]), int(parts[2])
        text, kb = build_calendar(y, m, HCOTH, f"{HCOTH}:start")
        try:
            if query:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
                return
        except Exception:
            pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if kind == "cal_pick":
        y, m, d = int(parts[1]), int(parts[2]), int(parts[3])
        session = OtherHealthcareSession.load(context.user_data)
        if session is None:
            session = OtherHealthcareSession.create(context.user_data)
        session.created_at = datetime(y, m, d).isoformat()
        session.step       = STEP_PATIENT
        session.save(context.user_data)
        logger.info(
            f"[other_hc] date picked: {y}-{m:02d}-{d:02d}  user={update.effective_user.id}"
        )
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


async def _on_patient(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or getattr(result, "cancelled", False):
        await _cancel(update, context); return
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        session = OtherHealthcareSession.create(context.user_data)
    patient              = result.patient if hasattr(result, "patient") else result
    session.patient_id   = patient.id   if patient else None
    session.patient_name = patient.name if patient else ""
    session.step         = STEP_OPERATIONS
    session.save(context.user_data)
    await multiselect.open(
        update, context,
        title="اختر نوع الإجراء",
        options=ACTION_OPTIONS,
        return_to=_RKEY_OPERATIONS,
        icon="📝",
        min_select=1,
    )


async def _on_operations(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = OtherHealthcareSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.operation_ids    = result.ids
    session.operation_labels = result.labels

    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    session.step = STEP_IMAGES
    session.save(context.user_data)
    await uploads.open(
        update, context,
        title="ارفع صور / مستندات (اختياري)",
        return_to=_RKEY_IMAGES,
        icon="📎",
        allowed_types=["photo", "image_document"],
        min_files=0,
        max_files=10,
    )


async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = OtherHealthcareSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.images = [f.to_dict() for f in result.files]

    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    session.step = STEP_NOTES
    session.save(context.user_data)
    text, kb = build_notes_prompt(session)
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[other_hc] notes prompt failed: {exc}")


async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        return
    if session.step == STEP_DATE_CUSTOM:
        dt = parse_date_input(update.message.text or "")
        if dt is None:
            text, kb = build_date_calendar_prompt(error=True)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.created_at = dt.isoformat()
        session.step = STEP_PATIENT
        session.save(context.user_data)
        logger.info(f"[other_hc] date set manually: {dt.date()}  user={update.effective_user.id}")
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)
        return
    elif session.step == STEP_NOTES:
        session.notes = (update.message.text or "").strip()
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_SPECIALIST
        session.save(context.user_data)
        text, kb = build_specialist_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    elif session.step == STEP_SPECIALIST:
        session.specialist_name = (update.message.text or "").strip()
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_REVIEW
        session.save(context.user_data)
        text, kb = build_review(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.notes = ""
    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return
    session.step = STEP_SPECIALIST
    session.save(context.user_data)
    text, kb = build_specialist_prompt(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_skip_specialist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.specialist_name  = ""
    session.edit_from_review = False   # always lands on review
    session.step             = STEP_REVIEW
    session.save(context.user_data)
    text, kb = build_review(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")




async def _handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    images_snap     = list(session.images)
    notes_snap      = session.notes
    specialist_snap = session.specialist_name
    date_snap       = session.created_at

    from modules.healthcare.other.models import save_other_record
    try:
        saved = save_other_record(
            patient_id=       session.patient_id,
            patient_name=     session.patient_name,
            operation_ids=    session.operation_ids,
            operation_labels= session.operation_labels,
            images=           session.images,
            notes=            session.notes,
            specialist_name=  session.specialist_name,
            created_by=       update.effective_user.id if update.effective_user else None,
        )
    except Exception as exc:
        logger.error(f"[other_hc] DB save failed: {exc}")
        text, kb = build_error("فشل حفظ التقرير.")
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    OtherHealthcareSession.clear(context.user_data)

    text, kb = build_success(saved.record_id, saved.patient_name, saved.image_count)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    user = update.effective_user
    from modules.healthcare.report_publisher import HealthcarePublishData, publish as _publish
    await _publish(
        bot=context.bot,
        data=HealthcarePublishData(
            workflow_type=   "other",
            workflow_label=  "إجراء صحي",
            workflow_icon=   "📝",
            record_id=       saved.record_id,
            patient_name=    saved.patient_name,
            operations=      saved.action_labels,
            images=          images_snap,
            notes=           notes_snap,
            specialist_name= specialist_snap,
            created_by_id=   user.id if user else None,
            created_by_name= (user.full_name or user.username or "مجهول") if user else "مجهول",
            record_date=     date_snap,
        ),
    )


# ── Back navigation ───────────────────────────────────────────────────────────

async def _handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Navigate to the previous step based on session.step."""
    query   = update.callback_query
    session = OtherHealthcareSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    async def _edit_or_reply(text, kb):
        try:
            if query:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
        except Exception:
            pass
        try:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as exc:
            logger.error(f"[other_hc] back reply failed: {exc}")

    # ── edit-from-review: back always returns to review ──
    if session.edit_from_review:
        await _go_to_review(update, context)
        return

    if session.step == STEP_NOTES:
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await uploads.open(update, context,
            title="ارفع صور / مستندات (اختياري)",
            return_to=_RKEY_IMAGES, icon="📎",
            allowed_types=["photo", "image_document"],
            min_files=0, max_files=10)

    elif session.step == STEP_SPECIALIST:
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await _edit_or_reply(text, kb)

    else:
        await _cancel(update, context)


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    OtherHealthcareSession.clear(context.user_data)
    text, kb = build_cancelled()
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
    except Exception:
        pass
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[other_hc] cancel failed: {exc}")


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass
    action = data[len(HCOTH) + 1:]

    # Calendar widget (cal_pick / cal_prev / cal_next / cal_noop)
    if action.startswith("cal_"):
        await _handle_cal_action(update, context, action)
        return

    if action in _REVIEW_EDIT_ROUTES:
        await _open_edit_step(action, update, context)
        return

    dispatch = {
        "start":           _start_flow,
        "date_today":      _handle_date_today,
        "date_calendar":   _handle_date_calendar,
        "back":            _handle_back,
        "skip_notes":      _handle_skip_notes,
        "skip_specialist": _handle_skip_specialist,
        "confirm":         _handle_confirm,
        "cancel":          _cancel,
    }
    handler = dispatch.get(action)
    if handler:
        await handler(update, context)
    else:
        logger.warning(f"[other_hc] unknown action: {action!r}")


def register_result_routes() -> None:
    _register_route(_RKEY_PATIENT, _on_patient)
    _register_route(_RKEY_OPERATIONS, _on_operations)
    _register_route(_RKEY_IMAGES, _on_images)
    logger.info("[other_hc] result routes registered")


def register_handlers(app) -> None:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input), group=6)  # unique group — avoids PTB v20 group-0 conflict
    app.add_handler(CallbackQueryHandler(_handle_callback, pattern=rf"^{HCOTH}:"), group=1)
    logger.info("[other_hc] handlers registered")
