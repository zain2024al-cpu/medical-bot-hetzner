# modules/residency/flow.py
# معالِج كولباك "rn:" + استقبال الصور/الملفات — نظام دورة الحياة الكامل.

import io
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module
from shared.calendar_picker import build_calendar
from shared.multiselect import engine as multiselect
from shared.result_router import register as _register_route

from modules.residency.constants import (
    RN, STATUS_ORDER, STATUS_LABELS, STATUS_WAITING_ARRIVAL, STATUS_LEGACY_PENDING,
    STATUS_ACTIVE,
)
from modules.residency import models as rn_models
from modules.residency import repository as rn_repo
from modules.residency import views as rn_views

logger = logging.getLogger(__name__)

_MODULE_KEY = "residency"
_CTX_UPLOAD_TARGET = "_rn_upload_target"     # {"kind": "onboard_photo"|"issue_file"|"doc_upload", "person_id": int, ...}
_CTX_CAL_TARGET = "_rn_cal_target"           # {"kind": "onboard_remind"|"issue_expiry", "person_id": int, "root_id": int}
_CTX_SEARCH_ACTIVE = "_rn_search_active"
_CTX_DOC_NAME_ACTIVE = "_rn_doc_name_active"  # {"person_id": int} — بانتظار اسم وثيقة "أخرى" نصّياً
_CTX_PRINT_ROOT_ID = "_rn_print_root_id"      # root_id بانتظار نتيجة شاشة اختيار وثائق الطباعة
_RKEY_PRINT_CATS = "rn.print_categories"
# ✅ الحالة الهدف المُختارة، محفوظة أثناء جمع تواريخ التنبيه الناقصة قبل
# تنفيذ النقل — {"root_id": int, "status": str}.
_CTX_LEGACY_MOVE = "_rn_legacy_move"
# ✅ 🏠 معالجة "معلّقات من الحالات السابقة": الوضع ("ext"/"noext") يُحدَّد بالزر
# المضغوط ويُحمَل داخل _CTX_CAL_TARGET/_CTX_UPLOAD_TARGET نفسيهما — لا حاجة
# لمفتاح سياق مستقل (الموضع داخل الطابور يُشتَقّ من القاعدة فيبقى المسار
# قابلاً للاستئناف بعد أي انقطاع).


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


def _clear_transient_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_CTX_UPLOAD_TARGET, None)
    context.user_data.pop(_CTX_CAL_TARGET, None)
    context.user_data.pop(_CTX_SEARCH_ACTIVE, None)
    context.user_data.pop(_CTX_DOC_NAME_ACTIVE, None)
    # ✅ يُنظَّف أيضاً حتى لا تبقى حالة نقل معلّقة لعائلة أخرى بعد مغادرة
    # الشاشة. `_show_legacy_move_reminder` يستدعي هذه الدالة **ثم** يضبط
    # المفتاح من جديد، فالترتيب سليم.
    context.user_data.pop(_CTX_LEGACY_MOVE, None)


async def _edit(update: Update, text: str, kb) -> None:
    query = update.callback_query
    if query:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Main menu / status lists / family detail ──────────────────────────────────

async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    counts = rn_repo.get_status_counts()
    text, kb = rn_views.build_main_menu(counts)
    await _edit(update, text, kb)


# مفتاح فتات التنقّل — آخر قائمة حالة دخل منها المستخدم. يُستعمَل ليعود
# زر الرجوع في تفاصيل الطلب إلى قائمته لا إلى القائمة الرئيسية.
_CTX_LAST_STATUS = "_rn_last_status"


# رقم الصفحة المعروضة من قائمة الحالة — حتى يعود زر الرجوع إليها هي لا
# إلى أولها. من فتح طلباً من الصفحة الرابعة يُفترض أن يجدها كما تركها.
_CTX_LAST_PAGE = "_rn_last_page"


def _back_to_list(context) -> str:
    """وجهة الرجوع من تفاصيل الطلب — قائمته **وصفحتها**، وإلا القائمة الرئيسية."""
    ud = context.user_data or {}
    st = ud.get(_CTX_LAST_STATUS)
    if not st:
        return f"{RN}:menu"
    return f"{RN}:lpage:{st}:{int(ud.get(_CTX_LAST_PAGE, 0))}"


async def _show_status_list(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            status: str, page: int = 0) -> None:
    context.user_data[_CTX_LAST_STATUS] = status
    context.user_data[_CTX_LAST_PAGE] = page
    families = rn_repo.get_requests_by_status(status)
    text, kb = rn_views.build_status_list(status, families, page=page)
    await _edit(update, text, kb)


async def _show_family(update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int, uid: int) -> None:
    family = rn_repo.get_family(root_id)
    if family is None:
        await _edit(update, "❌ لم يتم العثور على الطلب.", None)
        return
    if family.root.status == STATUS_WAITING_ARRIVAL:
        # ✅ ملخّص بيانات الوصول أولاً (بطلب المستخدم صراحةً — كان
        # ينتقل مباشرة لطلب الصورة بلا عرض أي بيانات) — زرّ "ابدأ
        # استكمال البيانات" هو من يدخل فعلياً في تسلسل الصورة/التنبيه.
        await _show_arrival_summary(update, context, family)
        return
    person_ids = [family.root.id] + [c.id for c in family.companions]
    # يشمل ملف الإقامة والصورة لا وثائق الجدول وحدها — وإلا ظهر
    # «الوثائق (0)» لشخص ملفاته مرفوعة فعلاً.
    doc_counts = rn_repo.get_file_counts(person_ids)
    text, kb = rn_views.build_family_detail(
        family, is_admin=is_admin(uid), doc_counts=doc_counts,
        back_to=_back_to_list(context),
    )
    await _edit(update, text, kb)


async def _show_arrival_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, family: rn_repo.FamilyRow) -> None:
    arrival = rn_repo.get_arrival_patient_docs_by_name(family.root.name)
    text, kb = rn_views.build_arrival_summary(
        family.root, arrival, family.companions, back_to=_back_to_list(context))
    await _edit(update, text, kb)


# ── Documents (📄) ───────────────────────────────────────────────────────────

async def _send_file(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     file_id: str, caption: str) -> None:
    """يرسل ملفاً بـfile_id مهما كان نوعه عند الرفع.

    ⚠️ `file_id` في تليجرام **مرتبط بنوعه**: مُعرِّف صورة يُرفَض من
    `sendDocument` والعكس. والوثيقة قد تُرفَع صورةً أو ملفاً، ولا نخزّن
    النوع — فتُجرَّب الطريقتان بدل افتراض واحدة.
    """
    chat_id = update.effective_chat.id
    try:
        await context.bot.send_document(chat_id, file_id, caption=caption)
        return
    except Exception:
        pass
    try:
        await context.bot.send_photo(chat_id, file_id, caption=caption)
    except Exception as exc:
        logger.error(f"[residency] تعذّر إرسال الملف {file_id[:20]}: {exc}")
        await _alert(update, context, "⚠️ تعذّر فتح الملف — قد يكون محذوفاً من تليجرام.")


async def _send_export(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       status: str, fmt: str) -> None:
    """يبني جدول الحالات ويرسله ملفاً.

    ⚠️ يُبنى الملف **قبل** أي إعلان نجاح: لو فشل التوليد بعد الإعلان بقي
    المستخدم ينتظر ملفاً لن يصل. والتنبيهات عبر `_alert` لأن المُرسِل
    يُجيب الضغطة مرة واحدة فقط (إدخال ٩٩).
    """
    from services import residency_table_export as rx

    if status == "ALL":
        families = []
        for s_ in STATUS_ORDER:
            families.extend(rn_repo.get_requests_by_status(s_))
        # ⚠️ عائلة لها أشخاص في حالتين تظهر في القائمتين فتتكرّر هنا —
        # تُزال بمعرّف الجذر لا بالكائن (FamilyRow لقطات مستقلة).
        seen, uniq = set(), []
        for f in families:
            if f.root.id not in seen:
                seen.add(f.root.id)
                uniq.append(f)
        families = uniq
        label = "كل الحالات"
    else:
        families = rn_repo.get_requests_by_status(status)
        label = STATUS_LABELS.get(status, status)

    rows = rx.collect_rows(families, lambda st: STATUS_LABELS.get(st, st))
    title = f"جدول الإقامات — {label}"

    try:
        buf = rx.build_excel(rows, title) if fmt == "xlsx" else rx.build_pdf(rows, title)
    except Exception as exc:
        logger.error(f"[residency.export] فشل توليد {fmt} لحالة {status}: {exc}",
                     exc_info=True)
        await _alert(update, context, "⚠️ تعذّر إنشاء الملف. راجع الإدارة.")
        return

    fname = rx.build_filename(label, "xlsx" if fmt == "xlsx" else "pdf")
    try:
        await context.bot.send_document(
            update.effective_chat.id, document=buf, filename=fname,
        caption=f"📤 {title}\n👥 {len(rows)} شخصاً في {len(families)} طلباً",
        )
    except Exception as exc:
        logger.error(f"[residency.export] تعذّر إرسال الملف: {exc}", exc_info=True)
        await _alert(update, context, "⚠️ أُنشئ الملف لكن تعذّر إرساله.")
        return
    await _alert(update, context, "✅ أُرسل الجدول.", show_alert=False)


async def _show_documents(update: Update, context: ContextTypes.DEFAULT_TYPE, person_id: int) -> None:
    person = rn_repo.get_person(person_id)
    if person is None:
        await _edit(update, "❌ لم يتم العثور على الشخص.", None)
        return
    documents = rn_repo.get_documents_for_person(person_id)
    text, kb = rn_views.build_documents_list(person, documents)
    await _edit(update, text, kb)


# ── ✏️ تعديل البيانات ────────────────────────────────────────────────────────
# مسار تصحيح مستقلّ عن تسلسل الإدخال. سببه: منطق الاستئناف يتخطّى كل حقل
# مملوء، فقيمة أُدخِلت خطأً لا يُعاد سؤالها أبداً — لا بالرجوع ولا بإعادة
# الدخول. انظر modules/residency/edit_fields.py.

async def _show_edit_picker(update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int) -> None:
    from modules.residency import edit_fields as ef
    family = rn_repo.get_family(root_id)
    if family is None:
        await _edit(update, "❌ لم يتم العثور على الطلب.", None)
        return
    text, kb = ef.build_person_picker(family)
    await _edit(update, text, kb)


async def _show_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, person_id: int) -> None:
    from modules.residency import edit_fields as ef
    _clear_transient_state(context)
    person = rn_repo.get_person(person_id)
    if person is None:
        await _edit(update, "❌ لم يتم العثور على الشخص.", None)
        return
    root_id = person.parent_id or person.id
    text, kb = ef.build_edit_menu(person, back_to=f"{RN}:editp_{root_id}")
    await _edit(update, text, kb)


async def _start_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE,
                            key: str, person_id: int) -> None:
    from modules.residency import edit_fields as ef
    person = rn_repo.get_person(person_id)
    if person is None:
        await _edit(update, "❌ لم يتم العثور على الشخص.", None)
        return
    _clear_transient_state(context)
    back = f"{RN}:edit_{person_id}"

    if ef.field_kind(key) == "date":
        context.user_data[_CTX_CAL_TARGET] = {
            "kind": f"editf_{key}", "person_id": person_id,
            "root_id": person.parent_id or person.id,
        }
        now = datetime.utcnow()
        cal_text, kb = build_calendar(
            now.year, now.month, RN, back_callback=back, quick_jump=True)
        header = f"✏️ **تصحيح {ef.field_label(key)}**\n👤 {person.name}\nالحالي: {ef.current_value(person, key)}"
        await _edit(update, f"{header}\n\n{cal_text}", kb)
    else:
        context.user_data[_CTX_UPLOAD_TARGET] = {
            "kind": f"editf_{key}", "person_id": person_id,
            "root_id": person.parent_id or person.id,
        }
        text, kb = ef.build_file_prompt(person, key, back_to=back)
        await _edit(update, text, kb)


# ── Onboarding (🟡) ──────────────────────────────────────────────────────────

def _build_onboard_state(root_id: int) -> dict:
    queue = rn_repo.get_onboarding_queue(root_id)
    for i, p in enumerate(queue):
        if not p.photo_file_id:
            return {"root_id": root_id, "queue_ids": [q.id for q in queue], "index": i, "step": "photo"}
        if not p.reminder_date:
            return {"root_id": root_id, "queue_ids": [q.id for q in queue], "index": i, "step": "reminder"}
    return {"root_id": root_id, "queue_ids": [q.id for q in queue], "index": len(queue), "step": "review"}


async def _show_onboard_step(update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int) -> None:
    state = _build_onboard_state(root_id)
    _clear_transient_state(context)

    if state["step"] == "review":
        queue_rows = [rn_repo.get_person(pid) for pid in state["queue_ids"]]
        text, kb = rn_views.build_onboard_review(
            [p for p in queue_rows if p], back_to=f"{RN}:family_{root_id}")
        await _edit(update, text, kb)
        return

    person = rn_repo.get_person(state["queue_ids"][state["index"]])
    if person is None:
        await _show_menu(update, context)
        return

    if state["step"] == "photo":
        context.user_data[_CTX_UPLOAD_TARGET] = {"kind": "onboard_photo", "person_id": person.id, "root_id": root_id}
        text, kb = rn_views.build_onboard_photo_prompt(
            person, state["index"] + 1, len(state["queue_ids"]),
            back_to=f"{RN}:family_{root_id}")
        await _edit(update, text, kb)
    else:  # reminder
        context.user_data[_CTX_CAL_TARGET] = {"kind": "onboard_remind", "person_id": person.id, "root_id": root_id}
        now = datetime.utcnow()
        # الرجوع للحالة لا للقائمة الرئيسية — الأدمن داخل تسلسل شخص بعينه
        text, kb = build_calendar(
            now.year, now.month, RN, back_callback=f"{RN}:family_{root_id}")
        await _edit(update, text, kb)


# ── 🏠 معالجة "معلّقات من الحالات السابقة" ────────────────────────────────────
# المريض القديم (LEGACY_PENDING) بياناته الأساسية مكتملة من شاشة الأدمن، وما
# ينقصه بيانات **الإقامة** نفسها. مساران:
#   ext   — توجد إقامة/تمديد: آخر إصدار → الانتهاء → التنبيه → صورة الإقامة
#           → الصورة الشخصية.
#   noext — لا يوجد تمديد: تاريخ الانتهاء فقط.
# يمرّ المسار على المريض ثم مرافقيه واحداً واحداً (نفس نمط الطابور المُستخدَم
# في استكمال بيانات الوصول)، ثم شاشة اختيار القائمة التي ينتقلون إليها معاً.

_LEGACY_STEPS_EXT = ["last_issue", "expiry", "reminder", "res_file", "photo"]
_LEGACY_STEPS_NOEXT = ["expiry"]


def _legacy_filled(person, step: str) -> bool:
    """هل اكتملت هذه الخطوة لهذا الشخص؟ (تُشتَقّ من القاعدة فيكون المسار
    قابلاً للاستئناف بعد أي انقطاع، تماماً كـ_build_onboard_state)."""
    return bool({
        "last_issue": person.last_issue_date,
        "expiry":     person.expiry_date,
        "reminder":   person.reminder_date,
        "res_file":   person.residency_file_id,
        "photo":      person.photo_file_id,
    }.get(step, ""))


def _build_legacy_state(root_id: int, mode: str) -> dict:
    steps = _LEGACY_STEPS_EXT if mode == "ext" else _LEGACY_STEPS_NOEXT
    queue = rn_repo.get_onboarding_queue(root_id)      # المريض ثم مرافقوه
    for i, p in enumerate(queue):
        for step in steps:
            if not _legacy_filled(p, step):
                return {
                    "root_id": root_id, "mode": mode,
                    "queue_ids": [q.id for q in queue],
                    "index": i, "step": step,
                }
    return {"root_id": root_id, "mode": mode,
            "queue_ids": [q.id for q in queue], "index": len(queue), "step": "choose"}


async def _show_legacy_step(update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int, mode: str) -> None:
    state = _build_legacy_state(root_id, mode)
    _clear_transient_state(context)

    # اكتمل الجميع ⇒ اختيار القائمة الهدف
    if state["step"] == "choose":
        family = rn_repo.get_family(root_id)
        if family is None:
            await _show_menu(update, context)
            return
        text, kb = rn_views.build_legacy_target_chooser(family)
        await _edit(update, text, kb)
        return

    person = rn_repo.get_person(state["queue_ids"][state["index"]])
    if person is None:
        await _show_menu(update, context)
        return

    idx, total = state["index"] + 1, len(state["queue_ids"])
    step = state["step"]

    if step in ("res_file", "photo"):
        context.user_data[_CTX_UPLOAD_TARGET] = {
            "kind": "legacy_res_file" if step == "res_file" else "legacy_photo",
            "person_id": person.id, "root_id": root_id, "mode": mode,
        }
        text, kb = rn_views.build_legacy_upload_prompt(
            person, step, idx, total,
            back_to=f"{RN}:family_{person.parent_id or person.id}",
        )
        await _edit(update, text, kb)
        return

    # خطوات التواريخ الثلاث — تقويم بقفز السنوات/الشهور (تواريخ قد تبعد
    # سنة أو أكثر، فالتنقّل شهراً شهراً غير عملي)
    context.user_data[_CTX_CAL_TARGET] = {
        "kind": f"legacy_{step}", "person_id": person.id,
        "root_id": root_id, "mode": mode,
    }
    now = datetime.utcnow()
    cal_text, kb = build_calendar(
        now.year, now.month, RN, back_callback=f"{RN}:family_{root_id}", quick_jump=True,
    )
    header = rn_views.legacy_step_header(person, step, idx, total)
    await _edit(update, f"{header}\n\n{cal_text}", kb)


def _missing_reminder_ids(root_id: int) -> list[int]:
    """من لم يُدخَل له تاريخ تنبيه بعد ضمن العائلة (وما زال LEGACY_PENDING).

    مسار "❌ لا يوجد تمديد" لا يجمع تاريخ تنبيه أصلاً، لكن الانتقال إلى
    "🟢 الحالات النشطة" يستلزمه — وإلا لن يظهر أي تنبيه لهذا المريض لاحقاً
    (بطلب المستخدم صراحةً). يُفحَص الحقل الفعلي لا الوضع، فيغطّي أي نقص
    مهما كان مصدره.
    """
    queue = rn_repo.get_onboarding_queue(root_id)
    return [
        p.id for p in queue
        if p.status == STATUS_LEGACY_PENDING and not p.reminder_date
    ]


async def _show_legacy_move_reminder(
    update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int, target_status: str,
) -> bool:
    """يعرض تقويم تاريخ التنبيه لأول شخص ينقصه. يعيد False إن لم ينقص أحداً
    (فينفّذ المستدعي النقل مباشرة)."""
    pending = _missing_reminder_ids(root_id)
    if not pending:
        return False

    person = rn_repo.get_person(pending[0])
    if person is None:
        return False

    queue_ids = [p.id for p in rn_repo.get_onboarding_queue(root_id)]
    idx = queue_ids.index(person.id) + 1 if person.id in queue_ids else 1

    _clear_transient_state(context)
    context.user_data[_CTX_LEGACY_MOVE] = {"root_id": root_id, "status": target_status}
    context.user_data[_CTX_CAL_TARGET] = {
        "kind": "legacy_move_remind", "person_id": person.id, "root_id": root_id,
    }
    now = datetime.utcnow()
    cal_text, kb = build_calendar(
        now.year, now.month, RN, back_callback=f"{RN}:family_{root_id}", quick_jump=True,
    )
    header = rn_views.legacy_step_header(person, "reminder", idx, len(queue_ids))
    await _edit(update, f"{header}\n\n{cal_text}", kb)
    return True


async def _finish_legacy_move(
    update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int,
    target_status: str, uid: int,
) -> None:
    moved = rn_models.move_family_to_status(root_id, target_status, performed_by=uid)
    context.user_data.pop(_CTX_LEGACY_MOVE, None)
    _clear_transient_state(context)
    if not moved:
        await _edit(update, "⚠️ لم يُنقَل أحد — قد تكون الحالة عولجت مسبقاً.", None)
        return
    await _show_family(update, context, root_id, uid)


# ── Issuance (🟣) ────────────────────────────────────────────────────────────

async def _show_issuance(update: Update, context: ContextTypes.DEFAULT_TYPE, person_id: int) -> None:
    person = rn_repo.get_person(person_id)
    if person is None:
        await _edit(update, "❌ لم يتم العثور على الشخص.", None)
        return
    # الرجوع لعائلة الشخص لا للقائمة الرئيسية — الأدمن يفحص حالة بعينها
    _root = person.parent_id or person.id
    text, kb = rn_views.build_issuance_view(person, back_to=f"{RN}:family_{_root}")
    await _edit(update, text, kb)


# ── Callback dispatcher ────────────────────────────────────────────────────────

# ── إيصال التنبيهات ──────────────────────────────────────────────────────────
# ⚠️ **تليجرام يقبل `answerCallbackQuery` مرة واحدة لكل ضغطة.** كان المُرسِل
# يستهلكها في سطره الثاني (`await _alert(update, context, )`)، فكل تنبيه بعدها يُرفَض
# ويُفجِّر المعالِج — فيُبتلَع النصّ ولا يتغيّر شيء على الشاشة. النتيجة
# الحرفية: موظف يضغط «🔵 تم التقديم» فلا يرى شيئاً ولا تنتقل الحالة، بلا
# أي تفسير. أُثبِت بمحاكاة تحترم قاعدة المرة الواحدة (المحاكاة السابقة
# كانت تسمح بإجابتين فأعطت ثقة كاذبة).
#
# القاعدة الآن: لا يُجاب في البداية إطلاقاً. من يريد تنبيهاً ينادي `_alert`،
# ومن لا يريد تُجاب ضغطته **في النهاية** — وهذا أيضاً أصحّ سلوكاً: تبقى
# دائرة الانتظار على الزر حتى يكتمل العمل فعلاً.
_ANSWERED = "_rn_answered"


async def _alert(update: Update, context: ContextTypes.DEFAULT_TYPE,
                 text: str, *, show_alert: bool = True) -> None:
    """تنبيه يصل فعلاً — وإن تعذّر، يُرسَل رسالةً مستقلة بدل أن يضيع."""
    query = update.callback_query
    if query is None:
        return
    try:
        await query.answer(text, show_alert=show_alert)
        if context.user_data is not None:
            context.user_data[_ANSWERED] = True
        return
    except Exception as exc:
        logger.warning(f"[residency] تعذّر تنبيه المستخدم عبر answer: {exc}")
    try:
        await context.bot.send_message(update.effective_chat.id, text)
    except Exception as exc:
        logger.error(f"[residency] وضاع التنبيه «{text[:40]}»: {exc}")


async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """غلاف يضمن إجابة الضغطة **مرة واحدة** — بعد انتهاء العمل لا قبله."""
    query = update.callback_query
    if query is None:
        return
    if context.user_data is not None:
        context.user_data.pop(_ANSWERED, None)
    try:
        await _dispatch_action(update, context)
    finally:
        if not (context.user_data or {}).pop(_ANSWERED, False):
            try:
                await query.answer()
            except Exception:
                pass


async def _dispatch_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    if not data.startswith(f"{RN}:"):
        return
    action = data[len(RN) + 1:]
    uid = query.from_user.id if query.from_user else 0

    if not query.from_user or not _is_authorized(uid):
        logger.warning(f"[residency.cb] blocked unauthorized user={uid}  action={action!r}")
        return

    if action == "menu":
        _clear_transient_state(context)
        await _show_menu(update, context)
        return

    if action.startswith("lpage:"):
        # `rn:lpage:{status}:{page}` — الحالة داخل الكولباك لا في الجلسة
        # وحدها، فتبقى الصفحة صحيحة حتى بعد إعادة تشغيل البوت.
        _, _st, _pg = action.split(":", 2)
        _clear_transient_state(context)
        if _st in STATUS_ORDER:
            try:
                _page = int(_pg)
            except ValueError:
                _page = 0
            await _show_status_list(update, context, _st, page=_page)
        return

    if action.startswith("status_"):
        # 🔴 التنظيف ضروري هنا وفي `family_`: هاتان الشاشتان هما وجهة زر
        # الرجوع من **داخل تسلسلات الإدخال** (رفع وثيقة، اختيار تاريخ).
        # بلا تنظيف يبقى `_rn_cal_target`/`_rn_upload_target` معلّقاً بعد
        # مغادرة التسلسل، فأول تاريخ يُختار أو ملف يُرفَع لاحقاً — ولو
        # لشخص آخر — قد يُكتَب في الخطوة المهجورة. `menu` كان ينظّف وحده،
        # وتوجيه الرجوع لهاتين الشاشتين كشف الفجوة.
        _clear_transient_state(context)
        status = action[len("status_"):]
        if status in STATUS_ORDER:
            await _show_status_list(update, context, status, page=0)
        return

    # 🔄 إضافة مرافقي الوصول الغائبين عن الإقامة (إضافة فقط، بلا حذف)
    if action.startswith("syncomp_"):
        root_id = int(action[len("syncomp_"):])
        n, names = rn_models.sync_companions_from_arrival(root_id, performed_by=uid)
        if n:
            await _alert(update, context,
                         f"✅ أُضيف {n} مرافق: {'، '.join(names)}")
        else:
            await _alert(update, context, "لا يوجد مرافق ناقص للإضافة.")
        await _show_family(update, context, root_id, uid)
        return

    # ✏️ التعديل — قبل `family_` لأن `editp_` لا يتقاطع لكن الترتيب أوضح
    if action.startswith("editp_"):
        await _show_edit_picker(update, context, int(action[len("editp_"):]))
        return

    if action.startswith("edit_"):
        await _show_edit_menu(update, context, int(action[len("edit_"):]))
        return

    # 🗑️ حذف ملف من شاشة التعديل — بتأكيد
    if action.startswith("edelgo_"):
        rest = action[len("edelgo_"):]
        key, _, pid = rest.rpartition("_")
        pid = int(pid)
        if key == "resfile":
            rn_models.clear_residency_file(pid)
        elif key == "photo":
            rn_models.clear_photo(pid)
        await _alert(update, context, "🗑️ حُذِف الملف", show_alert=False)
        await _show_edit_menu(update, context, pid)
        return

    if action.startswith("edel_"):
        from modules.residency import edit_fields as ef
        rest = action[len("edel_"):]
        key, _, pid = rest.rpartition("_")
        pid = int(pid)
        person = rn_repo.get_person(pid)
        if person is None:
            await _edit(update, "❌ لم يتم العثور على الشخص.", None)
            return
        text, kb = ef.build_delete_confirm(person, key, back_to=f"{RN}:edf_{key}_{pid}")
        await _edit(update, text, kb)
        return

    # 🗑️ حذف وثيقة من شاشة الوثائق
    if action.startswith("docdel_"):
        doc_id = int(action[len("docdel_"):])
        person_id = rn_repo.get_document_owner(doc_id)
        ok, label = rn_models.delete_document(doc_id)
        await _alert(update, context,
                     f"🗑️ حُذِفت: {label}" if ok else "⚠️ لم تُعثَر الوثيقة",
                     show_alert=not ok)
        if person_id:
            await _show_documents(update, context, person_id)
        else:
            await _show_menu(update, context)
        return

    if action.startswith("edf_"):
        rest = action[len("edf_"):]
        key, _, pid = rest.rpartition("_")
        await _start_edit_field(update, context, key, int(pid))
        return

    if action.startswith("family_"):
        _clear_transient_state(context)
        root_id = int(action[len("family_"):])
        await _show_family(update, context, root_id, uid)
        return

    if action.startswith("person_"):
        person_id = int(action[len("person_"):])
        root_id = rn_repo.get_root_id_for_person(person_id)
        if root_id:
            await _show_family(update, context, root_id, uid)
        return

    if action.startswith("onboard_resume_"):
        person_id = int(action[len("onboard_resume_"):])
        root_id = rn_repo.get_root_id_for_person(person_id) or person_id
        await _show_onboard_step(update, context, root_id)
        return

    if action.startswith("onboard_save_"):
        root_id = int(action[len("onboard_save_"):])
        rn_models.bulk_activate_request(root_id, performed_by=uid)
        _clear_transient_state(context)
        await _show_family(update, context, root_id, uid)
        return

    # ── 🏠 معلّقات من الحالات السابقة ──────────────────────────────────
    if action.startswith("lgc_ext_") or action.startswith("lgc_noext_"):
        mode = "ext" if action.startswith("lgc_ext_") else "noext"
        prefix = "lgc_ext_" if mode == "ext" else "lgc_noext_"
        try:
            root_id = int(action[len(prefix):])
        except ValueError:
            logger.warning(f"[residency.cb] lgc bad root_id action={action!r} user={uid}")
            return
        await _show_legacy_step(update, context, root_id, mode)
        return

    if action.startswith("lgc_to_"):
        # صيغة: lgc_to_{STATUS}_{root_id} — الحالة نفسها قد تحوي "_"
        rest = action[len("lgc_to_"):]
        target_status, _, root_raw = rest.rpartition("_")
        try:
            root_id = int(root_raw)
        except ValueError:
            logger.warning(f"[residency.cb] lgc_to bad root_id action={action!r} user={uid}")
            return
        if target_status not in STATUS_ORDER or target_status == STATUS_LEGACY_PENDING:
            logger.warning(f"[residency.cb] lgc_to invalid status={target_status!r} user={uid}")
            return
        # ✅ الانتقال إلى "🟢 الحالات النشطة" يستلزم تاريخ تنبيه لكل شخص —
        # وإلا لن يظهر أي تنبيه لهذا المريض لاحقاً. مسار "لا يوجد تمديد" لا
        # يجمعه، فيُطلَب هنا قبل تنفيذ النقل (بطلب المستخدم صراحةً). بقية
        # الحالات تُنقَل مباشرة كما كانت.
        if target_status == STATUS_ACTIVE:
            if await _show_legacy_move_reminder(update, context, root_id, target_status):
                return
        await _finish_legacy_move(update, context, root_id, target_status, uid)
        return

    if action.startswith("submit_"):
        person_id = int(action[len("submit_"):])
        # ⚠️ كان هذا **الزر الوحيد** في الوحدة كلها المقيَّد بالأدمن، بينما
        # رفع الملفات والتواريخ ونقل الحالات السابقة وتوثيق الإصدار وحذف
        # الوثائق كلها مفتوحة لمن يملك وحدة الإقامات. فكان الموظف يُكمل
        # دورة العمل كاملة ويتعثّر في خطوة واحدة وسطها. رُفِع القيد بقرار
        # المستخدم؛ `_is_authorized` في المُرسِل تبقى هي البوّابة.
        if not rn_models.mark_submitted(person_id, performed_by=uid):
            # ⚠️ القيمة المُعادة كانت **مُهمَلة**: إن رفضت الدالة (الحالة
            # ليست EXPIRY_PENDING) تُعاد رسم الشاشة كأن شيئاً لم يكن.
            await _alert(update, context,
                         "⚠️ تعذّر النقل — قد تكون الحالة عولجت مسبقاً.")
        root_id = rn_repo.get_root_id_for_person(person_id)
        if root_id:
            await _show_family(update, context, root_id, uid)
        return

    if action.startswith("issue_start_"):
        person_id = int(action[len("issue_start_"):])
        rn_models.start_issuance(person_id, performed_by=uid)
        await _show_issuance(update, context, person_id)
        return

    if action.startswith("issue_view_"):
        person_id = int(action[len("issue_view_"):])
        await _show_issuance(update, context, person_id)
        return

    if action.startswith("issue_expiry_"):
        person_id = int(action[len("issue_expiry_"):])
        context.user_data[_CTX_CAL_TARGET] = {"kind": "issue_expiry", "person_id": person_id}
        now = datetime.utcnow()
        text, kb = build_calendar(now.year, now.month, RN, back_callback=f"{RN}:issue_view_{person_id}")
        await _edit(update, text, kb)
        return

    if action.startswith("issue_file_"):
        person_id = int(action[len("issue_file_"):])
        context.user_data[_CTX_UPLOAD_TARGET] = {"kind": "issue_file", "person_id": person_id}
        person = rn_repo.get_person(person_id)
        if person:
            text, kb = rn_views.build_issuance_file_prompt(person)
            await _edit(update, text, kb)
        return

    if action.startswith("issue_confirm_"):
        person_id = int(action[len("issue_confirm_"):])
        ok = rn_models.confirm_issuance(person_id, performed_by=uid)
        if not ok:
            await _alert(update, context, "⚠️ أكمل تاريخ الانتهاء والملف أولاً.")
            return
        root_id = rn_repo.get_root_id_for_person(person_id)
        if root_id:
            await _show_family(update, context, root_id, uid)
        return

    if action.startswith("resview_"):
        person = rn_repo.get_person(int(action[len("resview_"):]))
        if person and (person.residency_file_id or "").strip():
            await _send_file(update, context, person.residency_file_id,
                             f"🪪 ملف الإقامة — {person.name}")
        else:
            await _alert(update, context, "لا يوجد ملف إقامة مرفوع.")
        return

    if action.startswith("photoview_"):
        person = rn_repo.get_person(int(action[len("photoview_"):]))
        if person and (person.photo_file_id or "").strip():
            await _send_file(update, context, person.photo_file_id,
                             f"🖼️ الصورة الشخصية — {person.name}")
        else:
            await _alert(update, context, "لا توجد صورة مرفوعة.")
        return

    if action.startswith("docview_"):
        doc_id = int(action[len("docview_"):])
        doc = rn_repo.get_document(doc_id)
        if doc:
            label = "Form C" if doc.doc_type == "form_c" else (doc.doc_name or "وثيقة")
            await _send_file(update, context, doc.file_id, f"📄 {label}")
        else:
            await _alert(update, context, "الوثيقة غير موجودة.")
        return

    if action.startswith("docs_"):
        person_id = int(action[len("docs_"):])
        _clear_transient_state(context)
        await _show_documents(update, context, person_id)
        return

    if action.startswith("doc_add_formc_"):
        person_id = int(action[len("doc_add_formc_"):])
        person = rn_repo.get_person(person_id)
        if person:
            context.user_data[_CTX_UPLOAD_TARGET] = {
                "kind": "doc_upload", "person_id": person_id, "doc_type": "form_c", "doc_name": "Form C",
            }
            text, kb = rn_views.build_doc_file_prompt(person, "Form C")
            await _edit(update, text, kb)
        return

    if action.startswith("doc_add_other_"):
        person_id = int(action[len("doc_add_other_"):])
        person = rn_repo.get_person(person_id)
        if person:
            context.user_data[_CTX_DOC_NAME_ACTIVE] = {"person_id": person_id}
            text, kb = rn_views.build_doc_name_prompt(person)
            await _edit(update, text, kb)
        return

    if action.startswith("doc_add_"):
        person_id = int(action[len("doc_add_"):])
        person = rn_repo.get_person(person_id)
        if person:
            text, kb = rn_views.build_doc_type_prompt(person)
            await _edit(update, text, kb)
        return

    if action.startswith("print_"):
        root_id = int(action[len("print_"):])
        context.user_data[_CTX_PRINT_ROOT_ID] = root_id
        await multiselect.open(
            update, context,
            title="🖨️ اختر الوثائق المطلوب طباعتها",
            options=rn_views.PRINT_DOC_OPTIONS,
            return_to=_RKEY_PRINT_CATS,
            icon="🖨️",
            min_select=0,
            preselected_ids=[o.id for o in rn_views.PRINT_DOC_OPTIONS],
        )
        return

    if action == "search":
        _clear_transient_state(context)
        context.user_data[_CTX_SEARCH_ACTIVE] = True
        text, kb = rn_views.build_search_prompt()
        await _edit(update, text, kb)
        return

    # ── 📤 تصدير جدول الحالات (PDF / Excel) ──────────────────────────────
    if action == "export":
        counts = rn_repo.get_status_counts()
        text, kb = rn_views.build_export_status_picker(counts)
        await _edit(update, text, kb)
        return

    if action.startswith("exp:"):
        st = action[len("exp:"):]
        if st != "ALL" and st not in STATUS_ORDER:
            await _alert(update, context, "حالة غير معروفة.")
            return
        n = (sum(rn_repo.get_status_counts().values()) if st == "ALL"
             else len(rn_repo.get_requests_by_status(st)))
        label = "كل الحالات" if st == "ALL" else STATUS_LABELS.get(st, st)
        text, kb = rn_views.build_export_format_picker(st, label, n)
        await _edit(update, text, kb)
        return

    if action.startswith("expdo:"):
        _, st, fmt = action.split(":", 2)
        await _send_export(update, context, st, fmt)
        return

    if action == "log" or action.startswith("logp:"):
        page = 0
        if action.startswith("logp:"):
            try:
                page = max(0, int(action.split(":", 1)[1]))
            except ValueError:
                page = 0
        per = rn_views._LOG_PER_PAGE
        entries, total = rn_repo.get_log_page(offset=page * per, limit=per)
        pages = max(1, (total + per - 1) // per)
        if not entries and total:          # صفحة خارج النطاق ⇒ آخر صفحة
            page = pages - 1
            entries, total = rn_repo.get_log_page(offset=page * per, limit=per)
        text, kb = rn_views.build_log_view(entries, page=page, pages=pages, total=total)
        await _edit(update, text, kb)
        return

    if action == "reports":
        counts = rn_repo.get_status_counts()
        text, kb = rn_views.build_reports_view(counts)
        await _edit(update, text, kb)
        return

    if action.startswith("cal_"):
        await _handle_calendar_action(update, context, action, uid)
        return


async def _handle_calendar_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, uid: int) -> None:
    query = update.callback_query
    target = context.user_data.get(_CTX_CAL_TARGET)
    if not target:
        await _show_menu(update, context)
        return

    parts = action.split(":")
    sub = parts[0]
    if sub == "cal_noop":
        return

    kind = target["kind"]
    is_edit = kind.startswith("editf_")
    is_legacy = kind.startswith("legacy_")

    def _back_cb() -> str:
        if is_legacy:
            return f"{RN}:family_{target['root_id']}"
        if is_edit:
            return f"{RN}:edit_{target['person_id']}"
        if kind == "onboard_remind":
            # كان `{RN}:menu` — يقفز للقائمة الرئيسية وسط تسلسل الاستكمال
            return f"{RN}:family_{target.get('root_id') or target['person_id']}"
        return f"{RN}:issue_view_{target['person_id']}"

    if sub in ("cal_prev", "cal_next", "cal_yprev", "cal_ynext", "cal_setmonth"):
        y, m = int(parts[1]), int(parts[2])
        text, kb = build_calendar(y, m, RN, back_callback=_back_cb(), quick_jump=is_legacy)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ✅ قفز السنة/الشهر — يُبنى فقط لتقويمات هذا المسار (quick_jump=True)،
    # فلا تصل هذه الأفعال من المسارات القديمة إطلاقاً.
    if sub in ("cal_years", "cal_yearpage"):
        from shared.calendar_picker import build_year_picker
        text, kb = build_year_picker(int(parts[1]), RN, _back_cb())
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if sub == "cal_setyear":
        from shared.calendar_picker import build_month_picker
        text, kb = build_month_picker(int(parts[1]), RN, _back_cb())
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if sub == "cal_pick":
        y, mo, d = int(parts[1]), int(parts[2]), int(parts[3])
        date_iso = f"{y:04d}-{mo:02d}-{d:02d}"
        person_id = target["person_id"]

        # ── 🔒 التحقّق من منطقية التاريخ قبل أي حفظ ──────────────────────
        # الرفض يُظهر تنبيهاً ويُبقي المستخدم في **نفس التقويم** ليختار
        # تاريخاً آخر — لا يُخرِجه من التسلسل ولا يحفظ شيئاً.
        from modules.residency.days import validate_reminder, validate_expiry

        _p = rn_repo.get_person(person_id)
        _err = None
        if _p is not None:
            _is_remind = (
                kind == "onboard_remind"
                or kind == "legacy_move_remind"
                or kind == "legacy_reminder"
                or kind == "editf_remind"
            )
            _is_expiry = kind in ("legacy_expiry", "editf_expiry")
            if _is_remind:
                _err = validate_reminder(_p.expiry_date, date_iso)
            elif _is_expiry:
                _err = validate_expiry(_p.reminder_date, date_iso)
        if _err:
            await _alert(update, context, _err)
            return

        if target["kind"] == "onboard_remind":
            rn_models.set_reminder_date(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            await _show_onboard_step(update, context, target["root_id"])
        elif target["kind"] == "issue_expiry":
            rn_models.set_issuance_expiry(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            await _show_issuance(update, context, person_id)
        elif is_edit:
            # ✏️ تصحيح تاريخ — يكتب فوق القديم ويعود لشاشة التعديل
            fkey = kind[len("editf_"):]
            if fkey == "expiry":
                rn_models.set_expiry_date(person_id, date_iso)
            elif fkey == "remind":
                rn_models.set_reminder_date(person_id, date_iso)
            elif fkey == "lastiss":
                rn_models.set_last_issue_date(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            await _show_edit_menu(update, context, person_id)
            return

        elif kind == "legacy_move_remind":
            # ✅ تاريخ تنبيه مطلوب قبل النقل إلى "الحالات النشطة": يُحفَظ ثم
            # يُنتقَل للشخص التالي الناقص، وعند اكتمال الجميع يُنفَّذ النقل.
            rn_models.set_reminder_date(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            pending_move = context.user_data.get(_CTX_LEGACY_MOVE) or {}
            root_id = pending_move.get("root_id", target["root_id"])
            status = pending_move.get("status", STATUS_ACTIVE)
            if not await _show_legacy_move_reminder(update, context, root_id, status):
                await _finish_legacy_move(update, context, root_id, status, uid)
            return

        elif is_legacy:
            # 🏠 تواريخ معالجة الحالات السابقة — كل خطوة تكتب حقلها ثم يُعاد
            # احتساب الخطوة التالية من القاعدة (قابل للاستئناف).
            step = kind[len("legacy_"):]
            if step == "last_issue":
                rn_models.set_last_issue_date(person_id, date_iso)
            elif step == "expiry":
                rn_models.set_expiry_date(person_id, date_iso)
            elif step == "reminder":
                rn_models.set_reminder_date(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            await _show_legacy_step(update, context, target["root_id"], target.get("mode", "ext"))
        return


# ── Text (search) ───────────────────────────────────────────────────────────

async def _on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_authorized(uid):
        return

    doc_target = context.user_data.get(_CTX_DOC_NAME_ACTIVE)
    if doc_target:
        context.user_data.pop(_CTX_DOC_NAME_ACTIVE, None)
        person_id = doc_target["person_id"]
        person = rn_repo.get_person(person_id)
        if not person:
            return
        doc_name = update.message.text.strip()
        context.user_data[_CTX_UPLOAD_TARGET] = {
            "kind": "doc_upload", "person_id": person_id, "doc_type": "other", "doc_name": doc_name,
        }
        text, kb = rn_views.build_doc_file_prompt(person, doc_name)
        await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if not context.user_data.get(_CTX_SEARCH_ACTIVE):
        return

    context.user_data.pop(_CTX_SEARCH_ACTIVE, None)
    query_text = update.message.text.strip()
    results = rn_repo.search_persons(query_text)
    text, kb = rn_views.build_search_results(query_text, results)
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Photo / document upload ───────────────────────────────────────────────────

def _extract_file_id(message) -> str | None:
    # ✅ لا يقتصر على الصور — الوثائق الرسمية (Form C وغيرها) كثيراً ما
    # تُرفَع كملف PDF لا صورة، فيجب قبول أي مستند بصرف النظر عن نوعه
    # (نفس نمط user_medical_attachments.py/admin_patient_attachments_bundle.py).
    if message.photo:
        return message.photo[-1].file_id
    if message.document:
        return message.document.file_id
    return None


async def _on_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = context.user_data.get(_CTX_UPLOAD_TARGET)
    if not target:
        return
    if not update.message:
        return
    uid = update.effective_user.id if update.effective_user else 0
    if not _is_authorized(uid):
        return

    file_id = _extract_file_id(update.message)
    if not file_id:
        return

    context.user_data.pop(_CTX_UPLOAD_TARGET, None)
    person_id = target["person_id"]

    if target["kind"] == "onboard_photo":
        final_file_id = file_id
        try:
            from modules.residency.photo_processing import resize_to_4x6

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
        except Exception as exc:
            logger.warning(f"[residency] photo resize failed, saving original: {exc}")

        rn_models.save_photo(person_id, final_file_id)
        await _show_onboard_step(update, context, target["root_id"])

    elif target["kind"].startswith("editf_"):
        # ✏️ تصحيح ملف — يحلّ محلّ السابق ثم يعود لشاشة التعديل
        fkey = target["kind"][len("editf_"):]
        if fkey == "resfile":
            rn_models.save_residency_file(person_id, file_id)
        elif fkey == "photo":
            final_file_id = file_id
            try:
                from modules.residency.photo_processing import resize_to_4x6

                tg_file = await context.bot.get_file(file_id)
                buf = io.BytesIO()
                await tg_file.download_to_memory(buf)
                buf.seek(0)
                sent = await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=io.BytesIO(resize_to_4x6(buf.read())),
                    caption="🖼️ الصورة مضبوطة على مقاس 4×6",
                )
                final_file_id = sent.photo[-1].file_id
            except Exception as exc:
                logger.warning(f"[residency] edit photo resize failed: {exc}")
            rn_models.save_photo(person_id, final_file_id)
        await _show_edit_menu(update, context, person_id)

    elif target["kind"] == "legacy_res_file":
        # 🪪 صورة آخر إقامة — مستند رسمي، بلا ضبط مقاس (نفس issue_file).
        rn_models.save_residency_file(person_id, file_id)
        await _show_legacy_step(update, context, target["root_id"], target.get("mode", "ext"))

    elif target["kind"] == "legacy_photo":
        # 📷 صورة شخصية — تُضبَط على 4×6 تماماً كصورة الوصول (نفس المعالجة
        # حتى تصلح للطباعة في ملف الحالة).
        final_file_id = file_id
        try:
            from modules.residency.photo_processing import resize_to_4x6

            tg_file = await context.bot.get_file(file_id)
            buf = io.BytesIO()
            await tg_file.download_to_memory(buf)
            buf.seek(0)
            sent = await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=io.BytesIO(resize_to_4x6(buf.read())),
                caption="🖼️ الصورة مضبوطة على مقاس 4×6",
            )
            final_file_id = sent.photo[-1].file_id
        except Exception as exc:
            logger.warning(f"[residency] legacy photo resize failed, saving original: {exc}")
        rn_models.save_photo(person_id, final_file_id)
        await _show_legacy_step(update, context, target["root_id"], target.get("mode", "ext"))

    elif target["kind"] == "issue_file":
        # ✅ لا ضبط مقاس هنا — هذا مستند/بطاقة إقامة رسمية، لا صورة شخصية.
        rn_models.save_issuance_file(person_id, file_id)
        person = rn_repo.get_person(person_id)
        if person:
            text, kb = rn_views.build_issuance_view(person)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

    elif target["kind"] == "doc_upload":
        # ✅ لا ضبط مقاس هنا كذلك — وثيقة مستقلة تُحفَظ كما رُفعت.
        rn_models.add_document(
            person_id, target.get("doc_type", "other"), target.get("doc_name", ""), file_id, created_by=uid,
        )
        person = rn_repo.get_person(person_id)
        if person:
            documents = rn_repo.get_documents_for_person(person_id)
            text, kb = rn_views.build_documents_list(person, documents)
            await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _on_print_categories(result, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نتيجة شاشة اختيار وثائق الطباعة (msel) — تُستدعى عبر result_router،
    مسار مختلف عن `_dispatch_callback` فلا يمرّ عبر حارسه التلقائي."""
    uid = update.effective_user.id if update.effective_user else 0
    if not update.effective_user or not _is_authorized(uid):
        logger.warning(f"[residency.print] blocked unauthorized user={uid}")
        return

    root_id = context.user_data.pop(_CTX_PRINT_ROOT_ID, None)
    if root_id is None:
        return

    if result is None or result.cancelled:
        try:
            await update.callback_query.edit_message_text("✅ تم إلغاء الطباعة.")
        except Exception:
            logger.debug("تم تجاهل استثناء في _on_print_categories", exc_info=True)
        return

    await _send_case_pdf(update, context, root_id, selected=set(result.ids))


async def _download_file_bytes(context: ContextTypes.DEFAULT_TYPE, file_id: str | None) -> bytes | None:
    if not file_id:
        return None
    try:
        tg_file = await context.bot.get_file(file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        return buf.getvalue()
    except Exception as exc:
        logger.warning(f"[residency] case pdf: failed to download file_id={file_id}: {exc}")
        return None


async def _build_person_pdf_dict(
    context: ContextTypes.DEFAULT_TYPE, person: rn_repo.PersonRow, *, role: str, selected: set[str],
) -> dict:
    from datetime import datetime as _dt
    from modules.residency.constants import status_line

    documents = rn_repo.get_documents_for_person(person.id)
    doc_dicts = []
    for d in documents:
        if d.doc_type == "form_c" and "formc" not in selected:
            continue
        if d.doc_type != "form_c" and "otherdocs" not in selected:
            continue
        label = "Form C" if d.doc_type == "form_c" else (d.doc_name or "وثيقة")
        file_bytes = await _download_file_bytes(context, d.file_id)
        # ✅ `doc_type` يُمرَّر ليُرتَّب Form C قبل بقية الوثائق في الملف
        doc_dicts.append({
            "label": label, "file_bytes": file_bytes, "doc_type": d.doc_type,
        })

    photo_bytes = await _download_file_bytes(context, person.photo_file_id) if "photo" in selected else None

    # ✅ لا رابط FK حقيقي بين res_persons وجداول الوصول — مطابقة بالاسم
    # الحرفي فقط (نفس دقّة get_patient_by_name)، الجذر → ArrivalPatient،
    # المرافق (parent_id مضبوط) → ArrivalCompanion.
    arrival = (
        rn_repo.get_arrival_patient_docs_by_name(person.name) if person.parent_id is None
        else rn_repo.get_arrival_companion_docs_by_name(person.name)
    )

    arrival_docs: dict[str, bytes | None] = {}
    if arrival:
        if "passport" in selected and arrival.passport_file_id:
            arrival_docs["passport"] = await _download_file_bytes(context, arrival.passport_file_id)
        if "visa" in selected and arrival.visa_file_id:
            arrival_docs["visa"] = await _download_file_bytes(context, arrival.visa_file_id)
        if "tickets" in selected and arrival.tickets_file_id:
            arrival_docs["tickets"] = await _download_file_bytes(context, arrival.tickets_file_id)

    # ✅ "صورة الإقامة" — إقامة واحدة فقط تُطبَع، الأحدث زمنياً أياً كان
    # مصدرها (وصول أو إصدار رسمي لاحق) — بطلب المستخدم صراحةً، لا تُعرَض
    # الاثنتان معاً أبداً.
    residence_doc = None
    if "residence" in selected:
        def _parse(d: str):
            try:
                return _dt.strptime(d, "%Y-%m-%d") if d else None
            except ValueError:
                return None

        # 🔴 **وجود الملف يقرّر، لا تاريخه**. كان الشرط `elif arrival_date:`
        # أي: لا تُعرَض إقامة الوصول إلا إذا نجح تحليل تاريخها. فإن كان
        # `created_at` لصف الوصول فارغاً (صفوف قديمة، أو أُنشئت بمسار لا
        # يضبطه) يصير `uploaded_at` نصّاً فارغاً ⇒ `_parse` تُرجِع None ⇒
        # **تُخفى الإقامة رغم أن ملفها مرفوع فعلاً**، وتُطبَع "لا توجد
        # إقامة مرفوعة" — بلا أي خطأ يكشف السبب.
        # التاريخ الآن يُستخدَم للترجيح بين مصدرين فقط، لا لإثبات الوجود.
        latest = rn_repo.get_latest_issuance(person.id)
        has_issuance = bool(latest and latest.file_id)
        has_arrival_res = bool(arrival and arrival.residence_file_id)

        issuance_date = _parse(latest.issued_at) if has_issuance else None
        arrival_date = _parse(arrival.uploaded_at) if has_arrival_res else None

        pick_issuance = False
        if has_issuance and has_arrival_res:
            # كلاهما موجود ⇒ الأحدث. وعند غياب أي تاريخ يُرجَّح الإصدار
            # الرسمي لأنه بطبيعته لاحق لوثيقة الوصول.
            if issuance_date and arrival_date:
                pick_issuance = issuance_date >= arrival_date
            else:
                pick_issuance = True
        elif has_issuance:
            pick_issuance = True

        if pick_issuance:
            file_bytes = await _download_file_bytes(context, latest.file_id)
            residence_doc = {"source": "إصدار رسمي", "date": latest.issued_at or "",
                             "file_bytes": file_bytes}
        elif has_arrival_res:
            file_bytes = await _download_file_bytes(context, arrival.residence_file_id)
            residence_doc = {"source": "من الوصول", "date": arrival.uploaded_at or "",
                             "file_bytes": file_bytes}
        else:
            residence_doc = {"source": None, "date": "", "file_bytes": None}

    return {
        "name": person.name, "role": role, "status_text": status_line(person.status),
        # ✅ **الاختيار يُمرَّر صراحةً** لا يُستنتَج من فراغ البيانات:
        # قسم فارغ لأن المستخدم ألغاه ≠ قسم فارغ لأنه لا بيانات فيه.
        # الأول يُحذَف كلياً، والثاني يُعرَض بـ"لا يوجد".
        "photo_selected": "photo" in selected,
        "docs_selected": ("formc" in selected) or ("otherdocs" in selected),
        "photo_bytes": photo_bytes,
        "expiry_date": person.expiry_date,
        "arrival_docs": arrival_docs,
        "residence_doc": residence_doc,
        "documents": doc_dicts,
    }


async def _send_case_pdf(
    update: Update, context: ContextTypes.DEFAULT_TYPE, root_id: int, *, selected: set[str],
) -> None:
    import asyncio
    from datetime import datetime as dt
    from services.residency_case_pdf import build_case_pdf

    family = rn_repo.get_family(root_id)
    if family is None:
        await _alert(update, context, "❌ لم يتم العثور على الطلب.")
        return

    await _alert(update, context, "⏳ جارٍ تجهيز الملف...", show_alert=False)

    people = [await _build_person_pdf_dict(context, family.root, role="المريض", selected=selected)]
    for c in family.companions:
        people.append(await _build_person_pdf_dict(context, c, role="مرافق", selected=selected))

    case = {
        "root_id": root_id, "case_no": str(root_id),
        "patient_name": family.root.name, "companion_count": len(family.companions),
        "created_at": dt.utcnow().strftime("%Y-%m-%d"),
        "people": people,
    }

    try:
        pdf_buf = await asyncio.to_thread(build_case_pdf, case)
    except Exception as exc:
        logger.error(f"[residency] case pdf build failed  root_id={root_id}: {exc}")
        await update.effective_chat.send_message("⚠️ تعذّر إنشاء الملف، حاول مرة أخرى.")
        return

    filename = f"ملف_الحالة_{family.root.name}_{root_id}.pdf".replace(" ", "_")
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=pdf_buf,
        filename=filename,
        caption=f"🖨️ ملف الحالة — {family.root.name}",
    )


def register_handlers(app) -> None:
    app.add_handler(CallbackQueryHandler(_dispatch_callback, pattern=r"^rn:"), group=20)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, _on_media_message), group=17)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_text_message), group=18)
    logger.info("[residency] flow handlers registered (rn: callbacks group 20, media group 17, text group 18)")


def register_result_routes() -> None:
    """نتيجة شاشة اختيار وثائق الطباعة (msel) — محرِّك الاختيار المتعدد
    نفسه مسجَّل عالمياً مسبقاً في bot/handlers_registry.py، هذا فقط
    يربط مفتاح النتيجة بدالّتنا."""
    _register_route(_RKEY_PRINT_CATS, _on_print_categories)
    logger.info(f"[residency] result routes registered: {_RKEY_PRINT_CATS}")
