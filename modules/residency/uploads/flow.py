# modules/residency/uploads/flow.py
# معالِج rnu: — أفعال ملحقة بملف مريض واحد: رفع فورم C، رفع الصورة
# الشخصية. الانتقال لمرحلة إقامة جديدة صار عبر زر «🪪 تجديد الإقامة»
# (`rnr:start_`) وحده — لا تدرّج وسيط (تم الرفع/تم الاستلام) بعد الآن.
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

from modules.residency.uploads.views import (
    build_form_c_saved, build_photo_saved, build_photo_target_picker,
    build_document_type_menu, build_document_target_picker, build_document_saved,
    DOCUMENT_TYPES,
)

logger = logging.getLogger(__name__)

RNU = "rnu"
_RKEY_FORM_C  = "res.uploads.form_c"
_RKEY_PHOTO   = "res.uploads.photo"
_RKEY_DOCUMENT = "res.uploads.document"
_MODULE_KEY  = "residency"

# المريض المستهدَف برفع فورم C — يُحفظ خارج جلسة الرفع لأن collector
# يعيد الملفات فقط ولا يحمل سياق المتصل.
_CTX_FORM_C_PROFILE = "_rnu_form_c_profile_id"
# ✅ هدف الصورة الشخصية — قد يكون المريض نفسه أو أحد مرافقيه، فيُخزَّن
# profile_id دائماً (للعودة لملف المريض) مع companion_id عند وجوده.
_CTX_PHOTO_TARGET   = "_rnu_photo_target"
# ✅ نفس فكرة _CTX_PHOTO_TARGET لكن لجواز/فيزا/تذكرة — يحمل doc_type أيضاً
# لأن معالِج نتيجة الرفع واحد مشترك للأنواع الثلاثة.
_CTX_DOC_TARGET     = "_rnu_doc_target"


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
    تُستدعى بعد كل فعل هنا (تقدّم مرحلة، أو نتيجة رفع فورم C/الصورة الملغاة)
    لإعادة رسم شاشة ملف المريض بحالته المُحدَّثة — لا قائمة.

    `_safe_edit` تُحرّر الرسالة إن جاء الاستدعاء من ضغطة زر (adv_)، وترسل
    رسالة جديدة إن جاء من نتيجة رفع (لا query نشِط حينها).
    """
    from modules.residency.profiles.repository import (
        get_profile_by_id, get_companions_for_profile,
        get_pending_missing_items,
    )
    from modules.residency.profiles.views import build_profile_detail

    profile = get_profile_by_id(profile_id)
    if profile is None:
        await _safe_edit(update, "❌ لم يتم العثور على الملف.", None)
        return
    companions    = get_companions_for_profile(profile_id)
    missing_items = get_pending_missing_items(profile_id)
    text, kb   = build_profile_detail(profile, companions, missing_items)
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

    # ── رفع الصورة الشخصية — اختيار الهدف أولاً (مريض أو مرافق) ────────────────
    if action.startswith("photosel_"):
        # format: photosel_{profile_id}_{"p" | companion_id}
        rest = action[len("photosel_"):]
        profile_id_str, _, who = rest.partition("_")
        profile_id = int(profile_id_str)

        from modules.residency.profiles.repository import get_profile_by_id, get_companions_for_profile
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return

        if who == "p":
            context.user_data[_CTX_PHOTO_TARGET] = {"profile_id": profile_id, "companion_id": None}
            target_name = profile.name
        else:
            companion_id = int(who)
            companions = get_companions_for_profile(profile_id)
            match = next((c for c in companions if c.id == companion_id), None)
            if match is None:
                await query.edit_message_text("❌ لم يتم العثور على المرافق.", parse_mode="Markdown")
                return
            context.user_data[_CTX_PHOTO_TARGET] = {"profile_id": profile_id, "companion_id": companion_id}
            target_name = match.name

        await uploads.open(
            update, context,
            title=f"🖼️ أرسل الصورة الشخصية لـ «{target_name}»",
            return_to=_RKEY_PHOTO,
            max_files=1,
        )
        return

    # ── رفع الصورة الشخصية (من ملف المريض) ────────────────────────────────────
    if action.startswith("photo_"):
        profile_id = int(action[6:])
        from modules.residency.profiles.repository import get_profile_by_id, get_companions_for_profile
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        companions = get_companions_for_profile(profile_id)

        # ✅ بلا مرافقين: لا داعي لتخيير المستخدم بين خيار واحد فقط — رفع
        # مباشر للمريض كالسابق تماماً. بمرافقين: شاشة اختيار «لمن الصورة؟».
        if not companions:
            context.user_data[_CTX_PHOTO_TARGET] = {"profile_id": profile_id, "companion_id": None}
            await uploads.open(
                update, context,
                title=f"🖼️ أرسل الصورة الشخصية لـ «{profile.name}»",
                return_to=_RKEY_PHOTO,
                max_files=1,
            )
            return

        text, kb = build_photo_target_picker(profile.name, profile_id, companions)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
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

    # ── القائمة الموحَّدة «🗂️ رفع وثيقة» ──────────────────────────────────────
    if action.startswith("docmenu_"):
        profile_id = int(action[len("docmenu_"):])
        text, kb = build_document_type_menu(profile_id)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── جواز/فيزا/تذكرة — اختيار الهدف أولاً (مريض أو مرافق) ───────────────────
    if action.startswith("docsel_"):
        # format: docsel_{doc_type}_{profile_id}_{"p" | companion_id}
        rest = action[len("docsel_"):]
        doc_type, _, rest = rest.partition("_")
        profile_id_str, _, who = rest.partition("_")
        profile_id = int(profile_id_str)

        from modules.residency.profiles.repository import get_profile_by_id, get_companions_for_profile
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return

        icon, label = DOCUMENT_TYPES[doc_type]
        if who == "p":
            context.user_data[_CTX_DOC_TARGET] = {"doc_type": doc_type, "profile_id": profile_id, "companion_id": None}
            target_name = profile.name
        else:
            companion_id = int(who)
            companions = get_companions_for_profile(profile_id)
            match = next((c for c in companions if c.id == companion_id), None)
            if match is None:
                await query.edit_message_text("❌ لم يتم العثور على المرافق.", parse_mode="Markdown")
                return
            context.user_data[_CTX_DOC_TARGET] = {"doc_type": doc_type, "profile_id": profile_id, "companion_id": companion_id}
            target_name = match.name

        await uploads.open(
            update, context,
            title=f"{icon} أرسل {label} لـ «{target_name}»",
            return_to=_RKEY_DOCUMENT,
            max_files=1,
        )
        return

    # ── جواز/فيزا/تذكرة (من ملف المريض) ─────────────────────────────────────────
    if action.startswith("doc_"):
        rest = action[len("doc_"):]
        doc_type, _, profile_id_str = rest.partition("_")
        profile_id = int(profile_id_str)
        if doc_type not in DOCUMENT_TYPES:
            logger.warning(f"[residency.uploads.cb] unknown doc_type={doc_type!r}")
            return

        from modules.residency.profiles.repository import get_profile_by_id, get_companions_for_profile
        profile = get_profile_by_id(profile_id)
        if profile is None:
            await query.edit_message_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
            return
        companions = get_companions_for_profile(profile_id)
        icon, label = DOCUMENT_TYPES[doc_type]

        # ✅ بلا مرافقين: رفع مباشر للمريض بلا شاشة اختيار (نفس منطق الصورة
        # الشخصية) — بمرافقين: شاشة اختيار «لمن الوثيقة؟».
        if not companions:
            context.user_data[_CTX_DOC_TARGET] = {"doc_type": doc_type, "profile_id": profile_id, "companion_id": None}
            await uploads.open(
                update, context,
                title=f"{icon} أرسل {label} لـ «{profile.name}»",
                return_to=_RKEY_DOCUMENT,
                max_files=1,
            )
            return

        text, kb = build_document_target_picker(doc_type, profile.name, profile_id, companions)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    logger.warning(f"[residency.uploads.cb] unhandled action={action!r}  user={uid}")


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
    target = context.user_data.pop(_CTX_PHOTO_TARGET, None) or {}
    profile_id   = target.get("profile_id")
    companion_id = target.get("companion_id")

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

    performed_by = update.effective_user.id if update.effective_user else None
    if companion_id:
        from modules.residency.uploads.repository import save_companion_photo
        name = save_companion_photo(
            profile_id=profile_id, companion_id=companion_id,
            file_id=final_file_id, performed_by=performed_by,
        )
    else:
        from modules.residency.uploads.repository import save_patient_photo
        name = save_patient_photo(
            profile_id=profile_id, file_id=final_file_id, performed_by=performed_by,
        )
    text, kb = build_photo_saved(name, profile_id, resized=resized_ok)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _on_document(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نتيجة رفع جواز/فيزا/تذكرة — نفس بنية _on_photo لكن بلا معالجة صورة."""
    target = context.user_data.pop(_CTX_DOC_TARGET, None) or {}
    doc_type     = target.get("doc_type")
    profile_id   = target.get("profile_id")
    companion_id = target.get("companion_id")

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
            "⚠️ لم يصل أي ملف. حاول مجدداً.", parse_mode="Markdown")
        return

    from modules.residency.uploads.repository import save_document
    name = save_document(
        doc_type=doc_type, profile_id=profile_id, companion_id=companion_id,
        file_id=file_id, performed_by=update.effective_user.id if update.effective_user else None,
    )
    text, kb = build_document_saved(doc_type, name, profile_id)
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── التسجيل ───────────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    app.add_handler(
        CallbackQueryHandler(_dispatch_callback, pattern=r"^rnu:"),
        group=20,
    )
    logger.info("[residency.uploads] rnu: CallbackQueryHandler registered (group 20)")


def register_result_routes() -> None:
    _register_route(_RKEY_FORM_C,   _on_form_c)
    _register_route(_RKEY_PHOTO,    _on_photo)
    _register_route(_RKEY_DOCUMENT, _on_document)
    logger.info("[residency.uploads] result routes registered")
