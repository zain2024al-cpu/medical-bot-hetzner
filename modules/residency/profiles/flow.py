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

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.calendar_picker import build_calendar
from shared.result_router import register as _register_route

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
    build_add_companion_name_prompt, build_add_companion_visa_expiry_prompt,
    build_add_companion_saved,
    build_missing_item_prompt, build_missing_item_saved,
    build_missing_items_pick, build_missing_item_resolved,
)
from modules.residency.profiles.repository import (
    get_profiles_page, get_profile_by_id,
    get_companions_for_profile, get_history_for_profile,
    search_profiles, get_pending_missing_items,
)

logger = logging.getLogger(__name__)

_MODULE_KEY = "residency"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


# ── إضافة مرافق لملف موجود (زر «➕ إضافة مرافق» في ملف المريض) ─────────────────
# جلسة خفيفة بلا dataclass — ثلاث خطوات فقط (اسم، تاريخ تأشيرة اختياري،
# صورتان اختياريتان)، بخلاف AddProfileSession الضخمة المخصَّصة لدفعة كاملة
# من مرضى جدد.
_CTX_ADD_COMP = "_rna_add_comp"
_RKEY_ADD_COMP_PASSPORT = "res.profiles.add_comp.passport"
_RKEY_ADD_COMP_VISA     = "res.profiles.add_comp.visa"

# ── طلب ناقص: تسجيل جديد أو رفع لإغلاق طلب قائم ────────────────────────────────
# ⚠️ نفس الاسم الحرفي يُستخدَم في modules/residency/uploads/flow.py (زر
# «❌ لا، يوجد نقص» عند تقديم الأوراق) — كلاهما يكتب نفس شكل القاموس، حتى
# تُعالَج الخطوة النصّية من هنا بغضّ النظر عن أي شاشة فتحتها.
_CTX_MISSING_ITEM = "_res_missing_item"
_CTX_MISSING_RESOLVE = "_res_missing_resolve"
_RKEY_MISSING_RESOLVE = "res.profiles.missing_resolve"


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

    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[res.profiles.cb] 🚫 blocked unauthorized user={uid}  action={action!r}")
        return

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
        from modules.residency.followup.repository import get_expiring_soon, get_dependent_pending
        profiles, total = get_profiles_page(page=page)
        text, kb = build_archive_list(
            profiles, page=page, total=total,
            expiring_count=len(get_expiring_soon()),
            pending_count=len(get_dependent_pending()),
        )
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Archive export (Excel / PDF) ──────────────────────────────────────────
    # نفس المنطق للصيغتين — المُنتِج والامتداد فقط يختلفان.
    if action in ("export", "export_pdf"):
        is_pdf = action == "export_pdf"
        await query.answer("⏳ جارٍ تجهيز الملف…")
        try:
            if is_pdf:
                from services.residency_archive_pdf import build_residency_archive_pdf as _build
            else:
                from services.residency_archive_excel import build_residency_archive_export as _build
            buf, count = _build()
        except Exception:
            logger.exception(f"[res.profiles.cb] archive export FAILED  pdf={is_pdf}  user={uid}")
            await query.answer("❌ تعذّر تجهيز الملف", show_alert=True)
            return

        if buf is None:
            await query.answer("لا يوجد مرضى في الأرشيف بعد.", show_alert=True)
            return

        from datetime import date as _date
        ext      = "pdf" if is_pdf else "xlsx"
        filename = f"residency_archive_{_date.today().strftime('%Y-%m-%d')}.{ext}"
        try:
            await query.message.reply_document(
                document=buf,
                filename=filename,
                caption=(
                    f"📁 **أرشيف الإقامات**\n"
                    f"👥 {count} شخص (مرضى ومرافقون)\n"
                    f"📅 {_date.today().strftime('%d/%m/%Y')}\n\n"
                    f"🔴 منتهية  🟠 خلال 30 يوم  🟡 خلال 90 يوم"
                ),
                parse_mode="Markdown",
            )
            logger.info(
                f"[res.profiles.cb] archive exported  fmt={ext}  rows={count}  user={uid}"
            )
        except Exception:
            logger.exception(f"[res.profiles.cb] failed to send archive file  user={uid}")
            await query.answer("❌ تعذّر إرسال الملف", show_alert=True)
        return

    # ── Profile view ──────────────────────────────────────────────────────────
    if action.startswith("view_"):
        profile_id = int(action[5:])
        profile    = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        companions    = get_companions_for_profile(profile_id)
        history       = get_history_for_profile(profile_id)
        missing_items = get_pending_missing_items(profile_id)
        text, kb   = build_profile_detail(profile, companions, history, missing_items)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── إضافة مرافق لملف موجود ──────────────────────────────────────────────────
    # ⚠️ الفروع الأخصّ (accal_/skipexp_) قبل الحالة العامة add_comp_{id} عمداً،
    # وإلا لالتُقطت بها أولاً فحاولت تحويل نصّها الكامل إلى رقم فتفشل.
    if action.startswith("add_comp_cal_"):
        profile_id = int(action[len("add_comp_cal_"):])
        from datetime import datetime as _dt
        now = _dt.utcnow()
        text, kb = build_calendar(
            now.year, now.month, callback_prefix=f"{RNA}:accal",
            back_callback=f"{RNA}:add_comp_skipexp_{profile_id}",
        )
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action.startswith("add_comp_skipexp_"):
        profile_id = int(action[len("add_comp_skipexp_"):])
        await _add_comp_start_passport(update, context, profile_id)
        return

    if action.startswith("add_comp_"):
        profile_id = int(action[len("add_comp_"):])
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        context.user_data[_CTX_ADD_COMP] = {
            "profile_id": profile_id, "name": "", "visa_expiry": "",
            "passport_file_id": "", "visa_file_id": "",
        }
        text, kb = build_add_companion_name_prompt(profile.name, profile_id)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── طلب ناقص: تسجيل جديد (مستقلّ — متاح في أي وقت، لا فقط عند التقديم) ──
    if action.startswith("missing_new_"):
        profile_id = int(action[len("missing_new_"):])
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        context.user_data[_CTX_MISSING_ITEM] = {"profile_id": profile_id, "advance_stage": False}
        text, kb = build_missing_item_prompt(profile.name, profile_id)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── طلب ناقص: اختيار أيّ الطلبات (عند وجود أكثر من واحد) ────────────────
    if action.startswith("missing_pick_"):
        profile_id = int(action[len("missing_pick_"):])
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        items = get_pending_missing_items(profile_id)
        text, kb = build_missing_items_pick(profile.name, profile_id, items)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── طلب ناقص: رفع المستند لإغلاق طلب محدَّد ──────────────────────────────
    if action.startswith("missing_resolve_"):
        item_id = int(action[len("missing_resolve_"):])
        context.user_data[_CTX_MISSING_RESOLVE] = {"item_id": item_id}
        from shared.uploads import collector as _uploads
        await _uploads.open(
            update, context,
            title="📎 أرسل صورة أو ملف الوثيقة المرفوعة لإغلاق هذا الطلب",
            return_to=_RKEY_MISSING_RESOLVE,
            max_files=1,
        )
        return

    # التقويم المخصَّص لهذه الخطوة وحدها — بادئة "accal:" منفصلة تماماً عن
    # "cal_pick:"/"cal_prev:" العامة (الويزارد القديم المعطَّل يستخدمها
    # بلا بادئة)، فلا التباس بين الجلستين رغم استخدام نفس build_calendar.
    if action.startswith("accal:cal_pick:"):
        parts = action[len("accal:cal_pick:"):].split(":")
        ctx_data = context.user_data.get(_CTX_ADD_COMP)
        if not ctx_data:
            await query.edit_message_text("❌ انتهت الجلسة. ابدأ من جديد.", parse_mode="Markdown")
            return
        from datetime import date as _date
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        ctx_data["visa_expiry"] = _date(y, m, d).isoformat()
        profile_id = ctx_data["profile_id"]
        context.user_data[_CTX_ADD_COMP] = ctx_data
        await _add_comp_start_passport(update, context, profile_id)
        return

    if action.startswith("accal:cal_prev:") or action.startswith("accal:cal_next:"):
        ctx_data = context.user_data.get(_CTX_ADD_COMP)
        if not ctx_data:
            await query.edit_message_text("❌ انتهت الجلسة. ابدأ من جديد.", parse_mode="Markdown")
            return
        profile_id = ctx_data["profile_id"]
        y, m = (int(p) for p in action.split(":")[2:4])
        text, kb = build_calendar(
            y, m, callback_prefix=f"{RNA}:accal",
            back_callback=f"{RNA}:add_comp_skipexp_{profile_id}",
        )
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if action == "accal:cal_noop":
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
    # ✅ build_calendar يُصدر cal_prev/cal_next — لا cal_nav. بدونهما كانت
    # أسهم ◀️/▶️ في التقويم لا تفعل شيئاً إطلاقاً (النقر يسقط بلا معالج).
    if action.startswith(("cal_nav:", "cal_prev:", "cal_next:")):
        parts = action.split(":")
        try:
            y, m = int(parts[1]), int(parts[2])
        except (IndexError, ValueError):
            logger.warning(f"[res.profiles.cb] cal nav parse error  action={action!r}  user={uid}")
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
                profile       = get_profile_by_id(edit_id)
                companions    = get_companions_for_profile(edit_id)
                history       = get_history_for_profile(edit_id)
                missing_items = get_pending_missing_items(edit_id)
                text, kb   = build_profile_detail(profile, companions, history, missing_items)
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


# ── إضافة مرافق — رفع الوثائق الاختيارية ───────────────────────────────────────

async def _add_comp_start_passport(update, context, profile_id: int) -> None:
    from shared.uploads import collector as _uploads
    await _uploads.open(
        update, context,
        title="🛂 أرسل صورة جواز سفر المرافق، أو اضغط ⏭️ تخطي إن لم تتوفر بعد",
        return_to=_RKEY_ADD_COMP_PASSPORT,
        max_files=1,
    )


async def _on_add_comp_passport(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx_data = context.user_data.get(_CTX_ADD_COMP)
    if not ctx_data:
        await update.effective_message.reply_text("⚠️ انتهت الجلسة. ابدأ من جديد.", parse_mode="Markdown")
        return

    if result.cancelled:
        context.user_data.pop(_CTX_ADD_COMP, None)
        await update.effective_message.reply_text("❌ أُلغيت إضافة المرافق.", parse_mode="Markdown")
        return

    if result.files:
        f = result.files[0]
        ctx_data["passport_file_id"] = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""
        context.user_data[_CTX_ADD_COMP] = ctx_data

    from shared.uploads import collector as _uploads
    await _uploads.open(
        update, context,
        title="📋 أرسل صورة التأشيرة (وختم الدخول)، أو اضغط ⏭️ تخطي إن لم تتوفر بعد",
        return_to=_RKEY_ADD_COMP_VISA,
        max_files=1,
    )


async def _on_add_comp_visa(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx_data = context.user_data.pop(_CTX_ADD_COMP, None)
    if not ctx_data:
        await update.effective_message.reply_text("⚠️ انتهت الجلسة. ابدأ من جديد.", parse_mode="Markdown")
        return

    if result.cancelled:
        await update.effective_message.reply_text("❌ أُلغيت إضافة المرافق.", parse_mode="Markdown")
        return

    if result.files:
        f = result.files[0]
        ctx_data["visa_file_id"] = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""

    from modules.residency.profiles.models import add_companion_to_profile
    name = add_companion_to_profile(
        profile_id=       ctx_data["profile_id"],
        name=             ctx_data["name"],
        visa_expiry=      ctx_data.get("visa_expiry", ""),
        passport_file_id= ctx_data.get("passport_file_id", ""),
        visa_file_id=     ctx_data.get("visa_file_id", ""),
        performed_by=     update.effective_user.id if update.effective_user else None,
    )
    text, kb = build_add_companion_saved(name or ctx_data["name"], ctx_data["profile_id"])
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── طلب ناقص — رفع المستند لإغلاق طلب قائم ─────────────────────────────────────

async def _on_missing_resolve(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx_data = context.user_data.pop(_CTX_MISSING_RESOLVE, None)
    if not ctx_data:
        await update.effective_message.reply_text("⚠️ انتهت الجلسة. ابدأ من جديد.", parse_mode="Markdown")
        return

    if result.cancelled:
        await update.effective_message.reply_text("❌ أُلغي رفع الوثيقة.", parse_mode="Markdown")
        return

    if not result.files:
        await update.effective_message.reply_text("⚠️ لم يُرسَل أي ملف.", parse_mode="Markdown")
        return

    f = result.files[0]
    file_id = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""

    from modules.residency.profiles.models import resolve_missing_item
    uid = update.effective_user.id if update.effective_user else None
    resolved = resolve_missing_item(item_id=ctx_data["item_id"], file_id=file_id, performed_by=uid)
    if resolved is None:
        await update.effective_message.reply_text("❌ لم يتم العثور على الطلب.", parse_mode="Markdown")
        return

    profile_id, description = resolved
    profile = get_profile_by_id(profile_id)
    profile_name = profile.name if profile else "—"

    from modules.residency.report_publisher import publish_event
    try:
        await publish_event(
            context.bot, action_label="✅ تم رفع الطلب — جاري انتظار الإقامة",
            patient_name=profile_name, body_lines=[f"الطلب: {description}"],
        )
    except Exception as exc:
        logger.warning(f"[res.profiles.missing_resolve] publish_event failed: {exc}")

    text, kb = build_missing_item_resolved(profile_name, description, profile_id)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Text handler (group 16) ───────────────────────────────────────────────────

async def _handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ⚠️ effective_message لا update.message — فلتر filters.TEXT المسجّل به
    # هذا المعالِج يقبل الرسائل المعدَلة أيضاً، وفيها update.message=None
    # فيرتدّ المعالِج صامتاً بلا سجلّ ولا ردّ. نفس العطب المُصلَح
    # في arrivals/flow.py وadmin_daily_patients.py.
    msg = update.effective_message
    if msg is None:
        return

    uid = update.effective_user.id if update.effective_user else "?"

    # ✅ الحماية داخل المعالِج نفسه — هذا معالِج نصوص عام (يطابق أي رسالة
    # نصية)، فيجب ألا يتقدّم بأي منطق داخلي قبل التحقق من الصلاحية.
    if not update.effective_user or not _is_authorized(update.effective_user.id):
        return

    # ── Search mode ───────────────────────────────────────────────────────────
    if context.user_data.get("_res_search_active"):
        query_text = (msg.text or "").strip()
        if not query_text:
            return
        context.user_data.pop("_res_search_active", None)
        results = search_profiles(query_text)
        if not results:
            text, kb = build_search_prompt(error=True)
            await msg.reply_text(text, reply_markup=kb, parse_mode="Markdown")
            context.user_data["_res_search_active"] = True
            return
        text, kb = build_search_results(results, query_text)
        await msg.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── إضافة مرافق — خطوة الاسم ──────────────────────────────────────────────
    _add_comp = context.user_data.get(_CTX_ADD_COMP)
    if _add_comp is not None and not _add_comp.get("name"):
        name = (msg.text or "").strip()
        if not name:
            return
        _add_comp["name"] = name
        context.user_data[_CTX_ADD_COMP] = _add_comp
        text, kb = build_add_companion_visa_expiry_prompt(name, _add_comp["profile_id"])
        await msg.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── طلب ناقص — إدخال الوصف يدوياً ─────────────────────────────────────────
    _missing = context.user_data.pop(_CTX_MISSING_ITEM, None)
    if _missing is not None:
        description = (msg.text or "").strip()
        if not description:
            context.user_data[_CTX_MISSING_ITEM] = _missing
            await msg.reply_text("⚠️ لا يمكن ترك الوصف فارغاً. أرسل نص الطلب الناقص.")
            return

        profile_id = _missing["profile_id"]
        profile = get_profile_by_id(profile_id)
        profile_name = profile.name if profile else "—"

        from modules.residency.profiles.models import add_missing_item
        add_missing_item(
            profile_id=profile_id,
            description=description,
            performed_by=uid if isinstance(uid, int) else None,
        )

        from modules.residency.report_publisher import publish_event

        if _missing.get("advance_stage"):
            from modules.residency.uploads.repository import advance_papers_stage
            ok, name, new_status = advance_papers_stage(profile_id=profile_id, performed_by=uid if isinstance(uid, int) else None)
            if ok:
                from modules.residency.views import format_status
                comps = get_companions_for_profile(profile_id)
                body_lines = (
                    [f"👥 المرافقون: {'، '.join(c.name for c in comps)}"] if comps
                    else ["👥 لا يوجد مرافقون"]
                )
                body_lines.append(f"⚠️ الطلب الناقص: {description}")
                try:
                    await publish_event(
                        context.bot, action_label=format_status(new_status),
                        patient_name=name, body_lines=body_lines,
                    )
                except Exception as exc:
                    logger.warning(f"[res.profiles.text] publish_event failed: {exc}")
        else:
            try:
                await publish_event(
                    context.bot, action_label="📝 طلب جديد",
                    patient_name=profile_name, body_lines=[f"الطلب: {description}"],
                )
            except Exception as exc:
                logger.warning(f"[res.profiles.text] publish_event failed: {exc}")

        text, kb = build_missing_item_saved(profile_name, description, profile_id)
        await msg.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ⚠️ لا خطوات نصّية متبقية في تجديد الإقامة (rnr:) — رقم الإقامة
    # والملاحظات أُزيلا من التدفق (قرار المستخدم: فقط تاريخ + وثيقة).

    # ── Add-batch text steps ──────────────────────────────────────────────────
    session = AddProfileSession.load(context.user_data)
    if session is None or session.step not in _TEXT_STEPS:
        return

    text = (msg.text or "").strip()
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
            await msg.reply_text(prompt, reply_markup=kb, parse_mode="Markdown")
            return
        session.created_at = dt.isoformat()
        session.step = STEP_PATIENT_COUNT
        session.save(context.user_data)
        logger.info(f"[res.profiles.text] STEP_DATE_CUSTOM → STEP_PATIENT_COUNT  date={dt.date()}  user={uid}")
        await _show_patient_count(update, context, session)
        return

    if step == STEP_P_NAME:
        if not text:
            await msg.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
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
            await msg.reply_text("⚠️ الاسم لا يمكن أن يكون فارغاً.")
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
    # ✅ الحماية داخل المعالِج نفسه — معالِج صور عام (يطابق أي صورة/مستند صورة).
    if not update.effective_user or not _is_authorized(update.effective_user.id):
        return
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
    _register_route(_RKEY_ADD_COMP_PASSPORT, _on_add_comp_passport)
    _register_route(_RKEY_ADD_COMP_VISA,     _on_add_comp_visa)
    _register_route(_RKEY_MISSING_RESOLVE,   _on_missing_resolve)
    logger.info("[residency.profiles] result routes registered")
