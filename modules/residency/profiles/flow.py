# modules/residency/profiles/flow.py
# Archive browse + add-new-patient batch flow (mirrors arrivals/flow.py).
#
# Handler groups:
#   group 16  MessageHandler(TEXT)                    — text input steps
#   group 17  MessageHandler(PHOTO | Document.IMAGE)  — photo steps
#   group 20  CallbackQueryHandler(^rna:)             — all callbacks

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from shared.calendar_picker import build_calendar

from modules.residency.profiles.session import (
    AddProfileSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_PATIENT_COUNT,
    STEP_P_NAME, STEP_P_VISA_EXPIRY, STEP_P_PASSPORT, STEP_P_VISA,
    STEP_P_HAS_COMPANION,
    STEP_C_NAME, STEP_C_VISA_EXPIRY, STEP_C_PASSPORT, STEP_C_VISA,
    STEP_BATCH_NOTES, STEP_REVIEW,
)
from modules.residency.profiles.views import (
    RNA, RN,
    build_residency_main_menu,
    build_archive_list, build_profile_detail,
    build_search_prompt, build_search_results,
    build_date_prompt, build_date_calendar_prompt,
    build_patient_count_prompt,
    build_p_name_prompt, build_p_visa_expiry_prompt,
    build_p_passport_prompt, build_p_visa_prompt,
    build_p_has_companion_prompt,
    build_c_name_prompt, build_c_visa_expiry_prompt,
    build_c_passport_prompt, build_c_visa_prompt,
    build_batch_notes_prompt,
    build_review, build_success, build_cancelled, build_error,
)
from modules.residency.profiles.repository import (
    get_profiles_page, get_profile_by_id,
    get_companions_for_profile, get_history_for_profile,
    search_profiles,
)

logger = logging.getLogger(__name__)

# ── Step sets ─────────────────────────────────────────────────────────────────

_TEXT_STEPS = {STEP_DATE_CUSTOM, STEP_P_NAME, STEP_BATCH_NOTES, STEP_C_NAME}

_PHOTO_STEPS = {STEP_P_PASSPORT, STEP_P_VISA, STEP_C_PASSPORT, STEP_C_VISA}


# ── Delivery helpers ──────────────────────────────────────────────────────────

async def _safe_edit(update, text, kb):
    """Edit existing inline message; fall back to reply_text on failure."""
    query = update.callback_query
    uid   = update.effective_user.id if update.effective_user else "?"
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception as exc:
            logger.warning(f"[res.profiles.delivery] EDIT failed ({exc!r}) — falling back  user={uid}")
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _cancel(update, context):
    AddProfileSession.clear(context.user_data)
    context.user_data.pop("_res_search_active", None)
    text, kb = build_cancelled()
    await _safe_edit(update, text, kb)


# ── Show helpers (match arrivals naming exactly) ──────────────────────────────

async def _show_date(update, context):
    text, kb = build_date_prompt()
    await _safe_edit(update, text, kb)


async def _show_patient_count(update, context, session):
    text, kb = build_patient_count_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_name(update, context, session):
    text, kb = build_p_name_prompt(session)
    uid = update.effective_user.id if update.effective_user else "?"
    logger.info(
        f"[res.profiles] _show_p_name"
        f"  p_idx={session.patient_index}/{session.patient_count}  user={uid}"
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


# ── Entry point (called from routing_nav rn:add) ──────────────────────────────

async def _start_add(update, context):
    uid = update.effective_user.id if update.effective_user else "?"
    logger.info(f"[res.profiles] _start_add  user={uid}")
    session = AddProfileSession.create(context.user_data)
    text, kb = build_date_prompt()
    await _safe_edit(update, text, kb)


# ── Advance helpers ───────────────────────────────────────────────────────────

async def _advance_after_patient_photos(update, context, session):
    """After patient's visa photo: go to companion question or next patient."""
    if session.current_patient.get("has_companion"):
        session.step = STEP_C_NAME
        session.save(context.user_data)
        await _show_c_name(update, context, session)
    else:
        session.finish_current_patient()
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


async def _advance_after_companion_photos(update, context, session):
    """After companion's visa photo: commit companion, finish patient, advance."""
    session.add_companion_to_current(session.current_companion)
    session.finish_current_patient()
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
    prefix = f"{RNA}:"
    if not data.startswith(prefix):
        return
    action = data[len(prefix):]
    uid    = query.from_user.id if query.from_user else "?"

    logger.info(f"[res.profiles.cb] FIRED  action={action!r}  user={uid}")

    try:
        await _dispatch_inner(update, context, action, uid)
    except Exception:
        logger.exception(f"[res.profiles.cb] UNHANDLED  action={action!r}  user={uid}")


async def _dispatch_inner(update, context, action: str, uid) -> None:
    query = update.callback_query

    # ── Archive page navigation ───────────────────────────────────────────────
    if action.startswith("page_"):
        page = int(action[5:])
        context.user_data["_res_archive_page"] = page
        profiles, total = get_profiles_page(page=page)
        text, kb = build_archive_list(profiles, page=page, total=total)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Profile view ──────────────────────────────────────────────────────────
    if action.startswith("view_"):
        profile_id = int(action[5:])
        profile    = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        companions = get_companions_for_profile(profile_id)
        history    = get_history_for_profile(profile_id)
        text, kb   = build_profile_detail(profile, companions, history)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── PDF document package ──────────────────────────────────────────────────
    if action.startswith("pdf_"):
        profile_id = int(action[4:])
        from modules.residency.profiles.documents import send_patient_pdf
        await send_patient_pdf(
            bot=context.bot,
            message=query.message,
            profile_id=profile_id,
        )
        return

    # ── Send raw document images ──────────────────────────────────────────────
    if action.startswith("send_docs_"):
        profile_id = int(action[10:])
        from modules.residency.profiles.documents import send_patient_documents
        await send_patient_documents(
            bot=context.bot,
            message=query.message,
            profile_id=profile_id,
        )
        return

    # ── Quick expiry date edit ────────────────────────────────────────────────
    if action.startswith("edit_expiry_"):
        profile_id = int(action[12:])
        context.user_data["_res_edit_expiry_id"] = profile_id
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=RNA,
            back_callback=f"{RNA}:view_{profile_id}",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    # ── Start ─────────────────────────────────────────────────────────────────
    if action == "start":
        await _start_add(update, context)
        return

    # ── Search (from archive) ─────────────────────────────────────────────────
    if action == "search":
        context.user_data["_res_search_active"] = True
        text, kb = build_search_prompt()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        logger.info(f"[res.profiles.cb] search activated  user={uid}")
        return

    # ── Date ─────────────────────────────────────────────────────────────────
    if action == "date_today":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        session.created_at = datetime.utcnow().isoformat()
        session.step = STEP_PATIENT_COUNT
        session.save(context.user_data)
        logger.info(f"[res.profiles.cb] date_today → STEP_PATIENT_COUNT  user={uid}")
        await _show_patient_count(update, context, session)
        return

    if action == "date_calendar":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_DATE_CUSTOM
        session.save(context.user_data)
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=RNA,
            back_callback=f"{RNA}:start",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    # ── Patient visa expiry calendar ──────────────────────────────────────────
    if action == "visa_expiry_cal":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=RNA,
            back_callback=f"{RNA}:visa_expiry_prompt",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "visa_expiry_prompt":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _show_p_visa_expiry(update, context, session)
        return

    # ── Companion visa expiry calendar ────────────────────────────────────────
    if action == "c_visa_expiry_cal":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = build_calendar(
            year=now.year, month=now.month,
            callback_prefix=RNA,
            back_callback=f"{RNA}:c_visa_expiry_prompt",
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "c_visa_expiry_prompt":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _show_c_visa_expiry(update, context, session)
        return

    # ── Calendar nav / pick ───────────────────────────────────────────────────
    if action.startswith("cal_nav:"):
        parts = action.split(":")
        try:
            y, m = int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            logger.warning(f"[res.profiles.cb] cal_nav parse error  action={action!r}  user={uid}")
            return
        _edit_id = context.user_data.get("_res_edit_expiry_id")
        _s       = AddProfileSession.load(context.user_data)
        if _edit_id is not None:
            _back = f"{RNA}:view_{_edit_id}"
        elif _s and _s.step == STEP_C_VISA_EXPIRY:
            _back = f"{RNA}:c_visa_expiry_prompt"
        elif _s and _s.step == STEP_P_VISA_EXPIRY:
            _back = f"{RNA}:visa_expiry_prompt"
        else:
            _back = f"{RNA}:start"
        cal_text, cal_kb = build_calendar(
            year=y, month=m, callback_prefix=RNA, back_callback=_back,
        )
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action.startswith("cal_pick:"):
        parts = action.split(":")
        try:
            from datetime import datetime
            dt = datetime(int(parts[1]), int(parts[2]), int(parts[3]))
        except (IndexError, ValueError):
            logger.warning(f"[res.profiles.cb] cal_pick parse error  action={action!r}  user={uid}")
            return

        # ── Quick expiry-date edit (no add-session needed) ────────────────
        edit_id = context.user_data.pop("_res_edit_expiry_id", None)
        if edit_id is not None:
            from modules.residency.profiles.models import update_profile_expiry_date
            ok = update_profile_expiry_date(
                edit_id,
                dt.strftime("%Y-%m-%d"),
                performed_by=update.effective_user.id if update.effective_user else None,
            )
            if ok:
                profile    = get_profile_by_id(edit_id)
                companions = get_companions_for_profile(edit_id)
                history    = get_history_for_profile(edit_id)
                text, kb   = build_profile_detail(profile, companions, history)
            else:
                text, kb = build_error("فشل تحديث التاريخ. حاول مجدداً.")
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return

        # ── Normal add-patient flow ───────────────────────────────────────
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return

        if session.step == STEP_P_VISA_EXPIRY:
            session.current_patient["visa_expiry"] = dt.strftime("%Y-%m-%d")
            session.step = STEP_P_HAS_COMPANION
            session.save(context.user_data)
            logger.info(f"[res.profiles.cb] cal_pick p_visa_expiry={dt.date()} → STEP_P_HAS_COMPANION  user={uid}")
            await _show_p_has_companion(update, context, session)

        elif session.step == STEP_C_VISA_EXPIRY:
            session.current_companion["visa_expiry"] = dt.strftime("%Y-%m-%d")
            session.step = STEP_C_PASSPORT
            session.save(context.user_data)
            logger.info(f"[res.profiles.cb] cal_pick c_visa_expiry={dt.date()} → STEP_C_PASSPORT  user={uid}")
            await _show_c_passport(update, context, session)

        else:
            # Arrival date calendar
            session.created_at = dt.isoformat()
            session.step = STEP_PATIENT_COUNT
            session.save(context.user_data)
            logger.info(f"[res.profiles.cb] cal_pick date={dt.date()} → STEP_PATIENT_COUNT  user={uid}")
            await _show_patient_count(update, context, session)
        return

    # ── Patient count ─────────────────────────────────────────────────────────
    if action.startswith("count_"):
        try:
            n = int(action[6:])
            assert 1 <= n <= 10
        except (ValueError, AssertionError):
            logger.warning(f"[res.profiles.cb] invalid count action={action!r}  user={uid}")
            return
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.patient_count      = n
        session.patient_index      = 0
        session.completed_patients = []
        session.init_current_patient()
        session.step = STEP_P_NAME
        session.save(context.user_data)
        logger.info(f"[res.profiles.cb] count={n} → STEP_P_NAME  user={uid}")
        await _show_p_name(update, context, session)
        return

    # ── Companion yes / no ────────────────────────────────────────────────────
    if action == "companion_yes":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["has_companion"] = True
        session.step = STEP_P_PASSPORT
        session.save(context.user_data)
        logger.info(f"[res.profiles.cb] companion_yes → STEP_P_PASSPORT  user={uid}")
        await _show_p_passport(update, context, session)
        return

    if action == "companion_no":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["has_companion"] = False
        session.step = STEP_P_PASSPORT
        session.save(context.user_data)
        logger.info(f"[res.profiles.cb] companion_no → STEP_P_PASSPORT  user={uid}")
        await _show_p_passport(update, context, session)
        return

    # ── Skip batch notes ──────────────────────────────────────────────────────
    if action == "skip_batch_notes":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.batch_notes = ""
        session.step = STEP_REVIEW
        session.save(context.user_data)
        logger.info(f"[res.profiles.cb] skip_batch_notes → STEP_REVIEW  user={uid}")
        await _show_review(update, context, session)
        return

    # ── Back navigation ───────────────────────────────────────────────────────
    if action == "back_p_name":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_NAME
        session.save(context.user_data)
        await _show_p_name(update, context, session)
        return

    if action == "back_p_visa_expiry":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_VISA_EXPIRY
        session.save(context.user_data)
        await _show_p_visa_expiry(update, context, session)
        return

    if action == "back_p_passport":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_PASSPORT
        session.save(context.user_data)
        await _show_p_passport(update, context, session)
        return

    if action == "back_p_visa":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_VISA
        session.save(context.user_data)
        await _show_p_visa(update, context, session)
        return

    if action == "back_c_name":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_NAME
        session.save(context.user_data)
        await _show_c_name(update, context, session)
        return

    if action == "back_c_visa_expiry":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_VISA_EXPIRY
        session.save(context.user_data)
        await _show_c_visa_expiry(update, context, session)
        return

    if action == "back_c_passport":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_PASSPORT
        session.save(context.user_data)
        await _show_c_passport(update, context, session)
        return

    if action == "back_to_batch_notes":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_BATCH_NOTES
        session.save(context.user_data)
        await _show_batch_notes(update, context, session)
        return

    # ── Confirm / Cancel ──────────────────────────────────────────────────────
    if action == "confirm":
        session = AddProfileSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        logger.info(
            f"[res.profiles.cb] confirm → saving batch"
            f"  patients={len(session.completed_patients)}  user={uid}"
        )
        try:
            from modules.residency.profiles.models import save_manual_batch
            count = save_manual_batch(
                patients=    session.completed_patients,
                batch_notes= session.batch_notes,
                created_at=  session.created_at,
                created_by=  update.effective_user.id if update.effective_user else None,
            )
        except Exception:
            logger.exception(f"[res.profiles.cb] save_manual_batch FAILED  user={uid}")
            text, kb = build_error("فشل حفظ البيانات. حاول مجدداً.")
            await _safe_edit(update, text, kb)
            return

        logger.info(f"[res.profiles.cb] batch saved  count={count}  user={uid}")
        AddProfileSession.clear(context.user_data)
        text, kb = build_success(count)
        await _safe_edit(update, text, kb)
        return

    if action == "cancel":
        logger.info(f"[res.profiles.cb] cancel → session cleared  user={uid}")
        await _cancel(update, context)
        return

    logger.warning(f"[res.profiles.cb] UNHANDLED action={action!r}  user={uid}")


# ── Text handler (group 16) ───────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    uid = update.effective_user.id if update.effective_user else "?"

    # ── Search mode ───────────────────────────────────────────────────────────
    if context.user_data.get("_res_search_active"):
        query_text = (update.message.text or "").strip()
        if not query_text:
            return
        context.user_data.pop("_res_search_active", None)
        results = search_profiles(query_text)
        if not results:
            text, kb = build_search_prompt(error=True)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            context.user_data["_res_search_active"] = True
            return
        text, kb = build_search_results(results, query_text)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Renewal text steps (residency number + notes) ────────────────────────
    from modules.residency.renewal.session import (
        RenewalSession,
        STEP_RESIDENCY_NUMBER   as _REN_STEP_RES_NUM,
        STEP_C_RESIDENCY_NUMBER as _REN_STEP_C_RES_NUM,
        STEP_NOTES              as _REN_STEP_NOTES,
        STEP_DOCUMENT           as _REN_STEP_DOC,
        STEP_C_DOCUMENT         as _REN_STEP_C_DOC,
        STEP_REVIEW             as _REN_STEP_REVIEW,
    )
    _ren = RenewalSession.load(context.user_data)
    if _ren is not None and _ren.step in {_REN_STEP_RES_NUM, _REN_STEP_C_RES_NUM, _REN_STEP_NOTES}:
        _input = (update.message.text or "").strip()
        if _ren.step == _REN_STEP_RES_NUM:
            _ren.new_residency_number = _input
            _ren.step = _REN_STEP_DOC
            _ren.save(context.user_data)
            logger.info(f"[res.text] STEP_RESIDENCY_NUMBER → STEP_DOCUMENT  num={_input!r}  user={uid}")
            from shared.uploads import collector as _uploads
            await _uploads.open(update, context, title="وثيقة الإقامة الجديدة", return_to="res.renewal.doc")
        elif _ren.step == _REN_STEP_C_RES_NUM:
            _c = _ren.current_companion
            if _c is not None:
                _c["_residency_number"] = _input
            _ren.step = _REN_STEP_C_DOC
            _ren.save(context.user_data)
            logger.info(f"[res.text] STEP_C_RESIDENCY_NUMBER → STEP_C_DOCUMENT  num={_input!r}  user={uid}")
            from shared.uploads import collector as _uploads
            _c2   = _ren.current_companion
            _title = f"وثيقة إقامة {_c2['name']}" if _c2 else "وثيقة إقامة المرافق"
            await _uploads.open(update, context, title=_title, return_to="res.renewal.c_doc")
        elif _ren.step == _REN_STEP_NOTES:
            _ren.notes = _input
            _ren.step  = _REN_STEP_REVIEW
            _ren.save(context.user_data)
            logger.info(f"[res.text] STEP_NOTES → STEP_REVIEW  notes={_input[:40]!r}  user={uid}")
            from modules.residency.renewal.views import build_renewal_review as _build_ren_review
            _txt, _kb = _build_ren_review(_ren)
            await update.message.reply_text(_txt, reply_markup=_kb, parse_mode="Markdown")
        return

    # ── Add-batch text steps ──────────────────────────────────────────────────
    session = AddProfileSession.load(context.user_data)
    if session is None or session.step not in _TEXT_STEPS:
        return

    text = (update.message.text or "").strip()
    step = session.step

    logger.info(
        f"[res.profiles.text] PROCESSING  step={step!r}"
        f"  text={text[:40]!r}  p_idx={session.patient_index}/{session.patient_count}"
        f"  user={uid}"
    )

    if step == STEP_DATE_CUSTOM:
        from modules.general_services.views import parse_date_input
        dt = parse_date_input(text)
        if dt is None:
            prompt, kb = build_date_calendar_prompt(error=True)
            await update.message.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
            return
        session.created_at = dt.isoformat()
        session.step = STEP_PATIENT_COUNT
        session.save(context.user_data)
        logger.info(f"[res.profiles.text] STEP_DATE_CUSTOM → STEP_PATIENT_COUNT  date={dt.date()}  user={uid}")
        await _show_patient_count(update, context, session)
        return

    if step == STEP_P_NAME:
        if not text:
            await update.message.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
            return
        session.current_patient["name"] = text
        session.step = STEP_P_VISA_EXPIRY
        session.save(context.user_data)
        logger.info(
            f"[res.profiles.text] STEP_P_NAME → STEP_P_VISA_EXPIRY"
            f"  name={text!r}  p_idx={session.patient_index}/{session.patient_count}  user={uid}"
        )
        await _show_p_visa_expiry(update, context, session)
        return

    if step == STEP_BATCH_NOTES:
        session.batch_notes = text
        session.step = STEP_REVIEW
        session.save(context.user_data)
        logger.info(f"[res.profiles.text] STEP_BATCH_NOTES → STEP_REVIEW  notes={text[:40]!r}  user={uid}")
        await _show_review(update, context, session)
        return

    if step == STEP_C_NAME:
        if not text:
            await update.message.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
            return
        session.current_companion["name"] = text
        session.step = STEP_C_VISA_EXPIRY
        session.save(context.user_data)
        logger.info(
            f"[res.profiles.text] STEP_C_NAME → STEP_C_VISA_EXPIRY"
            f"  c_name={text!r}  user={uid}"
        )
        await _show_c_visa_expiry(update, context, session)
        return

    logger.warning(
        f"[res.profiles.text] UNHANDLED step={step!r} — fell through all branches  user={uid}"
    )


# ── Photo handler (group 17) ──────────────────────────────────────────────────

async def _handle_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid     = update.effective_user.id if update.effective_user else "?"
    session = AddProfileSession.load(context.user_data)
    if session is None or session.step not in _PHOTO_STEPS:
        return

    file_id = _get_photo_file_id(update)
    if not file_id:
        return

    step = session.step
    logger.info(
        f"[res.profiles.photo] FIRED  step={step!r}"
        f"  p_idx={session.patient_index}/{session.patient_count}  user={uid}"
    )

    try:
        if step == STEP_P_PASSPORT:
            session.current_patient["passport_file_id"] = file_id
            session.step = STEP_P_VISA
            session.save(context.user_data)
            logger.info(f"[res.profiles.photo] STEP_P_PASSPORT → STEP_P_VISA  user={uid}")
            await _show_p_visa(update, context, session)
            return

        if step == STEP_P_VISA:
            session.current_patient["visa_file_id"] = file_id
            session.save(context.user_data)
            logger.info(f"[res.profiles.photo] STEP_P_VISA → _advance_after_patient_photos  user={uid}")
            await _advance_after_patient_photos(update, context, session)
            return

        if step == STEP_C_PASSPORT:
            session.current_companion["passport_file_id"] = file_id
            session.step = STEP_C_VISA
            session.save(context.user_data)
            logger.info(f"[res.profiles.photo] STEP_C_PASSPORT → STEP_C_VISA  user={uid}")
            await _show_c_visa(update, context, session)
            return

        if step == STEP_C_VISA:
            session.current_companion["visa_file_id"] = file_id
            session.save(context.user_data)
            logger.info(f"[res.profiles.photo] STEP_C_VISA → _advance_after_companion_photos  user={uid}")
            await _advance_after_companion_photos(update, context, session)
            return

    except Exception:
        logger.exception(
            f"[res.profiles.photo] EXCEPTION  step={step!r}  user={uid}"
        )


# ── Registration ──────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^rna:"),
        group=20,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text_input),
        group=16,
    )
    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.IMAGE, _handle_photo_input),
        group=17,
    )
    logger.info("[residency.profiles] handlers registered (groups 16, 17, 20)")


def register_result_routes() -> None:
    # No longer used — photos are handled directly (no uploads.open() in this flow).
    pass
