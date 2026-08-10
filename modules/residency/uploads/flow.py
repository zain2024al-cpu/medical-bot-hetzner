# modules/residency/uploads/flow.py
# معالِج rnu: — وحدة «📤 الرفع والمتابعة».
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

from modules.residency.constants import PROFILES_PAGE_SIZE
from modules.residency.uploads.views import (
    RNU, build_uploads_hub, build_papers_list,
    build_service_patient_list, build_service_menu,
    build_form_c_saved, build_not_found, build_photo_saved,
)

logger = logging.getLogger(__name__)

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


# ── الشاشات ───────────────────────────────────────────────────────────────────

async def show_hub(update, context) -> None:
    from modules.residency.uploads.repository import get_hub_counts
    text, kb = build_uploads_hub(get_hub_counts())
    await _safe_edit(update, text, kb)


async def _show_papers(update, context) -> None:
    from modules.residency.uploads.repository import get_papers_entries
    text, kb = build_papers_list(get_papers_entries())
    await _safe_edit(update, text, kb)


async def _show_service_list(update, context, page: int) -> None:
    from modules.residency.profiles.repository import get_profiles_page
    profiles, total = get_profiles_page(page=page)
    context.user_data["_rnu_service_page"] = page
    text, kb = build_service_patient_list(
        profiles, page=page, total=total, page_size=PROFILES_PAGE_SIZE,
    )
    await _safe_edit(update, text, kb)


async def _show_service_menu(update, context, profile_id: int) -> None:
    from modules.residency.profiles.repository import (
        get_profile_by_id, get_companions_for_profile,
    )
    profile = get_profile_by_id(profile_id)
    if profile is None:
        text, kb = build_not_found()
        await _safe_edit(update, text, kb)
        return
    text, kb = build_service_menu(profile, get_companions_for_profile(profile_id))
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

    if action == "hub":
        await show_hub(update, context); return

    if action == "papers":
        await _show_papers(update, context); return

    if action == "service":
        await _show_service_list(update, context, page=0); return

    if action.startswith("spage_"):
        await _show_service_list(update, context, page=int(action[6:])); return

    if action.startswith("svc_"):
        await _show_service_menu(update, context, int(action[4:])); return

    # ── تقدّم مرحلة (المريض + كل مرافقيه) ────────────────────────────────────
    if action.startswith("adv_"):
        profile_id = int(action[4:])
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
        await _notify(context, name, new_status)
        await _show_papers(update, context)
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
        await _show_papers(update, context)
        return

    # ── رفع الصورة الشخصية (من «➕ إضافة خدمة» حصراً) ──────────────────────────
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


async def _notify(context, name: str, new_status: str) -> None:
    from modules.residency.views import format_status
    try:
        from modules.residency.report_publisher import publish_event
        await publish_event(
            context.bot,
            action_label=format_status(new_status),
            patient_name=name,
            body_lines=["👥 يشمل المرافقين"],
        )
    except Exception as exc:
        logger.warning(f"[residency.uploads] publish_event failed: {exc}")


# ── نتيجة رفع فورم C ──────────────────────────────────────────────────────────

async def _on_form_c(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile_id = context.user_data.pop(_CTX_FORM_C_PROFILE, None)

    if result.cancelled or not profile_id:
        text, kb = build_uploads_hub(_counts())
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
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
    text, kb = build_form_c_saved(name)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _on_photo(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile_id = context.user_data.pop(_CTX_PHOTO_PROFILE, None)

    if result.cancelled or not profile_id:
        text, kb = build_uploads_hub(_counts())
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
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
    text, kb = build_photo_saved(name, resized=resized_ok)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def _counts() -> dict:
    from modules.residency.uploads.repository import get_hub_counts
    return get_hub_counts()


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
