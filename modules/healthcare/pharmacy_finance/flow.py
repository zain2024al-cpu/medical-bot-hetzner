# modules/healthcare/pharmacy_finance/flow.py
# 💰 التقرير المالي — بيانات مالية لعمليات صرف الصيدلية فقط.
# مسموح فقط للأدمن أو من مُنح صلاحية "pharmacy_finance".

import logging

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

from shared.calendar_picker import build_calendar

from modules.healthcare.pharmacy_finance.session import (
    PharmacyFinanceSession,
    STEP_LIST, STEP_ITEM_COUNT, STEP_INVOICE_NUMBER, STEP_EXPENSE_ITEM,
    STEP_INVOICE_TOTAL, STEP_DISCOUNT_PERCENT, STEP_REVIEW,
)
from modules.healthcare.pharmacy_finance.views import (
    HCPHFIN,
    build_list_prompt, build_date_list_prompt, build_item_count_prompt,
    build_invoice_number_prompt, build_expense_item_prompt,
    build_invoice_total_prompt, build_discount_percent_prompt,
    build_review, build_success, build_cancelled, build_error,
)

logger = logging.getLogger(__name__)

_MODULE_KEY = "pharmacy_finance"
_PAGE_SIZE = 10

_REVIEW_EDIT_ROUTES = {
    "edit_item_count":       STEP_ITEM_COUNT,
    "edit_invoice_number":   STEP_INVOICE_NUMBER,
    "edit_expense_item":     STEP_EXPENSE_ITEM,
    "edit_invoice_total":    STEP_INVOICE_TOTAL,
    "edit_discount_percent": STEP_DISCOUNT_PERCENT,
}


def _is_authorized(user_id: int) -> bool:
    return is_admin(user_id) or user_has_module(user_id, _MODULE_KEY)


async def _edit_or_reply(update: Update, text: str, kb) -> None:
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Entry point ────────────────────────────────────────────────────────────────

async def start_pharmacy_finance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_authorized(user.id):
        return
    PharmacyFinanceSession.clear(context.user_data)
    await _show_list(update, context, page=0)


async def _show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    from modules.healthcare.pharmacy_finance.models import list_pharmacy_source_records

    user = update.effective_user
    requester_id = user.id if user else None
    admin = bool(user and is_admin(user.id))
    # ✅ المستخدم العادي يرى فقط حالاته (وغير المموّلة)؛ الأدمن يرى الكل.
    rows, total = list_pharmacy_source_records(
        page=page, page_size=_PAGE_SIZE,
        requester_id=requester_id, is_admin=admin,
    )
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    text, kb = build_list_prompt(rows, page, total_pages, total)
    await _edit_or_reply(update, text, kb)


# ── تعديل تقرير بتاريخ ────────────────────────────────────────────────────────

async def _show_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int = None, month: int = None) -> None:
    from datetime import datetime
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    text, kb = build_calendar(year, month, HCPHFIN, back_callback=f"{HCPHFIN}:page:0")
    await _edit_or_reply(update, text, kb)


async def _show_date_list(update: Update, context: ContextTypes.DEFAULT_TYPE, target_date) -> None:
    from modules.healthcare.pharmacy_finance.models import list_pharmacy_source_records

    user = update.effective_user
    requester_id = user.id if user else None
    admin = bool(user and is_admin(user.id))
    # يوم واحد فقط — عدد الحالات المتوقَّع صغير، فلا حاجة لترقيم صفحات.
    rows, _total = list_pharmacy_source_records(
        page=0, page_size=1000,
        requester_id=requester_id, is_admin=admin, target_date=target_date,
    )
    await _edit_or_reply(update, *build_date_list_prompt(rows, target_date))


async def _handle_cal_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    from datetime import date as _date
    parts = action.split(":")
    kind = parts[0]

    if kind == "cal_noop":
        return
    if kind in ("cal_prev", "cal_next"):
        y, m = int(parts[1]), int(parts[2])
        await _show_date_calendar(update, context, year=y, month=m)
        return
    if kind == "cal_pick":
        y, m, d = int(parts[1]), int(parts[2]), int(parts[3])
        await _show_date_list(update, context, _date(y, m, d))
        return


# ── Pick a source record ────────────────────────────────────────────────────────

async def _handle_pick(update: Update, context: ContextTypes.DEFAULT_TYPE, source_type: str, source_record_id: int) -> None:
    from modules.healthcare.pharmacy_finance.models import get_source_record, get_financial_record

    source = get_source_record(source_type, source_record_id)
    if source is None:
        await _edit_or_reply(update, *build_error("لم يتم العثور على الحالة."))
        return

    existing = get_financial_record(source_type, source_record_id)

    # ✅ حارس ملكية دفاعي: يمنع مستخدماً عادياً من فتح/تعديل بيانات مالية
    # أنشأها مستخدم آخر (حتى لو وصل عبر callback قديم/مباشر لا يمر بالقائمة
    # المفلترة). الأدمن معفى — يراجع الكل.
    user = update.effective_user
    if existing and not (user and is_admin(user.id)):
        owner = existing.get("created_by")
        if owner is not None and user and owner != user.id:
            await _edit_or_reply(update, *build_error("هذا التقرير المالي يخص مستخدماً آخر."))
            return

    session = PharmacyFinanceSession.create(
        context.user_data, source_type=source_type, source_record_id=source_record_id,
        patient_name=source.patient_name, item_count=source.item_count,
    )

    if existing:
        session.is_edit = True
        session.existing_financial_id = existing["id"]
        session.invoice_number = existing["invoice_number"]
        session.expense_item = existing["expense_item"]
        session.invoice_total = existing["invoice_total"]
        session.discount_percent = existing["discount_percent"]
        session.discount_amount = existing["discount_amount"]
        session.net_amount = existing["net_amount"]
        session.step = STEP_REVIEW
        session.save(context.user_data)
        await _edit_or_reply(update, *build_review(session))
    else:
        session.step = STEP_INVOICE_NUMBER
        session.save(context.user_data)
        await _edit_or_reply(update, *build_invoice_number_prompt(session))


# ── Text input ───────────────────────────────────────────────────────────────

async def _reply(update: Update, text_and_kb: tuple) -> None:
    """يرسل رسالة رد جديدة (وليس تعديل) — يُستخدم لكل خطوات الإدخال
    النصي. ✅ لا تُستخدم *unpacking هنا: Message.reply_text()'s ثاني
    وسيط موضعي هو parse_mode وليس reply_markup (كان هذا يسبب
    TypeError: got multiple values for argument 'parse_mode' فعلياً في
    الإنتاج)."""
    text, kb = text_and_kb
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = PharmacyFinanceSession.load(context.user_data)
    if session is None:
        return
    user = update.effective_user
    if not user or not _is_authorized(user.id):
        return

    text = (update.message.text or "").strip()

    if session.step == STEP_ITEM_COUNT:
        # ✅ نص حر (رقم أو وصف) — بنفس منطق حقل عدد الأصناف الأصلي في
        # مسار الصرف؛ يُرفَض الفارغ فقط. لا مسار خطي يصل هنا عادة (هذه
        # الخطوة تُفتَح فقط من زر التعديل في شاشة المراجعة).
        if not text:
            await _reply(update, build_item_count_prompt(session, error=True))
            return
        session.item_count = text
        session.save(context.user_data)
        await _go_to_review(update, context)
        return

    if session.step == STEP_INVOICE_NUMBER:
        session.invoice_number = text
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_EXPENSE_ITEM
        session.save(context.user_data)
        await _reply(update, build_expense_item_prompt(session))

    elif session.step == STEP_EXPENSE_ITEM:
        session.expense_item = text
        if session.edit_from_review:
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_INVOICE_TOTAL
        session.save(context.user_data)
        await _reply(update, build_invoice_total_prompt(session))

    elif session.step == STEP_INVOICE_TOTAL:
        try:
            total = float(text.replace(",", ""))
            if total <= 0:
                raise ValueError("non-positive")
        except ValueError:
            await _reply(update, build_invoice_total_prompt(session, error=True))
            return
        session.invoice_total = total
        if session.edit_from_review:
            _recompute(session)
            session.save(context.user_data)
            await _go_to_review(update, context)
            return
        session.step = STEP_DISCOUNT_PERCENT
        session.save(context.user_data)
        await _reply(update, build_discount_percent_prompt(session))

    elif session.step == STEP_DISCOUNT_PERCENT:
        try:
            percent = float(text.replace("%", ""))
            if percent < 0 or percent > 100:
                raise ValueError("out of range")
        except ValueError:
            await _reply(update, build_discount_percent_prompt(session, error=True))
            return
        session.discount_percent = percent
        _recompute(session)
        session.edit_from_review = False
        session.step = STEP_REVIEW
        session.save(context.user_data)
        await _reply(update, build_review(session))


def _recompute(session: PharmacyFinanceSession) -> None:
    session.discount_amount = round(session.invoice_total * session.discount_percent / 100, 2)
    session.net_amount = round(session.invoice_total - session.discount_amount, 2)


async def _go_to_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = PharmacyFinanceSession.load(context.user_data)
    if session is None:
        return
    session.edit_from_review = False
    session.step = STEP_REVIEW
    session.save(context.user_data)
    await _edit_or_reply(update, *build_review(session))


# ── Edit-from-review routing ────────────────────────────────────────────────────

async def _open_edit_step(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    step = _REVIEW_EDIT_ROUTES.get(action)
    if step is None:
        return
    session = PharmacyFinanceSession.load(context.user_data)
    if session is None:
        return
    session.edit_from_review = True
    session.step = step
    session.save(context.user_data)

    if step == STEP_ITEM_COUNT:
        await _edit_or_reply(update, *build_item_count_prompt(session))
    elif step == STEP_INVOICE_NUMBER:
        await _edit_or_reply(update, *build_invoice_number_prompt(session))
    elif step == STEP_EXPENSE_ITEM:
        await _edit_or_reply(update, *build_expense_item_prompt(session))
    elif step == STEP_INVOICE_TOTAL:
        await _edit_or_reply(update, *build_invoice_total_prompt(session))
    elif step == STEP_DISCOUNT_PERCENT:
        await _edit_or_reply(update, *build_discount_percent_prompt(session))


# ── Back navigation ──────────────────────────────────────────────────────────

async def _handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = PharmacyFinanceSession.load(context.user_data)
    if session is None:
        await _show_list(update, context, page=0)
        return

    if session.edit_from_review:
        await _go_to_review(update, context)
        return

    if session.step == STEP_INVOICE_NUMBER:
        PharmacyFinanceSession.clear(context.user_data)
        await _show_list(update, context, page=0)
    elif session.step == STEP_EXPENSE_ITEM:
        session.step = STEP_INVOICE_NUMBER
        session.save(context.user_data)
        await _edit_or_reply(update, *build_invoice_number_prompt(session))
    elif session.step == STEP_INVOICE_TOTAL:
        session.step = STEP_EXPENSE_ITEM
        session.save(context.user_data)
        await _edit_or_reply(update, *build_expense_item_prompt(session))
    elif session.step == STEP_DISCOUNT_PERCENT:
        session.step = STEP_INVOICE_TOTAL
        session.save(context.user_data)
        await _edit_or_reply(update, *build_invoice_total_prompt(session))
    else:
        await _show_list(update, context, page=0)


# ── Confirm / cancel ─────────────────────────────────────────────────────────

async def _handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.healthcare.pharmacy_finance.models import save_financial_record, update_source_item_count

    session = PharmacyFinanceSession.load(context.user_data)
    if session is None:
        await _show_list(update, context, page=0)
        return

    user = update.effective_user
    try:
        saved = save_financial_record(
            source_type=session.source_type,
            source_record_id=session.source_record_id,
            invoice_number=session.invoice_number,
            expense_item=session.expense_item,
            invoice_total=session.invoice_total,
            discount_percent=session.discount_percent,
            created_by=user.id if user else None,
            existing_financial_id=session.existing_financial_id,
        )
        # ✅ عدد/تفاصيل الأصناف يُحدَّث على سجل الصرف الأصلي (وليس على
        # البيانات المالية) — حتى تعكس مسير الإخلاء القيمة الصحيحة الحالية
        # عند إعادة الطباعة (مثال: استرجاع أدوية يُنقص العدد).
        update_source_item_count(session.source_type, session.source_record_id, session.item_count)
    except Exception as exc:
        logger.error(f"[pharmacy_finance] save failed: {exc}", exc_info=True)
        await _edit_or_reply(update, *build_error("فشل حفظ البيانات المالية."))
        return

    patient_name = session.patient_name
    PharmacyFinanceSession.clear(context.user_data)
    await _edit_or_reply(update, *build_success(saved["net_amount"], patient_name))


async def _handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    PharmacyFinanceSession.clear(context.user_data)
    await _edit_or_reply(update, *build_cancelled())


# ── Callback dispatcher ──────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    user = update.effective_user
    try:
        await query.answer()
    except Exception:
        pass
    if not user or not _is_authorized(user.id):
        return

    data = query.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "noop":
        return
    if action == "cancel":
        await _handle_cancel(update, context)
        return
    if action == "back":
        await _handle_back(update, context)
        return
    if action == "confirm":
        await _handle_confirm(update, context)
        return
    if action == "page":
        page = int(parts[2]) if len(parts) > 2 else 0
        await _show_list(update, context, page=page)
        return
    if action == "datesearch":
        await _show_date_calendar(update, context)
        return
    if action.startswith("cal_"):
        # إعادة تجميع بقية الأجزاء (السنة/الشهر/اليوم) بعد بادئة الوحدة.
        await _handle_cal_action(update, context, ":".join(parts[1:]))
        return
    if action == "pick":
        source_type, source_record_id = parts[2], int(parts[3])
        await _handle_pick(update, context, source_type, source_record_id)
        return
    if action in _REVIEW_EDIT_ROUTES:
        await _open_edit_step(update, context, action)
        return

    logger.warning(f"[pharmacy_finance] unknown action: {action!r}")


# ── Registration ─────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    # ✅ group=10 صراحةً (وليس الافتراضي 0) — group 0 تحتوي على معالج
    # نصوص woundcare العام (filters.TEXT & ~filters.COMMAND) المسجَّل
    # قبل هذه الوحدة؛ تيليجرام يستدعي أول معالج مطابق فقط لكل مجموعة،
    # فكان زر "💰 التقرير المالي" (وأي نص آخر) يُبتلَع صامتاً هناك قبل
    # أن يصل لهذه الوحدة إطلاقاً. مسجَّل هنا أولاً ضمن نفس المجموعة قبل
    # handle_text_input العام، فيُطابَق التطابق الدقيق أولاً بلا تعارض.
    app.add_handler(MessageHandler(filters.Regex(r"^💰 التقرير المالي$"), start_pharmacy_finance), group=10)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input), group=10)
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=rf"^{HCPHFIN}:"), group=1)
    logger.info("[pharmacy_finance] handlers registered")
