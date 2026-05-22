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
    WOUNDCARE_SUPPLIES_OPTIONS, PHASE_MAP, SP_MAP,
    DEPT_OTHER_ID, SUPPLIES_OTHER_ID,
)
from modules.healthcare.woundcare.session import (
    WoundcareAddSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT, STEP_DEPARTMENT, STEP_DEPT_OTHER,
    STEP_OPERATION_NAME, STEP_PHASE, STEP_DESCRIPTION,
    STEP_SUPPLIES, STEP_SUPPLIES_OTHER, STEP_IMAGES,
    STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.healthcare.woundcare.views import (
    HC, WCA,
    build_date_prompt, build_date_calendar_prompt, build_woundcare_menu,
    build_dept_other_prompt, build_operation_name_prompt,
    build_phase_prompt, build_description_prompt,
    build_supplies_other_prompt, build_notes_prompt,
    build_specialist_prompt, build_review,
    build_success, build_cancelled, build_error,
)
from modules.healthcare.views import parse_date_input
from modules.healthcare.woundcare.models import save_wound_record

logger = logging.getLogger(__name__)


# ── Result router keys ────────────────────────────────────────────────────────

_RKEY_PATIENT     = "hc.woundcare.patient"
_RKEY_DEPARTMENTS = "hc.woundcare.departments"
_RKEY_SUPPLIES    = "hc.woundcare.supplies"
_RKEY_IMAGES      = "hc.woundcare.images"


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

    # No "أخرى" — proceed to operation name
    session.step = STEP_OPERATION_NAME
    session.save(context.user_data)
    text, kb = build_operation_name_prompt(session)
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[woundcare] operation_name prompt failed: {exc}")


# ── Step 7 → 7b / 8: supplies selected ───────────────────────────────────────

async def _on_supplies(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
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

    # No "أخرى" — proceed to images upload
    session.step = STEP_IMAGES
    session.save(context.user_data)
    await _open_images_upload(update, context)


# ── Step 8 → 9: images collected ─────────────────────────────────────────────

async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        await _cancel(update, context)
        return

    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.images = [f.to_dict() for f in result.files]
    session.step   = STEP_NOTES
    session.save(context.user_data)

    logger.info(f"[woundcare] images collected: {result.count}  patient={session.patient_name!r}")

    text, kb = build_notes_prompt(session)
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[woundcare] notes prompt failed: {exc}")


# ── Shared helper ─────────────────────────────────────────────────────────────

async def _open_images_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await uploads.open(
        update, context,
        title="ارفع صور الجرح / التوثيق (اختياري)",
        return_to=_RKEY_IMAGES,
        icon="📷",
        allowed_types=["photo", "image_document"],
        min_files=0,
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
            # Save to DB so it appears next time in the list
            save_custom_option(CTX_HC_DEPARTMENT, custom)
            session.medical_department_labels = [
                custom if lbl == "أخرى" else lbl
                for lbl in session.medical_department_labels
            ]
        session.step = STEP_OPERATION_NAME
        session.save(context.user_data)
        text, kb = build_operation_name_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_OPERATION_NAME:
        op = (update.message.text or "").strip()
        if not op:
            # Re-prompt without clearing
            text, kb = build_operation_name_prompt(session)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.operation_name = op
        session.step           = STEP_PHASE
        session.save(context.user_data)
        text, kb = build_phase_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_DESCRIPTION:
        desc = (update.message.text or "").strip()
        if not desc:
            text, kb = build_description_prompt(session)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.condition_description = desc
        session.step                  = STEP_SUPPLIES
        session.save(context.user_data)
        # Inject saved custom supplies at the top of the list
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
            # Save to DB so it appears next time in the list
            save_custom_option(CTX_WC_SUPPLIES, custom)
            session.supply_labels = [
                custom if lbl == "أخرى" else lbl
                for lbl in session.supply_labels
            ]
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images_upload(update, context)

    elif session.step == STEP_NOTES:
        session.notes = (update.message.text or "").strip()
        # If specialist already selected (edit_notes path), skip re-select
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
    session.step        = STEP_DESCRIPTION
    session.save(context.user_data)
    text, kb = build_description_prompt(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.notes = ""
    # If specialist already selected (edit_notes path), go straight to review
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
    session.specialist_name = name
    session.step            = STEP_REVIEW
    session.save(context.user_data)
    text, kb = build_review(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_edit_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    # Clear notes only; specialist stays → edit_notes → notes → review (skips re-select)
    session.notes = ""
    session.step  = STEP_NOTES
    session.save(context.user_data)
    text, kb = build_notes_prompt(session)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _handle_edit_specialist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = WoundcareAddSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.specialist_name = ""
    session.step            = STEP_SPECIALIST
    session.save(context.user_data)
    text, kb = build_specialist_prompt(session)
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
    condition_desc_snap     = session.condition_description
    supply_labels_snap      = list(session.supply_labels)
    images_snap             = list(session.images)
    notes_snap              = session.notes
    specialist_snap         = session.specialist_name
    date_snap               = session.created_at

    try:
        saved = save_wound_record(
            patient_id=               session.patient_id,
            patient_name=             session.patient_name,
            medical_department_ids=   session.medical_department_ids,
            medical_department_labels=session.medical_department_labels,
            operation_name=           session.operation_name,
            phase=                    session.phase,
            phase_label=              session.phase_label,
            condition_description=    session.condition_description,
            supply_ids=               session.supply_ids,
            supply_labels=            session.supply_labels,
            images=                   session.images,
            notes=                    session.notes,
            specialist_name=          session.specialist_name,
            created_by=               update.effective_user.id if update.effective_user else None,
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
    cond_text   = condition_desc_snap or "—"

    extra_sections = [
        ("🏥 *القسم الطبي:*",                         dept_text),
        (f"✍️ *اسم العملية:*  {operation_name_snap}",  ""),
        (f"🩹 *مرحلة المجارحة:*  {phase_label_snap}",  ""),
        ("📄 *وصف الحالة:*",                           cond_text),
        ("🧰 *المستلزمات الطبية:*",                    supply_text),
    ]

    # Publish report (errors are swallowed inside publish())
    user = update.effective_user
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
            operations=      [],   # no operations in official woundcare spec
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

    if session.step in (STEP_DEPT_OTHER, STEP_OPERATION_NAME):
        # Back to department multiselect
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

    elif session.step == STEP_SUPPLIES_OTHER:
        # Back to supplies multiselect
        session.step = STEP_SUPPLIES
        session.save(context.user_data)
        custom_supplies = load_custom_options(CTX_WC_SUPPLIES, icon="🧰")
        await multiselect.open(update, context,
            title="اختر المستلزمات الطبية المستخدمة",
            options=custom_supplies + WOUNDCARE_SUPPLIES_OPTIONS,
            return_to=_RKEY_SUPPLIES, icon="🧰", min_select=1)

    elif session.step == STEP_NOTES:
        # Back to images upload
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images_upload(update, context)

    elif session.step == STEP_SPECIALIST:
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await _edit_or_reply(text, kb)

    else:
        # Fallback: cancel
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

    dispatch = {
        "start":           _start_add_flow,
        "date_today":      _handle_date_today,
        "date_calendar":   _handle_date_calendar,
        "back":            _handle_back,
        "skip_notes":      _handle_skip_notes,
        "edit_notes":      _handle_edit_notes,
        "edit_specialist": _handle_edit_specialist,
        "confirm":         _handle_confirm,
        "cancel":          _cancel,
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

    action = data[len(HC) + 1:]  # strip "hc:"

    if action == "main":
        text, kb = build_healthcare_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "woundcare":
        text, kb = build_woundcare_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "followup":
        from modules.healthcare.medical_followup.views import build_followup_menu
        text, kb = build_followup_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "medications":
        from modules.healthcare.medications.views import build_medications_menu
        text, kb = build_medications_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif action == "other":
        from modules.healthcare.other.views import build_other_menu
        text, kb = build_other_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    else:
        logger.warning(f"[woundcare/hc] unknown hc action: {action!r}")


# ── Handler registration ──────────────────────────────────────────────────────

def register_result_routes() -> None:
    _register_route(_RKEY_PATIENT,     _on_patient)
    _register_route(_RKEY_DEPARTMENTS, _on_department)
    _register_route(_RKEY_SUPPLIES,    _on_supplies)
    _register_route(_RKEY_IMAGES,      _on_images)
    logger.info(
        f"[woundcare] result routes registered: "
        f"{_RKEY_PATIENT}, {_RKEY_DEPARTMENTS}, {_RKEY_SUPPLIES}, {_RKEY_IMAGES}"
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
