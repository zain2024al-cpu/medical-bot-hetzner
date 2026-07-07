# modules/healthcare/pharmacy_print/flow.py
# 🖨️ طباعة مسير إخلاء الأدوية والمستلزمات الطبية.
# مسموح فقط للأدمن أو من مُنح صلاحية "pharmacy_print".
#
# تقويم مستقل خاص بهذا المسار (وليس تعديل shared/calendar_picker.py
# المشترك) — نفس الاتفاقية المتّبعة في hceval:/cr:/da: هذه الجلسة.

import logging
from calendar import monthcalendar
from datetime import date, datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin
from core.access.access_service import user_has_module

logger = logging.getLogger(__name__)

_MODULE_KEY = "pharmacy_print"
_PFX = "hcphprint"
_KEY = "_hcphprint_ledger"

_MONTH_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
    7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
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

async def start_pharmacy_print(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not _is_authorized(user.id):
        return
    context.user_data.pop(_KEY, None)
    await _show_period_menu(update)


async def _show_period_menu(update: Update) -> None:
    text = "🖨️ *طباعة مسير الإخلاء*\n\nاختر الفترة:"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 يوم واحد", callback_data=f"{_PFX}:period:day")],
        [InlineKeyboardButton("📆 من تاريخ ← إلى تاريخ", callback_data=f"{_PFX}:period:range")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])
    await _edit_or_reply(update, text, kb)


# ── Calendar (مستقل عن shared/calendar_picker.py) ──────────────────────────────

def _calendar_kb(year: int, month: int, step: str) -> InlineKeyboardMarkup:
    today = date.today()
    buttons = []

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    nav_row = [
        InlineKeyboardButton("◀️", callback_data=f"{_PFX}:cal:{step}:navmonth:{prev_year}-{prev_month}"),
        InlineKeyboardButton(f"{_MONTH_AR[month]} {year}", callback_data=f"{_PFX}:noop"),
    ]
    if (year, month) < (today.year, today.month):
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"{_PFX}:cal:{step}:navmonth:{next_year}-{next_month}"))
    buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(d, callback_data=f"{_PFX}:noop") for d in ["إ", "ث", "ع", "خ", "ج", "س", "ح"]])

    for week in monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:noop"))
                continue
            d = date(year, month, day_num)
            if d > today:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:noop"))
            else:
                label = f"⭐{day_num}" if d == today else str(day_num)
                row.append(InlineKeyboardButton(label, callback_data=f"{_PFX}:cal:{step}:select:{d.isoformat()}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:back_to_period")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _show_calendar(update: Update, step: str, year: int | None = None, month: int | None = None) -> None:
    today = date.today()
    year = year or today.year
    month = month or today.month
    label = "تاريخ اليوم" if step == "day" else ("تاريخ البداية" if step == "start" else "تاريخ النهاية")
    text = f"🖨️ *طباعة مسير الإخلاء*\n\nاختر {label}:"
    await _edit_or_reply(update, text, _calendar_kb(year, month, step))


# ── Period selection ─────────────────────────────────────────────────────────

async def _handle_period(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> None:
    context.user_data[_KEY] = {"kind": kind}
    if kind == "day":
        await _show_calendar(update, step="day")
    else:
        await _show_calendar(update, step="start")


async def _handle_cal_select(update: Update, context: ContextTypes.DEFAULT_TYPE, step: str, iso_date: str) -> None:
    selected = date.fromisoformat(iso_date)
    state = context.user_data.setdefault(_KEY, {})

    if step == "day":
        state["start_date"] = selected
        state["end_date"] = selected
        await _generate_and_show_export_choice(update, context)
        return

    if step == "start":
        state["start_date"] = selected
        await _show_calendar(update, step="end", year=selected.year, month=selected.month)
        return

    if step == "end":
        start = state.get("start_date") or selected
        end = selected
        if end < start:
            start, end = end, start
        state["start_date"] = start
        state["end_date"] = end
        await _generate_and_show_export_choice(update, context)
        return


async def _handle_cal_nav(update: Update, context: ContextTypes.DEFAULT_TYPE, step: str, year: int, month: int) -> None:
    await _show_calendar(update, step=step, year=year, month=month)


# ── Generate ledger + show export choice ────────────────────────────────────

async def _generate_and_show_export_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from services.pharmacy_evacuation_service import get_evacuation_ledger_rows

    state = context.user_data.get(_KEY, {})
    start = state.get("start_date")
    end = state.get("end_date")
    if start is None or end is None:
        await _show_period_menu(update)
        return

    rows = await get_evacuation_ledger_rows(start, end)
    state["rows"] = rows
    context.user_data[_KEY] = state

    if not rows:
        text = (
            f"⚠️ لا توجد بيانات مطابقة لمعايير البحث المحددة.\n\n"
            f"الفترة: من {start.strftime('%Y-%m-%d')} إلى {end.strftime('%Y-%m-%d')}"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:back_to_period")]])
        await _edit_or_reply(update, text, kb)
        return

    total = sum(r["amount"] for r in rows)
    text = (
        f"✅ *تم إعداد المسير*\n\n"
        f"الفترة: من {start.strftime('%Y-%m-%d')} إلى {end.strftime('%Y-%m-%d')}\n"
        f"عدد السجلات: {len(rows)}\n"
        f"إجمالي المبلغ: {total:,.2f}\n\n"
        f"اختر صيغة التصدير:"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 PDF", callback_data=f"{_PFX}:export:pdf"),
         InlineKeyboardButton("📊 Excel", callback_data=f"{_PFX}:export:excel")],
        [InlineKeyboardButton("📄 PDF + 📊 Excel", callback_data=f"{_PFX}:export:both")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])
    await _edit_or_reply(update, text, kb)


async def _handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE, choice: str) -> None:
    from services.pharmacy_evacuation_pdf import build_evacuation_pdf
    from services.pharmacy_evacuation_excel import build_evacuation_excel

    state = context.user_data.get(_KEY, {})
    rows = state.get("rows")
    start = state.get("start_date")
    end = state.get("end_date")
    if rows is None or start is None or end is None:
        await _show_period_menu(update)
        return

    query = update.callback_query
    chat_id = update.effective_chat.id if update.effective_chat else None

    try:
        if choice in ("pdf", "both"):
            pdf_buf = build_evacuation_pdf(rows, start, end)
            await context.bot.send_document(
                chat_id=chat_id, document=pdf_buf,
                filename=f"مسير_اخلاء_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.pdf",
            )
        if choice in ("excel", "both"):
            xlsx_buf = build_evacuation_excel(rows, start, end)
            await context.bot.send_document(
                chat_id=chat_id, document=xlsx_buf,
                filename=f"مسير_اخلاء_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.xlsx",
            )
    except Exception as exc:
        logger.error(f"[pharmacy_print] export failed: {exc}", exc_info=True)
        try:
            await query.answer("❌ فشل إنشاء الملف.", show_alert=True)
        except Exception:
            pass
        return

    context.user_data.pop(_KEY, None)
    try:
        await query.answer("✅ تم الإرسال")
    except Exception:
        pass


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
        context.user_data.pop(_KEY, None)
        await _edit_or_reply(update, "✅ تم الإلغاء.", InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:back_to_period")
        ]]))
        return
    if action == "back_to_period":
        await _show_period_menu(update)
        return
    if action == "period":
        kind = parts[2] if len(parts) > 2 else "day"
        await _handle_period(update, context, kind)
        return
    if action == "cal":
        step = parts[2]
        sub = parts[3]
        if sub == "navmonth":
            y_str, m_str = parts[4].split("-")
            await _handle_cal_nav(update, context, step, int(y_str), int(m_str))
        elif sub == "select":
            await _handle_cal_select(update, context, step, parts[4])
        return
    if action == "export":
        choice = parts[2] if len(parts) > 2 else "pdf"
        await _handle_export(update, context, choice)
        return

    logger.warning(f"[pharmacy_print] unknown action: {action!r}")


# ── Registration ─────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    # ✅ group=11 صراحةً (وليس الافتراضي 0) — نفس سبب pharmacy_finance:
    # group 0 يحوي معالج نصوص woundcare العام الذي يبتلع أي رسالة نصية
    # قبل وصولها لهذه الوحدة. group=1 لكل CallbackQueryHandler بنفس
    # اتفاقية باقي وحدات الرعاية الصحية (hc:, hcmed:, hcsup:, ...).
    app.add_handler(MessageHandler(filters.Regex(r"^🖨️ طباعة مسير الإخلاء$"), start_pharmacy_print), group=11)
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=rf"^{_PFX}:"), group=1)
    logger.info("[pharmacy_print] handlers registered")
