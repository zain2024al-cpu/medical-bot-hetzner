# modules/general_services/departures/flow.py
# Departure documentation — 7-step workflow with interactive review editor.
#
# Handler groups:
#   group 12   MessageHandler(TEXT) — text input
#   group 15   CallbackQueryHandler(^gsd:) — callbacks

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from shared.calendar_picker import build_calendar
from shared.multiselect import engine as multiselect
from shared.multiselect import Option
from shared.uploads import collector as uploads
from shared.result_router import register as _register_route
from modules.general_services.views import parse_date_input, build_gs_menu
from modules.general_services.constants import HOSPITAL_MAP, STAFF_MAP
from modules.general_services.arrivals.repository import (
    get_active_arrivals, expand_patient_ids_to_names, mark_patients_departed,
)
from modules.general_services.departures.session import (
    DepartureSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_SELECT_ARRIVALS, STEP_IMAGES,
    STEP_HOSPITAL, STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.general_services.departures.views import (
    GSD, GS,
    build_departures_menu,
    build_date_prompt, build_date_calendar_prompt,
    build_no_arrivals_prompt, build_images_prompt,
    build_hospital_prompt, build_notes_prompt, build_specialist_prompt,
    build_review, build_success, build_cancelled, build_error,
)

logger = logging.getLogger(__name__)

_RKEY_ARRIVALS = "gs.departures.arrivals"
_RKEY_IMAGES   = "gs.departures.images"

# ── Review edit routes ────────────────────────────────────────────────────────

_REVIEW_EDIT_ROUTES: dict[str, str] = {
    "edit_patients":   STEP_SELECT_ARRIVALS,
    "edit_images":     STEP_IMAGES,
    "edit_hospital":   STEP_HOSPITAL,
    "edit_notes":      STEP_NOTES,
    "edit_specialist": STEP_SPECIALIST,
}

_TEXT_STEPS = {STEP_DATE_CUSTOM, STEP_NOTES}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _safe_edit(update, text, kb):
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _cancel(update, context):
    DepartureSession.clear(context.user_data)
    text, kb = build_cancelled()
    await _safe_edit(update, text, kb)


async def _go_to_review(update, context):
    session = DepartureSession.load(context.user_data)
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


async def _open_arrivals_selector(update, context):
    """Open the multiselect showing active arrival patients."""
    session = DepartureSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    active = get_active_arrivals()
    if not active:
        text, kb = build_no_arrivals_prompt()
        await _safe_edit(update, text, kb)
        return

    session.step = STEP_SELECT_ARRIVALS
    session.save(context.user_data)

    options = [
        Option(id=str(entry.patient_id), label=entry.display_label)
        for entry in active
    ]
    preselected = [str(pid) for pid in session.arrival_patient_ids]
    await multiselect.open(
        update,
        context,
        title="اختر المغادرين",
        options=options,
        return_to=_RKEY_ARRIVALS,
        min_select=1,
        preselected_ids=preselected,
    )


async def _open_images_upload(update, context):
    session = DepartureSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_IMAGES
    session.save(context.user_data)
    await uploads.open(
        update,
        context,
        title="صور المغادرة",
        return_to=_RKEY_IMAGES,
    )


async def _open_edit_step(action, update, context):
    step = _REVIEW_EDIT_ROUTES.get(action)
    if step is None:
        return
    session = DepartureSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.edit_from_review = True
    session.step             = step
    session.save(context.user_data)
    await _route_to_step(session, step, update, context)


async def _route_to_step(session, step, update, context):
    if step == STEP_SELECT_ARRIVALS:
        await _open_arrivals_selector(update, context)
    elif step == STEP_IMAGES:
        await _open_images_upload(update, context)
    elif step == STEP_HOSPITAL:
        text, kb = build_hospital_prompt()
        await _safe_edit(update, text, kb)
    elif step == STEP_NOTES:
        text, kb = build_notes_prompt(session)
        await _safe_edit(update, text, kb)
    elif step == STEP_SPECIALIST:
        text, kb = build_specialist_prompt(session)
        await _safe_edit(update, text, kb)


# ── Callback dispatcher ───────────────────────────────────────────────────────

async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data   = query.data or ""
    prefix = f"{GSD}:"
    if not data.startswith(prefix):
        return
    action = data[len(prefix):]

    # ── GS navigation ─────────────────────────────────────────────────────────
    if action == "departures":
        text, kb = build_departures_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "main":
        text, kb = build_gs_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Start ─────────────────────────────────────────────────────────────────
    if action == "start":
        session = DepartureSession.create(context.user_data)
        text, kb = build_date_prompt()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Review edit routes ────────────────────────────────────────────────────
    if action in _REVIEW_EDIT_ROUTES:
        await _open_edit_step(action, update, context)
        return

    # ── Date ──────────────────────────────────────────────────────────────────
    if action == "date_today":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        session.created_at = datetime.utcnow().isoformat()
        session.save(context.user_data)
        await _open_arrivals_selector(update, context)
        return

    if action == "date_calendar":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_DATE_CUSTOM
        session.save(context.user_data)
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=GSD,
            back_callback=f"{GSD}:start",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action.startswith("cal_nav:"):
        parts = action.split(":")
        try:
            y, m = int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            return
        cal_text, cal_kb = build_calendar(
            year=y, month=m,
            callback_prefix=GSD,
            back_callback=f"{GSD}:start",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action.startswith("cal_pick:"):
        parts = action.split(":")
        try:
            from datetime import datetime
            dt = datetime(int(parts[1]), int(parts[2]), int(parts[3]))
        except (IndexError, ValueError):
            return
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.created_at = dt.isoformat()
        session.save(context.user_data)
        await _open_arrivals_selector(update, context)
        return

    # ── Images ────────────────────────────────────────────────────────────────
    if action in ("images_done", "skip_images"):
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_HOSPITAL
        session.save(context.user_data)
        text, kb = build_hospital_prompt()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Hospital ──────────────────────────────────────────────────────────────
    if action.startswith("hospital_"):
        hid = action[len("hospital_"):]
        label = HOSPITAL_MAP.get(hid, "")
        if not label:
            return
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.hospital_id    = hid
        session.hospital_label = label
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Specialist ────────────────────────────────────────────────────────────
    if action.startswith("specialist_"):
        sid = action[len("specialist_"):]
        label = STAFF_MAP.get(sid, "")
        if not label:
            return
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.specialist_id    = sid
        session.specialist_label = label
        session.edit_from_review = False
        if session.step == STEP_SPECIALIST or session.edit_from_review:
            session.step = STEP_REVIEW
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    # ── Skip notes ────────────────────────────────────────────────────────────
    if action == "skip_notes":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.notes = ""
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_SPECIALIST
        session.save(context.user_data)
        text, kb = build_specialist_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Back navigation ────────────────────────────────────────────────────────
    if action == "back_to_patients":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        if session.edit_from_review:
            await _go_to_review(update, context); return
        await _open_arrivals_selector(update, context)
        return

    if action == "back_to_images":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_IMAGES
        session.save(context.user_data)
        text, kb = build_images_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "back_to_hospital":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_HOSPITAL
        session.save(context.user_data)
        text, kb = build_hospital_prompt()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "back_to_notes":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Confirm / Cancel ──────────────────────────────────────────────────────
    if action == "confirm":
        session = DepartureSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        try:
            from modules.general_services.departures.models import save_departure_record
            saved = save_departure_record(
                arrival_patient_ids= session.arrival_patient_ids,
                patients_text=       session.patients_text,
                hospital_id=         session.hospital_id,
                hospital_label=      session.hospital_label,
                images=              session.images,
                notes=               session.notes,
                specialist_id=       session.specialist_id,
                specialist_label=    session.specialist_label,
                created_by=          update.effective_user.id if update.effective_user else None,
            )
            if session.arrival_patient_ids:
                mark_patients_departed(session.arrival_patient_ids, saved.record_id)
        except Exception as exc:
            logger.error(f"[departures] save failed: {exc}", exc_info=True)
            text, kb = build_error("فشل حفظ البيانات. حاول مجدداً.")
            await _safe_edit(update, text, kb)
            return

        from modules.general_services.views import format_image_count
        imgs  = format_image_count(session.image_count)
        notes = session.notes or "لا توجد ملاحظات"
        user  = update.effective_user
        body  = [
            f"👥 *المغادرون:*  {session.patients_text or '—'}",
            f"🏥 *الجهة الموصلة:*  {session.hospital_label or '—'}",
            f"👨‍⚕️ *المسؤول:*  {session.specialist_label or '—'}",
            f"📎 *الوثائق:*  {imgs}",
            "─────────────────",
            f"📝 *الملاحظات:*  {notes}",
        ]

        from modules.general_services.report_publisher import GSPublishData, publish as _publish
        await _publish(
            bot=context.bot,
            data=GSPublishData(
                workflow_type="departures",
                workflow_label="تقرير مغادرة جديد",
                workflow_icon="🛫",
                body_lines=body,
                images=session.images,
                created_by_id=  user.id        if user else None,
                created_by_name=user.full_name if user else "",
                record_date=session.created_at,
            ),
        )

        DepartureSession.clear(context.user_data)
        text, kb = build_success(saved.record_id, saved.hospital_label)
        await _safe_edit(update, text, kb)
        return

    if action == "cancel":
        await _cancel(update, context)
        return


# ── Result routes ─────────────────────────────────────────────────────────────

async def _on_arrivals_selected(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = DepartureSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    if result.cancelled:
        if session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    # ids are stored as strings in multiselect Option; convert to int
    patient_ids = [int(oid) for oid in result.ids if oid.isdigit()]
    names       = expand_patient_ids_to_names(patient_ids)

    session.arrival_patient_ids = patient_ids
    session.patients_text       = "\n".join(names)

    if session.edit_from_review:
        session.save(context.user_data)
        await _go_to_review(update, context); return

    session.step = STEP_IMAGES
    session.save(context.user_data)
    await _open_images_upload(update, context)


async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = DepartureSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    if result.cancelled:
        if session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    session.images = [f.to_dict() if hasattr(f, "to_dict") else f for f in result.files]
    if session.edit_from_review:
        await _go_to_review(update, context); return

    session.step = STEP_HOSPITAL
    session.save(context.user_data)
    text, kb = build_hospital_prompt()
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Text handler (group 12) ───────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = DepartureSession.load(context.user_data)
    if session is None or session.step not in _TEXT_STEPS:
        return

    text = (update.message.text or "").strip()
    step = session.step

    if step == STEP_DATE_CUSTOM:
        dt = parse_date_input(text)
        if dt is None:
            prompt, kb = build_date_calendar_prompt(error=True)
            await update.message.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
            return
        session.created_at = dt.isoformat()
        session.save(context.user_data)
        await _open_arrivals_selector(update, context)
        return

    if step == STEP_NOTES:
        session.notes = text
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_SPECIALIST
        session.save(context.user_data)
        prompt, kb = build_specialist_prompt(session)
        await update.message.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
        return


# ── Registration ──────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^gsd:"),
        group=15,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input),
        group=12,
    )


def register_result_routes() -> None:
    _register_route(_RKEY_ARRIVALS, _on_arrivals_selected)
    _register_route(_RKEY_IMAGES,   _on_images)
