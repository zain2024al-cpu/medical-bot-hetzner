# bot/handlers/admin/admin_residency_monitor.py
#
# "🪪 متابعة الإقامات (اطّلاع فقط)" — نافذة قراءة محضة على وحدة الإقامة
# للأدمن: العدّادات، قوائم كل حالة، وتفاصيل كل عائلة — **بلا أي زر يغيّر
# شيئاً**.
#
# ⚠️ لماذا وحدة مستقلة لا إعادة استخدام modules/residency/views.py:
# باني الشاشات هناك يدمج أزرار العمل في نفس لوحة المفاتيح (نقل الحالة،
# رفع الوثائق، تأكيد الإصدار، الطباعة…). أي إعادة استخدام له كانت ستعني
# إمّا تمرير أعلام "أخفِ هذا الزر" عبر كل دالة — فيتلوّث التدفق التشغيلي
# بمنطق عرضٍ لا يخصّه ويصير أي زر جديد خطر تسرّب — أو تصفية الأزرار بعد
# بنائها وهي هشّة تنكسر بصمت مع أول تعديل هناك.
#
# هنا **لا وجود لأي `callback_data` تشغيلي أصلاً**: كل الأزرار المُنتَجة
# في هذا الملف بادئتها `rnv:` وكلها تنقّل لا أكثر. فحتى لو أُضيف غداً زر
# خطير في وحدة الإقامة، لا طريق له إلى هذه الشاشة بنيوياً.
#
# 🔒 الصلاحية: أدمن فقط. الاطّلاع لا يفتح أي صلاحية تنفيذ.

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes

from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

_PFX = "rnv"          # residency-view — منفصل تماماً عن `rn:` التشغيلي
_PER_PAGE = 8


# ── مساعدات عرض ───────────────────────────────────────────────────────────────

def _fmt(value: str) -> str:
    return value if (value or "").strip() else "—"


def _person_block(p, *, is_root: bool, since=None) -> list[str]:
    """أسطر شخص واحد — معلومات فقط."""
    from modules.residency.constants import status_line
    from modules.residency.days import badge as _day_badge

    head = "👤" if is_root else "   👥"
    lines = [f"{head} **{p.name}**"]
    pad = "   " if is_root else "      "
    lines.append(f"{pad}الحالة: {status_line(p.status)}")
    _b = _day_badge(p, since)
    if _b:
        lines.append(f"{pad}⏳ {_b}")
    lines.append(f"{pad}انتهاء الإقامة: {_fmt(p.expiry_date)}")
    lines.append(f"{pad}تاريخ التنبيه: {_fmt(p.reminder_date)}")
    if (getattr(p, "last_issue_date", "") or "").strip():
        lines.append(f"{pad}آخر إصدار: {p.last_issue_date}")
    marks = []
    if (p.residency_file_id or "").strip():
        marks.append("🪪 صورة إقامة")
    if (p.photo_file_id or "").strip():
        marks.append("📷 صورة شخصية")
    if marks:
        lines.append(f"{pad}المرفوع: {' · '.join(marks)}")
    return lines


def _nav(rows: list[list[InlineKeyboardButton]], back_cb: str) -> InlineKeyboardMarkup:
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_cb)])
    return InlineKeyboardMarkup(rows)


# ── الشاشات ───────────────────────────────────────────────────────────────────

def _build_home() -> tuple[str, InlineKeyboardMarkup]:
    from modules.residency.constants import STATUS_ORDER, STATUS_ICONS, STATUS_LABELS
    from modules.residency.repository import get_status_counts

    counts = get_status_counts()
    total = sum(counts.get(s, 0) for s in STATUS_ORDER)

    lines = [
        "🪪 **متابعة الإقامات**",
        "_عرض فقط — لا يمكن تعديل أي شيء من هذه الشاشة._",
        "",
        f"📊 **الإجمالي:** {total}",
    ]
    rows = []
    for s in STATUS_ORDER:
        n = counts.get(s, 0)
        rows.append([InlineKeyboardButton(
            f"{STATUS_ICONS[s]} {STATUS_LABELS[s]} ({n})",
            callback_data=f"{_PFX}:st:{s}:0",
        )])
    rows.append([InlineKeyboardButton("📋 آخر الحركات", callback_data=f"{_PFX}:log")])
    return "\n".join(lines), _nav(rows, "sys_menu:back")


def _build_status(status: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    from modules.residency.constants import status_line
    from modules.residency.repository import get_requests_by_status

    families = get_requests_by_status(status) or []
    total = len(families)
    pages = max(1, (total + _PER_PAGE - 1) // _PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = families[page * _PER_PAGE:(page + 1) * _PER_PAGE]

    lines = [f"{status_line(status)}", ""]
    if not families:
        lines.append("✅ لا توجد حالات هنا.")
    else:
        lines.append(f"📊 **العدد:** {total}   •   📄 **صفحة:** {page + 1} من {pages}")

    # نفس شارة الأيام المستخدَمة في الشاشات التشغيلية — مصدر واحد
    from modules.residency.days import family_badge
    from modules.residency.repository import get_status_since
    _ids = [p.id for f in chunk for p in ([f.root] + list(f.companions))]
    _since = get_status_since(_ids)

    rows = []
    for fam in chunk:
        n = len(fam.companions)
        suffix = f" (+{n} مرافق)" if n else ""
        bdg = family_badge(fam, _since)
        note = f" — {bdg}" if bdg else ""
        rows.append([InlineKeyboardButton(
            f"👤 {fam.root.name}{suffix}{note}",
            callback_data=f"{_PFX}:fam:{fam.root.id}:{status}:{page}",
        )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            "◀️ السابق", callback_data=f"{_PFX}:st:{status}:{page - 1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton(
            "التالي ▶️", callback_data=f"{_PFX}:st:{status}:{page + 1}"))
    if nav:
        rows.append(nav)

    return "\n".join(lines), _nav(rows, f"{_PFX}:home")


def _build_family(root_id: int, status: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    from modules.residency.repository import get_family, get_document_counts

    fam = get_family(root_id)
    if fam is None:
        return "⚠️ لم تُعثَر على هذه الحالة.", _nav([], f"{_PFX}:st:{status}:{page}")

    people = [fam.root] + list(fam.companions)
    from modules.residency.repository import get_status_since
    since_map = get_status_since([p.id for p in people])
    try:
        doc_counts = get_document_counts([p.id for p in people]) or {}
    except Exception:
        logger.debug("[rnv] تعذّر جلب عدد الوثائق", exc_info=True)
        doc_counts = {}

    lines = ["🪪 **تفاصيل الحالة**", ""]
    lines += _person_block(fam.root, is_root=True, since=since_map.get(fam.root.id))
    nd = doc_counts.get(fam.root.id, 0)
    if nd:
        lines.append(f"   الوثائق المرفقة: {nd}")

    if fam.companions:
        lines.append("")
        lines.append(f"👥 **المرافقون ({len(fam.companions)}):**")
        for c in fam.companions:
            lines.append("")
            lines += _person_block(c, is_root=False, since=since_map.get(c.id))
            nd = doc_counts.get(c.id, 0)
            if nd:
                lines.append(f"      الوثائق المرفقة: {nd}")

    lines.append("")
    lines.append("_للتنفيذ استخدم زر «🪪 الإقامة» في القائمة الرئيسية._")
    return "\n".join(lines), _nav([], f"{_PFX}:st:{status}:{page}")

def _build_log(page: int = 0) -> tuple[str, InlineKeyboardMarkup]:
    """آخر الحركات — مجمَّعة بالأيام ومصفَّحة، بنفس شكل سجل بوت الإقامات.

    ⚠️ كانت ٢٠ حركة بتسميات كاملة بلا تجميع ولا تصفّح — جدار نصّ. وُحِّد
    شكلها مع `build_log_view` عمداً: نفس المعلومة بشكلين مختلفين تُربِك.
    """
    from modules.residency.constants import status_chip
    from modules.residency.repository import get_log_page
    from modules.residency.views import _day_label

    per = _PER_PAGE
    try:
        entries, total = get_log_page(offset=page * per, limit=per)
    except Exception:
        logger.warning("[rnv] تعذّر جلب السجل", exc_info=True)
        entries, total = [], 0

    pages = max(1, (total + per - 1) // per)
    if not entries and total:                 # صفحة خارج النطاق ⇒ آخر صفحة
        page = pages - 1
        entries, total = get_log_page(offset=page * per, limit=per)

    lines = ["📋 **آخر الحركات**", ""]
    rows: list[list[InlineKeyboardButton]] = []

    if not entries:
        lines.append("لا توجد حركات مسجَّلة بعد.")
    else:
        lines.append(f"{total} حركة — صفحة {page + 1} من {pages}")
        current_day = None
        for e in entries:
            day, _, clock = (e.created_at or "").partition(" ")
            if day != current_day:
                current_day = day
                lines.append("")
                lines.append(f"📅 *{_day_label(day)}*")
            old = status_chip(e.old_status) if e.old_status else "—"
            new = status_chip(e.new_status)
            who = "" if e.performed_by else "  ⚙️"
            lines.append(f"🕐 {clock} · {e.person_name[:22]}")
            lines.append(f"      {old} ⟵ {new}{who}")

        if any(not e.performed_by for e in entries):
            lines.append("")
            lines.append("⚙️ = نقلٌ تلقائي بالمهمة اليومية")

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{_PFX}:log:{page - 1}"))
        if page + 1 < pages:
            nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{_PFX}:log:{page + 1}"))
        if nav:
            rows.append(nav)

    return "\n".join(lines), _nav(rows, f"{_PFX}:home")


# ── المعالِج ──────────────────────────────────────────────────────────────────

@require_admin
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    action = (query.data or "")[len(_PFX) + 1:]
    try:
        if action == "home" or not action:
            text, kb = _build_home()
        elif action.startswith("st:"):
            _, status, page = action.split(":", 2)
            text, kb = _build_status(status, int(page))
        elif action.startswith("fam:"):
            _, root_id, status, page = action.split(":", 3)
            text, kb = _build_family(int(root_id), status, int(page))
        elif action == "log" or action.startswith("log:"):
            _pg = action.split(":", 1)[1] if ":" in action else "0"
            text, kb = _build_log(int(_pg) if _pg.isdigit() else 0)
        else:
            return
    except Exception:
        logger.exception(f"[rnv] فشل بناء الشاشة action={action!r}")
        text, kb = "⚠️ تعذّر عرض البيانات.", _nav([], "sys_menu:back")

    try:
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        logger.debug("[rnv] تعذّر تعديل الرسالة", exc_info=True)


def register(app) -> None:
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=rf"^{_PFX}:"))
    logger.info(f"[rnv] residency monitor (read-only) registered  pattern='^{_PFX}:'")
