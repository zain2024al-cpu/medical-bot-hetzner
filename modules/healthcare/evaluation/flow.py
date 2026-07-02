# modules/healthcare/evaluation/flow.py
# Admin flow: select specialist (or comprehensive) → select period → receive PDF report.
#
# Entry point:  handle_evaluation_command(update, context)
# Registered:   via register_handlers(app) called from admin/menu or routing
#
# Callback data format:  hceval:<action>[:<payload>]

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, timedelta, datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler, MessageHandler, filters

logger = logging.getLogger(__name__)

_PREFIX = "hceval"

# ✅ قيمة مُخصَّصة (sentinel) تُخزَّن في _KEY_SPECIALIST للدلالة على
# "تقرير شامل لكل الصحيين" بدل اسم صحي واحد.
_ALL_SENTINEL = "__ALL__"
_ALL_LABEL    = "جميع الصحيين"


# ── Session keys ──────────────────────────────────────────────────────────────

_KEY_SPECIALIST  = "_hceval_specialist"
_KEY_PERIOD_TYPE = "_hceval_period"    # "month" | "custom"
_KEY_DATE_START  = "_hceval_start"     # "YYYY-MM-DD"
_KEY_DATE_END    = "_hceval_end"       # "YYYY-MM-DD"


# ── Entry: /eval_report command ───────────────────────────────────────────────

async def handle_evaluation_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Entry point — show specialist selection."""
    await _show_specialist_list(update, context)


# ── Step 1: Specialist selection ──────────────────────────────────────────────

async def _show_specialist_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    from .repository import list_specialist_names
    names = list_specialist_names()

    if not names:
        text = "⚠️ لا يوجد صحيون مسجلون في قاعدة البيانات بعد."
        query = update.callback_query
        if query:
            await query.edit_message_text(text)
        else:
            await update.effective_message.reply_text(text)
        return

    # ✅ خيار التقرير الشامل — يظهر أولاً قبل قائمة الصحيين
    buttons = [
        [InlineKeyboardButton("📊 تقرير شامل لكل الصحيين", callback_data=f"{_PREFIX}:allspecialists")],
    ]
    buttons += [
        [InlineKeyboardButton(name, callback_data=f"{_PREFIX}:specialist:{name}")]
        for name in names
    ]
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PREFIX}:cancel")])
    kb   = InlineKeyboardMarkup(buttons)
    text = "📊 *تقرير تقييم الأداء الصحي*\n\nاختر تقريراً شاملاً أو صحياً محدداً:"

    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 2: Period selection ──────────────────────────────────────────────────

_MONTH_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس",    4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو",   8: "أغسطس",
    9: "سبتمبر",10: "أكتوبر",11: "نوفمبر", 12: "ديسمبر",
}


def _display_name(specialist_key: str) -> str:
    """اسم العرض للصحي — يحوّل sentinel التقرير الشامل إلى نص مفهوم."""
    return _ALL_LABEL if specialist_key == _ALL_SENTINEL else specialist_key


async def _show_period_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, specialist: str | None
) -> None:
    """عرض اختيار الفترة الزمنية — خياران فقط: شهري، أو فترة محددة من التقويم.

    specialist=None → وضع التقرير الشامل (كل الصحيين معاً).
    """
    context.user_data[_KEY_SPECIALIST] = _ALL_SENTINEL if specialist is None else specialist
    today = date.today()

    # قائمة آخر 6 أشهر (تغطي خيار "شهري")
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()

    buttons = []
    for yr, mn in reversed(months):
        label = f"{_MONTH_AR[mn]} {yr}"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"{_PREFIX}:month:{yr}:{mn}"
        )])

    buttons += [
        [InlineKeyboardButton("📆 فترة محددة (من تاريخ إلى تاريخ)", callback_data=f"{_PREFIX}:customstart")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{_PREFIX}:back_to_specialists"),
         InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PREFIX}:cancel")],
    ]

    display = _display_name(context.user_data[_KEY_SPECIALIST])
    text = (
        f"📊 *تقرير تقييم الأداء*\n\n"
        f"الجهة: *{display}*\n\n"
        f"اختر الفترة الزمنية:\n"
        f"• شهر محدد من القائمة أدناه\n"
        f"• أو فترة مخصَّصة من التقويم"
    )
    kb = InlineKeyboardMarkup(buttons)
    query = update.callback_query
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 2.5: Custom date-range calendar (from date → to date) ────────────────

def _calendar_kb(year: int, month: int, step: str) -> InlineKeyboardMarkup:
    """
    تقويم شهري تفاعلي لاختيار يوم واحد — يُعاد استخدامه مرتين
    (مرة لاختيار تاريخ البداية، ومرة لتاريخ النهاية) عبر معامل step.
    مبني يدوياً هنا (بدل استيراد services/inline_calendar لتفادي تعقيد
    دمج بادئة callback خارجية مع نظام hceval: الحالي)، لكنه يتبع نفس
    منطق وتصميم التقويم المستخدم في باقي المشروع.
    """
    from calendar import monthcalendar

    today = date.today()
    buttons = []

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1)  if month == 12 else (year, month + 1)

    month_label = f"{_MONTH_AR[month]} {year}"
    nav_row = [
        InlineKeyboardButton("◀️", callback_data=f"{_PREFIX}:cal{step}:navmonth:{prev_year}-{prev_month}"),
        InlineKeyboardButton(month_label, callback_data=f"{_PREFIX}:noop"),
    ]
    # لا نسمح بالتنقل لأشهر مستقبلية (التقرير عن بيانات ماضية فقط)
    if (year, month) < (today.year, today.month):
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"{_PREFIX}:cal{step}:navmonth:{next_year}-{next_month}"))
    buttons.append(nav_row)

    day_headers = ["إ", "ث", "ع", "خ", "ج", "س", "ح"]
    buttons.append([InlineKeyboardButton(d, callback_data=f"{_PREFIX}:noop") for d in day_headers])

    cal = monthcalendar(year, month)
    for week in cal:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PREFIX}:noop"))
                continue
            d = date(year, month, day_num)
            if d > today:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PREFIX}:noop"))
            else:
                label = f"⭐{day_num}" if d == today else str(day_num)
                row.append(InlineKeyboardButton(label, callback_data=f"{_PREFIX}:cal{step}:select:{d.isoformat()}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{_PREFIX}:back_to_period")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PREFIX}:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _show_custom_calendar(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    step: str, year: int | None = None, month: int | None = None,
) -> None:
    today = date.today()
    year  = year  or today.year
    month = month or today.month

    step_label = "تاريخ البداية" if step == "start" else "تاريخ النهاية"
    display = _display_name(context.user_data.get(_KEY_SPECIALIST, ""))
    text = (
        f"📆 *اختيار فترة مخصَّصة*\n\n"
        f"الجهة: *{display}*\n"
        f"اختر {step_label}:"
    )
    query = update.callback_query
    try:
        await query.edit_message_text(text, reply_markup=_calendar_kb(year, month, step), parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=_calendar_kb(year, month, step), parse_mode="Markdown")


# ── Step 3: Generate and send PDF ────────────────────────────────────────────

async def _generate_and_send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    period_start: date,
    period_end:   date,
) -> None:
    specialist_key = context.user_data.get(_KEY_SPECIALIST, "")
    if not specialist_key:
        await _show_specialist_list(update, context)
        return

    is_comprehensive = specialist_key == _ALL_SENTINEL
    display = _display_name(specialist_key)

    query = update.callback_query
    chat_id = update.effective_chat.id

    # Show "generating…" message
    await query.edit_message_text(
        f"⏳ *جارٍ إنشاء تقرير {display}...*\n\n"
        f"الفترة: {period_start} → {period_end}\n"
        f"يرجى الانتظار...",
        parse_mode="Markdown",
    )

    try:
        from .repository import get_evaluation_data
        from .pdf_builder import build_evaluation_pdf

        data = get_evaluation_data(
            None if is_comprehensive else specialist_key,
            period_start, period_end,
        )

        if data.total_cases == 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"📊 *تقرير {display}*\n\n"
                    f"لا توجد حالات مسجلة في الفترة:\n"
                    f"{period_start} → {period_end}"
                ),
                parse_mode="Markdown",
            )
            return

        pdf_buf  = build_evaluation_pdf(data)
        filename = _make_filename(display, period_start, period_end)
        caption  = (
            f"📊 *تقرير تقييم الأداء*\n"
            f"👨‍⚕️ {display}\n"
            f"📅 {period_start} — {period_end}\n"
            f"📋 {data.total_cases} حالة | {data.active_days} يوم نشاط"
        )

        await context.bot.send_document(
            chat_id=chat_id,
            document=pdf_buf,
            filename=filename,
            caption=caption,
            parse_mode="Markdown",
        )
        logger.info(
            f"[evaluation] PDF sent  specialist={display!r}"
            f"  cases={data.total_cases}  period={period_start}/{period_end}"
        )

    except Exception:
        logger.exception(f"[evaluation] PDF generation FAILED  specialist={display!r}")
        await context.bot.send_message(
            chat_id=chat_id,
            text="❌ حدث خطأ أثناء إنشاء التقرير. يرجى المحاولة مرة أخرى.",
        )

    finally:
        # Clean up session
        for key in (_KEY_SPECIALIST, _KEY_PERIOD_TYPE, _KEY_DATE_START, _KEY_DATE_END):
            context.user_data.pop(key, None)


# ── Callback dispatcher ───────────────────────────────────────────────────────

async def _handle_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
    except Exception:
        pass

    data   = query.data or ""
    action = data[len(_PREFIX) + 1:]   # strip "hceval:"
    parts  = action.split(":")
    today  = date.today()

    if parts[0] == "start":
        await _show_specialist_list(update, context)

    elif parts[0] == "allspecialists":
        await _show_period_selection(update, context, specialist=None)

    elif parts[0] == "specialist":
        await _show_period_selection(update, context, specialist=":".join(parts[1:]))

    elif parts[0] == "month" and len(parts) == 3:
        y, m = int(parts[1]), int(parts[2])
        start = date(y, m, 1)
        end   = min(date(y, m, monthrange(y, m)[1]), today)
        await _generate_and_send(update, context, start, end)

    elif parts[0] == "customstart":
        await _show_custom_calendar(update, context, step="start")

    elif parts[0] in ("calstart", "calend"):
        step = "start" if parts[0] == "calstart" else "end"
        sub_action = parts[1] if len(parts) > 1 else ""

        if sub_action == "navmonth" and len(parts) >= 3:
            # payload: "السنة_الجديدة-الشهر_الجديد"
            try:
                nav_year_str, nav_month_str = parts[2].split("-")
                await _show_custom_calendar(
                    update, context, step=step,
                    year=int(nav_year_str), month=int(nav_month_str),
                )
            except Exception as exc:
                logger.error(f"[evaluation] Failed to parse calendar nav payload {parts[2]!r}: {exc}")

        elif sub_action == "select" and len(parts) >= 3:
            selected_str = parts[2]
            try:
                selected = date.fromisoformat(selected_str)
            except Exception:
                selected = today

            if step == "start":
                context.user_data[_KEY_DATE_START] = selected.isoformat()
                await _show_custom_calendar(
                    update, context, step="end",
                    year=selected.year, month=selected.month,
                )
            else:
                start_str = context.user_data.get(_KEY_DATE_START)
                start_d = date.fromisoformat(start_str) if start_str else selected
                end_d   = selected
                # ✅ ترتيب تلقائي إن اختار المستخدم تاريخ نهاية أقدم من البداية
                if end_d < start_d:
                    start_d, end_d = end_d, start_d
                await _generate_and_send(update, context, start_d, end_d)

    elif parts[0] == "back_to_period":
        specialist_key = context.user_data.get(_KEY_SPECIALIST, "")
        specialist = None if specialist_key == _ALL_SENTINEL else specialist_key
        await _show_period_selection(update, context, specialist=specialist)

    elif parts[0] == "back_to_specialists":
        await _show_specialist_list(update, context)

    elif parts[0] == "noop":
        pass

    elif parts[0] == "cancel":
        for key in (_KEY_SPECIALIST, _KEY_PERIOD_TYPE, _KEY_DATE_START, _KEY_DATE_END):
            context.user_data.pop(key, None)
        try:
            await query.edit_message_text("✅ تم إلغاء العملية.")
        except Exception:
            pass


# ── Registration ──────────────────────────────────────────────────────────────

def register_handlers(app) -> None:
    app.add_handler(
        CommandHandler("eval_report", handle_evaluation_command),
        group=1,
    )
    app.add_handler(
        CallbackQueryHandler(_handle_callback, pattern=rf"^{_PREFIX}:"),
        group=1,
    )
    # ReplyKeyboard button handler (admin main keyboard)
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^📊 تقرير تقييم الرعاية الصحية$"),
            handle_evaluation_command,
        ),
        group=1,
    )
    logger.info("[evaluation] handlers registered  command=/eval_report  button=📊 تقرير تقييم الرعاية الصحية")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_filename(display_name: str, start: date, end: date) -> str:
    import re
    safe = re.sub(r"[^\w؀-ۿ]", "_", display_name)[:15]
    return f"Evaluation_{safe}_{start}_{end}.pdf"
