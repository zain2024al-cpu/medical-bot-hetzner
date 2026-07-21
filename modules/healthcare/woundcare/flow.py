# modules/healthcare/woundcare/flow.py
# Woundcare operational documentation flow — official 11-step workflow.
#
# ── Flow overview ─────────────────────────────────────────────────────────────
#
#   Step 1   التاريخ          — auto (session.create)
#   Step 2   المريض           — patient_selector  (return_to=_RKEY_PATIENT)
#   Step 3   القسم الطبي      — DEPARTMENT_OPTIONS multiselect (return_to=_RKEY_DEPARTMENTS)
#   Step 3b  [أخرى branch]    — free-text dept_other → wca:skip_dept_other
#   Step 4   اسم العملية      — free-text (STEP_OPERATION_NAME, required)
#   Step 5   مرحلة المجارحة   — single-select callback (wca:phase_*)
#   Step 6   وصف الحالة       — free-text (STEP_DESCRIPTION, required)
#   Step 7   المستلزمات        — SUPPLIES_OPTIONS multiselect (return_to=_RKEY_SUPPLIES)
#   Step 7b  [أخرى branch]    — free-text supplies_other → wca:skip_supplies_other
#   Step 8   الصور            — uploads.open() (return_to=_RKEY_IMAGES, optional)
#   Step 9   الملاحظات        — free-text STEP_NOTES or wca:skip_notes
#   Step 10  اسم الصحي        — fixed 3-name selector (wca:sp_fadl/sp_sarour/sp_zakariya)
#   Step 11  مراجعة + نشر     — wca:confirm
#
# ── Handler groups ────────────────────────────────────────────────────────────
#   group  0  MessageHandler(TEXT, ~COMMAND) — text input steps
#   group  1  CallbackQueryHandler(^wca:|^hc:) — inline button actions

import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.result_router import register as _register_route
from shared.calendar_picker import build_calendar
from shared.selectors.patient_selector import selector as patient_selector
from shared.multiselect import engine as multiselect
from shared.uploads import collector as uploads

from modules.healthcare.views import build_healthcare_menu, DEPARTMENT_OPTIONS
from modules.healthcare.custom_options import (
    save_custom_option, load_custom_options,
    CTX_HC_DEPARTMENT, CTX_WC_SUPPLIES,
)
from modules.healthcare.woundcare.constants import (
    WOUNDCARE_SUPPLIES_OPTIONS, WOUND_CONDITION_OPTIONS,
    PHASE_MAP, SP_MAP,
    DEPT_OTHER_ID, SUPPLIES_OTHER_ID, CONDITION_OTHER_ID,
)
from modules.healthcare.woundcare.session import (
    WoundcareAddSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT, STEP_DEPARTMENT, STEP_DEPT_OTHER,
    STEP_OPERATION_NAME, STEP_PHASE, STEP_DESCRIPTION, STEP_DESCRIPTION_OTHER,
    STEP_SUPPLIES, STEP_SUPPLIES_OTHER, STEP_IMAGES,
    STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.healthcare.woundcare.views import (
    HC, WCA,
    build_date_prompt, build_date_calendar_prompt, build_woundcare_menu,
    build_dept_other_prompt, build_operation_name_prompt,
    build_phase_prompt, build_description_other_prompt,
    build_supplies_other_prompt, build_notes_prompt,
    build_specialist_prompt, build_review,
    build_success, build_cancelled, build_error,
)
from modules.healthcare.views import parse_date_input
from modules.healthcare.woundcare.models import save_wound_record

logger = logging.getLogger(__name__)


# ── Result router keys ────────────────────────────────────────────────────────

_RKEY_PATIENT      = "hc.woundcare.patient"
_RKEY_DEPARTMENTS  = "hc.woundcare.departments"
_RKEY_DESCRIPTION  = "hc.woundcare.description"
_RKEY_SUPPLIES     = "hc.woundcare.supplies"
_RKEY_IMAGES       = "hc.woundcare.images"

_MODULE_KEY = "healthcare"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


# ── Review edit routes ────────────────────────────────────────────────────────

_REVIEW_EDIT_ROUTES: dict[str, str] = {
    "edit_dept":       STEP_DEPARTMENT,
    "edit_operation":  STEP_OPERATION_NAME,
    "edit_phase":      STEP_PHASE,
    "edit_condition":  STEP_DESCRIPTION,
    "edit_supplies":   STEP_SUPPLIES,
    "edit_images":     STEP_IMAGES,
    "edit_notes":      STEP_NOTES,
    "edit_specialist": STEP_SPECIALIST,
}


# ── _go_to_review — shared helper ─────────────────────────────────────────────

async def _go_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reset edit_from_review flag, set step=REVIEW, render review screen."""
    session = WoundcareAddSession.load(context.user_data)
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


# ── _route_to_edit_step — open correct UI for each step ──────────────────────

async def _route_to_edit_step(
    session: "WoundcareAddSession",
    step: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Open the correct UI for a given step when called from the review editor."""
    query = update.callback_query

    async def _safe_edit(text, kb):
        if query:
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
            except Exception:
                pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    if step == STEP_DEPARTMENT:
        custom_depts = load_custom_options(CTX_HC_DEPARTMENT, icon="🏥")
        await multiselect.open(
            update, context,
            title="اختر القسم الطبي",
            options=custom_depts + DEPARTMENT_OPTIONS,
            return_to=_RKEY_DEPARTMENTS,
            icon="🏥", min_select=1,
            auto_confirm_ids=[DEPT_OTHER_ID],
            preselected_ids=session.medical_department_ids,
        )
    elif step == STEP_OPERATION_NAME:
        text, kb = build_operation_name_prompt(session)
        await _safe_edit(text, kb)
    elif step == STEP_PHASE:
        text, kb = build_phase_prompt(session)
        await _safe_edit(text, kb)
    elif step == STEP_DESCRIPTION:
        await multiselect.open(
            update, context,
            title="وصف حالة الجرح / العملية",
            options=WOUND_CONDITION_OPTIONS,
            return_to=_RKEY_DESCRIPTION,
            icon="🩹", min_select=1,
            auto_confirm_ids=[CONDITION_OTHER_ID],
            preselected_ids=session.condition_ids,
        )
    elif step == STEP_SUPPLIES:
        custom_supplies = load_custom_options(CTX_WC_SUPPLIES, icon="🧰")
        await multiselect.open(
            update, context,
            title="اختر المستلزمات الطبية المستخدمة",
            options=custom_supplies + WOUNDCARE_SUPPLIES_OPTIONS,
            return_to=_RKEY_SUPPLIES,
            icon="🧰", min_select=1,
            auto_confirm_ids=[SUPPLIES_OTHER_ID],
            preselected_ids=session.supply_ids,
        )
    elif step == STEP_IMAGES:
        await _open_images_upload(update, context)
    elif step == STEP_NOTES:
        text, kb = build_notes_prompt(session)
        await _safe_edit(text, kb)
    elif step == STEP_SPECIALIST:
        text, kb = build_specialist_prompt(session)
        await _safe_edit(text, kb)


# ── _open_edit_step — entry point from dispatcher ────────────────────────────

async def _open_edit_step(
    action: str, update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Called when user taps an edit button on the review screen."""
    step = _REVIEW_EDIT_ROUTES.get(action)
    if step is None:
        return
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.edit_from_review = True
    session.step             = step
    session.save(context.user_data)
    await _route_to_edit_step(session, step, update, context)


# ── Step 1: start — show date confirmation screen ────────────────────────────

async def _start_add_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    WoundcareAddSession.create(context.user_data)
    logger.info(f"[woundcare] flow started  user={update.effective_user.id}")
    text, kb = build_date_prompt()
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 1 → 2: date today — advance to patient selector ────────────────────

async def _handle_date_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose today's date — advance to patient selector."""
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        session = WoundcareAddSession.create(context.user_data)
    session.step = STEP_PATIENT
    session.save(context.user_data)
    logger.info(f"[woundcare] date confirmed (today)  user={update.effective_user.id}")
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


# ── Step 1b: date calendar — show inline calendar picker ────────────────────

async def _handle_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose calendar date — show inline month calendar."""
    from datetime import datetime
    query = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        session = WoundcareAddSession.create(context.user_data)
    session.step = STEP_DATE_CUSTOM
    session.save(context.user_data)
    now = datetime.utcnow()
    text, kb = build_calendar(now.year, now.month, WCA, f"{WCA}:start")
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
        text, kb = build_calendar(y, m, WCA, f"{WCA}:start")
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
        session = WoundcareAddSession.load(context.user_data)
        if session is None:
            session = WoundcareAddSession.create(context.user_data)
        session.created_at = datetime(y, m, d).isoformat()
        session.step       = STEP_PATIENT
        session.save(context.user_data)
        logger.info(
            f"[woundcare] date picked: {y}-{m:02d}-{d:02d}  user={update.effective_user.id}"
        )
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


# ── Step 2 → 3: patient selected ─────────────────────────────────────────────

async def _on_patient(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or getattr(result, "cancelled", False):
        await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        session = WoundcareAddSession.create(context.user_data)

    patient              = result.patient if hasattr(result, "patient") else result
    session.patient_id   = patient.id   if patient else None
    session.patient_name = patient.name if patient else ""
    session.step         = STEP_DEPARTMENT
    session.save(context.user_data)

    logger.info(f"[woundcare] patient selected: {session.patient_name!r}")

    # Inject saved custom departments at the top of the list
    custom_depts = load_custom_options(CTX_HC_DEPARTMENT, icon="🏥")
    await multiselect.open(
        update, context,
        title="اختر القسم الطبي",
        options=custom_depts + DEPARTMENT_OPTIONS,
        return_to=_RKEY_DEPARTMENTS,
        icon="🏥",
        min_select=1,
        auto_confirm_ids=[DEPT_OTHER_ID],
    )


# ── Step 3 → 3b / 4: department selected ─────────────────────────────────────

async def _on_department(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = WoundcareAddSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.medical_department_ids    = result.ids
    session.medical_department_labels = result.labels

    if DEPT_OTHER_ID in result.ids:
        session.step = STEP_DEPT_OTHER
        session.save(context.user_data)
        text, kb = build_dept_other_prompt(session)
        try:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as exc:
            logger.error(f"[woundcare] dept_other prompt failed: {exc}")
        return

    # No "أخرى"
    if session.edit_from_review:
        await _go_to_review(update, context)
        return

    session.step = STEP_OPERATION_NAME
    session.save(context.user_data)
    text, kb = build_operation_name_prompt(session)
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[woundcare] operation_name prompt failed: {exc}")


# ── Step 6 → 6b / 7: condition selected ──────────────────────────────────────

async def _on_condition(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = WoundcareAddSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.condition_ids    = result.ids
    session.condition_labels = result.labels

    if CONDITION_OTHER_ID in result.ids:
        session.step = STEP_DESCRIPTION_OTHER
        session.save(context.user_data)
        text, kb = build_description_other_prompt(session)
        try:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as exc:
            logger.error(f"[woundcare] description_other prompt failed: {exc}")
        return

    # No "أخرى"
    session.condition_other = ""
    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    session.step = STEP_SUPPLIES
    session.save(context.user_data)
    custom_supplies = load_custom_options(CTX_WC_SUPPLIES, icon="🧰")
    await multiselect.open(
        update, context,
        title="اختر المستلزمات الطبية المستخدمة",
        options=custom_supplies + WOUNDCARE_SUPPLIES_OPTIONS,
        return_to=_RKEY_SUPPLIES,
        icon="🧰",
        min_select=1,
        auto_confirm_ids=[SUPPLIES_OTHER_ID],
    )


# ── Step 7 → 7b / 8: supplies selected ───────────────────────────────────────

async def _on_supplies(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = WoundcareAddSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.supply_ids    = result.ids
    session.supply_labels = result.labels

    if SUPPLIES_OTHER_ID in result.ids:
        session.step = STEP_SUPPLIES_OTHER
        session.save(context.user_data)
        text, kb = build_supplies_other_prompt(session)
        try:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as exc:
            logger.error(f"[woundcare] supplies_other prompt failed: {exc}")
        return

    # No "أخرى"
    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    session.step = STEP_IMAGES
    session.save(context.user_data)
    await _open_images_upload(update, context)


# ── Step 8 → 9: images collected ─────────────────────────────────────────────

async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = WoundcareAddSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.images = [f.to_dict() for f in result.files]
    logger.info(f"[woundcare] images collected: {result.count}  patient={session.patient_name!r}")

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
        logger.error(f"[woundcare] notes prompt failed: {exc}")


# ── Shared helper ─────────────────────────────────────────────────────────────

async def _open_images_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await uploads.open(
        update, context,
        title="ارفع صور الجرح / التوثيق",
        return_to=_RKEY_IMAGES,
        icon="📷",
        allowed_types=["photo", "image_document"],
        min_files=1,
        max_files=10,
    )


# ── Text input dispatcher ─────────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Group-0 MessageHandler — dispatches to the correct step handler
    based on session.step.  Silent if no woundcare session is active or
    the step is not a text-input step.
    """
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        return

    # ✅ الحماية داخل المعالِج نفسه — هذا معالِج نصوص عام (group 0، يطابق أي
    # رسالة نصية عبر كامل البوت)؛ يُتحقَّق بعد التأكد من وجود جلسة فعلية
    # حتى لا يُبطئ أي رسالة نصية غير متعلقة بهذه الوحدة إطلاقاً.
    if not update.effective_user or not _is_authorized(update.effective_user.id):
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
        logger.info(f"[woundcare] date set manually: {dt.date()}  user={update.effective_user.id}")
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)
        return

    elif session.step == STEP_DEPT_OTHER:
        custom = (update.message.text or "").strip()
        if custom:
            save_custom_option(CTX_HC_DEPARTMENT, custom)
            session.medical_department_labels = [
                custom if lbl == "أخرى" else lbl
                for lbl in session.medical_department_labels
            ]
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_OPERATION_NAME
        session.save(context.user_data)
        text, kb = build_operation_name_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_OPERATION_NAME:
        op = (update.message.text or "").strip()
        if not op:
            text, kb = build_operation_name_prompt(session)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.operation_name = op
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_PHASE
        session.save(context.user_data)
        text, kb = build_phase_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_DESCRIPTION_OTHER:
        other_text = (update.message.text or "").strip()
        if not other_text:
            text, kb = build_description_other_prompt(session)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.condition_other = other_text
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_SUPPLIES
        session.save(context.user_data)
        custom_supplies = load_custom_options(CTX_WC_SUPPLIES, icon="🧰")
        await multiselect.open(
            update, context,
            title="اختر المستلزمات الطبية المستخدمة",
            options=custom_supplies + WOUNDCARE_SUPPLIES_OPTIONS,
            return_to=_RKEY_SUPPLIES,
            icon="🧰",
            min_select=1,
            auto_confirm_ids=[SUPPLIES_OTHER_ID],
        )

    elif session.step == STEP_SUPPLIES_OTHER:
        custom = (update.message.text or "").strip()
        if custom:
            save_custom_option(CTX_WC_SUPPLIES, custom)
            session.supply_labels = [
                custom if lbl == "أخرى" else lbl
                for lbl in session.supply_labels
            ]
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images_upload(update, context)

    elif session.step == STEP_NOTES:
        session.notes = (update.message.text or "").strip()
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        if session.specialist_name:
            session.step = STEP_REVIEW
            session.save(context.user_data)
            text, kb = build_review(session)
        else:
            session.step = STEP_SPECIALIST
            session.save(context.user_data)
            text, kb = build_specialist_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Callback handlers ─────────────────────────────────────────────────────────

async def _handle_select_phase(
    update: Update, context: ContextTypes.DEFAULT_TYPE, phase_key: str
) -> None:
    """Called when user taps one of the 4 phase buttons."""
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.phase       = phase_key
    session.phase_label = PHASE_MAP[phase_key]

    if session.edit_from_review:
        # Phase changed — go straight back to review (condition/supplies kept as-is)
        session.edit_from_review = False
        session.step             = STEP_REVIEW
        session.save(context.user_data)
        text, kb = build_review(session)
        try:
            if query:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
        except Exception:
            pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    session.step = STEP_DESCRIPTION
    session.save(context.user_data)
    await multiselect.open(
        update, context,
        title="وصف حالة الجرح / العملية",
        options=WOUND_CONDITION_OPTIONS,
        return_to=_RKEY_DESCRIPTION,
        icon="🩹",
        min_select=1,
        auto_confirm_ids=[CONDITION_OTHER_ID],
    )


async def _handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.notes = ""
    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return
    if session.specialist_name:
        session.step = STEP_REVIEW
        text, kb     = build_review(session)
    else:
        session.step = STEP_SPECIALIST
        text, kb     = build_specialist_prompt(session)
    session.save(context.user_data)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_select_specialist(
    update: Update, context: ContextTypes.DEFAULT_TYPE, name: str
) -> None:
    """Called when user taps one of the 3 fixed staff buttons."""
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.specialist_name  = name
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
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    # Snapshot all session data before clearing
    dept_labels_snap        = list(session.medical_department_labels)
    operation_name_snap     = session.operation_name
    phase_snap              = session.phase
    phase_label_snap        = session.phase_label
    condition_labels_snap   = list(session.condition_labels)
    condition_other_snap    = session.condition_other
    supply_labels_snap      = list(session.supply_labels)
    images_snap             = list(session.images)
    notes_snap              = session.notes
    specialist_snap         = session.specialist_name
    date_snap               = session.created_at

    # Generate condition description string for DB (replaces free-text field)
    _cond_for_db = list(condition_labels_snap)
    if condition_other_snap:
        _cond_for_db = [
            condition_other_snap if lbl == "أخرى" else lbl
            for lbl in _cond_for_db
        ]
    condition_desc_for_db = "\n".join(f"• {lbl}" for lbl in _cond_for_db) if _cond_for_db else ""

    _created_by = update.effective_user.id if update.effective_user else None
    logger.info(
        "[healthcare.publish] model=WoundRecord  payload:"
        f"  patient_id={session.patient_id}"
        f"  patient_name={session.patient_name!r}"
        f"  depts={session.medical_department_labels}"
        f"  operation_name={session.operation_name!r}"
        f"  phase={session.phase!r}"
        f"  phase_label={session.phase_label!r}"
        f"  condition={condition_desc_for_db!r}"
        f"  supplies={session.supply_labels}"
        f"  images={len(session.images)}"
        f"  notes={session.notes!r}"
        f"  specialist={session.specialist_name!r}"
        f"  created_by={_created_by}"
    )
    try:
        saved = save_wound_record(
            patient_id=               session.patient_id,
            patient_name=             session.patient_name,
            medical_department_ids=   session.medical_department_ids,
            medical_department_labels=session.medical_department_labels,
            operation_name=           session.operation_name,
            phase=                    session.phase,
            phase_label=              session.phase_label,
            condition_description=    condition_desc_for_db,
            supply_ids=               session.supply_ids,
            supply_labels=            session.supply_labels,
            images=                   session.images,
            notes=                    session.notes,
            specialist_name=          session.specialist_name,
            created_by=               _created_by,
        )
        logger.info(f"[healthcare.publish] save OK  model=WoundRecord  id={saved.record_id}  patient={saved.patient_name!r}")
    except Exception:
        logger.exception(
            f"[healthcare.publish] FAILED  model=WoundRecord"
            f"  patient_id={session.patient_id}  patient_name={session.patient_name!r}"
        )
        text, kb = build_error("فشل حفظ التقرير. يرجى المحاولة مرة أخرى.")
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    WoundcareAddSession.clear(context.user_data)
    logger.info(f"[woundcare] record saved id={saved.record_id}  patient={saved.patient_name!r}")

    # Show success screen immediately
    text, kb = build_success(saved.record_id, saved.patient_name, saved.image_count)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # Build extra_sections for the published report
    dept_text   = "\n".join(f"  • {d}" for d in dept_labels_snap)   or "  —"
    supply_text = "\n".join(f"  • {s}" for s in supply_labels_snap) or "  —"
    _cond_pub   = list(condition_labels_snap)
    if condition_other_snap:
        _cond_pub = [
            condition_other_snap if lbl == "أخرى" else lbl
            for lbl in _cond_pub
        ]
    cond_text = "\n".join(f"  • {lbl}" for lbl in _cond_pub) if _cond_pub else "—"

    extra_sections = [
        ("🏥 *القسم الطبي:*",                         dept_text),
        (f"✍️ *اسم العملية:*  {operation_name_snap}",  ""),
        (f"🩹 *مرحلة المجارحة:*  {phase_label_snap}",  ""),
        ("🩹 *وصف حالة الجرح:*",                       cond_text),
        ("🧰 *المستلزمات الطبية المستخدمة:*",            supply_text),
    ]

    # Publish report
    user = update.effective_user
    logger.info(
        f"[woundcare] calling publish  record_id={saved.record_id}"
        f"  images_snap={len(images_snap)}"
    )
    try:
        from modules.healthcare.report_publisher import HealthcarePublishData, publish as _publish
        await _publish(
            bot=context.bot,
            data=HealthcarePublishData(
                workflow_type=   "woundcare",
                workflow_label=  "المجارحة والعناية بالجرح",
                workflow_icon=   "🩺",
                record_id=       saved.record_id,
                patient_name=    saved.patient_name,
                extra_sections=  extra_sections,
                operations=      [],
                images=          images_snap,
                notes=           notes_snap,
                specialist_name= specialist_snap,
                created_by_id=   user.id if user else None,
                created_by_name= (
                    user.full_name or user.username or "مجهول"
                ) if user else "مجهول",
                record_date=     date_snap,
            ),
        )
        logger.info(f"[woundcare] publish completed  record_id={saved.record_id}")
    except Exception:
        logger.exception(f"[woundcare] publish RAISED  record_id={saved.record_id}")


# ── Back navigation ───────────────────────────────────────────────────────────

async def _handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Navigate to the previous step based on session.step."""
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    async def _edit_or_reply(text, kb):
        try:
            if query:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
        except Exception:
            pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # ── edit-from-review mode: back returns to review except within sub-branches ──
    if session.edit_from_review:
        if session.step == STEP_DEPT_OTHER:
            session.step = STEP_DEPARTMENT
            session.save(context.user_data)
            custom_depts = load_custom_options(CTX_HC_DEPARTMENT, icon="🏥")
            await multiselect.open(update, context,
                title="اختر القسم الطبي",
                options=custom_depts + DEPARTMENT_OPTIONS,
                return_to=_RKEY_DEPARTMENTS, icon="🏥", min_select=1,
                auto_confirm_ids=[DEPT_OTHER_ID],
                preselected_ids=session.medical_department_ids)
        elif session.step == STEP_DESCRIPTION_OTHER:
            session.step = STEP_DESCRIPTION
            session.save(context.user_data)
            await multiselect.open(update, context,
                title="وصف حالة الجرح / العملية",
                options=WOUND_CONDITION_OPTIONS,
                return_to=_RKEY_DESCRIPTION, icon="🩹", min_select=1,
                auto_confirm_ids=[CONDITION_OTHER_ID],
                preselected_ids=session.condition_ids)
        elif session.step == STEP_SUPPLIES_OTHER:
            session.step = STEP_SUPPLIES
            session.save(context.user_data)
            custom_supplies = load_custom_options(CTX_WC_SUPPLIES, icon="🧰")
            await multiselect.open(update, context,
                title="اختر المستلزمات الطبية المستخدمة",
                options=custom_supplies + WOUNDCARE_SUPPLIES_OPTIONS,
                return_to=_RKEY_SUPPLIES, icon="🧰", min_select=1,
                auto_confirm_ids=[SUPPLIES_OTHER_ID],
                preselected_ids=session.supply_ids)
        else:
            await _go_to_review(update, context)
        return

    # ── Normal back navigation ────────────────────────────────────────────────
    if session.step in (STEP_DEPT_OTHER, STEP_OPERATION_NAME):
        session.step = STEP_DEPARTMENT
        session.save(context.user_data)
        custom_depts = load_custom_options(CTX_HC_DEPARTMENT, icon="🏥")
        await multiselect.open(update, context,
            title="اختر القسم الطبي",
            options=custom_depts + DEPARTMENT_OPTIONS,
            return_to=_RKEY_DEPARTMENTS, icon="🏥", min_select=1)

    elif session.step == STEP_PHASE:
        session.step = STEP_OPERATION_NAME
        session.save(context.user_data)
        text, kb = build_operation_name_prompt(session)
        await _edit_or_reply(text, kb)

    elif session.step == STEP_DESCRIPTION:
        session.step = STEP_PHASE
        session.save(context.user_data)
        text, kb = build_phase_prompt(session)
        await _edit_or_reply(text, kb)

    elif session.step == STEP_DESCRIPTION_OTHER:
        session.step = STEP_DESCRIPTION
        session.save(context.user_data)
        await multiselect.open(
            update, context,
            title="وصف حالة الجرح / العملية",
            options=WOUND_CONDITION_OPTIONS,
            return_to=_RKEY_DESCRIPTION,
            icon="🩹", min_select=1,
            auto_confirm_ids=[CONDITION_OTHER_ID],
        )

    elif session.step == STEP_SUPPLIES_OTHER:
        session.step = STEP_SUPPLIES
        session.save(context.user_data)
        custom_supplies = load_custom_options(CTX_WC_SUPPLIES, icon="🧰")
        await multiselect.open(update, context,
            title="اختر المستلزمات الطبية المستخدمة",
            options=custom_supplies + WOUNDCARE_SUPPLIES_OPTIONS,
            return_to=_RKEY_SUPPLIES, icon="🧰", min_select=1)

    elif session.step == STEP_NOTES:
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images_upload(update, context)

    elif session.step == STEP_SPECIALIST:
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await _edit_or_reply(text, kb)

    else:
        await _cancel(update, context)


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
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[woundcare] could not send cancellation: {exc}")


# ── Callback dispatchers ──────────────────────────────────────────────────────

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
    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[woundcare] 🚫 blocked unauthorized user={getattr(query.from_user, 'id', '?')}")
        return

    action = data[len(WCA) + 1:]  # strip "wca:"

    # Phase selection (phase_pre_op / phase_post_1 / phase_post_last / phase_chronic)
    if action in PHASE_MAP:
        await _handle_select_phase(update, context, action)
        return

    # Fixed staff selection (sp_fadl / sp_sarour / sp_zakariya)
    if action in SP_MAP:
        await _handle_select_specialist(update, context, SP_MAP[action])
        return

    # Calendar widget (cal_pick / cal_prev / cal_next / cal_noop)
    if action.startswith("cal_"):
        await _handle_cal_action(update, context, action)
        return

    # Route any review edit button to the generic edit handler
    if action in _REVIEW_EDIT_ROUTES:
        await _open_edit_step(action, update, context)
        return

    dispatch = {
        "start":         _start_add_flow,
        "date_today":    _handle_date_today,
        "date_calendar": _handle_date_calendar,
        "back":          _handle_back,
        "skip_notes":    _handle_skip_notes,
        "confirm":       _handle_confirm,
        "cancel":        _cancel,
    }
    handler = dispatch.get(action)
    if handler:
        await handler(update, context)
    else:
        logger.warning(f"[woundcare] unknown wca action: {action!r}")


async def _handle_hc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Dispatch hc:* callbacks (healthcare-level navigation).
    Lives here because woundcare registers the hc: handler.
    Late-binding imports prevent circular import issues.
    """
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass
    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[woundcare.hc] 🚫 blocked unauthorized user={getattr(query.from_user, 'id', '?')}")
        return

    action = data[len(HC) + 1:]  # strip "hc:"

    if action == "main":
        text, kb = build_healthcare_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # ✅ تسهيل الشاشة: كانت هذه الأفرع تعرض "شاشة تأكيد" وسيطة (زر واحد
    # "➕ تسجيل جديد" + رجوع) بين القائمة الرئيسية وشاشة التاريخ — ضغطة
    # إضافية بلا أي خيار حقيقي. الآن تنتقل مباشرة لشاشة التاريخ (نفس ما
    # كان يحدث فقط بعد الضغط على "➕ تسجيل جديد" سابقاً). القائمة القديمة
    # (build_*_menu) تبقى معرَّفة في الملفات لكنها لم تعد تُستدعى من هنا.
    elif action == "woundcare":
        await _start_add_flow(update, context)

    elif action == "followup":
        from modules.healthcare.medical_followup.flow import _start_flow as _start_followup_flow
        await _start_followup_flow(update, context)

    elif action == "medications":
        from modules.healthcare.medications.flow import _start_flow as _start_medications_flow
        await _start_medications_flow(update, context)

    elif action == "supplies":
        from modules.healthcare.supplies.flow import _start_flow as _start_supplies_flow
        await _start_supplies_flow(update, context)

    elif action == "other":
        from modules.healthcare.other.flow import _start_flow as _start_other_flow
        await _start_other_flow(update, context)

    else:
        logger.warning(f"[woundcare/hc] unknown hc action: {action!r}")


# ── Handler registration ──────────────────────────────────────────────────────

def register_result_routes() -> None:
    _register_route(_RKEY_PATIENT,      _on_patient)
    _register_route(_RKEY_DEPARTMENTS,  _on_department)
    _register_route(_RKEY_DESCRIPTION,  _on_condition)
    _register_route(_RKEY_SUPPLIES,     _on_supplies)
    _register_route(_RKEY_IMAGES,       _on_images)
    logger.info(
        f"[woundcare] result routes registered: "
        f"{_RKEY_PATIENT}, {_RKEY_DEPARTMENTS}, {_RKEY_DESCRIPTION}, "
        f"{_RKEY_SUPPLIES}, {_RKEY_IMAGES}"
    )


def register_handlers(app) -> None:
    """
    group 0 — text MessageHandler (operation_name, description, notes, dept_other, supplies_other)
    group 1 — CallbackQueryHandlers for wca:* and hc:*
    """
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input),
        group=0,
    )
    app.add_handler(
        CallbackQueryHandler(_handle_wca_callback, pattern=rf"^{WCA}:"),
        group=1,
    )
    app.add_handler(
        CallbackQueryHandler(_handle_hc_callback, pattern=rf"^{HC}:"),
        group=1,
    )
    logger.info("[woundcare] handlers registered  text=group:0  wca/hc=group:1")
