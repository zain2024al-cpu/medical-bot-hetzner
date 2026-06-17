# modules/healthcare/evaluation/flow.py
# Admin flow: select specialist → select period → receive PDF report.
#
# Entry point:  handle_evaluation_command(update, context)
# Registered:   via register_handlers(app) called from admin/menu or routing
#
# Callback data format:  hceval:<action>[:<payload>]

from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

logger = logging.getLogger(__name__)

_PREFIX = "hceval"


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

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"{_PREFIX}:specialist:{name}")]
        for name in names
    ]
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PREFIX}:cancel")])
    kb   = InlineKeyboardMarkup(buttons)
    text = "📊 *تقرير تقييم الأداء الصحي*\n\nاختر الصحي:"

    query = update.callback_query
    try:
        if query:
            await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
    except Exception:
        pass
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 2: Period selection ──────────────────────────────────────────────────

async def _show_period_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE, specialist: str
) -> None:
    context.user_data[_KEY_SPECIALIST] = specialist
    today = date.today()

    # Build last 6 months list
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()

    _MONTH_AR = {
        1: "يناير", 2: "فبراير", 3: "مارس",    4: "أبريل",
        5: "مايو",  6: "يونيو",  7: "يوليو",   8: "أغسطس",
        9: "سبتمبر",10: "أكتوبر",11: "نوفمبر", 12: "ديسمبر",
    }

    buttons = []
    for yr, mn in reversed(months):
        label = f"{_MONTH_AR[mn]} {yr}"
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"{_PREFIX}:month:{yr}:{mn}"
        )])

    buttons += [
        [InlineKeyboardButton("📅 الشهر الحالي كاملاً",  callback_data=f"{_PREFIX}:this_month")],
        [InlineKeyboardButton("📅 آخر 30 يوم",           callback_data=f"{_PREFIX}:last30")],
        [InlineKeyboardButton("📅 آخر 90 يوم",           callback_data=f"{_PREFIX}:last90")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"{_PREFIX}:back_to_specialists"),
         InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PREFIX}:cancel")],
    ]

    text = (
        f"📊 *تقرير تقييم الأداء*\n\n"
        f"الصحي: *{specialist}*\n\n"
        f"اختر الفترة الزمنية:"
    )
    kb = InlineKeyboardMarkup(buttons)
    query = update.callback_query
    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


# ── Step 3: Generate and send PDF ────────────────────────────────────────────

async def _generate_and_send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    period_start: date,
    period_end:   date,
) -> None:
    specialist = context.user_data.get(_KEY_SPECIALIST, "")
    if not specialist:
        await _show_specialist_list(update, context)
        return

    query = update.callback_query
    chat_id = update.effective_chat.id

    # Show "generating…" message
    await query.edit_message_text(
        f"⏳ *جارٍ إنشاء تقرير {specialist}...*\n\n"
        f"الفترة: {period_start} → {period_end}\n"
        f"يرجى الانتظار...",
        parse_mode="Markdown",
    )

    try:
        from .repository import get_evaluation_data
        from .pdf_builder import build_evaluation_pdf

        data = get_evaluation_data(specialist, period_start, period_end)

        if data.total_cases == 0:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"📊 *تقرير {specialist}*\n\n"
                    f"لا توجد حالات مسجلة في الفترة:\n"
                    f"{period_start} → {period_end}"
                ),
                parse_mode="Markdown",
            )
            return

        pdf_buf  = build_evaluation_pdf(data)
        filename = _make_filename(specialist, period_start, period_end)
        caption  = (
            f"📊 *تقرير تقييم الأداء*\n"
            f"👨‍⚕️ {specialist}\n"
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
            f"[evaluation] PDF sent  specialist={specialist!r}"
            f"  cases={data.total_cases}  period={period_start}/{period_end}"
        )

    except Exception:
        logger.exception(f"[evaluation] PDF generation FAILED  specialist={specialist!r}")
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

    if parts[0] == "specialist":
        await _show_period_selection(update, context, ":".join(parts[1:]))

    elif parts[0] == "month" and len(parts) == 3:
        y, m = int(parts[1]), int(parts[2])
        start = date(y, m, 1)
        end   = date(y, m, monthrange(y, m)[1])
        await _generate_and_send(update, context, start, end)

    elif parts[0] == "this_month":
        start = today.replace(day=1)
        end   = today
        await _generate_and_send(update, context, start, end)

    elif parts[0] == "last30":
        await _generate_and_send(update, context, today - timedelta(days=29), today)

    elif parts[0] == "last90":
        await _generate_and_send(update, context, today - timedelta(days=89), today)

    elif parts[0] == "back_to_specialists":
        await _show_specialist_list(update, context)

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
    logger.info("[evaluation] handlers registered  command=/eval_report")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_filename(specialist: str, start: date, end: date) -> str:
    import re
    safe = re.sub(r"[^\w؀-ۿ]", "_", specialist)[:15]
    return f"Evaluation_{safe}_{start}_{end}.pdf"
