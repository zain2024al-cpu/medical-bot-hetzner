# bot/handlers/admin/admin_missing_attachments.py
#
# 📎 شاشة "تقارير ناقصة المرفقات" — متابعة يدوية من داخل "🛠️ إدارة النظام".
# تعرض التقارير التي عليها has_paper_report=1 (المترجم أكّد وجود تقرير طبي
# مرفوع وقت الإنشاء) لكن لا يوجد لها أي سجل فعلي في medical_attachment_files
# — تكشف فشلاً صامتاً كان يحدث سابقاً عند إرسال المرفق للمجموعة (بطاقة
# التقرير تنجح، لكن PDF الصور/الملف يفشل داخلياً بلا أي أثر ظاهر للمترجم).
# اعتباراً من هذا الإصلاح، المترجم يتلقّى تنبيهاً فورياً عند حدوث هذا — هذه
# الشاشة أداة متابعة إضافية للأدمن، ولتغطية الحالات التاريخية السابقة للإصلاح.
#
# ✅ بدون ConversationHandler (نفس نمط admin_pending_reports.py) —
# CallbackQueryHandler مستقل دائم التفعيل.

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

_PFX = "msngatt"
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


def _render_item_text(r: dict) -> str:
    action = (r.get("medical_action") or "—").strip()
    date_str = r["report_date"].strftime("%d/%m/%Y") if r.get("report_date") else "—"
    return (
        f"👤 {r['patient_name']}\n"
        f"   🩺 نوع الفحص: {action}\n"
        f"   🏢 القسم: {r['department']}\n"
        f"   👤 المترجم: {r['translator_name']}\n"
        f"   📅 تاريخ التقرير: {date_str}\n"
        f"   🆔 رقم التقرير: #{r['report_id']}"
    )


async def _render_list(query, page: int) -> None:
    from services.medical_attachment_files_service import get_reports_missing_attachments

    items = get_reports_missing_attachments()
    total = len(items)

    if not items:
        try:
            await query.edit_message_text(
                "📎 تقارير ناقصة المرفقات\n\n"
                "✅ لا توجد تقارير ناقصة حالياً — كل تقرير عليه \"يوجد تقرير طبي\" له مرفق فعلي مسجَّل.",
                reply_markup=_list_kb(0, 1),
            )
        except Exception as exc:
            await _handle_render_error(query, exc, page=0)
        return

    per_page = _PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = items[page * per_page: (page + 1) * per_page]

    lines = [
        "📎 تقارير ناقصة المرفقات",
        f"العدد الإجمالي: {total}",
        "ℹ️ هذه تقارير عليها \"✅ يوجد تقرير طبي\" لكن بلا أي ملف فعلي مسجَّل — "
        "اطلب من المترجم رفعه عبر \"📎 المرفقات الطبية\".",
        "",
    ]
    lines.extend(_render_item_text(r) + "\n" for r in page_items)

    try:
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=_list_kb(page, total_pages),
        )
    except Exception as exc:
        await _handle_render_error(query, exc, page=page)


async def _handle_render_error(query, exc: Exception, page: int) -> None:
    if "message is not modified" in str(exc).lower():
        try:
            await query.answer("✅ القائمة محدَّثة بالفعل.")
        except Exception:
            pass
        return
    logger.error(f"[msngatt] Failed to render list (page={page}): {exc}")


async def handle_missing_attachments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    """تسجيل شاشة التقارير الناقصة المرفقات (بدون ConversationHandler)."""
    app.add_handler(
        CallbackQueryHandler(handle_missing_attachments_callback, pattern=rf"^{_PFX}:")
    )
    logger.info("[msngatt] Missing attachments screen handlers registered")
