# modules/healthcare/medical_followup/flow.py
# Medical follow-up operational documentation flow — official 11-step workflow.
#
# Steps: التاريخ → المريض → القسم الطبي → نوع الإجراء → الشكوى الرئيسية
#        → العلامات الحيوية (×4) → الأدوية والمستلزمات → الصور
#        → الملاحظات → اسم الصحي → مراجعة → نشر

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from shared.result_router import register as _register_route
from shared.calendar_picker import build_calendar
from shared.selectors.patient_selector import selector as patient_selector
from shared.multiselect import engine as multiselect
from shared.uploads import collector as uploads

from modules.healthcare.custom_options import (
    save_custom_option, load_custom_options,
    CTX_HC_DEPARTMENT, CTX_FU_COMPLAINT, CTX_FU_MEDS_SUPPLY,
)
from modules.healthcare.medical_followup.constants import (
    PROCEDURE_TYPE_OPTIONS, COMPLAINT_OPTIONS, MEDS_SUPPLY_OPTIONS,
    SP_MAP, DEPT_OTHER_ID, COMPLAINT_OTHER_ID, MEDS_SUPPLY_OTHER_ID,
)
from modules.healthcare.medical_followup.session import (
    MedicalFollowupSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT, STEP_DEPARTMENT, STEP_DEPT_OTHER,
    STEP_PROC_TYPE, STEP_COMPLAINT, STEP_COMPLAINT_OTHER,
    STEP_VITALS_TEMP, STEP_VITALS_BP, STEP_VITALS_PULSE, STEP_VITALS_SPO2,
    STEP_MEDS_SUPPLY, STEP_MEDS_SUPPLY_OTHER,
    STEP_IMAGES, STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.healthcare.medical_followup.views import (
    HC, HCFU,
    build_date_prompt, build_date_calendar_prompt, build_followup_menu,
    build_dept_other_prompt,
    build_complaint_other_prompt,
    build_vitals_temp_prompt, build_vitals_bp_prompt,
    build_vitals_pulse_prompt, build_vitals_spo2_prompt,
    build_meds_supply_other_prompt,
    build_notes_prompt, build_specialist_prompt,
    build_review, build_success, build_cancelled, build_error,
)
from modules.healthcare.views import parse_date_input

logger = logging.getLogger(__name__)

_RKEY_PATIENT     = "hc.followup.patient"
_RKEY_DEPARTMENTS = "hc.followup.departments"
_RKEY_PROC_TYPE   = "hc.followup.proc_type"
_RKEY_COMPLAINT   = "hc.followup.complaint"
_RKEY_MEDS_SUPPLY = "hc.followup.meds_supply"
_RKEY_IMAGES      = "hc.followup.images"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _safe_edit(query, text: str, kb) -> None:
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass


async def _safe_reply(update: Update, text: str, kb) -> None:
    try:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[followup] send failed: {exc}")


# ── Flow steps ────────────────────────────────────────────────────────────────

async def _start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    MedicalFollowupSession.create(context.user_data)
    logger.info(f"[followup] flow started  user={update.effective_user.id}")
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
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        session = MedicalFollowupSession.create(context.user_data)
    session.step = STEP_PATIENT
    session.save(context.user_data)
    logger.info(f"[followup] date confirmed (today)  user={update.effective_user.id}")
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


async def _handle_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose calendar date — show inline month calendar."""
    from datetime import datetime
    query = update.callback_query
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        session = MedicalFollowupSession.create(context.user_data)
    session.step = STEP_DATE_CUSTOM
    session.save(context.user_data)
    now = datetime.utcnow()
    text, kb = build_calendar(now.year, now.month, HCFU, f"{HCFU}:start")
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
        text, kb = build_calendar(y, m, HCFU, f"{HCFU}:start")
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
        session = MedicalFollowupSession.load(context.user_data)
        if session is None:
            session = MedicalFollowupSession.create(context.user_data)
        session.created_at = datetime(y, m, d).isoformat()
        session.step       = STEP_PATIENT
        session.save(context.user_data)
        logger.info(
            f"[followup] date picked: {y}-{m:02d}-{d:02d}  user={update.effective_user.id}"
        )
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


async def _on_patient(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or getattr(result, "cancelled", False):
        await _cancel(update, context)
        return

    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        session = MedicalFollowupSession.create(context.user_data)

    patient              = result.patient if hasattr(result, "patient") else result
    session.patient_id   = patient.id   if patient else None
    session.patient_name = patient.name if patient else ""
    session.step         = STEP_DEPARTMENT
    session.save(context.user_data)

    from modules.healthcare.views import DEPARTMENT_OPTIONS
    custom_depts = load_custom_options(CTX_HC_DEPARTMENT, icon="🏥")
    await multiselect.open(
        update, context,
        title="القسم الطبي",
        options=custom_depts + DEPARTMENT_OPTIONS,
        return_to=_RKEY_DEPARTMENTS,
        icon="🏥",
        min_select=1,
        auto_confirm_ids=[DEPT_OTHER_ID],
    )


async def _on_department(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        await _cancel(update, context)
        return

    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.medical_department_ids    = result.ids
    session.medical_department_labels = result.labels
    session.step = STEP_DEPT_OTHER if DEPT_OTHER_ID in result.ids else STEP_PROC_TYPE
    session.save(context.user_data)

    if session.step == STEP_DEPT_OTHER:
        text, kb = build_dept_other_prompt(session)
        await _safe_reply(update, text, kb)
    else:
        await _open_proc_type(update, context)


async def _open_proc_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await multiselect.open(
        update, context,
        title="نوع الإجراء",
        options=PROCEDURE_TYPE_OPTIONS,
        return_to=_RKEY_PROC_TYPE,
        icon="📋",
        min_select=1,
    )


async def _on_proc_type(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        await _cancel(update, context)
        return

    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.procedure_type_ids    = result.ids
    session.procedure_type_labels = result.labels
    session.step                  = STEP_COMPLAINT
    session.save(context.user_data)

    custom_complaints = load_custom_options(CTX_FU_COMPLAINT, icon="😷")
    await multiselect.open(
        update, context,
        title="الشكوى الرئيسية",
        options=custom_complaints + COMPLAINT_OPTIONS,
        return_to=_RKEY_COMPLAINT,
        icon="😷",
        min_select=1,
        auto_confirm_ids=[COMPLAINT_OTHER_ID],
    )


async def _on_complaint(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        await _cancel(update, context)
        return

    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.complaint_ids    = result.ids
    session.complaint_labels = result.labels
    session.step = STEP_COMPLAINT_OTHER if COMPLAINT_OTHER_ID in result.ids else STEP_VITALS_TEMP
    session.save(context.user_data)

    if session.step == STEP_COMPLAINT_OTHER:
        text, kb = build_complaint_other_prompt(session)
        await _safe_reply(update, text, kb)
    else:
        text, kb = build_vitals_temp_prompt(session)
        await _safe_reply(update, text, kb)


async def _on_meds_supply(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        await _cancel(update, context)
        return

    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.meds_supply_ids    = result.ids
    session.meds_supply_labels = result.labels
    session.step = STEP_MEDS_SUPPLY_OTHER if MEDS_SUPPLY_OTHER_ID in result.ids else STEP_IMAGES
    session.save(context.user_data)

    if session.step == STEP_MEDS_SUPPLY_OTHER:
        text, kb = build_meds_supply_other_prompt(session)
        await _safe_reply(update, text, kb)
    else:
        await _open_images(update, context)


async def _open_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await uploads.open(
        update, context,
        title="ارفع صور الإجراء الطبي",
        return_to=_RKEY_IMAGES,
        icon="📷",
        allowed_types=["photo", "image_document"],
        min_files=0,
        max_files=10,
    )


async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        await _cancel(update, context)
        return

    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context)
        return

    session.images = [f.to_dict() for f in result.files]
    session.step   = STEP_NOTES
    session.save(context.user_data)

    text, kb = build_notes_prompt(session)
    await _safe_reply(update, text, kb)


# ── Text input handler ────────────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        return

    text_in = (update.message.text or "").strip()

    if session.step == STEP_DATE_CUSTOM:
        dt = parse_date_input(text_in)
        if dt is None:
            text, kb = build_date_calendar_prompt(error=True)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.created_at = dt.isoformat()
        session.step = STEP_PATIENT
        session.save(context.user_data)
        logger.info(f"[followup] date set manually: {dt.date()}  user={update.effective_user.id}")
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)
        return

    elif session.step == STEP_DEPT_OTHER:
        if text_in:
            save_custom_option(CTX_HC_DEPARTMENT, text_in)
            session.medical_department_labels = [
                text_in if lbl == "أخرى" else lbl
                for lbl in session.medical_department_labels
            ]
        session.step = STEP_PROC_TYPE
        session.save(context.user_data)
        await _open_proc_type(update, context)

    elif session.step == STEP_COMPLAINT_OTHER:
        if text_in:
            save_custom_option(CTX_FU_COMPLAINT, text_in)
            session.complaint_labels = [
                text_in if lbl == "أخرى" else lbl
                for lbl in session.complaint_labels
            ]
        session.step = STEP_VITALS_TEMP
        session.save(context.user_data)
        text, kb = build_vitals_temp_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_VITALS_TEMP:
        session.vitals_temp = text_in
        session.step        = STEP_VITALS_BP
        session.save(context.user_data)
        text, kb = build_vitals_bp_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_VITALS_BP:
        session.vitals_bp = text_in
        session.step      = STEP_VITALS_PULSE
        session.save(context.user_data)
        text, kb = build_vitals_pulse_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_VITALS_PULSE:
        session.vitals_pulse = text_in
        session.step         = STEP_VITALS_SPO2
        session.save(context.user_data)
        text, kb = build_vitals_spo2_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif session.step == STEP_VITALS_SPO2:
        session.vitals_spo2 = text_in
        session.step        = STEP_MEDS_SUPPLY
        session.save(context.user_data)
        custom_meds = load_custom_options(CTX_FU_MEDS_SUPPLY, icon="💊")
        await multiselect.open(
            update, context,
            title="الأدوية والمستلزمات",
            options=custom_meds + MEDS_SUPPLY_OPTIONS,
            return_to=_RKEY_MEDS_SUPPLY,
            icon="💊",
            min_select=0,
            auto_confirm_ids=[MEDS_SUPPLY_OTHER_ID],
        )

    elif session.step == STEP_MEDS_SUPPLY_OTHER:
        if text_in:
            save_custom_option(CTX_FU_MEDS_SUPPLY, text_in)
            session.meds_supply_labels = [
                text_in if lbl == "أخرى" else lbl
                for lbl in session.meds_supply_labels
            ]
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images(update, context)

    elif session.step == STEP_NOTES:
        session.notes = text_in
        session.step  = STEP_SPECIALIST
        session.save(context.user_data)
        text, kb = build_specialist_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Callback action handlers ──────────────────────────────────────────────────

async def _handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.notes = ""
    session.step  = STEP_SPECIALIST
    session.save(context.user_data)
    text, kb = build_specialist_prompt(session)
    await _safe_edit(query, text, kb)


async def _handle_specialist_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, sp_key: str
) -> None:
    query   = update.callback_query
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.specialist_name = SP_MAP.get(sp_key, "")
    session.step            = STEP_REVIEW
    session.save(context.user_data)
    text, kb = build_review(session)
    await _safe_edit(query, text, kb)


async def _handle_edit_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.notes = ""
    # Do NOT clear specialist_name — if already selected, edit_notes skips re-select
    session.step  = STEP_NOTES
    session.save(context.user_data)
    text, kb = build_notes_prompt(session)
    await _safe_edit(query, text, kb)


async def _handle_edit_specialist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.specialist_name = ""
    session.step            = STEP_SPECIALIST
    session.save(context.user_data)
    text, kb = build_specialist_prompt(session)
    await _safe_edit(query, text, kb)


async def _handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    # Snapshot all mutable state before any async work
    images_snap       = list(session.images)
    notes_snap        = session.notes
    specialist_snap   = session.specialist_name
    date_snap         = session.created_at
    dept_snap         = list(session.medical_department_labels)
    proc_snap         = list(session.procedure_type_labels)
    complaint_snap    = list(session.complaint_labels)
    vitals_temp_snap  = session.vitals_temp
    vitals_bp_snap    = session.vitals_bp
    vitals_pulse_snap = session.vitals_pulse
    vitals_spo2_snap  = session.vitals_spo2
    meds_snap         = list(session.meds_supply_labels)

    from modules.healthcare.medical_followup.models import save_followup_record
    try:
        saved = save_followup_record(
            patient_id=                session.patient_id,
            patient_name=              session.patient_name,
            medical_department_ids=    session.medical_department_ids,
            medical_department_labels= session.medical_department_labels,
            procedure_type_ids=        session.procedure_type_ids,
            procedure_type_labels=     session.procedure_type_labels,
            complaint_ids=             session.complaint_ids,
            complaint_labels=          session.complaint_labels,
            vitals_temp=               session.vitals_temp,
            vitals_bp=                 session.vitals_bp,
            vitals_pulse=              session.vitals_pulse,
            vitals_spo2=               session.vitals_spo2,
            meds_supply_ids=           session.meds_supply_ids,
            meds_supply_labels=        session.meds_supply_labels,
            images=                    session.images,
            notes=                     session.notes,
            specialist_name=           session.specialist_name,
            created_by=                update.effective_user.id if update.effective_user else None,
        )
    except Exception as exc:
        logger.error(f"[followup] DB save failed: {exc}")
        text, kb = build_error("فشل حفظ التقرير.")
        await _safe_edit(query, text, kb)
        return

    MedicalFollowupSession.clear(context.user_data)

    text, kb = build_success(saved.record_id, saved.patient_name, saved.image_count)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await _safe_reply(update, text, kb)

    # Build extra_sections for the published report
    dept_text   = "\n".join(f"  • {d}" for d in dept_snap)      if dept_snap      else "  —"
    proc_text   = "\n".join(f"  • {p}" for p in proc_snap)      if proc_snap      else "  —"
    cmp_text    = "\n".join(f"  • {c}" for c in complaint_snap) if complaint_snap else "  —"
    vitals_text = (
        f"  🌡️ الحرارة: {vitals_temp_snap}\n"
        f"  🩸 الضغط: {vitals_bp_snap}\n"
        f"  💓 النبض: {vitals_pulse_snap}\n"
        f"  🫁 الأكسجين: {vitals_spo2_snap}"
    )
    meds_text = "\n".join(f"  • {m}" for m in meds_snap) if meds_snap else "  —"

    extra_sections = [
        ("🏥 *القسم الطبي:*",             dept_text),
        ("📋 *نوع الإجراء:*",             proc_text),
        ("😷 *الشكوى الرئيسية:*",         cmp_text),
        ("❤️ *العلامات الحيوية:*",        vitals_text),
        ("💊 *الأدوية والمستلزمات:*",     meds_text),
    ]

    user = update.effective_user
    from modules.healthcare.report_publisher import HealthcarePublishData, publish as _publish
    await _publish(
        bot=context.bot,
        data=HealthcarePublishData(
            workflow_type=   "followup",
            workflow_label=  "المتابعة الطبية",
            workflow_icon=   "📋",
            record_id=       saved.record_id,
            patient_name=    saved.patient_name,
            extra_sections=  extra_sections,
            operations=      [],
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
    session = MedicalFollowupSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    async def _edit_or_reply(text, kb):
        try:
            if query:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
        except Exception:
            pass
        await _safe_reply(update, text, kb)

    if session.step in (STEP_DEPT_OTHER, STEP_PROC_TYPE):
        # Back to department multiselect
        session.step = STEP_DEPARTMENT
        session.save(context.user_data)
        from modules.healthcare.views import DEPARTMENT_OPTIONS
        custom_depts = load_custom_options(CTX_HC_DEPARTMENT, icon="🏥")
        await multiselect.open(update, context,
            title="القسم الطبي",
            options=custom_depts + DEPARTMENT_OPTIONS,
            return_to=_RKEY_DEPARTMENTS, icon="🏥", min_select=1,
            auto_confirm_ids=[DEPT_OTHER_ID])

    elif session.step in (STEP_COMPLAINT, STEP_COMPLAINT_OTHER):
        # Back to procedure type multiselect
        session.step = STEP_PROC_TYPE
        session.save(context.user_data)
        await _open_proc_type(update, context)

    elif session.step == STEP_VITALS_TEMP:
        # Back to complaint multiselect
        session.step = STEP_COMPLAINT
        session.save(context.user_data)
        custom_complaints = load_custom_options(CTX_FU_COMPLAINT, icon="😷")
        await multiselect.open(update, context,
            title="الشكوى الرئيسية",
            options=custom_complaints + COMPLAINT_OPTIONS,
            return_to=_RKEY_COMPLAINT, icon="😷", min_select=1,
            auto_confirm_ids=[COMPLAINT_OTHER_ID])

    elif session.step == STEP_VITALS_BP:
        session.step = STEP_VITALS_TEMP
        session.save(context.user_data)
        text, kb = build_vitals_temp_prompt(session)
        await _edit_or_reply(text, kb)

    elif session.step == STEP_VITALS_PULSE:
        session.step = STEP_VITALS_BP
        session.save(context.user_data)
        text, kb = build_vitals_bp_prompt(session)
        await _edit_or_reply(text, kb)

    elif session.step == STEP_VITALS_SPO2:
        session.step = STEP_VITALS_PULSE
        session.save(context.user_data)
        text, kb = build_vitals_pulse_prompt(session)
        await _edit_or_reply(text, kb)

    elif session.step in (STEP_MEDS_SUPPLY, STEP_MEDS_SUPPLY_OTHER):
        # Back to vitals_spo2 — re-show spo2 prompt
        session.step = STEP_VITALS_SPO2
        session.save(context.user_data)
        text, kb = build_vitals_spo2_prompt(session)
        await _edit_or_reply(text, kb)

    elif session.step == STEP_NOTES:
        # Back to images upload
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images(update, context)

    elif session.step == STEP_SPECIALIST:
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await _edit_or_reply(text, kb)

    else:
        await _cancel(update, context)


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    MedicalFollowupSession.clear(context.user_data)
    text, kb = build_cancelled()
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await _safe_reply(update, text, kb)


# ── HC callbacks (shared navigation) — late-binding to avoid circular imports ──

async def _handle_hc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        from modules.healthcare.views import build_healthcare_menu
        text, kb = build_healthcare_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await _safe_reply(update, text, kb)
    elif action == "followup":
        text, kb = build_followup_menu()
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            await _safe_reply(update, text, kb)
    else:
        logger.debug(f"[followup] hc: action not handled here: {action!r}")


# ── HCFU callback dispatcher ──────────────────────────────────────────────────

async def _handle_hcfu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    try:
        await query.answer()
    except Exception:
        pass

    action = data[len(HCFU) + 1:]   # strip "hcfu:"

    if action == "start":
        await _start_flow(update, context)
    elif action == "date_today":
        await _handle_date_today(update, context)
    elif action == "date_calendar":
        await _handle_date_calendar(update, context)
    elif action == "back":
        await _handle_back(update, context)
    elif action == "skip_notes":
        await _handle_skip_notes(update, context)
    elif action in SP_MAP:
        await _handle_specialist_choice(update, context, action)
    elif action == "edit_notes":
        await _handle_edit_notes(update, context)
    elif action == "edit_specialist":
        await _handle_edit_specialist(update, context)
    elif action == "confirm":
        await _handle_confirm(update, context)
    elif action == "cancel":
        await _cancel(update, context)
    elif action.startswith("cal_"):
        await _handle_cal_action(update, context, action)
    else:
        logger.warning(f"[followup] unknown hcfu: action: {action!r}")


# ── Registration ──────────────────────────────────────────────────────────────

def register_result_routes() -> None:
    _register_route(_RKEY_PATIENT,     _on_patient)
    _register_route(_RKEY_DEPARTMENTS, _on_department)
    _register_route(_RKEY_PROC_TYPE,   _on_proc_type)
    _register_route(_RKEY_COMPLAINT,   _on_complaint)
    _register_route(_RKEY_MEDS_SUPPLY, _on_meds_supply)
    _register_route(_RKEY_IMAGES,      _on_images)
    logger.info("[followup] result routes registered")


def register_handlers(app) -> None:
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input),
        group=2,  # unique group — avoids PTB v20 group-0 conflict with woundcare
    )
    app.add_handler(
        CallbackQueryHandler(_handle_hcfu_callback, pattern=rf"^{HCFU}:"),
        group=1,
    )
    app.add_handler(
        CallbackQueryHandler(_handle_hc_callback, pattern=rf"^{HC}:"),
        group=1,
    )
    logger.info("[followup] handlers registered")
