# modules/residency/renewal/flow.py
# Handles rnr: callbacks — the issuance/renewal flow.
#
# Handler groups:
#   group 20  CallbackQueryHandler(^rnr:)
#   (text input for notes handled by group 16 in profiles/flow.py via session step check)

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.calendar_picker import build_calendar
from shared.uploads import collector as uploads
from shared.result_router import register as _register_route

from modules.residency.renewal.session import (
    RenewalSession,
    STEP_EXPIRY_DATE, STEP_RESIDENCY_NUMBER, STEP_DOCUMENT,
    STEP_COMPANIONS,
    STEP_C_EXPIRY_DATE, STEP_C_RESIDENCY_NUMBER, STEP_C_DOCUMENT,
    STEP_NOTES, STEP_REVIEW,
)
from modules.residency.renewal.views import (
    RNR, RN,
    build_renewal_expiry_prompt,
    build_renewal_residency_number_prompt, build_renewal_c_residency_number_prompt,
    build_renewal_document_prompt,
    build_renewal_companions_prompt, build_renewal_c_expiry_prompt,
    build_renewal_c_document_prompt, build_renewal_notes_prompt,
    build_renewal_review, build_renewal_success, build_renewal_cancelled,
)

logger = logging.getLogger(__name__)

_RKEY_RENEWAL_DOC = "res.renewal.doc"
_RKEY_C_DOC       = "res.renewal.c_doc"

_MODULE_KEY = "residency"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


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
    RenewalSession.clear(context.user_data)
    text, kb = build_renewal_cancelled()
    await _safe_edit(update, text, kb)


async def _go_to_review(update, context):
    session = RenewalSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_REVIEW
    session.save(context.user_data)
    text, kb = build_renewal_review(session)
    await _safe_edit(update, text, kb)


async def _open_expiry_calendar(update, context, session):
    from datetime import datetime
    now = datetime.utcnow()
    cal_text, cal_kb = build_calendar(
        year=now.year, month=now.month,
        callback_prefix=RNR,
        back_callback=f"{RNR}:cancel",
    )
    prompt, _ = build_renewal_expiry_prompt(session)
    await _safe_edit(update, prompt, _)
    await update.effective_message.reply_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")


async def _open_c_expiry_calendar(update, context, session):
    from datetime import datetime
    now = datetime.utcnow()
    cal_text, cal_kb = build_calendar(
        year=now.year, month=now.month,
        callback_prefix=RNR,
        back_callback=f"{RNR}:companions_yes",
    )
    prompt, prompt_kb = build_renewal_c_expiry_prompt(session)
    await _safe_edit(update, prompt, prompt_kb)
    await update.effective_message.reply_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")


async def _open_doc_upload(update, context):
    session = RenewalSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_DOCUMENT
    session.save(context.user_data)
    await uploads.open(update, context, title="وثيقة الإقامة الجديدة", return_to=_RKEY_RENEWAL_DOC)


async def _open_c_doc_upload(update, context):
    session = RenewalSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return
    session.step = STEP_C_DOCUMENT
    session.save(context.user_data)
    c = session.current_companion
    title = f"وثيقة إقامة {c['name']}" if c else "وثيقة إقامة المرافق"
    await uploads.open(update, context, title=title, return_to=_RKEY_C_DOC)


async def _advance_companion(
    update, context, session,
    new_expiry: str, file_id: str, skipped: bool,
    residency_number: str = "",
):
    """Finish current companion and advance to next or to notes."""
    session.finish_current_companion(
        new_expiry=new_expiry, file_id=file_id,
        skipped=skipped, residency_number=residency_number,
    )
    if session.companions_done:
        session.step = STEP_NOTES
        session.save(context.user_data)
        text, kb = build_renewal_notes_prompt(session)
        await _safe_edit(update, text, kb)
    else:
        session.step = STEP_C_EXPIRY_DATE
        session.save(context.user_data)
        await _open_c_expiry_calendar(update, context, session)


# ── Calendar handling ─────────────────────────────────────────────────────────

async def _handle_cal_action(update, context, action: str):
    session = RenewalSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    if action == "cal_noop":
        return

    parts = action.split(":")
    tag   = parts[0]

    if tag in ("cal_prev", "cal_next"):
        y, m = int(parts[1]), int(parts[2])
        back = f"{RNR}:cancel" if session.step == STEP_EXPIRY_DATE else f"{RNR}:companions_yes"
        cal_text, cal_kb = build_calendar(year=y, month=m, callback_prefix=RNR, back_callback=back)
        await _safe_edit(update, cal_text, cal_kb)
        return

    if tag == "cal_pick":
        y, m, d    = int(parts[1]), int(parts[2]), int(parts[3])
        date_str   = f"{y:04d}-{m:02d}-{d:02d}"

        if session.step == STEP_EXPIRY_DATE:
            session.new_expiry_date = date_str
            session.step = STEP_RESIDENCY_NUMBER
            session.save(context.user_data)
            text, kb = build_renewal_residency_number_prompt(session)
            await _safe_edit(update, text, kb)

        elif session.step == STEP_C_EXPIRY_DATE:
            # Store temporarily on the companion entry
            c = session.current_companion
            if c is not None:
                c["_new_expiry"] = date_str
            session.step = STEP_C_RESIDENCY_NUMBER
            session.save(context.user_data)
            text, kb = build_renewal_c_residency_number_prompt(session)
            await _safe_edit(update, text, kb)


# ── Callback dispatcher ───────────────────────────────────────────────────────

async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data   = query.data or ""
    prefix = f"{RNR}:"
    if not data.startswith(prefix):
        return
    action = data[len(prefix):]
    uid    = query.from_user.id if query.from_user else "?"

    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[residency.renewal.cb] 🚫 blocked unauthorized user={uid}  action={action!r}")
        return

    logger.info(f"[residency.renewal.cb] action={action!r}  user={uid}")

    try:
        await _dispatch_inner(update, context, action, uid)
    except Exception:
        logger.exception(f"[residency.renewal.cb] unhandled  action={action!r}  user={uid}")


async def _dispatch_inner(update, context, action: str, uid) -> None:

    # ── Calendar ──────────────────────────────────────────────────────────────
    if action.startswith("cal_"):
        await _handle_cal_action(update, context, action)
        return

    # ── Start renewal for a profile (entry point) ─────────────────────────────
    if action.startswith("start_"):
        profile_id = int(action[6:])
        from modules.residency.renewal.repository import get_profile_with_companions
        profile, companions = get_profile_with_companions(profile_id)
        if profile is None:
            await update.callback_query.edit_message_text("❌ لم يتم العثور على الملف.")
            return

        companions_only = context.user_data.pop("_rnr_complete_companions", False)
        session = RenewalSession.create(
            user_data=       context.user_data,
            profile_id=      profile_id,
            profile_name=    profile["name"],
            companions=      companions,
            companions_only= companions_only,
        )
        logger.info(
            f"[residency.renewal] start  profile_id={profile_id}"
            f"  companions={len(companions)}  companions_only={companions_only}  user={uid}"
        )

        if companions_only:
            # Skip directly to companions step
            session.step = STEP_COMPANIONS
            session.save(context.user_data)
            text, kb = build_renewal_companions_prompt(session)
            await _safe_edit(update, text, kb)
        else:
            text, kb = build_renewal_expiry_prompt(session)
            await _safe_edit(update, text, kb)
            # Open calendar immediately
            from datetime import datetime
            now = datetime.utcnow()
            cal_text, cal_kb = build_calendar(
                year=now.year, month=now.month,
                callback_prefix=RNR,
                back_callback=f"{RNR}:cancel",
            )
            await update.effective_message.reply_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    # ── Residency number skip (main patient) ─────────────────────────────────
    if action == "skip_residency_number":
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.new_residency_number = ""
        session.step = STEP_DOCUMENT
        session.save(context.user_data)
        await _open_doc_upload(update, context)
        return

    # ── Residency number skip (companion) ─────────────────────────────────────
    if action == "skip_c_residency_number":
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        c = session.current_companion
        if c is not None:
            c["_residency_number"] = ""
        session.step = STEP_C_DOCUMENT
        session.save(context.user_data)
        await _open_c_doc_upload(update, context)
        return

    # ── Document done / skip ──────────────────────────────────────────────────
    if action in ("doc_done", "skip_doc"):
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_COMPANIONS
        session.save(context.user_data)
        text, kb = build_renewal_companions_prompt(session)
        await _safe_edit(update, text, kb)
        return

    # ── Companions: yes / skip / none ─────────────────────────────────────────
    if action in ("companions_yes", "companions_skip", "no_companions"):
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return

        if action == "companions_yes" and session.companions:
            session.step = STEP_C_EXPIRY_DATE
            session.save(context.user_data)
            await _open_c_expiry_calendar(update, context, session)
        else:
            # Skip all companions → will result in dependent_pending if companions exist
            for c in session.companions:
                session.finish_current_companion(new_expiry="", file_id="", skipped=True, residency_number="")
            session.step = STEP_NOTES
            session.save(context.user_data)
            text, kb = build_renewal_notes_prompt(session)
            await _safe_edit(update, text, kb)
        return

    # ── Skip companion entirely ───────────────────────────────────────────────
    if action == "skip_c":
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _advance_companion(update, context, session, new_expiry="", file_id="", skipped=True)
        return

    # ── Companion document done / skip ────────────────────────────────────────
    if action in ("c_doc_done", "skip_c_doc"):
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        c               = session.current_companion
        new_expiry      = c.get("_new_expiry", "")      if c else ""
        residency_number= c.get("_residency_number", "") if c else ""
        # File_id will have been set by the result route handler
        file_id         = context.user_data.pop("_rnr_pending_c_file_id", "")
        await _advance_companion(
            update, context, session,
            new_expiry=new_expiry, file_id=file_id,
            skipped=False, residency_number=residency_number,
        )
        return

    # ── Notes skip ────────────────────────────────────────────────────────────
    if action == "skip_notes":
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.notes = ""
        session.step  = STEP_REVIEW
        session.save(context.user_data)
        text, kb = build_renewal_review(session)
        await _safe_edit(update, text, kb)
        return

    # ── Confirm ───────────────────────────────────────────────────────────────
    if action == "confirm":
        session = RenewalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        try:
            from modules.residency.renewal.models import save_renewal
            saved = save_renewal(
                profile_id=           session.profile_id,
                new_expiry_date=      session.new_expiry_date,
                new_residency_number= session.new_residency_number,
                document_file_id=     session.document_file_id,
                notes=                session.notes,
                completed_companions= session.completed_companions,
                performed_by=         uid if isinstance(uid, int) else None,
            )
        except Exception as exc:
            logger.error(f"[residency.renewal] save_renewal FAILED: {exc}", exc_info=True)
            from modules.residency.profiles.views import build_error
            text, kb = build_error("فشل حفظ التجديد. حاول مجدداً.")
            await _safe_edit(update, text, kb)
            return

        is_dependent = any(c.get("skipped") for c in session.completed_companions)

        # Publish notification
        try:
            from modules.residency.report_publisher import publish_event
            from modules.residency.views import format_expiry_date
            details = [f"📅 الانتهاء الجديد: {format_expiry_date(session.new_expiry_date)}"]
            if is_dependent:
                details.append("⏳ مرافقون معلقون")
            await publish_event(
                context.bot,
                action_label="تم إصدار إقامة جديدة",
                patient_name=session.profile_name,
                body_lines=details,
            )
        except Exception as exc:
            logger.warning(f"[residency.renewal] publish_event failed: {exc}")

        RenewalSession.clear(context.user_data)
        text, kb = build_renewal_success(saved.profile_id, saved.profile_name, is_dependent)
        await _safe_edit(update, text, kb)
        logger.info(
            f"[residency.renewal] confirmed  profile_id={saved.profile_id}"
            f"  dependent={is_dependent}  user={uid}"
        )
        return

    # ── Cancel ────────────────────────────────────────────────────────────────
    if action == "cancel":
        await _cancel(update, context)
        return

    logger.warning(f"[residency.renewal.cb] unhandled action={action!r}  user={uid}")


# ── Result routes ─────────────────────────────────────────────────────────────

async def _on_renewal_doc(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = RenewalSession.load(context.user_data)
    if session is None:
        text, kb = build_renewal_cancelled()
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if result.cancelled:
        await _cancel(update, context); return

    if result.files:
        f = result.files[0]
        session.document_file_id = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""
    session.step = STEP_COMPANIONS
    session.save(context.user_data)
    text, kb = build_renewal_companions_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _on_c_doc(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = RenewalSession.load(context.user_data)
    if session is None:
        text, kb = build_renewal_cancelled()
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if result.cancelled:
        await _cancel(update, context); return

    file_id = ""
    if result.files:
        f = result.files[0]
        file_id = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""

    c               = session.current_companion
    new_expiry      = c.get("_new_expiry", "")      if c else ""
    residency_number= c.get("_residency_number", "") if c else ""
    await _advance_companion(
        update, context, session,
        new_expiry=new_expiry, file_id=file_id,
        skipped=False, residency_number=residency_number,
    )


# ── Registration ──────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^rnr:"),
        group=20,
    )
    logger.info("[residency.renewal] rnr: CallbackQueryHandler registered (group 20)")


def register_result_routes() -> None:
    _register_route(_RKEY_RENEWAL_DOC, _on_renewal_doc)
    _register_route(_RKEY_C_DOC,       _on_c_doc)
    logger.info("[residency.renewal] result routes registered")
