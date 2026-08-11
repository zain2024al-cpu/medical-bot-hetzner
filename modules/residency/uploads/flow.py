# modules/residency/uploads/flow.py
# معالِج rnu: — أفعال ملحقة بملف مريض واحد: تقدّم/تراجع مرحلة الأوراق،
# رفع فورم C، رفع الصورة الشخصية.
#
# ⚠️ لا شاشة قائمة هنا بعد الآن — «📤 الرفع والمتابعة» بأزرارها ومنتقياتها
# حُذفت (قرار المستخدم: كل شيء عبر «📁 أرشيف المرضى» ← ملف المريض). كل
# فعل هنا يُستدعى مباشرةً من `rnu:{action}_{profile_id}` على زر في
# `build_profile_detail` نفسه، وبعد التنفيذ يُعاد رسم **نفس شاشة الملف**
# لا قائمة — فالمستخدم يبقى حيث كان.
#
# Handler group:
#   group 20  CallbackQueryHandler(^rnu:)   — نفس مجموعة بقية callbacks الإقامة
#                                             (مقيَّدة بالنمط فلا تعارض)
#
# ⚠️ لا يُكرَّر هنا شيء من مسار الإصدار: زر «🪪 رفع التمديد الجديد» و«تسجيل
# الإقامة الجديدة» كلاهما يُصدر callback_data بصيغة `rnr:start_{id}` فيلتقطه
# معالج التجديد الموجود كما هو (تقويم الإقامة الجديدة + رقم الإقامة + رفع
# الوثيقة + حلقة المرافقين). بناء نسخة ثانية منه كان سيعني تدفقين ينحرفان.

import io
import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.uploads import collector as uploads
from shared.result_router import register as _register_route

from modules.residency.uploads.views import build_form_c_saved, build_photo_saved

logger = logging.getLogger(__name__)

RNU = "rnu"
_RKEY_FORM_C = "res.uploads.form_c"
_RKEY_PHOTO  = "res.uploads.photo"
_MODULE_KEY  = "residency"

# المريض المستهدَف برفع فورم C — يُحفظ خارج جلسة الرفع لأن collector
# يعيد الملفات فقط ولا يحمل سياق المتصل.
_CTX_FORM_C_PROFILE = "_rnu_form_c_profile_id"
_CTX_PHOTO_PROFILE  = "_rnu_photo_profile_id"


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


async def _safe_edit(update, text, kb):
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            logger.debug("تم تجاهل استثناء في _safe_edit", exc_info=True)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── الشاشة الوحيدة المتبقّية: إعادة رسم ملف المريض نفسه ───────────────────────

async def _render_profile(update, context, profile_id: int) -> None:
    """
    تُستدعى بعد كل فعل هنا (تقدّم/تراجع مرحلة، أو نتيجة رفع فورم C/الصورة
    الملغاة) لإعادة رسم شاشة ملف المريض بحالته المُحدَّثة — لا قائمة.

    `_safe_edit` تُحرّر الرسالة إن جاء الاستدعاء من ضغطة زر (adv_/undo_)،
    وترسل رسالة جديدة إن جاء من نتيجة رفع (لا query نشِط حينها).
    """
    from modules.residency.profiles.repository import (
        get_profile_by_id, get_companions_for_profile, get_history_for_profile,
        get_pending_missing_items,
    )
    from modules.residency.profiles.views import build_profile_detail

    profile = get_profile_by_id(profile_id)
    if profile is None:
        await _safe_edit(update, "❌ لم يتم العثور على الملف.", None)
        return
    companions    = get_companions_for_profile(profile_id)
    history       = get_history_for_profile(profile_id)
    missing_items = get_pending_missing_items(profile_id)
    text, kb   = build_profile_detail(profile, companions, history, missing_items)
    await _safe_edit(update, text, kb)


# ── المرسِل ───────────────────────────────────────────────────────────────────

async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith(f"{RNU}:"):
        return
    action = data[len(RNU) + 1:]
    uid    = query.from_user.id if query.from_user else "?"

    # ✅ الحماية داخل المعالِج نفسه — مستقلة تماماً عن ظهور الزر في القائمة.
    if not query.from_user or not _is_authorized(query.from_user.id):
        logger.warning(f"[residency.uploads.cb] 🚫 blocked unauthorized user={uid}  action={action!r}")
        return

    logger.info(f"[residency.uploads.cb] action={action!r}  user={uid}")
    try:
        await _dispatch_inner(update, context, action, uid)
    except Exception:
        logger.exception(f"[residency.uploads.cb] unhandled  action={action!r}  user={uid}")


async def _dispatch_inner(update, context, action: str, uid) -> None:
    query   = update.callback_query
    user_id = uid if isinstance(uid, int) else None

    # ── تقدّم مرحلة (المريض + كل مرافقيه) ────────────────────────────────────
    # ⚠️ «تقديم الأوراق» تحديداً (النقلة إلى renewal_submitted) تمرّ أولاً
    # عبر سؤال «هل اكتملت؟» — بقية النقلات (استلام التمديد/تسجيل الإقامة
    # الجديدة) تبقى فورية كما كانت، فلا معنى لسؤال الاكتمال هناك.
    if action.startswith("adv_"):
        profile_id = int(action[4:])
        from modules.residency.constants import PAPERS_ADVANCE
        from modules.residency.profiles.repository import get_profile_by_id as _get_p
        _p = _get_p(profile_id)
        if _p is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        _next = PAPERS_ADVANCE.get(_p.status, (None, None))[1]
        if _next == "renewal_submitted":
            from modules.residency.profiles.views import build_submit_complete_prompt
            text, kb = build_submit_complete_prompt(_p.name, profile_id)
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return

        from modules.residency.uploads.repository import advance_papers_stage
        ok, name, new_status = advance_papers_stage(
            profile_id=profile_id, performed_by=user_id,
        )
        if not ok:
            # `extension_received` ⇒ الزر يفتح مسار الإصدار بدل تغيير حالة
            await _open_renewal(update, context, profile_id)
            return

        from modules.residency.views import format_status
        await query.answer(f"✅ {name} — {format_status(new_status)}", show_alert=True)
        await _notify(context, name, new_status, submitted_by=user_id)
        await _render_profile(update, context, profile_id)
        return

    # ── تقديم الأوراق: كاملة ⇒ تقدّم فوري ونشر عادي ───────────────────────────
    if action.startswith("submit_yes_"):
        profile_id = int(action[len("submit_yes_"):])
        from modules.residency.uploads.repository import advance_papers_stage
        ok, name, new_status = advance_papers_stage(profile_id=profile_id, performed_by=user_id)
        if ok:
            from modules.residency.views import format_status
            await query.answer(f"✅ {name} — {format_status(new_status)}", show_alert=True)
            await _notify(context, name, new_status, profile_id=profile_id, complete=True, submitted_by=user_id)
        await _render_profile(update, context, profile_id)
        return

    # ── تقديم الأوراق: ناقصة ⇒ تُطلَب التفاصيل عبر نصّ ثم تقدّم + نشر مختلف ───
    if action.startswith("submit_no_"):
        profile_id = int(action[len("submit_no_"):])
        from modules.residency.profiles.repository import get_profile_by_id as _get_p2
        from modules.residency.profiles.views import build_missing_item_prompt
        _p2 = _get_p2(profile_id)
        if _p2 is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        # ✅ نفس مفتاح السياق الذي يقرأه _handle_text_input في profiles/flow.py
        # (`_CTX_MISSING_ITEM`) — `advance_stage=True` يُفرّق هذا المسار عن
        # زر «📝 تسجيل طلب ناقص» المستقل الذي لا يُقدِّم الأوراق فور الحفظ.
        context.user_data["_res_missing_item"] = {"profile_id": profile_id, "advance_stage": True}
        text, kb = build_missing_item_prompt(_p2.name, profile_id)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── تراجع خطوة ────────────────────────────────────────────────────────────
    if action.startswith("undo_"):
        profile_id = int(action[5:])
        from modules.residency.uploads.repository import undo_papers_stage
        ok, name, restored = undo_papers_stage(
            profile_id=profile_id, performed_by=user_id,
        )
        if ok:
            from modules.residency.views import format_status
            await query.answer(f"↩️ {name} — {format_status(restored)}", show_alert=True)
        else:
            await query.answer("لا يوجد ما يمكن التراجع عنه.", show_alert=True)
        await _render_profile(update, context, profile_id)
        return

    # ── رفع الصورة الشخصية (من ملف المريض) ────────────────────────────────────
    if action.startswith("photo_"):
        profile_id = int(action[6:])
        context.user_data[_CTX_PHOTO_PROFILE] = profile_id
        await uploads.open(
            update, context,
            title="🖼️ أرسل الصورة الشخصية للمريض",
            return_to=_RKEY_PHOTO,
            max_files=1,
        )
        return

    # ── رفع فورم C ────────────────────────────────────────────────────────────
    if action.startswith("formc_"):
        profile_id = int(action[6:])
        context.user_data[_CTX_FORM_C_PROFILE] = profile_id
        await uploads.open(
            update, context,
            title="📄 أرفق فورم C (للعائلة)",
            return_to=_RKEY_FORM_C,
            max_files=1,
        )
        return

    logger.warning(f"[residency.uploads.cb] unhandled action={action!r}  user={uid}")


async def _open_renewal(update, context, profile_id: int) -> None:
    """يسلّم التحكم لمسار الإصدار الموجود `rnr:` بدل تكرار منطقه."""
    update.callback_query.data = f"rnr:start_{profile_id}"
    from modules.residency.renewal.flow import _dispatch_callback as rnr_cb
    await rnr_cb(update, context)


async def _notify(
    context, name: str, new_status: str, *,
    profile_id: int | None = None, complete: bool = True,
    submitted_by: int | None = None,
) -> None:
    """
    ينشر حدث تقدّم المرحلة. عند تمرير `profile_id` (مسار «تم التقديم» فقط)
    تُذكَر أسماء المرافقين فعلياً بدل سطر عام — طلب المستخدم صراحةً: «ينتشر
    في المجموعة أنه تم التقديم للمريض مع المرافقين».
    """
    from modules.residency.views import format_status
    body_lines = ["👥 يشمل المرافقين"]
    if profile_id is not None:
        try:
            from modules.residency.profiles.repository import get_companions_for_profile
            comps = get_companions_for_profile(profile_id)
            body_lines = (
                [f"👥 المرافقون: {'، '.join(c.name for c in comps)}"] if comps
                else ["👥 لا يوجد مرافقون"]
            )
            if not complete:
                body_lines.append("⚠️ ناقص — راجع ملف المريض للتفاصيل")
        except Exception:
            logger.debug("تم تجاهل استثناء أثناء جلب أسماء المرافقين للنشر", exc_info=True)
    try:
        from modules.residency.report_publisher import publish_event
        await publish_event(
            context.bot,
            action_label=format_status(new_status),
            patient_name=name,
            body_lines=body_lines,
            submitted_by=submitted_by,
        )
    except Exception as exc:
        logger.warning(f"[residency.uploads] publish_event failed: {exc}")


# ── نتيجة رفع فورم C ──────────────────────────────────────────────────────────

async def _on_form_c(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile_id = context.user_data.pop(_CTX_FORM_C_PROFILE, None)

    if result.cancelled or not profile_id:
        # ✅ يعود لملف المريض إن عُرف (الإلغاء يحدث بعد فتح الرفع من ملفه
        # فعلياً، فـ profile_id متاح غالباً)، وإلا رسالة عامة بلا كسر.
        if profile_id:
            await _render_profile(update, context, profile_id)
        else:
            await update.effective_message.reply_text("تم الإلغاء.", parse_mode="Markdown")
        return

    file_id = ""
    if result.files:
        f = result.files[0]
        file_id = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""

    if not file_id:
        await update.effective_message.reply_text(
            "⚠️ لم يصل أي ملف. حاول مجدداً.", parse_mode="Markdown")
        return

    from modules.residency.uploads.repository import save_form_c
    name = save_form_c(
        profile_id=profile_id, file_id=file_id,
        performed_by=update.effective_user.id if update.effective_user else None,
    )
    text, kb = build_form_c_saved(name, profile_id)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _on_photo(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile_id = context.user_data.pop(_CTX_PHOTO_PROFILE, None)

    if result.cancelled or not profile_id:
        if profile_id:
            await _render_profile(update, context, profile_id)
        else:
            await update.effective_message.reply_text("تم الإلغاء.", parse_mode="Markdown")
        return

    file_id = ""
    if result.files:
        f = result.files[0]
        file_id = f.to_dict().get("file_id", "") if hasattr(f, "to_dict") else ""

    if not file_id:
        await update.effective_message.reply_text(
            "⚠️ لم تصل أي صورة. حاول مجدداً.", parse_mode="Markdown")
        return

    # ✅ ضبط المقاس على 4×6 (طلب المستخدم صراحةً) — يُنزَّل الأصل، يُقصّ
    # ويُصغَّر، ثم يُعاد رفعه ليحمل file_id جديداً يمثّل النسخة المضبوطة لا
    # الأصل الخام. فشل المعالجة لا يُسقط العملية: يُحفَظ الأصل كما هو ويُخبَر
    # المستخدم أن الضبط لم يتم — أفضل من ضياع الصورة كلياً.
    resized_ok = False
    final_file_id = file_id
    try:
        from modules.residency.uploads.photo_processing import resize_to_4x6

        tg_file = await context.bot.get_file(file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        buf.seek(0)
        resized_bytes = resize_to_4x6(buf.read())

        sent = await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=io.BytesIO(resized_bytes),
            caption="🖼️ الصورة مضبوطة على مقاس 4×6",
        )
        final_file_id = sent.photo[-1].file_id
        resized_ok = True
    except Exception as exc:
        logger.warning(f"[residency.uploads] photo resize failed, saving original: {exc}")

    from modules.residency.uploads.repository import save_patient_photo
    name = save_patient_photo(
        profile_id=profile_id, file_id=final_file_id,
        performed_by=update.effective_user.id if update.effective_user else None,
    )
    text, kb = build_photo_saved(name, profile_id, resized=resized_ok)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── التسجيل ───────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^rnu:"),
        group=20,
    )
    logger.info("[residency.uploads] rnu: CallbackQueryHandler registered (group 20)")


def register_result_routes() -> None:
    _register_route(_RKEY_FORM_C, _on_form_c)
    _register_route(_RKEY_PHOTO,  _on_photo)
    logger.info("[residency.uploads] result routes registered")
