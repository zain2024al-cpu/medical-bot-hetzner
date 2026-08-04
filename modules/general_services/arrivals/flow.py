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

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.calendar_picker import build_calendar, build_year_picker, build_month_picker
from shared.selectors.patient_selector import selector as patient_selector
from shared.result_router import register as _register_route
from modules.general_services.views import parse_date_input, build_gs_menu
from modules.general_services.constants import (
    STAFF_MAP, ESCORT_ENTITY_MAP, ESCORT_ENTITY_OTHER_ID,
)
from modules.general_services.arrivals.session import (
    ArrivalSession,
    STEP_DATE, STEP_DATE_CUSTOM, STEP_SPECIALIST,
    STEP_PATIENT_COUNT,
    STEP_P_NAME, STEP_P_ARRIVAL_DATE, STEP_P_PASSPORT_EXPIRY, STEP_P_VISA_EXPIRY,
    STEP_P_HAS_COMPANION, STEP_P_PASSPORT, STEP_P_VISA, STEP_P_ENTRY_STAMP, STEP_P_TICKETS,
    STEP_P_RESIDENCE, STEP_P_RESIDENCE_EXPIRY, STEP_P_INDIV_NOTES, STEP_P_SERVICES,
    STEP_P_ESCORT_ENTITY, STEP_P_RESIDENCE_ADDRESS,
    STEP_BATCH_NOTES,
    STEP_C_NAME, STEP_C_ARRIVAL_DATE, STEP_C_PASSPORT_EXPIRY, STEP_C_VISA_EXPIRY,
    STEP_C_PASSPORT, STEP_C_VISA, STEP_C_ENTRY_STAMP, STEP_C_TICKETS, STEP_C_RESIDENCE,
    STEP_C_INDIV_NOTES, STEP_C_SERVICES, STEP_C_ESCORT_ENTITY, STEP_C_RESIDENCE_ADDRESS,
    STEP_C_MORE, STEP_P_SPECIALIST,
    STEP_REVIEW,
)
from modules.general_services.arrivals.views import (
    GSA, GS,
    build_arrivals_menu,
    build_date_prompt, build_date_calendar_prompt,
    build_specialist_prompt,
    build_patient_count_prompt,
    build_p_arrival_date_prompt, build_p_passport_expiry_prompt, build_p_visa_expiry_prompt,
    build_p_has_companion_prompt,
    build_p_passport_prompt, build_p_visa_prompt,
    build_p_entry_stamp_prompt, build_p_tickets_prompt,
    build_p_residence_prompt, build_p_residence_expiry_prompt,
    build_p_indiv_notes_prompt, build_p_services_prompt,
    build_p_escort_entity_prompt, build_p_residence_address_prompt,
    build_p_escort_entity_manual_prompt, build_c_more_prompt, build_p_specialist_prompt,
    build_batch_notes_prompt,
    build_c_arrival_date_prompt, build_c_passport_expiry_prompt, build_c_visa_expiry_prompt,
    build_c_passport_prompt, build_c_visa_prompt,
    build_c_entry_stamp_prompt, build_c_tickets_prompt, build_c_residence_prompt,
    build_c_indiv_notes_prompt, build_c_services_prompt,
    build_c_escort_entity_prompt, build_c_residence_address_prompt,
    build_review, build_success, build_cancelled, build_error,
)

logger = logging.getLogger(__name__)

_MODULE_KEY = "general_services"

# ✅ result_router keys — الاسم يُختار إلزامياً من هنا (لا كتابة حرة إطلاقاً).
_RKEY_P_NAME = "gsa.arrivals.p_name"
_RKEY_C_NAME = "gsa.arrivals.c_name"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


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
    STEP_P_ENTRY_STAMP,
    STEP_P_TICKETS,
    STEP_P_RESIDENCE,
    STEP_C_PASSPORT,
    STEP_C_VISA,
    STEP_C_ENTRY_STAMP,
    STEP_C_TICKETS,
    STEP_C_RESIDENCE,
}

# ── Text steps — active in group 10 ──────────────────────────────────────────
# STEP_PATIENT_COUNT is intentionally excluded: it uses inline keyboard buttons
# (count_1 … count_20 callbacks) so the bot receives input in group chats
# without requiring bot admin / privacy-mode-off configuration.
# STEP_P_NAME/STEP_C_NAME excluded: الاسم يُختار إلزامياً من patient_selector،
# لا يوجد إدخال نص للاسم إطلاقاً.
# كل حقول التقويم (arrival_date/passport_expiry/visa_expiry/residence_expiry)
# مستثناة: تُعالَج عبر أزرار التقويم (callbacks) فقط.
_TEXT_STEPS = {
    STEP_DATE_CUSTOM,
    STEP_BATCH_NOTES,
    STEP_P_INDIV_NOTES,
    STEP_P_SERVICES,
    STEP_P_ESCORT_ENTITY,
    STEP_P_RESIDENCE_ADDRESS,
    STEP_C_INDIV_NOTES,
    STEP_C_SERVICES,
    STEP_C_ESCORT_ENTITY,
    STEP_C_RESIDENCE_ADDRESS,
}


# ── Calendar rendering — one source for all date steps ────────────────────────
# زر "⬅️ رجوع" داخل التقويم يعتمد على أي تقويم مفتوح حالياً.
_STEP_TO_CAL_BACK_CB: dict[str, str] = {
    STEP_P_ARRIVAL_DATE:     f"{GSA}:p_arrival_date_prompt",
    STEP_P_PASSPORT_EXPIRY:  f"{GSA}:p_passport_expiry_prompt",
    STEP_P_VISA_EXPIRY:      f"{GSA}:visa_expiry_prompt",
    STEP_P_RESIDENCE_EXPIRY: f"{GSA}:p_residence_expiry_prompt",
    STEP_C_ARRIVAL_DATE:     f"{GSA}:c_arrival_date_prompt",
    STEP_C_PASSPORT_EXPIRY:  f"{GSA}:c_passport_expiry_prompt",
    STEP_C_VISA_EXPIRY:      f"{GSA}:c_visa_expiry_prompt",
}

# ✅ خطوات "تاريخ انتهاء" — تواريخها بعيدة بسنوات (جواز ينتهي 2032 مثلاً)،
# فتُعرض بتقويم فيه قفز سريع للسنة/الشهر (4 ضغطات بدل ~96). تاريخ الوصول
# وتاريخ الدفعة قريبان دائماً فيبقيان بالتقويم العادي.
_QUICK_JUMP_STEPS: set[str] = {
    STEP_P_PASSPORT_EXPIRY,
    STEP_P_VISA_EXPIRY,
    STEP_P_RESIDENCE_EXPIRY,
    STEP_C_PASSPORT_EXPIRY,
    STEP_C_VISA_EXPIRY,
}


def _cal_for_step(step: str | None, year: int, month: int):
    """يبني التقويم المناسب للخطوة الحالية (زر الرجوع + القفز السريع)."""
    return build_calendar(
        year=year,
        month=month,
        callback_prefix=GSA,
        back_callback=_STEP_TO_CAL_BACK_CB.get(step, f"{GSA}:start"),
        quick_jump=step in _QUICK_JUMP_STEPS,
    )


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


async def _show_specialist(update, context):
    text, kb = build_specialist_prompt()
    await _safe_edit(update, text, kb)


async def _show_patient_count(update, context, session):
    text, kb = build_patient_count_prompt(session)
    await _safe_edit(update, text, kb)


# ── Patient loop — "show" functions ───────────────────────────────────────────

async def _show_p_name(update, context, session):
    """✅ الاسم يُختار إلزامياً من patient_selector — لا شاشة كتابة حرة."""
    uid = update.effective_user.id if update.effective_user else "?"
    logger.info(
        f"[arrivals] _show_p_name → opening patient_selector"
        f"  patient_index={session.patient_index}/{session.patient_count}  user={uid}"
    )
    await patient_selector.enter(update, context, return_to=_RKEY_P_NAME, only_companion_flow=True)


async def _show_p_arrival_date(update, context, session):
    text, kb = build_p_arrival_date_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_passport_expiry(update, context, session):
    text, kb = build_p_passport_expiry_prompt(session)
    await _safe_edit(update, text, kb)


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


async def _show_p_entry_stamp(update, context, session):
    text, kb = build_p_entry_stamp_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_tickets(update, context, session):
    text, kb = build_p_tickets_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_residence(update, context, session):
    text, kb = build_p_residence_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_residence_expiry(update, context, session):
    text, kb = build_p_residence_expiry_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_p_indiv_notes(update, context, session):
    text, kb = build_p_indiv_notes_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_services(update, context, session):
    text, kb = build_p_services_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_escort_entity(update, context, session):
    text, kb = build_p_escort_entity_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_residence_address(update, context, session):
    text, kb = build_p_residence_address_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_batch_notes(update, context, session):
    text, kb = build_batch_notes_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Companion loop — "show" functions ─────────────────────────────────────────

async def _show_c_name(update, context, session):
    """✅ الاسم يُختار إلزامياً من patient_selector — لا شاشة كتابة حرة."""
    logger.info("[arrivals] _show_c_name → opening patient_selector")
    await patient_selector.enter(update, context, return_to=_RKEY_C_NAME, only_companion_flow=True)


async def _show_c_arrival_date(update, context, session):
    text, kb = build_c_arrival_date_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_passport_expiry(update, context, session):
    text, kb = build_c_passport_expiry_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_visa_expiry(update, context, session):
    text, kb = build_c_visa_expiry_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_passport(update, context, session):
    text, kb = build_c_passport_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_c_visa(update, context, session):
    text, kb = build_c_visa_prompt(session)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_c_entry_stamp(update, context, session):
    text, kb = build_c_entry_stamp_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_tickets(update, context, session):
    text, kb = build_c_tickets_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_residence(update, context, session):
    text, kb = build_c_residence_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_indiv_notes(update, context, session):
    text, kb = build_c_indiv_notes_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_services(update, context, session):
    text, kb = build_c_services_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_escort_entity(update, context, session):
    text, kb = build_c_escort_entity_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_residence_address(update, context, session):
    text, kb = build_c_residence_address_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_c_more(update, context, session):
    text, kb = build_c_more_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_specialist(update, context, session):
    text, kb = build_p_specialist_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_p_escort_entity_manual(update, context, session):
    text, kb = build_p_escort_entity_manual_prompt(session)
    await _safe_edit(update, text, kb)


async def _show_review(update, context, session):
    text, kb = build_review(session)
    await _safe_edit(update, text, kb)


# ── Advance chains ─────────────────────────────────────────────────────────────

async def _advance_after_patient_uploads(update, context, session):
    """After patient's residence photo (upload or skip): show residence expiry step."""
    session.step = STEP_P_RESIDENCE_EXPIRY
    session.save(context.user_data)
    await _show_p_residence_expiry(update, context, session)


async def _advance_after_p_residence_expiry(update, context, session):
    """After patient's residence expiry date is set/skipped: residence address."""
    session.step = STEP_P_RESIDENCE_ADDRESS
    session.save(context.user_data)
    await _show_p_residence_address(update, context, session)


async def _advance_after_p_core_done(update, context, session):
    """
    After the patient's own fields are done (last one = services):
    run the companion loop first, then the shared closing block.

    ✅ الملاحظات/الجهة الموصلة/المختص **لم تعد** هنا — انتقلت لكتلة الختام
    التي تلي كل المرافقين (مريض ومرافقوه = وحدة واحدة، بطلب المستخدم).
    """
    await _start_next_companion(update, context, session)


async def _start_next_companion(update, context, session):
    """
    يبدأ إدخال بيانات المرافق التالي من قائمة مرافقي المريض المعروفة مسبقاً
    من السجل. إن انتهت القائمة (أو كانت فارغة) ⇒ كتلة الختام مباشرة.

    ✅ لا سؤال "هل يوجد مرافق؟" ولا "هل يوجد مرافق آخر؟" — الأدمن أدخل
    المريض ومرافقيه معاً، فالبوت يعرفهم ويكمل بياناتهم تلقائياً بالاسم.
    """
    queue = session.current_patient.get("companion_queue") or []
    done  = len(session.current_patient.get("companions", []))

    if done >= len(queue):
        await _advance_to_patient_closing(update, context, session)
        return

    nxt = queue[done]
    session.current_companion = {"name": nxt.get("name", "")}
    session.step = STEP_C_ARRIVAL_DATE
    session.save(context.user_data)
    logger.info(
        f"[arrivals] companion {done + 1}/{len(queue)} = {nxt.get('name')!r}"
        f" → STEP_C_ARRIVAL_DATE (auto, from registry)"
    )
    await _show_c_arrival_date(update, context, session)


async def _advance_to_patient_closing(update, context, session):
    """كتلة الختام لكل مريض: ملاحظات → الجهة الموصلة → المختص."""
    session.step = STEP_P_INDIV_NOTES
    session.save(context.user_data)
    await _show_p_indiv_notes(update, context, session)


async def _advance_after_companion_done(update, context, session):
    """
    After the last per-companion field: commit the companion, then ask whether
    there is another one.

    ✅ كان هذا يُنهي المريض فوراً بعد أول مرافق — فلا يمكن إدخال أكثر من
    مرافق واحد إطلاقاً. الآن يعرض "هل يوجد مرافق آخر؟".
    """
    session.add_companion_to_current(session.current_companion)
    session.current_companion = {}
    session.save(context.user_data)
    # ✅ المرافق التالي (إن بقي) يبدأ تلقائياً بلا سؤال
    await _start_next_companion(update, context, session)


async def _finish_patient_and_advance(update, context, session):
    """
    Called after the patient's closing block (specialist chosen):
    commit the patient and move to the next one, or to the review screen.
    """
    _finish_and_advance(session)
    session.save(context.user_data)
    if session.patients_done:
        session.step = STEP_REVIEW
        session.save(context.user_data)
        await _show_review(update, context, session)
    else:
        session.init_current_patient()
        session.step = STEP_P_NAME
        session.save(context.user_data)
        await _show_p_name(update, context, session)


def _finish_and_advance(session: ArrivalSession) -> None:
    session.finish_current_patient()


# ── Mandatory registry-pick result routes ─────────────────────────────────────

async def _on_p_name_selected(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = ArrivalSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    if result is None or getattr(result, "cancelled", False):
        # ✅ لا بديل نصي بعد الآن — الإلغاء من شاشة الاختيار يُعامَل كإلغاء
        # للدفعة بأكملها (يطابق سلوك زر "❌ إلغاء" على الشاشة القديمة).
        logger.info("[arrivals] p_name selection cancelled → cancelling whole batch")
        await _cancel(update, context)
        return

    patient = result.patient if hasattr(result, "patient") else result
    name = patient.name if patient else ""
    if not name:
        await _show_p_name(update, context, session)
        return

    session.current_patient["name"] = name

    # ✅ مرافقو هذا المريض معروفون مسبقاً من إدخال الأدمن ("مريض جديد مع
    # مرافقين") — نجلبهم هنا بدل سؤال المستخدم "هل يوجد مرافق؟" ثم اختيار
    # كل مرافق يدوياً من قائمة كل المرافقين في النظام. أسماؤهم تُملأ تلقائياً
    # وتُطلب بياناتهم واحداً تلو الآخر بعد إتمام المريض.
    try:
        from services.patients_service import get_companions_for_patient
        _pid = getattr(patient, "id", None)
        queue = get_companions_for_patient(int(_pid)) if _pid else []
    except Exception:
        logger.exception("[arrivals] failed to load registry companions — continuing without")
        queue = []

    session.current_patient["companion_queue"] = queue
    session.current_patient["has_companion"] = bool(queue)
    session.step = STEP_P_ARRIVAL_DATE
    session.save(context.user_data)
    logger.info(
        f"[arrivals] p_name selected={name!r} companions={[c['name'] for c in queue]}"
        f" → STEP_P_ARRIVAL_DATE"
        f"  patient_index={session.patient_index}/{session.patient_count}"
    )
    await _show_p_arrival_date(update, context, session)


async def _on_c_name_selected(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = ArrivalSession.load(context.user_data)
    if session is None:
        await _cancel(update, context); return

    if result is None or getattr(result, "cancelled", False):
        logger.info("[arrivals] c_name selection cancelled → cancelling whole batch")
        await _cancel(update, context)
        return

    patient = result.patient if hasattr(result, "patient") else result
    name = patient.name if patient else ""
    if not name:
        await _show_c_name(update, context, session)
        return

    session.current_companion["name"] = name
    session.step = STEP_C_ARRIVAL_DATE
    session.save(context.user_data)
    logger.info(f"[arrivals] c_name selected={name!r} → STEP_C_ARRIVAL_DATE")
    await _show_c_arrival_date(update, context, session)


def register_result_routes() -> None:
    _register_route(_RKEY_P_NAME, _on_p_name_selected)
    _register_route(_RKEY_C_NAME, _on_c_name_selected)
    logger.info(f"[arrivals] result routes registered: {_RKEY_P_NAME}, {_RKEY_C_NAME}")


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

    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[arrivals.cb] 🚫 blocked unauthorized user={uid}  action={action!r}")
        return

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
        session.step = STEP_PATIENT_COUNT
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] date_today → STEP_PATIENT_COUNT  user={uid}")
        await _show_patient_count(update, context, session)
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
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    # ── Patient/companion arrival-date calendar (NEW) ─────────────────────────
    if action == "p_arrival_date_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "p_arrival_date_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _show_p_arrival_date(update, context, session)
        return

    if action == "p_passport_expiry_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "p_passport_expiry_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _show_p_passport_expiry(update, context, session)
        return

    if action == "c_arrival_date_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "c_arrival_date_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _show_c_arrival_date(update, context, session)
        return

    if action == "c_passport_expiry_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        from datetime import datetime
        now = datetime.utcnow()
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "c_passport_expiry_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        await _show_c_passport_expiry(update, context, session)
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
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
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
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
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

    # ── Patient residence expiry calendar ─────────────────────────────────────
    if action == "p_residence_expiry_cal":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] p_residence_expiry_cal — no session  user={uid}")
            await _cancel(update, context); return
        session.step = STEP_P_RESIDENCE_EXPIRY
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] p_residence_expiry_cal → calendar shown  user={uid}")
        from datetime import datetime as _dt
        now = _dt.utcnow()
        cal_text, cal_kb = _cal_for_step(session.step, now.year, now.month)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    if action == "p_residence_expiry_prompt":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            logger.warning(f"[arrivals.cb] p_residence_expiry_prompt — no session  user={uid}")
            await _cancel(update, context); return
        session.step = STEP_P_RESIDENCE_EXPIRY
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] p_residence_expiry_prompt → re-show  user={uid}")
        await _show_p_residence_expiry(update, context, session)
        return

    # ── Calendar navigation ───────────────────────────────────────────────────
    # cal_nav (توافق قديم) + cal_prev/cal_next (شهر) + cal_yprev/cal_ynext (سنة)
    # كلها تُعيد رسم شبكة الأيام لسنة/شهر معيّنين.
    if action.startswith(("cal_nav:", "cal_prev:", "cal_next:", "cal_yprev:", "cal_ynext:")):
        parts = action.split(":")
        try:
            y, m = int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            logger.warning(f"[arrivals.cb] cal nav parse error  action={action!r}  user={uid}")
            return
        _nav_session = ArrivalSession.load(context.user_data)
        _step = _nav_session.step if _nav_session else None
        logger.info(f"[arrivals.cb] cal nav → {y}/{m}  step={_step!r}  user={uid}")
        cal_text, cal_kb = _cal_for_step(_step, y, m)
        await query.edit_message_text(cal_text, reply_markup=cal_kb, parse_mode="Markdown")
        return

    # ── Quick jump: year grid → month grid → day grid ─────────────────────────
    # يُفتح فقط من تقويم بُني بـquick_jump=True (خطوات تواريخ الانتهاء).
    if action.startswith(("cal_years:", "cal_yearpage:")):
        parts = action.split(":")
        try:
            base_y = int(parts[1])
        except (IndexError, ValueError):
            logger.warning(f"[arrivals.cb] cal_years parse error  action={action!r}  user={uid}")
            return
        _nav_session = ArrivalSession.load(context.user_data)
        _step = _nav_session.step if _nav_session else None
        back_cb = _STEP_TO_CAL_BACK_CB.get(_step, f"{GSA}:start")
        logger.info(f"[arrivals.cb] cal_years base={base_y}  step={_step!r}  user={uid}")
        text, kb = build_year_picker(base_y, GSA, back_cb)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action.startswith("cal_setyear:"):
        parts = action.split(":")
        try:
            y = int(parts[1])
        except (IndexError, ValueError):
            logger.warning(f"[arrivals.cb] cal_setyear parse error  action={action!r}  user={uid}")
            return
        _nav_session = ArrivalSession.load(context.user_data)
        _step = _nav_session.step if _nav_session else None
        back_cb = _STEP_TO_CAL_BACK_CB.get(_step, f"{GSA}:start")
        logger.info(f"[arrivals.cb] cal_setyear={y}  step={_step!r}  user={uid}")
        text, kb = build_month_picker(y, GSA, back_cb)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action.startswith("cal_setmonth:"):
        parts = action.split(":")
        try:
            y, m = int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            logger.warning(f"[arrivals.cb] cal_setmonth parse error  action={action!r}  user={uid}")
            return
        _nav_session = ArrivalSession.load(context.user_data)
        _step = _nav_session.step if _nav_session else None
        logger.info(f"[arrivals.cb] cal_setmonth → {y}/{m}  step={_step!r}  user={uid}")
        cal_text, cal_kb = _cal_for_step(_step, y, m)
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
        # Dispatch by step.
        if session.step == STEP_P_ARRIVAL_DATE:
            session.current_patient["arrival_date"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_P_PASSPORT_EXPIRY
            session.save(context.user_data)
            logger.info(f"[arrivals.cb] cal_pick p_arrival_date={dt.date()} → STEP_P_PASSPORT_EXPIRY  user={uid}")
            await _show_p_passport_expiry(update, context, session)
        elif session.step == STEP_P_PASSPORT_EXPIRY:
            session.current_patient["passport_expiry"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_P_VISA_EXPIRY
            session.save(context.user_data)
            logger.info(f"[arrivals.cb] cal_pick p_passport_expiry={dt.date()} → STEP_P_VISA_EXPIRY  user={uid}")
            await _show_p_visa_expiry(update, context, session)
        elif session.step == STEP_P_VISA_EXPIRY:
            session.current_patient["visa_expiry"] = dt.strftime("%d/%m/%Y")
            # ✅ لا سؤال "هل يوجد مرافق؟" — معروف مسبقاً من السجل عند اختيار
            # الاسم (companion_queue). ننتقل مباشرة لرفع الوثائق.
            session.step = STEP_P_PASSPORT
            session.save(context.user_data)
            logger.info(
                f"[arrivals.cb] cal_pick p_visa_expiry={dt.date()} → STEP_P_PASSPORT  user={uid}"
            )
            await _show_p_passport(update, context, session)
        elif session.step == STEP_P_RESIDENCE_EXPIRY:
            session.current_patient["residence_expiry"] = dt.strftime("%Y-%m-%d")
            session.save(context.user_data)
            logger.info(
                f"[arrivals.cb] cal_pick p_residence_expiry={dt.date()} → _advance_after_p_residence_expiry  user={uid}"
            )
            await _advance_after_p_residence_expiry(update, context, session)
        elif session.step == STEP_C_ARRIVAL_DATE:
            session.current_companion["arrival_date"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_C_PASSPORT_EXPIRY
            session.save(context.user_data)
            logger.info(f"[arrivals.cb] cal_pick c_arrival_date={dt.date()} → STEP_C_PASSPORT_EXPIRY  user={uid}")
            await _show_c_passport_expiry(update, context, session)
        elif session.step == STEP_C_PASSPORT_EXPIRY:
            session.current_companion["passport_expiry"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_C_VISA_EXPIRY
            session.save(context.user_data)
            logger.info(f"[arrivals.cb] cal_pick c_passport_expiry={dt.date()} → STEP_C_VISA_EXPIRY  user={uid}")
            await _show_c_visa_expiry(update, context, session)
        elif session.step == STEP_C_VISA_EXPIRY:
            # ✅ كان يُكتب في "residence_expiry" بالخطأ — تاريخ انتهاء تأشيرة
            # المرافق كان يُحفظ في حقل الإقامة، فيضيع من عمود visa_expiry
            # تماماً (ويُفسد تاريخ الإقامة أيضاً). نفس نمط الحقل المُخزَّن
            # بمفتاح خاطئ الذي أُصلح مراراً هذه الجلسة.
            session.current_companion["visa_expiry"] = dt.strftime("%d/%m/%Y")
            session.step = STEP_C_PASSPORT
            session.save(context.user_data)
            logger.info(
                f"[arrivals.cb] cal_pick c_visa_expiry={dt.date()} → STEP_C_PASSPORT  user={uid}"
            )
            await _show_c_passport(update, context, session)
        else:
            session.created_at = dt.isoformat()
            session.step = STEP_PATIENT_COUNT
            session.save(context.user_data)
            logger.info(f"[arrivals.cb] cal_pick date={dt.date()} → STEP_PATIENT_COUNT  user={uid}")
            await _show_patient_count(update, context, session)
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
        session.step             = STEP_REVIEW
        session.save(context.user_data)
        logger.info(
            f"[arrivals.cb] specialist={sid!r} ({label!r}) → STEP_REVIEW  user={uid}"
        )
        await _show_review(update, context, session)
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
            f"  session.step={session.step!r}  user={uid}"
        )
        await _show_p_name(update, context, session)
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

    # ── Skip buttons — patient chain (NEW fields) ─────────────────────────────
    if action == "skip_p_arrival_date":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["arrival_date"] = ""
        session.step = STEP_P_PASSPORT_EXPIRY
        session.save(context.user_data)
        await _show_p_passport_expiry(update, context, session)
        return

    if action == "skip_p_passport_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["passport_expiry"] = ""
        session.step = STEP_P_VISA_EXPIRY
        session.save(context.user_data)
        await _show_p_visa_expiry(update, context, session)
        return

    if action == "skip_p_entry_stamp":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["entry_stamp_file_id"] = ""
        session.step = STEP_P_TICKETS
        session.save(context.user_data)
        await _show_p_tickets(update, context, session)
        return

    if action == "skip_p_tickets":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["tickets_file_id"] = ""
        session.step = STEP_P_RESIDENCE
        session.save(context.user_data)
        await _show_p_residence(update, context, session)
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

    if action == "skip_p_residence_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["residence_expiry"] = ""
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] skip_p_residence_expiry → _advance_after_p_residence_expiry  user={uid}")
        await _advance_after_p_residence_expiry(update, context, session)
        return

    # ✅ الترتيب الجديد داخل كتلة الختام: ملاحظات → الجهة الموصلة → المختص
    if action == "skip_p_indiv_notes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["notes"] = ""
        session.step = STEP_P_ESCORT_ENTITY
        session.save(context.user_data)
        await _show_p_escort_entity(update, context, session)
        return

    # ✅ الخدمات آخر حقل من حقول المريض نفسه → حلقة المرافقين ثم كتلة الختام
    if action == "skip_p_services":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["services_provided"] = ""
        session.save(context.user_data)
        await _advance_after_p_core_done(update, context, session)
        return

    if action == "skip_p_escort_entity":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["escort_entity"] = ""
        session.step = STEP_P_SPECIALIST
        session.save(context.user_data)
        await _show_p_specialist(update, context, session)
        return

    # ✅ عنوان السكن يسبق الخدمات الآن (كلاهما من حقول المريض نفسه)
    if action == "skip_p_residence_address":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_patient["residence_address"] = ""
        session.step = STEP_P_SERVICES
        session.save(context.user_data)
        await _show_p_services(update, context, session)
        return

    # ── Escort entity buttons (patient) ───────────────────────────────────────
    if action.startswith("p_escort_"):
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        eid = action[len("p_escort_"):]
        if eid == ESCORT_ENTITY_OTHER_ID:
            # "أخرى" → شاشة كتابة يدوية (الخطوة تبقى STEP_P_ESCORT_ENTITY
            # فيلتقطها معالج النص أدناه).
            logger.info(f"[arrivals.cb] p_escort other → manual entry  user={uid}")
            await _show_p_escort_entity_manual(update, context, session)
            return
        label = ESCORT_ENTITY_MAP.get(eid, "")
        if not label:
            logger.warning(f"[arrivals.cb] unknown escort id={eid!r}  user={uid}")
            return
        session.current_patient["escort_entity"] = label
        session.step = STEP_P_SPECIALIST
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] p_escort={label!r} → STEP_P_SPECIALIST  user={uid}")
        await _show_p_specialist(update, context, session)
        return

    # ── Per-patient specialist ────────────────────────────────────────────────
    if action.startswith("p_specialist_"):
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        sid   = action[len("p_specialist_"):]
        label = STAFF_MAP.get(sid, "")
        if not label:
            logger.warning(f"[arrivals.cb] unknown specialist id={sid!r}  user={uid}")
            return
        session.current_patient["specialist_id"]    = sid
        session.current_patient["specialist_label"] = label
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] p_specialist={label!r} → finish patient  user={uid}")
        await _finish_patient_and_advance(update, context, session)
        return

    # ── Companion loop: another companion? ────────────────────────────────────
    if action == "c_more_yes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion = {}
        session.step = STEP_C_NAME
        session.save(context.user_data)
        logger.info(f"[arrivals.cb] c_more_yes → another companion  user={uid}")
        await _show_c_name(update, context, session)
        return

    if action == "c_more_no":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        logger.info(f"[arrivals.cb] c_more_no → patient closing block  user={uid}")
        await _advance_to_patient_closing(update, context, session)
        return

    # ── Skip buttons — companion chain (NEW fields) ───────────────────────────
    if action == "skip_c_arrival_date":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["arrival_date"] = ""
        session.step = STEP_C_PASSPORT_EXPIRY
        session.save(context.user_data)
        await _show_c_passport_expiry(update, context, session)
        return

    if action == "skip_c_passport_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["passport_expiry"] = ""
        session.step = STEP_C_VISA_EXPIRY
        session.save(context.user_data)
        await _show_c_visa_expiry(update, context, session)
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

    if action == "skip_c_entry_stamp":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["entry_stamp_file_id"] = ""
        session.step = STEP_C_TICKETS
        session.save(context.user_data)
        await _show_c_tickets(update, context, session)
        return

    if action == "skip_c_tickets":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["tickets_file_id"] = ""
        session.step = STEP_C_RESIDENCE
        session.save(context.user_data)
        await _show_c_residence(update, context, session)
        return

    # ✅ ذيل المرافق الجديد: عنوان السكن → الخدمات → "هل يوجد مرافق آخر؟"
    # (بلا ملاحظات/جهة موصلة/مختص — تُسأل مرة واحدة للمريض ومرافقيه معاً)
    if action == "skip_c_residence":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["residence_file_id"] = ""
        session.step = STEP_C_RESIDENCE_ADDRESS
        session.save(context.user_data)
        await _show_c_residence_address(update, context, session)
        return

    if action == "skip_c_residence_address":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["residence_address"] = ""
        session.step = STEP_C_SERVICES
        session.save(context.user_data)
        await _show_c_services(update, context, session)
        return

    if action == "skip_c_services":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.current_companion["services_provided"] = ""
        session.save(context.user_data)
        await _advance_after_companion_done(update, context, session)
        return

    # ── Back navigation ────────────────────────────────────────────────────────
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

    if action == "back_p_arrival_date":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_ARRIVAL_DATE
        session.save(context.user_data)
        await _show_p_arrival_date(update, context, session)
        return

    if action == "back_p_passport_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_PASSPORT_EXPIRY
        session.save(context.user_data)
        await _show_p_passport_expiry(update, context, session)
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

    if action == "back_p_entry_stamp":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_ENTRY_STAMP
        session.save(context.user_data)
        await _show_p_entry_stamp(update, context, session)
        return

    if action == "back_p_tickets":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_TICKETS
        session.save(context.user_data)
        await _show_p_tickets(update, context, session)
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

    if action == "back_p_residence_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_RESIDENCE_EXPIRY
        session.save(context.user_data)
        await _show_p_residence_expiry(update, context, session)
        return

    if action == "back_p_indiv_notes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_INDIV_NOTES
        session.save(context.user_data)
        await _show_p_indiv_notes(update, context, session)
        return

    if action == "back_p_services":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_SERVICES
        session.save(context.user_data)
        await _show_p_services(update, context, session)
        return

    if action == "back_p_escort_entity":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_P_ESCORT_ENTITY
        session.save(context.user_data)
        await _show_p_escort_entity(update, context, session)
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

    if action == "back_c_arrival_date":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_ARRIVAL_DATE
        session.save(context.user_data)
        await _show_c_arrival_date(update, context, session)
        return

    if action == "back_c_passport_expiry":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_PASSPORT_EXPIRY
        session.save(context.user_data)
        await _show_c_passport_expiry(update, context, session)
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

    if action == "back_c_visa":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_VISA
        session.save(context.user_data)
        await _show_c_visa(update, context, session)
        return

    if action == "back_c_entry_stamp":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_ENTRY_STAMP
        session.save(context.user_data)
        await _show_c_entry_stamp(update, context, session)
        return

    if action == "back_c_tickets":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_TICKETS
        session.save(context.user_data)
        await _show_c_tickets(update, context, session)
        return

    if action == "back_c_residence":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_RESIDENCE
        session.save(context.user_data)
        await _show_c_residence(update, context, session)
        return

    if action == "back_c_indiv_notes":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_INDIV_NOTES
        session.save(context.user_data)
        await _show_c_indiv_notes(update, context, session)
        return

    if action == "back_c_services":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_SERVICES
        session.save(context.user_data)
        await _show_c_services(update, context, session)
        return

    if action == "back_c_escort_entity":
        session = ArrivalSession.load(context.user_data)
        if session is None:
            await _cancel(update, context); return
        session.step = STEP_C_ESCORT_ENTITY
        session.save(context.user_data)
        await _show_c_escort_entity(update, context, session)
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
        # ✅ المختص أصبح لكل مريض، فلم تعد هناك خطوة مختص للدفعة. ترويسة
        # الدفعة (ArrivalBatch) لا تزال تحمل عموداً واحداً، فنشتقّه من المرضى:
        # مختص واحد لكل الدفعة ⇒ اسمه، أكثر من واحد ⇒ "متعدد".
        _sp_ids = {p.get("specialist_id", "") for p in session.completed_patients if p.get("specialist_id")}
        if len(_sp_ids) == 1:
            _batch_sp_id    = next(iter(_sp_ids))
            _batch_sp_label = STAFF_MAP.get(_batch_sp_id, session.specialist_label or "")
        elif len(_sp_ids) > 1:
            _batch_sp_id    = ""
            _batch_sp_label = "متعدد"
        else:
            _batch_sp_id    = session.specialist_id
            _batch_sp_label = session.specialist_label

        try:
            from modules.general_services.arrivals.models import save_arrival_batch
            saved = save_arrival_batch(
                specialist_id=    _batch_sp_id,
                specialist_label= _batch_sp_label,
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

        # ── Auto-create residency profiles (fire-and-forget, never breaks arrivals) ──
        try:
            from modules.residency.profiles.models import create_profiles_from_arrival_batch
            created = create_profiles_from_arrival_batch(
                batch_id=   saved.batch_id,
                patients=   session.completed_patients,
                created_by= update.effective_user.id if update.effective_user else None,
            )
            logger.info(
                f"[arrivals.cb] residency profiles auto-created: {created}"
                f"  batch_id={saved.batch_id}"
            )
        except Exception:
            logger.exception(
                f"[arrivals.cb] residency profile creation FAILED (non-fatal)"
                f"  batch_id={saved.batch_id}"
            )

        # ── Sync patient names to Master Patient Registry (fire-and-forget) ──
        try:
            from services.patients_service import sync_arrivals_to_patient_registry
            added, skipped = sync_arrivals_to_patient_registry(session.completed_patients)
            logger.info(
                f"[arrivals.cb] patient registry sync"
                f"  added={added}  skipped={skipped}"
                f"  batch_id={saved.batch_id}"
            )
        except Exception:
            logger.exception(
                f"[arrivals.cb] patient registry sync FAILED (non-fatal)"
                f"  batch_id={saved.batch_id}"
            )

        user  = update.effective_user
        count = len(session.completed_patients)

        # ── Header ────────────────────────────────────────────────────────────
        with_companion = sum(1 for p in session.completed_patients if p.get("has_companion"))
        companion_note = f"  (منهم {with_companion} بمرافق)" if with_companion else ""
        body = [
            f"👨‍⚕️ *المسؤول:*  {session.specialist_label}",
            f"👥 *إجمالي المرضى:*  {count}{companion_note}",
            "─────────────────",
            "*قائمة المرضى:*",
            "",
        ]

        # ── Patient list (كل الحقول الجديدة تُعرض هنا: تاريخ الوصول/الجواز،
        # ختم الدخول/التذاكر، الجهة الموصلة، الخدمات، عنوان السكن، ملاحظات) ──
        for i, p in enumerate(session.completed_patients):
            p_pass    = "✅" if p.get("passport_file_id")     else "⬜"
            p_visa    = "✅" if p.get("visa_file_id")          else "⬜"
            p_stamp   = "✅" if p.get("entry_stamp_file_id")   else "⬜"
            p_tickets = "✅" if p.get("tickets_file_id")       else "⬜"
            p_res     = "✅" if p.get("residence_file_id")     else "⬜"
            vis_exp   = p.get("visa_expiry") or "—"
            comp_icon = "✅" if p.get("has_companion") else "❌"
            body += [
                f"*{i + 1}.* {p.get('name', '—')}",
                f"   📋 تأشيرة: {vis_exp}   🤝 مرافق: {comp_icon}",
                f"   📎 جواز {p_pass}   تأشيرة {p_visa}   ختم {p_stamp}   تذاكر {p_tickets}   إقامة {p_res}",
                f"   🚐 الجهة الموصلة: {p.get('escort_entity') or '—'}",
            ]
            if p.get("services_provided"):
                body.append(f"   🛎️ الخدمات: {p['services_provided']}")
            if p.get("notes"):
                body.append(f"   📝 ملاحظات: {p['notes']}")
            body.append("")
            for c in p.get("companions", []):
                c_pass    = "✅" if c.get("passport_file_id")   else "⬜"
                c_visa    = "✅" if c.get("visa_file_id")        else "⬜"
                c_stamp   = "✅" if c.get("entry_stamp_file_id") else "⬜"
                c_tickets = "✅" if c.get("tickets_file_id")     else "⬜"
                body += [
                    f"   ↳ *{c.get('name', '—')}*",
                    f"      📎 جواز {c_pass}   تأشيرة {c_visa}   ختم {c_stamp}   تذاكر {c_tickets}",
                    f"      🚐 الجهة الموصلة: {c.get('escort_entity') or '—'}",
                    "",
                ]

        # ── Notes ─────────────────────────────────────────────────────────────
        body += [
            "─────────────────",
            f"📝 *الملاحظات:*  {session.batch_notes or 'لا توجد ملاحظات'}",
        ]

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
        text, kb = build_success(saved.batch_id, saved.patient_count)
        await _safe_edit(update, text, kb)
        return

    if action == "cancel":
        logger.info(f"[arrivals.cb] cancel → session cleared  user={uid}")
        await _cancel(update, context)
        return

    logger.warning(f"[arrivals.cb] UNHANDLED action={action!r}  user={uid}")


# ── Text handler (group 10) ───────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ✅ الحماية داخل المعالِج نفسه — معالِج نصوص عام (يطابق أي رسالة نصية).
    if not update.effective_user or not _is_authorized(update.effective_user.id):
        return

    if not update.message:
        return

    session = ArrivalSession.load(context.user_data)
    if session is None:
        return
    if session.step not in _TEXT_STEPS:
        return

    text = (update.message.text or "").strip()
    step = session.step
    uid  = update.effective_user.id if update.effective_user else "unknown"
    logger.info(
        f"[arrivals.text] PROCESSING"
        f"  step={step!r}"
        f"  text={text[:40]!r}"
        f"  patient_index={session.patient_index}/{session.patient_count}"
        f"  user={uid}"
    )

    if step == STEP_DATE_CUSTOM:
        try:
            dt = parse_date_input(text)
            if dt is None:
                prompt, kb = build_date_calendar_prompt(error=True)
                await update.message.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
                return
            session.created_at = dt.isoformat()
            session.step = STEP_PATIENT_COUNT
            session.save(context.user_data)
            logger.info(
                f"[arrivals.text] STEP_DATE_CUSTOM → STEP_PATIENT_COUNT"
                f"  date={dt.date()}  user={uid}"
            )
            await _show_patient_count(update, context, session)
        except Exception:
            logger.exception(
                f"[arrivals.text] EXCEPTION in STEP_DATE_CUSTOM"
                f"  session=({_session_debug_str(session)})  user={uid}"
            )
        return

    if step == STEP_BATCH_NOTES:
        try:
            session.batch_notes = text
            session.step = STEP_SPECIALIST
            session.save(context.user_data)
            logger.info(
                f"[arrivals.text] STEP_BATCH_NOTES → STEP_SPECIALIST"
                f"  notes={text[:40]!r}  user={uid}"
            )
            await _show_specialist(update, context)
        except Exception:
            logger.exception(
                f"[arrivals.text] EXCEPTION in STEP_BATCH_NOTES  user={uid}"
            )
        return

    # ✅ كتلة الختام لكل مريض: ملاحظات → الجهة الموصلة → المختص
    if step == STEP_P_INDIV_NOTES:
        try:
            session.current_patient["notes"] = text
            session.step = STEP_P_ESCORT_ENTITY
            session.save(context.user_data)
            await _show_p_escort_entity(update, context, session)
        except Exception:
            logger.exception(f"[arrivals.text] EXCEPTION in STEP_P_INDIV_NOTES  user={uid}")
        return

    # ✅ الخدمات آخر حقول المريض نفسه → حلقة المرافقين ثم كتلة الختام
    if step == STEP_P_SERVICES:
        try:
            session.current_patient["services_provided"] = text
            session.save(context.user_data)
            await _advance_after_p_core_done(update, context, session)
        except Exception:
            logger.exception(f"[arrivals.text] EXCEPTION in STEP_P_SERVICES  user={uid}")
        return

    # ✅ يصل هنا فقط عبر زر "أخرى (كتابة يدوية)" في شاشة الجهة الموصلة
    if step == STEP_P_ESCORT_ENTITY:
        try:
            session.current_patient["escort_entity"] = text
            session.step = STEP_P_SPECIALIST
            session.save(context.user_data)
            await _show_p_specialist(update, context, session)
        except Exception:
            logger.exception(f"[arrivals.text] EXCEPTION in STEP_P_ESCORT_ENTITY  user={uid}")
        return

    if step == STEP_P_RESIDENCE_ADDRESS:
        try:
            session.current_patient["residence_address"] = text
            session.step = STEP_P_SERVICES
            session.save(context.user_data)
            await _show_p_services(update, context, session)
        except Exception:
            logger.exception(f"[arrivals.text] EXCEPTION in STEP_P_RESIDENCE_ADDRESS  user={uid}")
        return

    # ── Companion tail: address → services → "another companion?" ─────────────
    # ✅ لا ملاحظات/جهة موصلة/مختص للمرافق — تُسأل مرة واحدة للمريض ومرافقيه
    # معاً في كتلة الختام (قرار المستخدم: "لكل شخص = مريض + مرافقيه").
    if step == STEP_C_RESIDENCE_ADDRESS:
        try:
            session.current_companion["residence_address"] = text
            session.step = STEP_C_SERVICES
            session.save(context.user_data)
            await _show_c_services(update, context, session)
        except Exception:
            logger.exception(f"[arrivals.text] EXCEPTION in STEP_C_RESIDENCE_ADDRESS  user={uid}")
        return

    if step == STEP_C_SERVICES:
        try:
            session.current_companion["services_provided"] = text
            session.save(context.user_data)
            await _advance_after_companion_done(update, context, session)
        except Exception:
            logger.exception(f"[arrivals.text] EXCEPTION in STEP_C_SERVICES  user={uid}")
        return

    logger.warning(
        f"[arrivals.text] UNHANDLED step={step!r} — fell through all branches"
        f"  session=({_session_debug_str(session)})  user={uid}"
    )


# ── Photo handler (group 11) ──────────────────────────────────────────────────

async def _handle_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id if update.effective_user else "?"
    # ✅ الحماية داخل المعالِج نفسه — معالِج صور عام (يطابق أي صورة/مستند صورة).
    if not update.effective_user or not _is_authorized(update.effective_user.id):
        return
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

        # ✅ الفيزا وختم الدخول أصبحا رفعة واحدة ("صورة الفيزا مع ختم الدخول")
        # بطلب المستخدم — خطوة STEP_P_ENTRY_STAMP لم تعد جزءاً من التسلسل.
        # عمود entry_stamp_file_id يبقى في القاعدة للسجلات القديمة فقط.
        if step == STEP_P_VISA:
            session.current_patient["visa_file_id"] = file_id
            session.step = STEP_P_TICKETS
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_P_VISA (+stamp) → STEP_P_TICKETS  user={uid}")
            await _show_p_tickets(update, context, session)
            return

        if step == STEP_P_TICKETS:
            session.current_patient["tickets_file_id"] = file_id
            session.step = STEP_P_RESIDENCE
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_P_TICKETS → STEP_P_RESIDENCE  user={uid}")
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
            session.step = STEP_C_TICKETS
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_C_VISA (+stamp) → STEP_C_TICKETS  user={uid}")
            await _show_c_tickets(update, context, session)
            return

        if step == STEP_C_TICKETS:
            session.current_companion["tickets_file_id"] = file_id
            session.step = STEP_C_RESIDENCE
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_C_TICKETS → STEP_C_RESIDENCE  user={uid}")
            await _show_c_residence(update, context, session)
            return

        if step == STEP_C_RESIDENCE:
            session.current_companion["residence_file_id"] = file_id
            session.step = STEP_C_RESIDENCE_ADDRESS
            session.save(context.user_data)
            logger.info(f"[arrivals.photo] STEP_C_RESIDENCE → STEP_C_RESIDENCE_ADDRESS  user={uid}")
            await _show_c_residence_address(update, context, session)
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
