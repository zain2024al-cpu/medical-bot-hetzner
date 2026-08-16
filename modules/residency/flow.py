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

from modules.residency.constants import RN, STATUS_ORDER, STATUS_WAITING_ARRIVAL
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


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


def _clear_transient_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(_CTX_UPLOAD_TARGET, None)
    context.user_data.pop(_CTX_CAL_TARGET, None)
    context.user_data.pop(_CTX_SEARCH_ACTIVE, None)
    context.user_data.pop(_CTX_DOC_NAME_ACTIVE, None)


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


async def _show_status_list(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str) -> None:
    families = rn_repo.get_requests_by_status(status)
    text, kb = rn_views.build_status_list(status, families)
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
    doc_counts = rn_repo.get_document_counts(person_ids)
    text, kb = rn_views.build_family_detail(family, is_admin=is_admin(uid), doc_counts=doc_counts)
    await _edit(update, text, kb)


async def _show_arrival_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, family: rn_repo.FamilyRow) -> None:
    arrival = rn_repo.get_arrival_patient_docs_by_name(family.root.name)
    text, kb = rn_views.build_arrival_summary(family.root, arrival, family.companions)
    await _edit(update, text, kb)


# ── Documents (📄) ───────────────────────────────────────────────────────────

async def _show_documents(update: Update, context: ContextTypes.DEFAULT_TYPE, person_id: int) -> None:
    person = rn_repo.get_person(person_id)
    if person is None:
        await _edit(update, "❌ لم يتم العثور على الشخص.", None)
        return
    documents = rn_repo.get_documents_for_person(person_id)
    text, kb = rn_views.build_documents_list(person, documents)
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
        text, kb = rn_views.build_onboard_review([p for p in queue_rows if p])
        await _edit(update, text, kb)
        return

    person = rn_repo.get_person(state["queue_ids"][state["index"]])
    if person is None:
        await _show_menu(update, context)
        return

    if state["step"] == "photo":
        context.user_data[_CTX_UPLOAD_TARGET] = {"kind": "onboard_photo", "person_id": person.id, "root_id": root_id}
        text, kb = rn_views.build_onboard_photo_prompt(person, state["index"] + 1, len(state["queue_ids"]))
        await _edit(update, text, kb)
    else:  # reminder
        context.user_data[_CTX_CAL_TARGET] = {"kind": "onboard_remind", "person_id": person.id, "root_id": root_id}
        now = datetime.utcnow()
        text, kb = build_calendar(now.year, now.month, RN, back_callback=f"{RN}:menu")
        await _edit(update, text, kb)


# ── Issuance (🟣) ────────────────────────────────────────────────────────────

async def _show_issuance(update: Update, context: ContextTypes.DEFAULT_TYPE, person_id: int) -> None:
    person = rn_repo.get_person(person_id)
    if person is None:
        await _edit(update, "❌ لم يتم العثور على الشخص.", None)
        return
    text, kb = rn_views.build_issuance_view(person)
    await _edit(update, text, kb)


# ── Callback dispatcher ────────────────────────────────────────────────────────

async def _dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
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

    if action.startswith("status_"):
        status = action[len("status_"):]
        if status in STATUS_ORDER:
            await _show_status_list(update, context, status)
        return

    if action.startswith("family_"):
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

    if action.startswith("submit_"):
        person_id = int(action[len("submit_"):])
        if not is_admin(uid):
            await query.answer("🚫 هذا الزر للأدمن فقط.", show_alert=True)
            return
        rn_models.mark_submitted(person_id, performed_by=uid)
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
            await query.answer("⚠️ أكمل تاريخ الانتهاء والملف أولاً.", show_alert=True)
            return
        root_id = rn_repo.get_root_id_for_person(person_id)
        if root_id:
            await _show_family(update, context, root_id, uid)
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

    if action == "log":
        entries = rn_repo.get_recent_log(30)
        text, kb = rn_views.build_log_view(entries)
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

    if sub in ("cal_prev", "cal_next"):
        y, m = int(parts[1]), int(parts[2])
        back = f"{RN}:menu" if target["kind"] == "onboard_remind" else f"{RN}:issue_view_{target['person_id']}"
        text, kb = build_calendar(y, m, RN, back_callback=back)
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    if sub == "cal_pick":
        y, mo, d = int(parts[1]), int(parts[2]), int(parts[3])
        date_iso = f"{y:04d}-{mo:02d}-{d:02d}"
        person_id = target["person_id"]

        if target["kind"] == "onboard_remind":
            rn_models.set_reminder_date(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            await _show_onboard_step(update, context, target["root_id"])
        elif target["kind"] == "issue_expiry":
            rn_models.set_issuance_expiry(person_id, date_iso)
            context.user_data.pop(_CTX_CAL_TARGET, None)
            await _show_issuance(update, context, person_id)
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
        doc_dicts.append({"label": label, "file_bytes": file_bytes})

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

        latest = rn_repo.get_latest_issuance(person.id)
        issuance_date = _parse(latest.issued_at) if (latest and latest.file_id) else None
        arrival_date = _parse(arrival.uploaded_at) if (arrival and arrival.residence_file_id) else None

        if issuance_date and (not arrival_date or issuance_date >= arrival_date):
            file_bytes = await _download_file_bytes(context, latest.file_id)
            residence_doc = {"source": "إصدار رسمي", "date": latest.issued_at, "file_bytes": file_bytes}
        elif arrival_date:
            file_bytes = await _download_file_bytes(context, arrival.residence_file_id)
            residence_doc = {"source": "من الوصول", "date": arrival.uploaded_at, "file_bytes": file_bytes}
        else:
            residence_doc = {"source": None, "date": "", "file_bytes": None}

    return {
        "name": person.name, "role": role, "status_text": status_line(person.status),
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
        await update.callback_query.answer("❌ لم يتم العثور على الطلب.", show_alert=True)
        return

    await update.callback_query.answer("⏳ جارٍ تجهيز الملف...")

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
