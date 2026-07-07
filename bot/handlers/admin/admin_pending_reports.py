# bot/handlers/admin/admin_pending_reports.py
#
# 📋 شاشة "التقارير المعلقة" — متابعة يدوية من داخل "🛠️ إدارة النظام"
# بديل/مكمّل لتنبيه الساعة 9 مساءً التلقائي: يعرض كل الحالات المعلقة
# فعلياً (يعتمد على نفس services/pending_reports_service.py المستخدَمة
# في التنبيه اليومي — بلا أي تكرار للمنطق) مع عدد أيام الانتظار، بترقيم
# صفحات إن كانت القائمة طويلة.
#
# ✅ بدون ConversationHandler (نفس نمط admin_system_menu.py وغيره هذه
# الجلسة) — CallbackQueryHandler مستقل دائم التفعيل.

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

_PFX = "pndrep"
_PER_PAGE = 8


def _list_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{_PFX}:page:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data=f"{_PFX}:noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{_PFX}:page:{page + 1}"))

    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("🔄 تحديث", callback_data=f"{_PFX}:page:{page}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="sys_menu:back")])
    return InlineKeyboardMarkup(rows)


def _urgency_emoji(days_waiting: int) -> str:
    if days_waiting >= 3:
        return "🔴"
    if days_waiting >= 1:
        return "🟡"
    return "🟢"


def _render_item_text(p: dict) -> str:
    reason = (p.get("no_report_reason") or "—").strip()
    return (
        f"{_urgency_emoji(p['days_waiting'])} {p['patient_name']}\n"
        f"   🏢 القسم: {p['department']}\n"
        f"   👤 المترجم: {p['translator_name']}\n"
        f"   📝 السبب: {reason}\n"
        f"   ⏳ منتظر منذ: {p['days_waiting']} يوم"
    )


async def _render_list(query, page: int) -> None:
    from services.pending_reports_service import get_pending_reports

    items = get_pending_reports()
    items.sort(key=lambda x: x["days_waiting"], reverse=True)
    total = len(items)

    if not items:
        try:
            await query.edit_message_text(
                "📋 التقارير الطبية المعلقة\n\n"
                "✅ لا توجد تقارير معلقة حالياً — جميع التقارير جاهزة!",
                reply_markup=_list_kb(0, 1),
            )
        except Exception as exc:
            await _handle_render_error(query, exc, page=0)
        return

    per_page = _PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = items[page * per_page: (page + 1) * per_page]

    lines = [f"📋 التقارير الطبية المعلقة", f"العدد الإجمالي: {total}", ""]
    lines.extend(_render_item_text(p) + "\n" for p in page_items)

    try:
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=_list_kb(page, total_pages),
        )
    except Exception as exc:
        await _handle_render_error(query, exc, page=page)


async def _handle_render_error(query, exc: Exception, page: int) -> None:
    """تيليجرام يرفض edit_message_text إن كان المحتوى الجديد مطابقاً
    تماماً للحالي (مثال: ضغط 'تحديث' على قائمة لم تتغيّر) — هذا سلوك
    طبيعي متوقَّع وليس خطأ، فنعرض تنبيهاً خفيفاً بدل تسجيله كـERROR."""
    if "message is not modified" in str(exc).lower():
        try:
            await query.answer("✅ القائمة محدَّثة بالفعل.")
        except Exception:
            pass
        return
    logger.error(f"[pndrep] Failed to render list (page={page}): {exc}")


async def handle_pending_reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "noop":
        return

    if action == "page":
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            page = 0
        await _render_list(query, page)
        return


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """تسجيل شاشة التقارير المعلقة (بدون ConversationHandler)."""
    app.add_handler(
        CallbackQueryHandler(handle_pending_reports_callback, pattern=rf"^{_PFX}:")
    )
    logger.info("[pndrep] Pending reports screen handlers registered")
