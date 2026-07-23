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
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters,
)
from sqlalchemy import func

from bot.shared_auth import is_admin
from core.access.access_service import resolve_tg_user_id
from db.models import Translator, TranslatorDirectory
from db.session import SessionLocal

logger = logging.getLogger(__name__)

CB = "aum"  # admin users management callbacks

AWAIT_TRANSLATOR_NAME = "AUM_AWAIT_TRANSLATOR_NAME"


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


def _resolve_translator_directory_name(tg_user_id: int | None) -> str | None:
    """
    الاسم النظيف الموحَّد من TranslatorDirectory (مطابقة بآيدي تيليجرام) إن
    وُجد — يُعرَض بدل الاسم الفوضوي المأخوذ من بروفايل تيليجرام (حرف واحد/
    نقاط/اسم مستعار) الذي يظهر أحياناً في full_name عند التسجيل.
    """
    if not tg_user_id:
        return None
    try:
        with SessionLocal() as s:
            row = s.query(TranslatorDirectory).filter_by(translator_id=tg_user_id).first()
            if row and (row.name or "").strip():
                return row.name.strip()
    except Exception as e:
        logger.error("aum: failed to resolve translator directory name for tg_user_id=%s: %s", tg_user_id, e)
    return None


def _display_name(user: Translator) -> str:
    """الاسم المعروض: النظيف من دليل المترجمين إن وُجد تطابق، وإلا الاسم الخام من تيليجرام."""
    raw = (user.full_name or "").strip() or f"User {user.id}"
    clean = _resolve_translator_directory_name(getattr(user, "tg_user_id", None))
    return clean or raw


def _list_kb(kind: str, page: int, total_pages: int, users: list[Translator]) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    for u in users:
        icon = "🔒" if getattr(u, "is_suspended", False) else ("✅" if getattr(u, "is_approved", False) else "⏳")
        name = _display_name(u)
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


def _perm_list_kb(page: int, total_pages: int, users: list[Translator]) -> InlineKeyboardMarkup:
    """
    ✅ قائمة مستخدمين مخصَّصة لمسار "🔐 إدارة الصلاحيات" (من قائمة
    إدارة النظام → إدارة الحسابات). الضغط على أي اسم يفتح شاشة صلاحياته
    (amod:list:<tg_id>) مباشرة — بدون المرور بشاشة "تفاصيل المستخدم"
    وأزرار الموافقة/الرفض/التجميد الخاصة بمسار "إدارة المستخدمين"
    العادي، لأن هذه الأزرار لا معنى لها هنا.
    """
    kb: list[list[InlineKeyboardButton]] = []
    for u in users:
        name = _display_name(u)
        access_tg_user_id = _resolve_access_tg_user_id(u)
        if access_tg_user_id:
            kb.append([InlineKeyboardButton(f"🔐 {name}", callback_data=f"amod:list:{access_tg_user_id}")])
        else:
            # لا يوجد معرف تليجرام حقيقي لهذا المستخدم — لا يمكن إدارة صلاحياته
            kb.append([InlineKeyboardButton(f"⚠️ {name} (لا يوجد معرف)", callback_data="noop")])

    nav: list[InlineKeyboardButton] = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{CB}:permlist:{page-1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{CB}:permlist:{page+1}"))
    if nav:
        kb.append(nav)

    # الرجوع هنا يعيد لقائمة "إدارة الحسابات" (الأب الفعلي لهذا المسار)
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="sys_menu:accounts")])
    return InlineKeyboardMarkup(kb)


def _resolve_access_tg_user_id(user: Translator) -> int | None:
    """
    Return the Telegram user id required by RBAC.

    Identity resolution lives in the RBAC layer so legacy user rows and
    TranslatorDirectory rows follow one contract.
    """
    return resolve_tg_user_id(user)


def _user_actions_kb(
    user_id: int,
    approved: bool,
    suspended: bool,
    access_tg_user_id: int | None = None,
) -> InlineKeyboardMarkup:
    row1: list[InlineKeyboardButton] = []
    if not approved:
        row1.append(InlineKeyboardButton("✅ موافقة", callback_data=f"{CB}:act:approve:{user_id}"))
    row1.append(InlineKeyboardButton("❌ رفض", callback_data=f"{CB}:act:reject:{user_id}"))

    row2: list[InlineKeyboardButton] = []
    if not suspended:
        row2.append(InlineKeyboardButton("🔒 تجميد", callback_data=f"{CB}:act:suspend:{user_id}"))
    else:
        row2.append(InlineKeyboardButton("🔓 فك التجميد", callback_data=f"{CB}:act:unsuspend:{user_id}"))

    rows = [row1, row2]

    # Module access management requires a real Telegram user id.
    if access_tg_user_id:
        rows.append([
            InlineKeyboardButton("🔑 إدارة الوصول", callback_data=f"amod:list:{access_tg_user_id}")
        ])

    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{CB}:home")])
    return InlineKeyboardMarkup(rows)


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


async def _render_perm_list(query, page: int):
    """
    ✅ قائمة المستخدمين المعتمدين لمسار "🔐 إدارة الصلاحيات" — اختيار
    اسم هنا يفتح شاشة صلاحياته مباشرة (بدون شاشة تفاصيل المستخدم).
    """
    per_page = 10
    with SessionLocal() as s:
        base = s.query(Translator).filter(Translator.is_approved.is_(True))

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
        f"🔐 **إدارة الصلاحيات**\n\nالعدد: {total}\n\nاختر مستخدمًا لعرض/تعديل صلاحياته:",
        reply_markup=_perm_list_kb(page, total_pages, users),
        parse_mode="Markdown",
    )


async def _render_user(query, user_id: int):
    with SessionLocal() as s:
        u = s.query(Translator).filter(Translator.id == int(user_id)).first()
        if not u:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_home_kb())
            return

        raw_name = (u.full_name or "").strip() or f"User {u.id}"
        tg = u.tg_user_id
        clean_name = _resolve_translator_directory_name(tg)
        access_tg_user_id = _resolve_access_tg_user_id(u)
        phone = (getattr(u, "phone_number", None) or "").strip() or "غير محدد"
        approved = bool(getattr(u, "is_approved", False))
        suspended = bool(getattr(u, "is_suspended", False))

    # Escape user-supplied strings so stray _ * ` chars don't break Markdown v1
    def _esc(t: str) -> str:
        for ch in ("_", "*", "`", "["):
            t = t.replace(ch, f"\\{ch}")
        return t

    name_line = f"• *الاسم:* {_esc(clean_name or raw_name)}\n"
    if clean_name and clean_name != raw_name:
        name_line += f"• *الاسم المسجَّل في تيليجرام:* {_esc(raw_name)}\n"

    await query.edit_message_text(
        "👤 *تفاصيل المستخدم*\n\n"
        f"{name_line}"
        f"• *Telegram ID:* `{tg}`\n"
        f"• *الهاتف:* {_esc(phone)}\n"
        f"• *موافقة:* {'✅' if approved else '⏳'}\n"
        f"• *تجميد:* {'🔒' if suspended else '🔓'}\n",
        reply_markup=_user_actions_kb(
            int(user_id),
            approved,
            suspended,
            access_tg_user_id=access_tg_user_id,
        ),
        parse_mode="Markdown",
    )


async def _apply_action(query, context: ContextTypes.DEFAULT_TYPE, action: str, user_id: int):
    with SessionLocal() as s:
        u = s.query(Translator).filter(Translator.id == int(user_id)).first()
        if not u:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_home_kb())
            return

        tg = u.tg_user_id
        name = _display_name(u)

        # ملاحظة: "approve" لا يُعالَج هنا — له مسار محادثة مستقل
        # (handle_approve_entry) يوافق ثم يطلب اسم المترجم؛ مُسجَّل بنمط
        # أضيق (aum:act:approve:\d+) قبل هذا الموزّع العام فيلتقطه أولاً.

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


async def handle_approve_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نقطة دخول '✅ موافقة': يعتمد المستخدم فوراً، ثم يطلب من الأدمن اسم هذا
    الشخص ليُحفظ مباشرة في دليل المترجمين (TranslatorDirectory) بنفس آيدي
    تيليجرام الحقيقي حقّه — فيظهر تلقائياً في زر المترجمين عند إنشاء تقرير،
    ويتوحّد اسمه في هذه الشاشة والتقييم وإدارة الوصول، بلا أي خطوة يدوية
    منفصلة لاحقاً.
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    parts = (query.data or "").split(":")
    if len(parts) < 4 or not parts[3].isdigit():
        return ConversationHandler.END
    user_id = int(parts[3])

    with SessionLocal() as s:
        u = s.query(Translator).filter(Translator.id == user_id).first()
        if not u:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_home_kb())
            return ConversationHandler.END

        tg = u.tg_user_id
        name = _display_name(u)

        u.is_approved = True
        u.is_suspended = False
        u.updated_at = datetime.utcnow()
        s.commit()

    try:
        await context.bot.send_message(chat_id=tg, text="✅ تم تفعيل حسابك. اضغط /start للبدء.")
    except Exception:
        pass

    if not tg:
        # لا يوجد آيدي تيليجرام حقيقي — لا يمكن ربطه بدليل المترجمين
        await query.edit_message_text(f"✅ تم اعتماد المستخدم: {name}", reply_markup=_home_kb())
        return ConversationHandler.END

    context.user_data['aum_pending_translator_tg_id'] = tg

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ تخطي", callback_data="aum:skip_translator_link")],
    ])
    await query.edit_message_text(
        f"✅ تم اعتماد المستخدم: {name}\n\n"
        "🔤 أدخل الآن الاسم الذي سيظهر له في زر المترجمين عند إنشاء تقرير:\n"
        "(أو اضغط 'تخطي' لو هذا المستخدم ليس مترجماً)",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return AWAIT_TRANSLATOR_NAME


async def handle_translator_name_for_approved_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المترجم بعد الموافقة على مستخدم."""
    text = (update.message.text or "").strip()

    tg = context.user_data.get('aum_pending_translator_tg_id')
    if not tg:
        await update.message.reply_text("❌ خطأ: انتهت صلاحية هذا الطلب.")
        return ConversationHandler.END

    if not text or len(text) < 2:
        await update.message.reply_text("⚠️ الاسم قصير جداً. أدخل اسماً صحيحاً، أو اضغط 'تخطي':")
        return AWAIT_TRANSLATOR_NAME

    from bot.handlers.admin.admin_translators_management import (
        _db_add_translator_ex, get_translator_names_from_file, save_translator_names_to_file,
    )

    status = _db_add_translator_ex(text, telegram_id=tg)
    if status is None:
        await update.message.reply_text("❌ حدث خطأ في الحفظ في قاعدة البيانات. حاول مرة أخرى:")
        return AWAIT_TRANSLATOR_NAME

    if status in ("inserted", "backfilled"):
        names = get_translator_names_from_file()
        if text not in names:
            names.append(text)
            save_translator_names_to_file(names)

    context.user_data.pop('aum_pending_translator_tg_id', None)

    if status == "conflict_skipped":
        await update.message.reply_text(
            f"⚠️ هذا الآيدي مرتبط مسبقاً باسم آخر في دليل المترجمين — لم يُضَف \"{text}\" لتفادي التكرار.\n"
            "يمكنك تعديل الاسم لاحقاً من دليل المترجمين إن احتجت."
        )
    else:
        await update.message.reply_text(f"✅ تم حفظ الاسم: {text}\n👥 سيظهر عند إنشاء تقرير جديد.")

    return ConversationHandler.END


async def handle_skip_translator_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي ربط المستخدم المعتمد بدليل المترجمين."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop('aum_pending_translator_tg_id', None)
    await query.edit_message_text("✅ تم تخطي إضافة المترجم.", reply_markup=_home_kb())
    return ConversationHandler.END


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
    if len(parts) >= 3 and parts[1] == "permlist":
        page = int(parts[2] or 0)
        await _render_perm_list(query, page)
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
            filters.Regex("^👥 إدارة المستخدمين$"),
            start_user_management,
        )
    )
    # فتح من أمر بديل
    app.add_handler(CommandHandler("users", start_user_management))

    # ✅ مسار الموافقة → طلب اسم المترجم — يجب تسجيله قبل الموزّع العام
    # (نمط أضيق aum:act:approve:\d+ يلتقط ضغطة "✅ موافقة" أولاً ضمن نفس
    # المجموعة؛ أي aum: أخرى تمر للموزّع العام كالمعتاد).
    approve_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_approve_entry, pattern=r"^aum:act:approve:\d+$"),
        ],
        states={
            AWAIT_TRANSLATOR_NAME: [
                CallbackQueryHandler(handle_skip_translator_link, pattern="^aum:skip_translator_link$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_name_for_approved_user),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_skip_translator_link, pattern="^aum:skip_translator_link$"),
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
        name="aum_approve_conv",
    )
    app.add_handler(approve_conv, group=1)

    # callbacks الخاصة بالشاشة الجديدة فقط
    app.add_handler(CallbackQueryHandler(handle_callbacks, pattern=r"^aum:"), group=1)


