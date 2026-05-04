"""
bot/handlers/admin/admin_users_management.py
👥 إدارة المستخدمين — نسخة جديدة بسيطة وثابتة

- بدون ConversationHandler (لتجنب تعليق الحالات)
- تعمل من زر لوحة الأدمن أو من /users
- تعتمد على InlineKeyboard + CallbackQuery فقط
"""

from __future__ import annotations

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from sqlalchemy import func

from bot.shared_auth import is_admin
from db.models import Translator
from db.session import SessionLocal

logger = logging.getLogger(__name__)

CB = "aum"  # admin users management callbacks


def _get_anchor(update: Update):
    return update.message or (update.callback_query.message if update.callback_query else None)


def _home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏳ المعلقين", callback_data=f"{CB}:list:pending:0")],
            [InlineKeyboardButton("✅ المعتمدين", callback_data=f"{CB}:list:approved:0")],
            [InlineKeyboardButton("🔒 المجمدين", callback_data=f"{CB}:list:suspended:0")],
            [InlineKeyboardButton("📋 الجميع", callback_data=f"{CB}:list:all:0")],
            [InlineKeyboardButton("❌ إغلاق", callback_data=f"{CB}:close")],
        ]
    )


def _list_kb(kind: str, page: int, total_pages: int, users: list[Translator]) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    for u in users:
        icon = "🔒" if getattr(u, "is_suspended", False) else ("✅" if getattr(u, "is_approved", False) else "⏳")
        name = (u.full_name or f"User {u.id}").strip()
        kb.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"{CB}:user:{u.id}")])

    nav: list[InlineKeyboardButton] = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{CB}:list:{kind}:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{CB}:list:{kind}:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{CB}:home")])
    return InlineKeyboardMarkup(kb)


def _user_actions_kb(user_id: int, approved: bool, suspended: bool) -> InlineKeyboardMarkup:
    row1: list[InlineKeyboardButton] = []
    if not approved:
        row1.append(InlineKeyboardButton("✅ موافقة", callback_data=f"{CB}:act:approve:{user_id}"))
    row1.append(InlineKeyboardButton("❌ رفض", callback_data=f"{CB}:act:reject:{user_id}"))

    row2: list[InlineKeyboardButton] = []
    if not suspended:
        row2.append(InlineKeyboardButton("🔒 تجميد", callback_data=f"{CB}:act:suspend:{user_id}"))
    else:
        row2.append(InlineKeyboardButton("🔓 فك التجميد", callback_data=f"{CB}:act:unsuspend:{user_id}"))

    return InlineKeyboardMarkup(
        [
            row1,
            row2,
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"{CB}:home")],
        ]
    )


async def start_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_admin(user.id):
        a = _get_anchor(update)
        if a:
            await a.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return

    a = _get_anchor(update)
    if not a:
        return

    await a.reply_text(
        "👥 **إدارة المستخدمين**\n\nاختر نوع العرض:",
        reply_markup=_home_kb(),
        parse_mode="Markdown",
    )


async def _render_list(query, kind: str, page: int):
    per_page = 10
    with SessionLocal() as s:
        base = s.query(Translator)

        if kind == "pending":
            base = base.filter(Translator.is_approved.is_(False))
        elif kind == "approved":
            base = base.filter(Translator.is_approved.is_(True))
        elif kind == "suspended":
            base = base.filter(getattr(Translator, "is_suspended").is_(True))
        else:
            kind = "all"

        total = int(base.with_entities(func.count(Translator.id)).scalar() or 0)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(0, min(int(page), total_pages - 1))
        users = (
            base.order_by(Translator.created_at.desc())
            .offset(page * per_page)
            .limit(per_page)
            .all()
        )

    await query.edit_message_text(
        f"👥 **قائمة المستخدمين**\n\nالنوع: `{kind}`\nالعدد: {total}\n\nاختر مستخدمًا:",
        reply_markup=_list_kb(kind, page, total_pages, users),
        parse_mode="Markdown",
    )


async def _render_user(query, user_id: int):
    with SessionLocal() as s:
        u = s.query(Translator).filter(Translator.id == int(user_id)).first()
        if not u:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_home_kb())
            return

        name = (u.full_name or "").strip() or f"User {u.id}"
        tg = u.tg_user_id
        phone = (getattr(u, "phone_number", None) or "").strip() or "غير محدد"
        approved = bool(getattr(u, "is_approved", False))
        suspended = bool(getattr(u, "is_suspended", False))

    await query.edit_message_text(
        "👤 **تفاصيل المستخدم**\n\n"
        f"- **الاسم**: {name}\n"
        f"- **Telegram ID**: `{tg}`\n"
        f"- **الهاتف**: {phone}\n"
        f"- **موافقة**: {'✅' if approved else '⏳'}\n"
        f"- **تجميد**: {'🔒' if suspended else '🔓'}\n",
        reply_markup=_user_actions_kb(int(user_id), approved, suspended),
        parse_mode="Markdown",
    )


async def _apply_action(query, context: ContextTypes.DEFAULT_TYPE, action: str, user_id: int):
    with SessionLocal() as s:
        u = s.query(Translator).filter(Translator.id == int(user_id)).first()
        if not u:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_home_kb())
            return

        tg = u.tg_user_id
        name = (u.full_name or "").strip() or f"User {u.id}"

        if action == "approve":
            u.is_approved = True
            u.is_suspended = False
            u.updated_at = datetime.utcnow()
            s.commit()
            try:
                await context.bot.send_message(chat_id=tg, text="✅ تم تفعيل حسابك. اضغط /start للبدء.")
            except Exception:
                pass
            await query.edit_message_text(f"✅ تم اعتماد المستخدم: {name}", reply_markup=_home_kb())
            return

        if action == "reject":
            s.delete(u)
            s.commit()
            try:
                await context.bot.send_message(chat_id=tg, text="❌ تم رفض طلبك. تواصل مع الإدارة.")
            except Exception:
                pass
            await query.edit_message_text(f"🚫 تم رفض المستخدم: {name}", reply_markup=_home_kb())
            return

        if action == "suspend":
            u.is_suspended = True
            u.suspended_at = datetime.utcnow()
            u.suspension_reason = "إيقاف بواسطة الأدمن"
            s.commit()
            try:
                await context.bot.send_message(chat_id=tg, text="🔒 تم إيقاف حسابك مؤقتًا. تواصل مع الإدارة.")
            except Exception:
                pass
            await query.edit_message_text(f"🔒 تم تجميد المستخدم: {name}", reply_markup=_home_kb())
            return

        if action == "unsuspend":
            u.is_suspended = False
            u.suspended_at = None
            u.suspension_reason = None
            s.commit()
            try:
                await context.bot.send_message(chat_id=tg, text="🔓 تم إعادة تفعيل حسابك. اضغط /start للمتابعة.")
            except Exception:
                pass
            await query.edit_message_text(f"🔓 تم فك تجميد المستخدم: {name}", reply_markup=_home_kb())
            return

    await query.answer("⚠️ إجراء غير معروف", show_alert=True)


async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    data = query.data or ""
    if not data.startswith(f"{CB}:"):
        return

    parts = data.split(":")
    # aum:home | aum:close | aum:list:kind:page | aum:user:id | aum:act:action:id
    if len(parts) >= 2 and parts[1] == "home":
        await query.edit_message_text("👥 **إدارة المستخدمين**\n\nاختر نوع العرض:", reply_markup=_home_kb(), parse_mode="Markdown")
        return
    if len(parts) >= 2 and parts[1] == "close":
        try:
            await query.message.delete()
        except Exception:
            await query.edit_message_text("✅ تم الإغلاق.")
        return
    if len(parts) >= 4 and parts[1] == "list":
        kind = parts[2]
        page = int(parts[3] or 0)
        await _render_list(query, kind, page)
        return
    if len(parts) >= 3 and parts[1] == "user":
        await _render_user(query, int(parts[2]))
        return
    if len(parts) >= 4 and parts[1] == "act":
        action = parts[2]
        uid = int(parts[3])
        await _apply_action(query, context, action, uid)
        return


def register(app):
    # فتح من زر لوحة الأدمن (ReplyKeyboard)
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^(?:👥\ufe0f?\\s*)?إدارة\\s*المستخدمين\\s*$"),
            start_user_management,
        )
    )
    # فتح من أمر بديل
    app.add_handler(CommandHandler("users", start_user_management))
    # callbacks الخاصة بالشاشة الجديدة فقط
    app.add_handler(CallbackQueryHandler(handle_callbacks, pattern=r"^aum:"))


