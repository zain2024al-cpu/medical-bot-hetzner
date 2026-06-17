# modules/general_services/public_services/flow.py
# Public / administrative service documentation — 8-step workflow.
#
# Handler groups:
#   group 14   MessageHandler(TEXT) — text input
#   group 15   CallbackQueryHandler(^gsp:) — callbacks

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from shared.calendar_picker import build_calendar
from shared.selectors.patient_selector import selector as patient_selector
from shared.uploads import collector as uploads
from shared.result_router import register as _register_route
from shared.selectors import result_router as _patient_router
from modules.general_services.views import parse_date_input, build_gs_menu
from modules.general_services.constants import STAFF_MAP
from modules.general_services.public_services.session import (
    PublicServiceSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT, STEP_SERVICE_TYPE,
    STEP_COUNT, STEP_IMAGES, STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.general_services.public_services.views import (
    GSP, GS,
    build_public_services_menu,
    build_date_prompt, build_date_calendar_prompt,
    build_patient_prompt, build_service_type_prompt,
    build_count_prompt, build_notes_prompt,
    build_specialist_prompt,
    build_review, build_success, build_cancelled, build_error,
)

logger = logging.getLogger(__name__)

_RKEY_PATIENT = "gs.public.patient"
_RKEY_IMAGES  = "gs.public.images"

# ── Review edit routes ────────────────────────────────────────────────────────

_REVIEW_EDIT_ROUTES: dict[str, str] = {
    "edit_patient":       STEP_PATIENT,
    "edit_service_type":  STEP_SERVICE_TYPE,
    "edit_count":         STEP_COUNT,
    "edit_images":        STEP_IMAGES,
    "edit_notes":         STEP_NOTES,
    "edit_specialist":    STEP_SPECIALIST,
}

_TEXT_STEPS = {STEP_DATE_CUSTOM, STEP_SERVICE_TYPE, STEP_COUNT, STEP_NOTES}


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
    PublicServiceSession.clear(context.user_data)
    text, kb = build_cancelled()
    await _safe_edit(update, text, kb)


async def _go_to_review(update, context):
    session = PublicServiceSession.load(context.user_data)
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


async def _open_patient_selector(update, context):
    session = PublicServiceSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_PATIENT
    session.save(context.user_data)
    await patient_selector.enter(update, context, return_to=_RKEY_PATIENT)


async def _show_service_type_prompt(update, context):
    session = PublicServiceSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_SERVICE_TYPE
    session.save(context.user_data)
    text, kb = build_service_type_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _open_images_upload(update, context):
    session = PublicServiceSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_IMAGES
    session.save(context.user_data)
    await uploads.open(
        update,
        context,
        title="صور الخدمة",
        return_to=_RKEY_IMAGES,
    )


async def _open_edit_step(action, update, context):
    step = _REVIEW_EDIT_ROUTES.get(action)
    if step is None:
        return
    session = PublicServiceSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.edit_from_review = True
    session.step             = step
    session.save(context.user_data)
    if step == STEP_PATIENT:
        await _open_patient_selector(update, context)
    elif step == STEP_SERVICE_TYPE:
        await _show_service_type_prompt(update, context)
    elif step == STEP_COUNT:
        text, kb = build_count_prompt(session)
        await _safe_edit(update, text, kb)
    elif step == STEP_IMAGES:
        await _open_images_upload(update, context)
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
    prefix = f"{GSP}:"
    if not data.startswith(prefix):
        return
    action = data[len(prefix):]

    # ── GS navigation ─────────────────────────────────────────────────────────
    if action == "public_services":
        text, kb = build_public_services_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "main":
        text, kb = build_gs_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Start ─────────────────────────────────────────────────────────────────
    if action == "start":
        session = PublicServiceSession.create(context.user_data)
        text, kb = build_date_prompt()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Review edit routes ────────────────────────────────────────────────────
    if action in _REVIEW_EDIT_ROUTES:
        await _open_edit_step(action, update, context)
        return

    # ── Date ──────────────────────────────────────────────────────────────────
    if action == "date_today":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        session.created_at = datetime.utcnow().isoformat()
        session.step = STEP_PATIENT
        session.save(context.user_data)
        await _open_patient_selector(update, context)
        return

    if action == "date_calendar":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_DATE_CUSTOM
        session.save(context.user_data)
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=GSP,
            back_callback=f"{GSP}:start",
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
            callback_prefix=GSP,
            back_callback=f"{GSP}:start",
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
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.created_at = dt.isoformat()
        session.step = STEP_PATIENT
        session.save(context.user_data)
        await _open_patient_selector(update, context)
        return

    # ── Images done ────────────────────────────────────────────────────────────
    if action == "images_done":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Skip notes ─────────────────────────────────────────────────────────────
    if action == "skip_notes":
        session = PublicServiceSession.load(context.user_data)
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

    # ── Specialist ────────────────────────────────────────────────────────────
    if action.startswith("specialist_"):
        sid = action[len("specialist_"):]
        label = STAFF_MAP.get(sid, "")
        if not label:
            return
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.specialist_id    = sid
        session.specialist_label = label
        session.edit_from_review = False
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    # ── Back navigation ────────────────────────────────────────────────────────
    if action == "back_to_patient":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        if session.edit_from_review:
            await _go_to_review(update, context); return
        await _open_patient_selector(update, context)
        return

    if action == "back_to_service_type":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        if session.edit_from_review:
            await _go_to_review(update, context); return
        await _show_service_type_prompt(update, context)
        return

    if action == "back_to_count":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_COUNT
        session.save(context.user_data)
        text, kb = build_count_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "back_to_images":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _open_images_upload(update, context)
        return

    if action == "back_to_notes":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_notes_prompt(session)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Confirm / Cancel ──────────────────────────────────────────────────────
    if action == "confirm":
        session = PublicServiceSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        try:
            from modules.general_services.public_services.models import save_public_service_record
            saved = save_public_service_record(
                patient_id=          session.patient_id,
                patient_name=        session.patient_name,
                service_type_labels= session.service_type_labels,
                item_count=          session.item_count,
                images=              session.images,
                notes=               session.notes,
                specialist_id=       session.specialist_id,
                specialist_label=    session.specialist_label,
                created_by=          update.effective_user.id if update.effective_user else None,
            )
        except Exception as exc:
            logger.error(f"[public_services] save failed: {exc}", exc_info=True)
            text, kb = build_error("فشل حفظ البيانات. حاول مجدداً.")
            await _safe_edit(update, text, kb)
            return

        from modules.general_services.views import format_image_count
        svc   = session.service_type_labels[0] if session.service_type_labels else "—"
        imgs  = format_image_count(session.image_count)
        notes = session.notes or "لا توجد ملاحظات"
        user  = update.effective_user
        body  = [
            f"👤 *المريض:*  {session.patient_name or '—'}",
            f"🧾 *نوع الخدمة:*  {svc}",
            f"🔢 *عدد البنود:*  {session.item_count}",
            f"📎 *الوثائق:*  {imgs}",
            f"👨‍⚕️ *المختص:*  {session.specialist_label or '—'}",
            "─────────────────",
            f"📝 *الملاحظات:*  {notes}",
        ]

        from modules.general_services.report_publisher import GSPublishData, publish as _publish
        await _publish(
            bot=context.bot,
            data=GSPublishData(
                workflow_type="public_services",
                workflow_label="تقرير خدمة عامة جديد",
                workflow_icon="🧾",
                body_lines=body,
                images=session.images,
                created_by_id=  user.id        if user else None,
                created_by_name=user.full_name if user else "",
                record_date=session.created_at,
            ),
        )

        PublicServiceSession.clear(context.user_data)
        text, kb = build_success(saved.record_id, saved.patient_name)
        await _safe_edit(update, text, kb)
        return

    if action == "cancel":
        await _cancel(update, context)
        return


# ── Result routes ─────────────────────────────────────────────────────────────

async def _on_patient(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = PublicServiceSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    if result.cancelled:
        if session.edit_from_review:
            await _go_to_review(update, context)
        else:
            await _cancel(update, context)
        return

    session.patient_id   = result.patient.id   if result.patient else None
    session.patient_name = result.patient.name if result.patient else ""
    session.save(context.user_data)
    if session.edit_from_review:
        await _go_to_review(update, context); return
    await _show_service_type_prompt(update, context)


async def _on_images(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = PublicServiceSession.load(context.user_data)
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
    session.step = STEP_NOTES
    session.save(context.user_data)
    text, kb = build_notes_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Text handler (group 14) ───────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = PublicServiceSession.load(context.user_data)
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
        session.step = STEP_PATIENT
        session.save(context.user_data)
        await _open_patient_selector(update, context)
        return

    if step == STEP_SERVICE_TYPE:
        if not text:
            await update.message.reply_text("⚠️ نوع الخدمة لا يمكن أن يكون فارغاً.")
            return
        session.service_type_labels = [text]
        session.save(context.user_data)
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_COUNT
        session.save(context.user_data)
        prompt, kb = build_count_prompt(session)
        await update.message.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
        return

    if step == STEP_COUNT:
        try:
            n = int(text)
            assert n >= 0
        except (ValueError, AssertionError):
            await update.message.reply_text("⚠️ أدخل رقماً صحيحاً (0 أو أكثر).")
            return
        session.item_count = n
        if session.edit_from_review:
            await _go_to_review(update, context); return
        session.step = STEP_IMAGES
        session.save(context.user_data)
        await _open_images_upload(update, context)
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
        CallbackQueryHandler(_dispatch_callback, pattern=r"^gsp:"),
        group=15,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input),
        group=14,
    )


def register_result_routes() -> None:
    _patient_router.register(_RKEY_PATIENT, _on_patient)
    _register_route(_RKEY_IMAGES, _on_images)
