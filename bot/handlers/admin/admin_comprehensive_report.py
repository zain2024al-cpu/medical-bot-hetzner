# bot/handlers/admin/admin_comprehensive_report.py
#
# Comprehensive PDF report handler — all cases in a date range, with
# dynamic cascading filters (hospitals → departments → doctors → action
# types), each scoped to what actually has data given prior selections.
#
# Dialog flow:
#   📊 Comprehensive Report selected
#       ↓
#   Choose period: [📅 شهر كامل] [📆 فترة مخصصة]
#       ↓ (شهر كامل: سنة ديناميكية ← شهر)  أو  (فترة مخصصة: تقويمان بداية/نهاية)
#   Hospitals (multi-select, counts, only options with data)
#       ↓
#   Departments (scoped to selected hospitals)
#       ↓
#   Doctors (scoped to selected hospitals+departments)
#       ↓
#   Action types (scoped to all prior selections)
#       ↓
#   Summary of all selected filters → ✅ إنشاء التقرير
#       ↓
#   Generate PDF and send
#
# Callback prefix: cr:
# States: CR_PERIOD → END (all delegated screens are plain CallbackQueryHandlers
#         under the same "cr:" prefix, matching the pattern already proven
#         today for admin_patient_report_v2.py / modules/healthcare/evaluation)
#
from __future__ import annotations

import asyncio
import logging
from calendar import monthrange
from datetime import datetime, timedelta, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CallbackQueryHandler,
)

from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
CR_PERIOD = 801

_PFX = "cr"  # callback prefix

_KEY = "cr_filters"  # context.user_data key holding the in-progress filter state

_MONTH_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس",    4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو",   8: "أغسطس",
    9: "سبتمبر",10: "أكتوبر",11: "نوفمبر", 12: "ديسمبر",
}

# كل شريحة فلترة: مفتاحها في filters dict، بادئة الـcallback الخاصة بها،
# العنوان المعروض، ودالة جلب الخيارات (تُستدعى بمعاملات الشرائح السابقة).
_TIERS = ["hospitals", "departments", "doctors", "actions"]
_TIER_META = {
    "hospitals":   {"cb": "hsel",  "title": "المستشفيات"},
    "departments": {"cb": "dsel",  "title": "الأقسام"},
    "doctors":     {"cb": "dosel", "title": "الأطباء"},
    "actions":     {"cb": "asel",  "title": "أنواع الإجراءات"},
}
_TIER_ORDER = {name: i for i, name in enumerate(_TIERS)}


def _new_filters() -> dict:
    return {
        "start": None, "end": None, "period_label": None,
        "hospitals": [], "departments": [], "doctors": [], "actions": [],
        "hospitals_all": True, "departments_all": True,
        "doctors_all": True, "actions_all": True,
        "_options": [],   # current tier's [{"name","count"}, ...] (index-addressable)
        "_page": 0,
        "_year_center": date.today().year,
    }


def _f(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault(_KEY, _new_filters())


# ── Legacy period keyboard (kept registered for backward compatibility) ───────

def _period_kb() -> InlineKeyboardMarkup:
    """Period selection — النسخة الجديدة: خياران فقط."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 شهر كامل", callback_data=f"{_PFX}:period:month")],
        [InlineKeyboardButton("📆 فترة مخصصة (من - إلى)", callback_data=f"{_PFX}:period:custom")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Show period menu (entry point — called by admin_reports_menu.py) ──────────

async def show_period_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Show period selection menu."""
    context.user_data[_KEY] = _new_filters()
    try:
        await update.callback_query.edit_message_text(
            "📊 *التقرير الشامل*\n\n"
            "📅 اختر الفترة الزمنية:",
            reply_markup=_period_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await update.callback_query.message.reply_text(
            "📊 *التقرير الشامل*\n\n"
            "📅 اختر الفترة الزمنية:",
            reply_markup=_period_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    return CR_PERIOD


# ── Year → month picker ("📅 شهر كامل") ─────────────────────────────────────

def _year_kb(center_year: int) -> InlineKeyboardMarkup:
    years = [center_year - 1, center_year, center_year + 1]
    row = [InlineKeyboardButton(str(y), callback_data=f"{_PFX}:yr:pick:{y}") for y in years]
    nav = [
        InlineKeyboardButton("◀️ سنوات أقدم", callback_data=f"{_PFX}:yr:nav:{center_year - 3}"),
        InlineKeyboardButton("أحدث ▶️", callback_data=f"{_PFX}:yr:nav:{center_year + 3}"),
    ]
    return InlineKeyboardMarkup([
        row, nav,
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:period:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


def _month_kb(year: int) -> InlineKeyboardMarkup:
    today = date.today()
    buttons = []
    row = []
    for m in range(1, 13):
        disabled = (year, m) > (today.year, today.month)
        label = _MONTH_AR[m] if not disabled else f"· {_MONTH_AR[m]} ·"
        cb = f"{_PFX}:noop" if disabled else f"{_PFX}:mo:pick:{year}:{m}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 رجوع للسنوات", callback_data=f"{_PFX}:period:month")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Custom range calendar (يوم-بيوم، بنفس فكرة معايرة hceval) ────────────────

def _calendar_kb(year: int, month: int, step: str) -> InlineKeyboardMarkup:
    from calendar import monthcalendar

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

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:period:back")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _show_calendar(query, step: str, year: int | None = None, month: int | None = None) -> None:
    today = date.today()
    year = year or today.year
    month = month or today.month
    label = "تاريخ البداية" if step == "start" else "تاريخ النهاية"
    try:
        await query.edit_message_text(
            f"📆 *فترة مخصصة*\n\nاختر {label}:",
            reply_markup=_calendar_kb(year, month, step),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[comprehensive_report] calendar render failed: {exc}")


# ── Generic multi-select filter tier (hospitals / departments / doctors / actions) ─

async def _fetch_tier_options(tier: str, filt: dict) -> list[dict]:
    from services.reports_repository import (
        get_hospitals_in_scope, get_departments_in_scope,
        get_doctors_in_scope, get_actions_in_scope,
    )
    start, end = filt["start"], filt["end"]
    hospitals = None if filt["hospitals_all"] else filt["hospitals"]
    departments = None if filt["departments_all"] else filt["departments"]
    doctors = None if filt["doctors_all"] else filt["doctors"]

    if tier == "hospitals":
        return await get_hospitals_in_scope(start, end)
    if tier == "departments":
        return await get_departments_in_scope(start, end, hospitals=hospitals)
    if tier == "doctors":
        return await get_doctors_in_scope(start, end, hospitals=hospitals, departments=departments)
    if tier == "actions":
        return await get_actions_in_scope(start, end, hospitals=hospitals, departments=departments, doctors=doctors)
    return []


def _tier_kb(tier: str, filt: dict, page: int) -> InlineKeyboardMarkup:
    cb = _TIER_META[tier]["cb"]
    options = filt["_options"]
    selected = set(filt[tier])
    per_page = 8
    total_pages = max(1, (len(options) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = options[page * per_page: (page + 1) * per_page]

    buttons = [[InlineKeyboardButton(
        ("✅ " if filt[f"{tier}_all"] else "☑️ ") + "جميع " + _TIER_META[tier]["title"],
        callback_data=f"{_PFX}:{cb}:all",
    )]]

    for local_idx, opt in enumerate(page_items):
        global_idx = page * per_page + local_idx
        checked = "✅" if opt["name"] in selected else "◻️"
        label = f"{checked} {opt['name']} ({opt['count']})"
        if len(label) > 60:
            label = label[:57] + "…"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{_PFX}:{cb}:toggle:{global_idx}")])

    nav = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{_PFX}:{cb}:page:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data=f"{_PFX}:noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{_PFX}:{cb}:page:{page + 1}"))
    if nav:
        buttons.append(nav)

    n_selected = len(selected)
    continue_label = "➡️ متابعة" if filt[f"{tier}_all"] or n_selected == 0 else f"➡️ متابعة ({n_selected} محدد)"
    buttons.append([InlineKeyboardButton(continue_label, callback_data=f"{_PFX}:{cb}:done")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:{cb}:back")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _show_tier(query, context: ContextTypes.DEFAULT_TYPE, tier: str, page: int = 0) -> None:
    filt = _f(context)
    options = await _fetch_tier_options(tier, filt)

    if not options:
        # ✅ لا يوجد أي خيار له بيانات في هذه الشريحة — نتخطاها تلقائياً
        # (يطابق "لا يعرض أي خيار لا يحتوي على بيانات" — هنا بمستوى الشريحة كاملة)
        filt[f"{tier}_all"] = True
        filt[tier] = []
        await _advance_after_tier(query, context, tier)
        return

    filt["_options"] = options
    filt["_page"] = page

    title = _TIER_META[tier]["title"]
    text = f"📊 *التقرير الشامل*\n\n🔎 اختر {title} (يظهر عدد الحالات بجانب كل خيار):"
    try:
        await query.edit_message_text(
            text, reply_markup=_tier_kb(tier, filt, page), parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[comprehensive_report] tier render failed ({tier}): {exc}")


async def _advance_after_tier(query, context: ContextTypes.DEFAULT_TYPE, tier: str) -> None:
    idx = _TIER_ORDER[tier]
    if idx + 1 < len(_TIERS):
        await _show_tier(query, context, _TIERS[idx + 1])
    else:
        await _show_summary(query, context)


async def _back_before_tier(query, context: ContextTypes.DEFAULT_TYPE, tier: str) -> None:
    idx = _TIER_ORDER[tier]
    if idx == 0:
        await _show_period_menu_edit(query, context)
    else:
        await _show_tier(query, context, _TIERS[idx - 1])


async def _show_period_menu_edit(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[_KEY] = _new_filters()
    try:
        await query.edit_message_text(
            "📊 *التقرير الشامل*\n\n📅 اختر الفترة الزمنية:",
            reply_markup=_period_kb(), parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass


# ── Summary + generate ─────────────────────────────────────────────────────────

def _summary_text(filt: dict) -> str:
    def line(title: str, tier: str) -> str:
        if filt[f"{tier}_all"] or not filt[tier]:
            return f"• {title}: جميع {_TIER_META[tier]['title']}"
        return f"• {title}: " + "، ".join(filt[tier])

    return (
        f"📊 *ملخص التقرير الشامل*\n\n"
        f"📅 الفترة: {filt['period_label']}\n"
        f"{line('المستشفيات', 'hospitals')}\n"
        f"{line('الأقسام', 'departments')}\n"
        f"{line('الأطباء', 'doctors')}\n"
        f"{line('أنواع الإجراءات', 'actions')}\n\n"
        f"اضغط ✅ لإنشاء التقرير."
    )


async def _show_summary(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    filt = _f(context)
    buttons = [
        [InlineKeyboardButton("✅ إنشاء التقرير", callback_data=f"{_PFX}:generate")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:{_TIER_META['actions']['cb']}:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ]
    try:
        await query.edit_message_text(
            _summary_text(filt), reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[comprehensive_report] summary render failed: {exc}")


async def _generate_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    filt = _f(context)

    await query.edit_message_text("⏳ جارٍ إعداد التقرير...", parse_mode=ParseMode.MARKDOWN)

    try:
        from services.reports_repository import get_reports, compute_stats
        from services.comprehensive_report_pdf import build_comprehensive_pdf

        hospitals = None if filt["hospitals_all"] else filt["hospitals"]
        departments = None if filt["departments_all"] else filt["departments"]
        doctors = None if filt["doctors_all"] else filt["doctors"]
        actions = None if filt["actions_all"] else filt["actions"]

        reports = await get_reports(
            filt["start"], filt["end"],
            depts=departments, actions=actions, hospitals=hospitals, doctors=doctors,
        )

        if not reports:
            await query.edit_message_text(
                f"⚠️ لا توجد حالات مطابقة لمعايير البحث المحددة.\n\n{_summary_text(filt)}",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # ✅ compute_stats/build_comprehensive_pdf عمل CPU ثقيل متزامن (matplotlib +
        # reportlab لبناء رسوم بيانية وجداول). استدعاؤه مباشرة داخل هذا الـ async
        # handler يُجمِّد حلقة الأحداث الوحيدة للبوت بالكامل — أي كل المستخدمين —
        # طوال مدة البناء. asyncio.to_thread ينقله لخيط منفصل فلا يعلّق البوت.
        stats = await asyncio.to_thread(compute_stats, reports)
        filters_summary = {
            "hospitals": [] if filt["hospitals_all"] else filt["hospitals"],
            "departments": [] if filt["departments_all"] else filt["departments"],
            "doctors": [] if filt["doctors_all"] else filt["doctors"],
            "actions": [] if filt["actions_all"] else filt["actions"],
            "generated_at": datetime.now(),
        }
        pdf_buf = await asyncio.to_thread(
            build_comprehensive_pdf, reports, stats, filt["period_label"], filters_summary=filters_summary
        )

        filename = f"Comprehensive_{filt['start']}_{filt['end']}.pdf"
        caption = (
            f"📊 *التقرير الشامل*\n"
            f"📅 {filt['period_label']}\n"
            f"📋 {stats['total']} حالة | {stats['unique_patients']} مريض | "
            f"{stats['unique_hospitals']} مستشفى"
        )

        try:
            await query.delete_message()
        except Exception:
            pass

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buf, filename=filename, caption=caption, parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(
            f"[comprehensive_report] PDF sent  period={filt['period_label']}"
            f"  cases={stats['total']}  patients={stats['unique_patients']}"
        )
    except Exception:
        logger.exception("[comprehensive_report] PDF generation failed")
        try:
            await query.edit_message_text("❌ حدث خطأ أثناء إعداد التقرير.", parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
    finally:
        context.user_data.pop(_KEY, None)


# ── Main callback dispatcher ────────────────────────────────────────────────────

@require_admin
async def handle_period(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Main callback dispatcher for the whole cr: namespace."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""
    parts = data[len(_PFX) + 1:].split(":")  # strip "cr:"
    action = parts[0]

    if action == "cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.pop(_KEY, None)
        return ConversationHandler.END

    if action == "noop":
        return CR_PERIOD

    if action == "back":
        from . import admin_reports_menu
        context.user_data.pop(_KEY, None)
        return await admin_reports_menu.start_reports_menu(update, context)

    # ── Period: legacy quick presets (kept for backward compatibility) ────────
    if action in ("today", "week", "month", "3m", "year"):
        start, end, period_label = _resolve_period(action)
        if start:
            filt = _f(context)
            filt["start"], filt["end"], filt["period_label"] = start, end, period_label
            await _show_tier(query, context, _TIERS[0])
        return CR_PERIOD

    # ── Period: new UI ("📅 شهر كامل" / "📆 فترة مخصصة") ───────────────────────
    if action == "period":
        sub = parts[1] if len(parts) > 1 else ""
        if sub == "back":
            await _show_period_menu_edit(query, context)
        elif sub == "month":
            filt = _f(context)
            await query.edit_message_text(
                "📊 *التقرير الشامل*\n\n📅 اختر السنة:",
                reply_markup=_year_kb(filt["_year_center"]), parse_mode=ParseMode.MARKDOWN,
            )
        elif sub == "custom":
            await _show_calendar(query, step="start")
        return CR_PERIOD

    if action == "yr":
        sub = parts[1]
        if sub == "nav":
            year = int(parts[2])
            filt = _f(context)
            filt["_year_center"] = year
            await query.edit_message_text(
                "📊 *التقرير الشامل*\n\n📅 اختر السنة:",
                reply_markup=_year_kb(year), parse_mode=ParseMode.MARKDOWN,
            )
        elif sub == "pick":
            year = int(parts[2])
            await query.edit_message_text(
                f"📊 *التقرير الشامل*\n\n📅 اختر الشهر — {year}:",
                reply_markup=_month_kb(year), parse_mode=ParseMode.MARKDOWN,
            )
        return CR_PERIOD

    if action == "mo" and parts[1] == "pick":
        year, month = int(parts[2]), int(parts[3])
        start = date(year, month, 1)
        end = min(date(year, month, monthrange(year, month)[1]), date.today())
        filt = _f(context)
        filt["start"], filt["end"] = start, end
        filt["period_label"] = f"{_MONTH_AR[month]} {year}"
        await _show_tier(query, context, _TIERS[0])
        return CR_PERIOD

    # ── Custom date-range calendar ──────────────────────────────────────────
    if action == "cal":
        step = parts[1]
        sub = parts[2]
        if sub == "navmonth":
            y_str, m_str = parts[3].split("-")
            await _show_calendar(query, step=step, year=int(y_str), month=int(m_str))
        elif sub == "select":
            selected = date.fromisoformat(parts[3])
            filt = _f(context)
            if step == "start":
                filt["start"] = selected
                await _show_calendar(query, step="end", year=selected.year, month=selected.month)
            else:
                start_d = filt.get("start") or selected
                end_d = selected
                if end_d < start_d:
                    start_d, end_d = end_d, start_d
                end_d = min(end_d, date.today())
                filt["start"], filt["end"] = start_d, end_d
                filt["period_label"] = f"{start_d.strftime('%d/%m/%Y')} إلى {end_d.strftime('%d/%m/%Y')}"
                await _show_tier(query, context, _TIERS[0])
        return CR_PERIOD

    # ── Multi-select filter tiers (hospitals / departments / doctors / actions) ──
    tier_by_cb = {meta["cb"]: name for name, meta in _TIER_META.items()}
    if action in tier_by_cb:
        tier = tier_by_cb[action]
        sub = parts[1] if len(parts) > 1 else ""
        filt = _f(context)

        if sub == "all":
            filt[f"{tier}_all"] = True
            filt[tier] = []
            await _advance_after_tier(query, context, tier)
        elif sub == "toggle":
            idx = int(parts[2])
            options = filt["_options"]
            if 0 <= idx < len(options):
                name = options[idx]["name"]
                current = set(filt[tier])
                if name in current:
                    current.discard(name)
                else:
                    current.add(name)
                filt[tier] = list(current)
                filt[f"{tier}_all"] = False
            await _show_tier(query, context, tier, page=filt.get("_page", 0))
        elif sub == "page":
            page = int(parts[2])
            await _show_tier(query, context, tier, page=page)
        elif sub == "done":
            if not filt[tier]:
                filt[f"{tier}_all"] = True
            await _advance_after_tier(query, context, tier)
        elif sub == "back":
            await _back_before_tier(query, context, tier)
        return CR_PERIOD

    if action == "generate":
        await _generate_report(update, context)
        return ConversationHandler.END

    return CR_PERIOD


# ── Period resolution (legacy presets) ──────────────────────────────────────────

def _resolve_period(code: str) -> tuple[date | None, date | None, str]:
    """Resolve legacy period code to (start, end, label). Kept for backward compat."""
    today = date.today()

    if code == "today":
        return today, today, f"اليوم {today.strftime('%d/%m/%Y')}"

    if code == "week":
        start = today - timedelta(days=today.weekday())
        end = today
        return start, end, f"هذا الأسبوع ({start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')})"

    if code == "month":
        start = today.replace(day=1)
        end = today
        return start, end, f"هذا الشهر {today.strftime('%m/%Y')}"

    if code == "3m":
        start = today - timedelta(days=90)
        end = today
        return start, end, f"آخر 3 أشهر ({start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')})"

    if code == "year":
        start = today.replace(month=1, day=1)
        end = today
        return start, end, f"السنة {today.year}"

    return None, None, ""


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register comprehensive report handler (as fallback, not primary entry)."""
    # NOTE: This handler is delegated to by admin_reports_menu,
    #       NOT registered as a primary ConversationHandler entry point.
    #       Pattern broadened to the whole "cr:" namespace (verified exclusive
    #       to this file — no other module in the project uses this prefix).
    app.add_handler(
        CallbackQueryHandler(handle_period, pattern=rf"^{_PFX}:"),
    )
    logger.info("[comprehensive_report] Callback handlers registered  prefix=cr:")
