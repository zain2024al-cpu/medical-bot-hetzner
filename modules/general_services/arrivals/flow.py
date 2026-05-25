# modules/general_services/arrivals/flow.py
# Arrivals batch registration — nested patient + companion loop.
#
# Handler groups:
#   group 10  MessageHandler(TEXT)  — text input steps
#   group 11  MessageHandler(PHOTO | Document.IMAGE) — single-photo steps
#   group 15  CallbackQueryHandler(^gsa:) — all arrivals callbacks

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from shared.calendar_picker import build_calendar
from modules.general_services.views import parse_date_input, build_gs_menu
from modules.general_services.constants import HOSPITAL_MAP, STAFF_MAP
from modules.general_services.arrivals.session import (
    ArrivalSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_HOSPITAL, STEP_SPECIALIST,
    STEP_PATIENT_COUNT,
    STEP_P_NAME, STEP_P_VISA_EXPIRY, STEP_P_HAS_COMPANION,
    STEP_P_PASSPORT, STEP_P_VISA, STEP_P_RESIDENCE, STEP_P_RESIDENCE_EXPIRY,
    STEP_BATCH_NOTES,
    STEP_C_NAME, STEP_C_VISA_EXPIRY, STEP_C_PASSPORT, STEP_C_VISA,
    STEP_REVIEW,
)
from modules.general_services.arrivals.views import (
    GSA, GS,
    build_arrivals_menu,
    build_date_prompt, build_date_calendar_prompt,
    build_hospital_prompt, build_specialist_prompt,
    build_patient_count_prompt,
    build_p_name_prompt, build_p_visa_expiry_prompt,
    build_p_has_companion_prompt,
    build_p_passport_prompt, build_p_visa_prompt,
    build_p_residence_prompt, build_p_residence_expiry_prompt,
    build_batch_notes_prompt,
    build_c_name_prompt, build_c_visa_expiry_prompt, build_c_passport_prompt, build_c_visa_prompt,
    build_review, build_success, build_cancelled, build_error,
)

logger = logging.getLogger(__name__)


def _session_debug_str(session: ArrivalSession) -> str:
    """Compact one-line session snapshot — included in every exception log."""
    return (
        f"step={session.step!r}"
        f"  p_idx={session.patient_index}/{session.patient_count}"
        f"  p_name={session.current_patient.get('name', '—')!r}"
        f"  completed={len(session.completed_patients)}"
        f"  has_companion={session.current_patient.get('has_companion', '?')}"
    )


# ── Photo steps — active in group 11 ─────────────────────────────────────────
_PHOTO_STEPS = {
    STEP_P_PASSPORT,
    STEP_P_VISA,
    STEP_P_RESIDENCE,
    STEP_C_PASSPORT,
    STEP_C_VISA,
}

# ── Text steps — active in group 10 ──────────────────────────────────────────
# STEP_PATIENT_COUNT is intentionally excluded: it uses inline keyboard buttons
# (count_1 … count_20 callbacks) so the bot receives input in group chats
# without requiring bot admin / privacy-mode-off configuration.
# STEP_P_VISA_EXPIRY excluded: now handled via calendar picker (callbacks only).
# STEP_P_RESIDENCE_EXPIRY excluded: step removed from flow entirely.
_TEXT_STEPS = {
    STEP_DATE_CUSTOM,
    STEP_P_NAME,
    STEP_BATCH_NOTES,
    STEP_C_NAME,
}


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _safe_edit(update, text, kb):
    """
    DELIVERY LOG key:
      EDIT   → edits an existing inline-keyboard message in place
               (user must type a NEW standalone message — privacy-mode risk)
      REPLY  → sends a brand-new message replying to update.effective_message
               (always safe; works in groups)
      FALLBACK → edit failed, fell through to reply_text
    """
    query = update.callback_query
    uid   = update.effective_user.id if update.effective_user else "?"
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            logger.info(
                f"[arrivals.delivery] EDIT  msg_id={query.message.message_id}"
                f"  chat={query.message.chat_id}  user={uid}"
            )
            return
        except Exception as exc:
            logger.warning(
                f"[arrivals.delivery] EDIT FAILED ({exc!r}) — falling back to reply_text"
                f"  user={uid}"
            )
    msg = update.effective_message
    await msg.reply_text(text, reply_markup=kb, parse_mode="Markdown")
    logger.info(
        f"[arrivals.delivery] REPLY  msg_id={msg.message_id}"
        f"  chat={msg.chat_id}  user={uid}"
    )


async def _cancel(update, context):
    ArrivalSession.clear(context.user_data)
    text, kb = build_cancelled()
    await _safe_edit(update, text, kb)


async def _show_date(update, context):
    text, kb = build_date_prompt()
    await _safe_edit(update, text, kb)


async def _show_hospital(update, context):
    text, kb = build_hospital_prompt()
    await _safe_edit(update, text, kb)


async def _show_specialist(update, context):
    text, kb = build_specialist_prompt()
    await _safe_edit(update, text, kb)


async def _show_patient_count(update, context, session):
    text, kb = build_patient_count_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_name(update, context, session):
    text, kb = build_p_name_prompt(session)
    uid = update.effective_user.id if update.effective_user else "?"
    logger.info(
        f"[arrivals] _show_p_name via=REPLY"
        f"  patient_index={session.patient_index}"
        f"  patient_count={session.patient_count}"
        f"  user={uid}"
    )
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_p_visa_expiry(update, context, session):
    text, kb = build_p_visa_expiry_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_has_companion(update, context, session):
    text, kb = build_p_has_companion_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_p_passport(update, context, session):
    text, kb = build_p_passport_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_p_visa(update, context, session):
    text, kb = build_p_visa_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_p_residence(update, context, session):
    text, kb = build_p_residence_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_p_residence_expiry(update, context, session):
    text, kb = build_p_residence_expiry_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_batch_notes(update, context, session):
    text, kb = build_batch_notes_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_c_name(update, context, session):
    text, kb = build_c_name_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_c_visa_expiry(update, context, session):
    text, kb = build_c_visa_expiry_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_passport(update, context, session):
    text, kb = build_c_passport_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_c_visa(update, context, session):
    text, kb = build_c_visa_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_review(update, context, session):
    text, kb = build_review(session)
    await _safe_edit(update, text, kb)


async def _advance_after_patient_uploads(update, context, session):
    """After patient's last upload (residence): go to companion loop or finish patient."""
    if session.current_patient.get("has_companion"):
        session.step = STEP_C_NAME
        session.save(context.user_data)
        await _show_c_name(update, context, session)
    else:
        _finish_and_advance(session)
        session.save(context.user_data)
        if session.patients_done:
            session.step = STEP_BATCH_NOTES
            session.save(context.user_data)
            await _show_batch_notes(update, context, session)
        else:
            session.init_current_patient()
            session.step = STEP_P_NAME
            session.save(context.user_data)
            await _show_p_name(update, context, session)


async def _advance_after_companion_done(update, context, session):
    """After companion residence expiry: commit companion, finish patient, advance."""
    session.add_companion_to_current(session.current_companion)
    session.current_companion = {}
    _finish_and_advance(session)
    session.save(context.user_data)
    if session.patients_done:
        session.step = STEP_BATCH_NOTES
        session.save(context.user_data)
        await _show_batch_notes(update, context, session)
    else:
        session.init_current_patient()
        session.step = STEP_P_NAME
        session.save(context.user_data)
        await _show_p_name(update, context, session)


def _finish_and_advance(session: ArrivalSession) -> None:
    session.finish_current_patient()


# ── Photo extraction ──────────────────────────────────────────────────────────

def _get_photo_file_id(update: Update) -> str | None:
    msg = update.effective_message
    if msg.photo:
        return msg.photo[-1].file_id
    if msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        return msg.document.file_id
    return None


# ── Callback dispatcher ───────────────────────────────────────────────────────

async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data   = query.data or ""
    prefix = f"{GSA}:"
    if not data.startswith(prefix):
        return
    action = data[len(prefix):]

    # ── Central entry log — visible for EVERY callback that reaches this handler
    uid  = query.from_user.id   if query.from_user  else "?"
    chat = query.message.chat_id if query.message   else "?"
    logger.info(
        f"[arrivals.cb] FIRED  action={action!r}"
        f"  user={uid}  chat={chat}"
    )

    try:
        await _dispatch_callback_inner(update, context, action, uid)
    except Exception:
        logger.exception(
            f"[arrivals.cb] UNHANDLED EXCEPTION  action={action!r}  user={uid}"
        )


async def _dispatch_callback_inner(
    update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, uid
) -> None:
    query = update.callback_query

    # ── GS navigation ─────────────────────────────────────────────────────────
    if action == "arrivals":
        logger.info(f"[arrivals.cb] NAV → arrivals menu  user={uid}")
        text, kb = build_arrivals_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "main":
        logger.info(f"[arrivals.cb] NAV → main GS menu  user={uid}")
        text, kb = build_gs_menu()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Start ─────────────────────────────────────────────────────────────────
    if action == "start":
        session = ArrivalSession.create(context.user_data)
        logger.info(f"[arrivals.cb] start → session created → STEP_DATE  user={uid}")
        text, kb = build_date_prompt()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Date ──────────────────────────────────────────────────────────────────
    if action == "date_today":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] date_today — no session  user={uid}")
            await _cancel(update, context); return
        from datetime import datetime
        session.created_at = datetime.utcnow().isoformat()
        session.step = STEP_HOSPITAL
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] date_today → STEP_HOSPITAL  user={uid}")
        await _show_hospital(update, context)
        return

    if action == "date_calendar":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] date_calendar — no session  user={uid}")
            await _cancel(update, context); return
        session.step = STEP_DATE_CUSTOM
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] date_calendar → STEP_DATE_CUSTOM (calendar shown)  user={uid}")
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=GSA,
            back_callback=f"{GSA}:start",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    # ── Visa expiry calendar ───────────────────────────────────────────────────
    if action == "visa_expiry_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] visa_expiry_cal — no session  user={uid}")
            await _cancel(update, context); return
        logger.info(f"[arrivals.cb] visa_expiry_cal → calendar shown  user={uid}")
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=GSA,
            back_callback=f"{GSA}:visa_expiry_prompt",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "visa_expiry_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] visa_expiry_prompt — no session  user={uid}")
            await _cancel(update, context); return
        logger.info(f"[arrivals.cb] visa_expiry_prompt → re-show  user={uid}")
        await _show_p_visa_expiry(update, context, session)
        return

    # ── Companion visa expiry calendar ─────────────────────────────────────────
    if action == "c_visa_expiry_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] c_visa_expiry_cal — no session  user={uid}")
            await _cancel(update, context); return
        logger.info(f"[arrivals.cb] c_visa_expiry_cal → calendar shown  user={uid}")
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=GSA,
            back_callback=f"{GSA}:c_visa_expiry_prompt",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "c_visa_expiry_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] c_visa_expiry_prompt — no session  user={uid}")
            await _cancel(update, context); return
        logger.info(f"[arrivals.cb] c_visa_expiry_prompt → re-show  user={uid}")
        await _show_c_visa_expiry(update, context, session)
        return

    if action.startswith("cal_nav:"):
        parts = action.split(":")
        try:
            y, m = int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            logger.warning(f"[arrivals.cb] cal_nav parse error  action={action!r}  user={uid}")
            return
        # Back callback depends on which calendar is currently open.
        _nav_session = ArrivalSession.load(context.user_data)
        if _nav_session and _nav_session.step == STEP_P_VISA_EXPIRY:
            _back_cb = f"{GSA}:visa_expiry_prompt"
        elif _nav_session and _nav_session.step == STEP_C_VISA_EXPIRY:
            _back_cb = f"{GSA}:c_visa_expiry_prompt"
        else:
            _back_cb = f"{GSA}:start"
        logger.info(f"[arrivals.cb] cal_nav → {y}/{m}  back={_back_cb!r}  user={uid}")
        cal_text, cal_kb = build_calendar(
            year=y, month=m,
            callback_prefix=GSA,
            back_callback=_back_cb,
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action.startswith("cal_pick:"):
        parts = action.split(":")
        try:
            from datetime import datetime
            dt = datetime(int(parts[1]), int(parts[2]), int(parts[3]))
        except (IndexError, ValueError):
            logger.warning(f"[arrivals.cb] cal_pick parse error  action={action!r}  user={uid}")
            return
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] cal_pick — no session  user={uid}")
            await _cancel(update, context); return
        # Dispatch by step: patient visa expiry / companion visa expiry / arrival date.
        if session.step == STEP_P_VISA_EXPIRY:
            session.current_patient["visa_expiry"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_P_HAS_COMPANION
            session.save(context.user_data)
            logger.info(
                f"[arrivals.cb] cal_pick p_visa_expiry={dt.date()} → STEP_P_HAS_COMPANION  user={uid}"
            )
            await _show_p_has_companion(update, context, session)
        elif session.step == STEP_C_VISA_EXPIRY:
            session.current_companion["visa_expiry"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_C_PASSPORT
            session.save(context.user_data)
            logger.info(
                f"[arrivals.cb] cal_pick c_visa_expiry={dt.date()} → STEP_C_PASSPORT  user={uid}"
            )
            await _show_c_passport(update, context, session)
        else:
            session.created_at = dt.isoformat()
            session.step = STEP_HOSPITAL
            session.save(context.user_data)
            logger.info(f"[arrivals.cb] cal_pick date={dt.date()} → STEP_HOSPITAL  user={uid}")
            await _show_hospital(update, context)
        return

    # ── Hospital ──────────────────────────────────────────────────────────────
    if action.startswith("hospital_"):
        hid = action[len("hospital_"):]
        label = HOSPITAL_MAP.get(hid, "")
        if not label:
            logger.warning(f"[arrivals.cb] hospital unknown hid={hid!r}  user={uid}")
            return
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] hospital — no session  user={uid}")
            await _cancel(update, context); return
        session.hospital_id    = hid
        session.hospital_label = label
        session.step           = STEP_SPECIALIST
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] hospital={hid!r} ({label!r}) → STEP_SPECIALIST  user={uid}")
        await _show_specialist(update, context)
        return

    # ── Specialist ────────────────────────────────────────────────────────────
    if action.startswith("specialist_"):
        sid = action[len("specialist_"):]
        label = STAFF_MAP.get(sid, "")
        if not label:
            logger.warning(f"[arrivals.cb] specialist unknown sid={sid!r}  user={uid}")
            return
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] specialist — no session  user={uid}")
            await _cancel(update, context); return
        session.specialist_id    = sid
        session.specialist_label = label
        session.step             = STEP_PATIENT_COUNT
        session.save(context.user_data)
        logger.info(
            f"[arrivals.cb] specialist={sid!r} ({label!r}) → STEP_PATIENT_COUNT  user={uid}"
        )
        await _show_patient_count(update, context, session)
        return

    # ── Patient count (inline button 1–20) ───────────────────────────────────
    if action.startswith("count_"):
        try:
            n = int(action[len("count_"):])
            assert 1 <= n <= 20
        except (ValueError, AssertionError):
            logger.warning(f"[arrivals.cb] invalid count action={action!r}  user={uid}")
            return
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] count — no session  user={uid}")
            await _cancel(update, context); return
        session.patient_count      = n
        session.patient_index      = 0
        session.completed_patients = []
        session.init_current_patient()
        session.step = STEP_P_NAME
        session.save(context.user_data)
        logger.info(
            f"[arrivals.cb] count={n} → STEP_P_NAME saved"
            f"  session.step={session.step!r}"
            f"  user_data key present={('_gsarr_add' in context.user_data)}"
            f"  user={uid}"
        )
        await _show_p_name(update, context, session)
        logger.info(
            f"[arrivals.cb] _show_p_name returned"
            f"  — text handler fires on next TEXT message (group 10)  user={uid}"
        )
        return

    # ── Companion ─────────────────────────────────────────────────────────────
    if action == "companion_yes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["has_companion"] = True
        session.step = STEP_P_PASSPORT
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] companion_yes → STEP_P_PASSPORT  user={uid}")
        await _show_p_passport(update, context, session)
        return

    if action == "companion_no":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["has_companion"] = False
        session.step = STEP_P_PASSPORT
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] companion_no → STEP_P_PASSPORT  user={uid}")
        await _show_p_passport(update, context, session)
        return

    if action == "skip_p_residence":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["residence_file_id"] = ""
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] skip_p_residence → _advance_after_patient_uploads  user={uid}")
        await _advance_after_patient_uploads(update, context, session)
        return

    if action == "skip_batch_notes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.batch_notes = ""
        session.step = STEP_REVIEW
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] skip_batch_notes → STEP_REVIEW  user={uid}")
        await _show_review(update, context, session)
        return

    if action == "skip_c_passport":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["passport_file_id"] = ""
        session.step = STEP_C_VISA
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] skip_c_passport → STEP_C_VISA  user={uid}")
        await _show_c_visa(update, context, session)
        return

    # ── Back navigation ────────────────────────────────────────────────────────
    if action == "back_to_hospital":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_HOSPITAL
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_to_hospital → STEP_HOSPITAL  user={uid}")
        await _show_hospital(update, context)
        return

    if action == "back_to_specialist":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_SPECIALIST
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_to_specialist → STEP_SPECIALIST  user={uid}")
        await _show_specialist(update, context)
        return

    if action == "back_to_count":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_PATIENT_COUNT
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_to_count → STEP_PATIENT_COUNT  user={uid}")
        await _show_patient_count(update, context, session)
        return

    if action == "back_to_batch_notes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_BATCH_NOTES
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_to_batch_notes → STEP_BATCH_NOTES  user={uid}")
        await _show_batch_notes(update, context, session)
        return

    if action == "back_p_name":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_NAME
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_p_name → STEP_P_NAME  user={uid}")
        await _show_p_name(update, context, session)
        return

    if action == "back_p_visa_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_VISA_EXPIRY
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_p_visa_expiry → STEP_P_VISA_EXPIRY  user={uid}")
        await _show_p_visa_expiry(update, context, session)
        return

    if action == "back_p_companion":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_HAS_COMPANION
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_p_companion → STEP_P_HAS_COMPANION  user={uid}")
        await _show_p_has_companion(update, context, session)
        return

    if action == "back_p_passport":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_PASSPORT
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_p_passport → STEP_P_PASSPORT  user={uid}")
        await _show_p_passport(update, context, session)
        return

    if action == "back_p_visa":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_VISA
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_p_visa → STEP_P_VISA  user={uid}")
        await _show_p_visa(update, context, session)
        return

    if action == "back_p_residence":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_RESIDENCE
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_p_residence → STEP_P_RESIDENCE  user={uid}")
        await _show_p_residence(update, context, session)
        return

    if action == "back_c_name":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_NAME
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_c_name → STEP_C_NAME  user={uid}")
        await _show_c_name(update, context, session)
        return

    if action == "back_c_visa_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_VISA_EXPIRY
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_c_visa_expiry → STEP_C_VISA_EXPIRY  user={uid}")
        await _show_c_visa_expiry(update, context, session)
        return

    if action == "back_c_passport":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_PASSPORT
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] back_c_passport → STEP_C_PASSPORT  user={uid}")
        await _show_c_passport(update, context, session)
        return

    # ── Confirm / Cancel ──────────────────────────────────────────────────────
    if action == "confirm":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        logger.info(
            f"[arrivals.cb] confirm → saving batch"
            f"  patients={len(session.completed_patients)}  user={uid}"
        )
        try:
            from modules.general_services.arrivals.models import save_arrival_batch
            saved = save_arrival_batch(
                hospital_id=      session.hospital_id,
                hospital_label=   session.hospital_label,
                specialist_id=    session.specialist_id,
                specialist_label= session.specialist_label,
                patients=         session.completed_patients,
                created_by=       update.effective_user.id if update.effective_user else None,
            )
        except Exception:
            logger.exception(
                f"[arrivals.cb] confirm — save_arrival_batch FAILED"
                f"  session=({_session_debug_str(session)})  user={uid}"
            )
            text, kb = build_error("فشل حفظ البيانات. حاول مجدداً.")
            await _safe_edit(update, text, kb)
            return

        logger.info(
            f"[arrivals.cb] batch saved  batch_id={saved.batch_id}"
            f"  patient_count={saved.patient_count}  user={uid}"
        )
        user  = update.effective_user
        count = len(session.completed_patients)
        body  = [
            f"🏥 {session.hospital_label}  •  👨‍⚕️ {session.specialist_label}",
            f"👥 *عدد المرضى:*  {count}",
        ]
        for i, p in enumerate(session.completed_patients):
            p_pass   = "✅" if p.get("passport_file_id")  else "⬜"
            p_visa   = "✅" if p.get("visa_file_id")       else "⬜"
            p_res    = "✅" if p.get("residence_file_id")  else "⬜"
            vis_exp  = p.get("visa_expiry") or "—"
            comp_icon = "✅" if p.get("has_companion") else "❌"
            body += [
                "",
                f"*{i + 1}.* {p.get('name', '—')}",
                f"تأشيرة: {vis_exp}  •  مرافق: {comp_icon}",
                f"📎 {p_pass} جواز  {p_visa} تأشيرة  {p_res} إقامة",
            ]
            for c in p.get("companions", []):
                c_pass = "✅" if c.get("passport_file_id") else "⬜"
                c_visa = "✅" if c.get("visa_file_id")     else "⬜"
                body.append(f"↳ {c.get('name', '—')}  📎 {c_pass} جواز  {c_visa} تأشيرة")
        body += ["", f"📝 *الملاحظات:*  {session.batch_notes or 'لا توجد ملاحظات'}"]

        from modules.general_services.report_publisher import GSPublishData, publish as _publish
        await _publish(
            bot=context.bot,
            data=GSPublishData(
                workflow_type="arrivals",
                workflow_label="دفعة وصول جديدة",
                workflow_icon="🛬",
                body_lines=body,
                created_by_id=  user.id   if user else None,
                created_by_name=user.full_name if user else "",
                record_date=session.created_at,
            ),
        )

        ArrivalSession.clear(context.user_data)
        text, kb = build_success(saved.batch_id, saved.hospital_label, saved.patient_count)
        await _safe_edit(update, text, kb)
        return

    if action == "cancel":
        logger.info(f"[arrivals.cb] cancel → session cleared  user={uid}")
        await _cancel(update, context)
        return

    logger.warning(f"[arrivals.cb] UNHANDLED action={action!r}  user={uid}")


# ── Text handler (group 10) ───────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ── Diagnostic: confirm handler is being invoked at all ──────────────────
    uid  = update.effective_user.id if update.effective_user else "unknown"
    chat = update.effective_chat.id  if update.effective_chat  else "unknown"
    logger.info(
        f"[arrivals.text] FIRED  user={uid}  chat={chat}"
        f"  has_message={bool(update.message)}"
        f"  has_callback={bool(update.callback_query)}"
    )

    # Only process new messages — skip edited-message updates where
    # update.message is None (would cause AttributeError on .text).
    if not update.message:
        logger.debug(f"[arrivals.text] SKIP — edited-message update (no .message)  user={uid}")
        return

    # ── Load & validate session ───────────────────────────────────────────────
    raw_session_data = context.user_data.get("_gsarr_add")
    logger.info(
        f"[arrivals.text] user_data._gsarr_add present={raw_session_data is not None}"
        + (f"  step={raw_session_data.get('step')!r}" if raw_session_data else "")
        + f"  user={uid}"
    )

    session = ArrivalSession.load(context.user_data)
    if session is None:
        logger.debug(f"[arrivals.text] SKIP — no active ArrivalSession  user={uid}")
        return
    if session.step not in _TEXT_STEPS:
        logger.debug(
            f"[arrivals.text] SKIP — step={session.step!r} not in _TEXT_STEPS  user={uid}"
            f"  _TEXT_STEPS={_TEXT_STEPS}"
        )
        return

    text = (update.message.text or "").strip()
    step = session.step
    # ── Full state snapshot before any processing — visible in pm2 logs ───────
    logger.info(
        f"[arrivals.text] PROCESSING"
        f"  step={step!r}"
        f"  text={text[:40]!r}"
        f"  patient_index={session.patient_index}/{session.patient_count}"
        f"  p_name={session.current_patient.get('name', '—')!r}"
        f"  user={uid}"
    )

    # ── Step handlers — every branch wrapped so exceptions surface fully ──────

    if step == STEP_DATE_CUSTOM:
        try:
            dt = parse_date_input(text)
            if dt is None:
                prompt, kb = build_date_calendar_prompt(error=True)
                await update.message.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
                return
            session.created_at = dt.isoformat()
            session.step = STEP_HOSPITAL
            session.save(context.user_data)
            logger.info(
                f"[arrivals.text] STEP_DATE_CUSTOM → STEP_HOSPITAL"
                f"  date={dt.date()}  user={uid}"
            )
            await _show_hospital(update, context)
        except Exception:
            logger.exception(
                f"[arrivals.text] EXCEPTION in STEP_DATE_CUSTOM"
                f"  session=({_session_debug_str(session)})  user={uid}"
            )
        return

    if step == STEP_P_NAME:
        try:
            if not text:
                await update.message.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
                return
            session.current_patient["name"] = text
            session.step = STEP_P_VISA_EXPIRY
            session.save(context.user_data)
            logger.info(
                f"[arrivals.text] STEP_P_NAME → STEP_P_VISA_EXPIRY"
                f"  name={text!r}  patient_index={session.patient_index}/{session.patient_count}"
                f"  user={uid}"
            )
            await _show_p_visa_expiry(update, context, session)
        except Exception:
            logger.exception(
                f"[arrivals.text] EXCEPTION in STEP_P_NAME"
                f"  session=({_session_debug_str(session)})  user={uid}"
            )
        return

    if step == STEP_BATCH_NOTES:
        try:
            session.batch_notes = text
            session.step = STEP_REVIEW
            session.save(context.user_data)
            logger.info(
                f"[arrivals.text] STEP_BATCH_NOTES → STEP_REVIEW"
                f"  notes={text[:40]!r}  user={uid}"
            )
            await _show_review(update, context, session)
        except Exception:
            logger.exception(
                f"[arrivals.text] EXCEPTION in STEP_BATCH_NOTES  user={uid}"
            )
        return

    if step == STEP_C_NAME:
        try:
            if not text:
                await update.message.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
                return
            session.current_companion["name"] = text
            session.step = STEP_C_VISA_EXPIRY
            session.save(context.user_data)
            logger.info(
                f"[arrivals.text] STEP_C_NAME → STEP_C_VISA_EXPIRY"
                f"  companion_name={text!r}  session=({_session_debug_str(session)})  user={uid}"
            )
            await _show_c_visa_expiry(update, context, session)
        except Exception:
            logger.exception(
                f"[arrivals.text] EXCEPTION in STEP_C_NAME"
                f"  session=({_session_debug_str(session)})  user={uid}"
            )
        return

    logger.warning(
        f"[arrivals.text] UNHANDLED step={step!r} — fell through all branches"
        f"  session=({_session_debug_str(session)})  user={uid}"
    )


# ── Photo handler (group 11) ──────────────────────────────────────────────────

async def _handle_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else "?"
    session = ArrivalSession.load(context.user_data)
    if session is None or session.step not in _PHOTO_STEPS:
        return

    file_id = _get_photo_file_id(update)
    if not file_id:
        logger.debug(f"[arrivals.photo] SKIP — no photo/image in message  user={uid}")
        return

    step = session.step
    logger.info(
        f"[arrivals.photo] FIRED  step={step!r}"
        f"  session=({_session_debug_str(session)})  user={uid}"
    )

    try:
        if step == STEP_P_PASSPORT:
            session.current_patient["passport_file_id"] = file_id
            session.step = STEP_P_VISA
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_P_PASSPORT → STEP_P_VISA  user={uid}")
            await _show_p_visa(update, context, session)
            return

        if step == STEP_P_VISA:
            session.current_patient["visa_file_id"] = file_id
            session.step = STEP_P_RESIDENCE
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_P_VISA → STEP_P_RESIDENCE  user={uid}")
            await _show_p_residence(update, context, session)
            return

        if step == STEP_P_RESIDENCE:
            session.current_patient["residence_file_id"] = file_id
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_P_RESIDENCE → _advance_after_patient_uploads  user={uid}")
            await _advance_after_patient_uploads(update, context, session)
            return

        if step == STEP_C_PASSPORT:
            session.current_companion["passport_file_id"] = file_id
            session.step = STEP_C_VISA
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_C_PASSPORT → STEP_C_VISA  user={uid}")
            await _show_c_visa(update, context, session)
            return

        if step == STEP_C_VISA:
            session.current_companion["visa_file_id"] = file_id
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_C_VISA → _advance_after_companion_done  user={uid}")
            await _advance_after_companion_done(update, context, session)
            return

    except Exception:
        logger.exception(
            f"[arrivals.photo] EXCEPTION  step={step!r}"
            f"  session=({_session_debug_str(session)})  user={uid}"
        )


# ── Registration ──────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    # Callback handler — arrivals prefix + gs navigation (arrivals + main)
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^gsa:"),
        group=15,
    )
    # Text input
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input),
        group=10,
    )
    # Single-photo input
    app.add_handler(
        MessageHandler(
            filters.PHOTO | filters.Document.IMAGE,
            _handle_photo_input,
        ),
        group=11,
    )
