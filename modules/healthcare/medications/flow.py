# modules/healthcare/medications/flow.py
# Medication dispensing — official 10-step operational workflow.
#
#   1.  التاريخ          — اليوم أو من التقويم (كبقية وحدات الرعاية الصحية)
#   2.  اسم المريض       — patient_selector
#   3.  القسم            — DEPARTMENT_OPTIONS multiselect (+ DEPT_OTHER branch for أخرى)
#   4.  عدد الأصناف      — free text input, رقم أو وصف (STEP_COUNT)
#   5.  صورة الوصفة      — uploads (optional, 0-10)
#   6.  جهة الصرف        — 2-button callback: الصيدلية / المخزن (REQUIRED, no skip)
#   7.  ملاحظات          — text input (optional)
#   8.  اسم الصحي        — fixed 3-name single-select callback (REQUIRED, no skip)
#   9.  مراجعة نهائية   — review screen
#   10. نشر             — DB save + publish

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.result_router import register as _register_route
from shared.calendar_picker import build_calendar
from shared.selectors.patient_selector import selector as patient_selector
from shared.multiselect import engine as multiselect
from shared.uploads import collector as uploads

from modules.healthcare.views import DEPARTMENT_OPTIONS
from modules.healthcare.custom_options import (
    save_custom_option, load_custom_options, CTX_HC_DEPARTMENT,
)
from modules.healthcare.medications.constants import (
    SP_MAP, DEPT_OTHER_ID, DISPENSE_SOURCE_MAP,
)
from modules.healthcare.medications.session import (
    MedicationSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT, STEP_DEPARTMENT, STEP_DEPT_OTHER,
    STEP_COUNT, STEP_IMAGES, STEP_DISPENSE_SOURCE, STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.healthcare.medications.views import (
    HC, HCMED,
    build_date_prompt, build_date_calendar_prompt, build_dept_other_prompt,
    build_count_prompt, build_dispense_source_prompt, build_notes_prompt,
    build_specialist_prompt, build_review, build_success, build_cancelled, build_error,
)
from modules.healthcare.views import parse_date_input

logger = logging.getLogger(__name__)

# ── Result router keys ────────────────────────────────────────────────────────

_RKEY_PATIENT     = "hc.medications.patient"
_RKEY_DEPARTMENTS = "hc.medications.departments"
_RKEY_IMAGES      = "hc.medications.images"

_MODULE_KEY = "healthcare"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


# ── Review edit routes ────────────────────────────────────────────────────────

_REVIEW_EDIT_ROUTES: dict[str, str] = {
    "edit_dept":       STEP_DEPARTMENT,
    "edit_count":      STEP_COUNT,
    "edit_images":     STEP_IMAGES,
    "edit_source":     STEP_DISPENSE_SOURCE,
    "edit_notes":      STEP_NOTES,
    "edit_specialist": STEP_SPECIALIST,
}


# ── _go_to_review — shared helper ─────────────────────────────────────────────

async def _go_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = MedicationSession.load(context.user_data)
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
    session: "MedicationSession",
    step: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query

    async def _safe_edit(text, kb):
        if query:
            try:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
            except Exception:
                pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    if step == STEP_DEPARTMENT:
        custom_depts = load_custom_options(CTX_HC_DEPARTMENT)
        await multiselect.open(
            update, context,
            title="اختر القسم الطبي",
            options=custom_depts + DEPARTMENT_OPTIONS,
            return_to=_RKEY_DEPARTMENTS,
            icon="🏥", min_select=1,
            auto_confirm_ids=[DEPT_OTHER_ID],
            preselected_ids=session.medical_department_ids,
        )
    elif step == STEP_COUNT:
        text, kb = build_count_prompt(session)
        await _safe_edit(text, kb)
    elif step == STEP_IMAGES:
        await _open_images_upload(update, context)
    elif step == STEP_DISPENSE_SOURCE:
        text, kb = build_dispense_source_prompt(session)
        await _safe_edit(text, kb)
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
    session = MedicationSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.edit_from_review = True
    session.step             = step
    session.save(context.user_data)
    await _route_to_edit_step(session, step, update, context)


# ── Step 1: start — show date confirmation screen ────────────────────────────

async def _start_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    MedicationSession.create(context.user_data)
    logger.info(f"[medications] flow started  user={update.effective_user.id}")
    text, kb = build_date_prompt()
    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 1 → 2: date confirmed — open patient selector ───────────────────────

async def _handle_date_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose today's date — advance to patient selector."""
    session = MedicationSession.load(context.user_data)
    if session is None:
        session = MedicationSession.create(context.user_data)
    session.step = STEP_PATIENT
    session.save(context.user_data)
    logger.info(f"[medications] date confirmed (today)  user={update.effective_user.id}")
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT, include_pharmacy=True)


async def _handle_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User chose calendar date — show inline month calendar."""
    from datetime import datetime
    query = update.callback_query
    session = MedicationSession.load(context.user_data)
    if session is None:
        session = MedicationSession.create(context.user_data)
    session.step = STEP_DATE_CUSTOM
    session.save(context.user_data)
    now = datetime.utcnow()
    text, kb = build_calendar(now.year, now.month, HCMED, f"{HCMED}:start")
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
        text, kb = build_calendar(y, m, HCMED, f"{HCMED}:start")
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
        session = MedicationSession.load(context.user_data)
        if session is None:
            session = MedicationSession.create(context.user_data)
        session.created_at = datetime(y, m, d).isoformat()
        session.step       = STEP_PATIENT
        session.save(context.user_data)
        logger.info(
            f"[medications] date picked: {y}-{m:02d}-{d:02d}  user={update.effective_user.id}"
        )
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT, include_pharmacy=True)


# ── Step 2: patient selected ──────────────────────────────────────────────────


async def _on_patient(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or getattr(result, "cancelled", False):
        await _cancel(update, context); return
    session = MedicationSession.load(context.user_data)
    if session is None:
        session = MedicationSession.create(context.user_data)
    patient              = result.patient if hasattr(result, "patient") else result
    session.patient_id   = patient.id   if patient else None
    session.patient_name = patient.name if patient else ""
    session.step         = STEP_DEPARTMENT
    session.save(context.user_data)
    custom_depts = load_custom_options(CTX_HC_DEPARTMENT)
    await multiselect.open(
        update, context,
        title="اختر القسم الطبي",
        options=custom_depts + DEPARTMENT_OPTIONS,
        return_to=_RKEY_DEPARTMENTS,
        icon="🏥",
        min_select=1,
        auto_confirm_ids=[DEPT_OTHER_ID],
    )


# ── Step 3: department selected ───────────────────────────────────────────────

async def _on_department(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = MedicationSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return
    session = MedicationSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    session.medical_department_ids    = result.ids
    session.medical_department_labels = result.labels

    if DEPT_OTHER_ID in result.ids:
        session.step = STEP_DEPT_OTHER
        session.save(context.user_data)
        text, kb = build_dept_other_prompt(session)
        try:
            await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as exc:
            logger.error(f"[medications] dept_other prompt failed: {exc}")
        return

    if session.edit_from_review:
        await _go_to_review(update, context)
        return

    session.step = STEP_COUNT
    session.save(context.user_data)
    text, kb = build_count_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 5: images collected ──────────────────────────────────────────────────

async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if result is None or result.cancelled:
        session = MedicationSession.load(context.user_data)
        if session and session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return
    session = MedicationSession.load(context.user_data)
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
        logger.error(f"[medications] notes prompt failed: {exc}")


# ── Step 6: dispense source selected ─────────────────────────────────────────

async def _handle_dispense_source(
    update: Update, context: ContextTypes.DEFAULT_TYPE, source_label: str
) -> None:
    """Called when user taps الصيدلية or المخزن button."""
    query   = update.callback_query
    session = MedicationSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.dispense_source = source_label

    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    session.step = STEP_IMAGES
    session.save(context.user_data)
    await _open_images_upload(update, context)


# ── Shared helper ─────────────────────────────────────────────────────────────

async def _open_images_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await uploads.open(
        update, context,
        title="ارفع صورة الوصفة / الأدوية (اختياري)",
        return_to=_RKEY_IMAGES,
        icon="📷",
        allowed_types=["photo", "image_document"],
        min_files=0,
        max_files=10,
    )


# ── Text input handler (steps: DEPT_OTHER, COUNT, NOTES) ─────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ✅ الحماية داخل المعالِج نفسه — معالِج نصوص عام (يطابق أي رسالة نصية).
    if not update.effective_user or not _is_authorized(update.effective_user.id):
        return
    session = MedicationSession.load(context.user_data)
    if session is None:
        return

    # ── 1b. Manual date entry ──
    if session.step == STEP_DATE_CUSTOM:
        dt = parse_date_input(update.message.text or "")
        if dt is None:
            text, kb = build_date_calendar_prompt(error=True)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.created_at = dt.isoformat()
        session.step = STEP_PATIENT
        session.save(context.user_data)
        logger.info(f"[medications] date set manually: {dt.date()}  user={update.effective_user.id}")
        await patient_selector.enter(update, context, return_to=_RKEY_PATIENT, include_pharmacy=True)
        return

    # ── 3b. Department free-text ("أخرى") ──
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
        session.step = STEP_COUNT
        session.save(context.user_data)
        text, kb = build_count_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # ── 4. عدد الأصناف — نص حر (رقم أو وصف الأصناف)؛ يُرفَض الفارغ فقط ──
    elif session.step == STEP_COUNT:
        raw = (update.message.text or "").strip()
        if not raw:
            text, kb = build_count_prompt(session, error=True)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        session.item_count = raw
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_DISPENSE_SOURCE
        session.save(context.user_data)
        text, kb = build_dispense_source_prompt(session)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # ── 7. ملاحظات ──
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

async def _handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query   = update.callback_query
    session = MedicationSession.load(context.user_data)
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
    session = MedicationSession.load(context.user_data)
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
    session = MedicationSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    images_snap          = list(session.images)
    notes_snap           = session.notes
    specialist_snap      = session.specialist_name
    date_snap            = session.created_at
    dept_snap            = list(session.medical_department_labels)
    dispense_source_snap = session.dispense_source

    _created_by = update.effective_user.id if update.effective_user else None
    logger.info(
        "[healthcare.publish] model=MedicationRecord  payload:"
        f"  patient_id={session.patient_id}"
        f"  patient_name={session.patient_name!r}"
        f"  depts={session.medical_department_labels}"
        f"  item_count={session.item_count}"
        f"  dispense_source={session.dispense_source!r}"
        f"  images={len(session.images)}"
        f"  notes={session.notes!r}"
        f"  specialist={session.specialist_name!r}"
        f"  created_by={_created_by}"
    )
    from modules.healthcare.medications.models import save_medication_record
    try:
        saved = save_medication_record(
            patient_id=                session.patient_id,
            patient_name=              session.patient_name,
            medical_department_ids=    session.medical_department_ids,
            medical_department_labels= session.medical_department_labels,
            item_count=                session.item_count,
            dispense_source=           session.dispense_source,
            images=                    session.images,
            notes=                     session.notes,
            specialist_name=           session.specialist_name,
            created_by=                _created_by,
        )
        logger.info(f"[healthcare.publish] save OK  model=MedicationRecord  id={saved.record_id}  patient={saved.patient_name!r}")
    except Exception:
        logger.exception(
            f"[healthcare.publish] FAILED  model=MedicationRecord"
            f"  patient_id={session.patient_id}  patient_name={session.patient_name!r}"
            f"  dispense_source={session.dispense_source!r}"
        )
        text, kb = build_error("فشل حفظ التقرير.")
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        return

    MedicationSession.clear(context.user_data)

    text, kb = build_success(saved.record_id, saved.patient_name, saved.image_count)
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # Build extra_sections for the published report
    dept_text = "\n".join(f"  • {d}" for d in dept_snap) if dept_snap else "  —"
    extra_sections = [
        ("🏥 *القسم الطبي:*",                        dept_text),
        (f"🔢 *عدد الأصناف:*  {saved.item_count}",   ""),
        (f"🏪 *جهة الصرف:*   {dispense_source_snap or '—'}", ""),
    ]

    user = update.effective_user
    from modules.healthcare.report_publisher import HealthcarePublishData, publish as _publish
    await _publish(
        bot=context.bot,
        data=HealthcarePublishData(
            workflow_type=   "medications",
            workflow_label=  "صرف الأدوية",
            workflow_icon=   "💊",
            record_id=       saved.record_id,
            patient_name=    saved.patient_name,
            extra_sections=  extra_sections,
            operations=      [],          # no medication categories in official workflow
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
    session = MedicationSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    async def _edit_or_reply(text, kb):
        try:
            if query:
                await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown"); return
        except Exception:
            pass
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    # ── edit-from-review mode ──
    if session.edit_from_review:
        if session.step == STEP_DEPT_OTHER:
            session.step = STEP_DEPARTMENT
            session.save(context.user_data)
            custom_depts = load_custom_options(CTX_HC_DEPARTMENT)
            await multiselect.open(update, context,
                title="اختر القسم الطبي",
                options=custom_depts + DEPARTMENT_OPTIONS,
                return_to=_RKEY_DEPARTMENTS, icon="🏥", min_select=1,
                auto_confirm_ids=[DEPT_OTHER_ID],
                preselected_ids=session.medical_department_ids)
        else:
            await _go_to_review(update, context)
        return

    # ── Normal back navigation ────────────────────────────────────────────────
    if session.step in (STEP_DEPT_OTHER, STEP_COUNT):
        session.step = STEP_DEPARTMENT
        session.save(context.user_data)
        custom_depts = load_custom_options(CTX_HC_DEPARTMENT)
        await multiselect.open(update, context,
            title="اختر القسم الطبي",
            options=custom_depts + DEPARTMENT_OPTIONS,
            return_to=_RKEY_DEPARTMENTS, icon="🏥", min_select=1)

    elif session.step == STEP_DISPENSE_SOURCE:
        session.step = STEP_COUNT
        session.save(context.user_data)
        text, kb = build_count_prompt(session)
        await _edit_or_reply(text, kb)

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


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    MedicationSession.clear(context.user_data)
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
        logger.error(f"[medications] cancel failed: {exc}")


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        logger.warning(f"[medications] 🚫 blocked unauthorized user={getattr(query.from_user, 'id', '?')}")
        return
    action = data[len(HCMED) + 1:]

    # Dispense source selection (disp_pharmacy / disp_warehouse)
    if action in DISPENSE_SOURCE_MAP:
        await _handle_dispense_source(update, context, DISPENSE_SOURCE_MAP[action])
        return

    # Fixed staff selection (sp_sarour / sp_fadl / sp_zakariya)
    if action in SP_MAP:
        await _handle_select_specialist(update, context, SP_MAP[action])
        return

    # Calendar widget (cal_pick / cal_prev / cal_next / cal_noop)
    if action.startswith("cal_"):
        await _handle_cal_action(update, context, action)
        return

    if action in _REVIEW_EDIT_ROUTES:
        await _open_edit_step(action, update, context)
        return

    dispatch = {
        "start":         _start_flow,
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
        logger.warning(f"[medications] unknown action: {action!r}")


# ── Registration ──────────────────────────────────────────────────────────────

def register_result_routes() -> None:
    _register_route(_RKEY_PATIENT,     _on_patient)
    _register_route(_RKEY_DEPARTMENTS, _on_department)
    _register_route(_RKEY_IMAGES,      _on_images)
    logger.info("[medications] result routes registered")


def register_handlers(app) -> None:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input), group=4)  # unique group — avoids PTB v20 group-0 conflict
    app.add_handler(CallbackQueryHandler(_handle_callback, pattern=rf"^{HCMED}:"), group=1)
    logger.info("[medications] handlers registered")
