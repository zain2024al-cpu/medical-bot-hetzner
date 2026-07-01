# bot/handlers/admin/admin_delete_reports_menu.py
#
# قائمة حذف التقارير الموحدة
# تتيح حذف:
# - تقارير المترجمين (User Reports)
# - تقارير الرعاية الصحية (Healthcare Reports)
# - تقارير الخدمات العامة (General Services Reports)

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler,
    filters
)

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

# ── States ─────────────────────────────────────────────────────────────────────
(
    SHOW_MENU,
) = range(1)

_PFX = "del_menu"


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """Delete menu options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍⚕️ تقارير المترجمين", callback_data=f"{_PFX}:translators")],
        [InlineKeyboardButton("🏥 تقارير الرعاية الصحية", callback_data=f"{_PFX}:healthcare")],
        [InlineKeyboardButton("🛠️ تقارير الخدمات العامة", callback_data=f"{_PFX}:services")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_delete_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Show delete menu."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()

    try:
        await update.message.reply_text(
            "🗑️ *حذف التقارير*\n\n"
            "اختر نوع التقارير المراد حذفها:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Failed to show menu: {exc}")

    return SHOW_MENU


async def handle_menu_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle delete choice - delegate to appropriate handler."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    # Mark which type of reports to delete
    if data == f"{_PFX}:translators":
        context.user_data["_delete_type"] = "translators"
        type_label = "تقارير المترجمين"
    elif data == f"{_PFX}:healthcare":
        context.user_data["_delete_type"] = "healthcare"
        type_label = "تقارير الرعاية الصحية"
    elif data == f"{_PFX}:services":
        context.user_data["_delete_type"] = "services"
        type_label = "تقارير الخدمات العامة"
    else:
        return SHOW_MENU

    # Show confirmation message and delegate to appropriate handler
    try:
        await query.edit_message_text(
            f"جاري تحميل {type_label}...",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

    # Delegate to the appropriate delete handler
    if context.user_data.get("_delete_type") == "translators":
        try:
            from bot.handlers.admin.admin_delete_reports import _year_keyboard, _show_year_selection

            # Call the year selection directly
            await query.edit_message_text("🗑️ *حذف تقارير المترجمين*\n\nاختر السنة:")
            await _show_year_selection(query.message, context)
        except Exception as exc:
            logger.error(f"[del_menu] Failed to delegate to delete reports: {exc}")
            try:
                await query.edit_message_text("❌ فشل تحميل حذف التقارير.\n\nحاول مرة أخرى.")
            except Exception:
                pass
    elif context.user_data.get("_delete_type") == "healthcare":
        await _delete_healthcare_reports(update, context)
    elif context.user_data.get("_delete_type") == "services":
        await _delete_services_reports(update, context)

    return ConversationHandler.END


async def _delete_healthcare_reports(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete healthcare reports - show year selection."""
    query = update.callback_query
    from datetime import datetime
    from sqlalchemy import extract
    from db.session import SessionLocal
    from db.models import OtherHealthcareRecord

    try:
        # Get years from healthcare records
        with SessionLocal() as s:
            db_years = [
                int(r[0]) for r in
                s.query(extract('year', OtherHealthcareRecord.created_at))
                 .filter(OtherHealthcareRecord.created_at.isnot(None))
                 .group_by(extract('year', OtherHealthcareRecord.created_at))
                 .order_by(extract('year', OtherHealthcareRecord.created_at).desc())
                 .all()
            ]

        if not db_years:
            db_years = [datetime.now().year]

        # Build year buttons
        buttons = []
        row = []
        for year in db_years:
            row.append(InlineKeyboardButton(f"📅 {year}", callback_data=f"del_hc:year:{year}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])

        await query.edit_message_text(
            "🏥 *حذف تقارير الرعاية الصحية*\n\n"
            "اختر السنة:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Healthcare year selection failed: {exc}")
        try:
            await query.edit_message_text("❌ خطأ في تحميل السنوات.")
        except Exception:
            pass


async def _delete_services_reports(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete services reports - show year selection."""
    query = update.callback_query
    from datetime import datetime
    from sqlalchemy import extract
    from db.session import SessionLocal
    from db.models import PublicServiceRecord

    try:
        # Get years from service records
        with SessionLocal() as s:
            db_years = [
                int(r[0]) for r in
                s.query(extract('year', PublicServiceRecord.created_at))
                 .filter(PublicServiceRecord.created_at.isnot(None))
                 .group_by(extract('year', PublicServiceRecord.created_at))
                 .order_by(extract('year', PublicServiceRecord.created_at).desc())
                 .all()
            ]

        if not db_years:
            db_years = [datetime.now().year]

        # Build year buttons
        buttons = []
        row = []
        for year in db_years:
            row.append(InlineKeyboardButton(f"📅 {year}", callback_data=f"del_svc:year:{year}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])

        await query.edit_message_text(
            "🛠️ *حذف تقارير الخدمات العامة*\n\n"
            "اختر السنة:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Services year selection failed: {exc}")
        try:
            await query.edit_message_text("❌ خطأ في تحميل السنوات.")
        except Exception:
            pass


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel handler."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Callback handlers for healthcare and services ────────────────────────────

async def handle_healthcare_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle healthcare deletion callbacks (del_hc:*)"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data.startswith("del_hc:year:"):
        # Year selected - show months
        year = int(data.split(":")[2])
        context.user_data["_hc_year"] = year

        from datetime import datetime

        buttons = []
        months = list(range(1, 13))
        for i in range(0, len(months), 3):
            row = []
            for month in months[i:i+3]:
                month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]
                row.append(InlineKeyboardButton(month_name, callback_data=f"del_hc:month:{year}:{month}"))
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])

        try:
            await query.edit_message_text(
                f"🏥 *اختر الشهر* - {year}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    elif data.startswith("del_hc:month:"):
        # Month selected - confirm deletion
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from datetime import datetime
        from db.session import SessionLocal
        from db.models import OtherHealthcareRecord
        from sqlalchemy import extract

        with SessionLocal() as s:
            count = s.query(OtherHealthcareRecord).filter(
                extract('year', OtherHealthcareRecord.created_at) == year,
                extract('month', OtherHealthcareRecord.created_at) == month,
            ).count()

        month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                     "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]

        buttons = [
            [
                InlineKeyboardButton("✅ نعم، احذف الكل", callback_data=f"del_hc:confirm:{year}:{month}"),
                InlineKeyboardButton("❌ رجوع", callback_data=f"{_PFX}:cancel")
            ]
        ]

        try:
            await query.edit_message_text(
                f"⚠️ *تأكيد حذف تقارير الرعاية الصحية*\n\n"
                f"📅 {month_name} {year}\n"
                f"📊 عدد التقارير: {count}\n\n"
                f"⚠️ هذا الإجراء **لا يمكن التراجع عنه!**",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    elif data.startswith("del_hc:confirm:"):
        # Confirm deletion
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from db.session import SessionLocal
        from db.models import OtherHealthcareRecord
        from sqlalchemy import extract

        try:
            with SessionLocal() as s:
                deleted = s.query(OtherHealthcareRecord).filter(
                    extract('year', OtherHealthcareRecord.created_at) == year,
                    extract('month', OtherHealthcareRecord.created_at) == month,
                ).delete()
                s.commit()

            month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                         "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]

            await query.edit_message_text(
                f"✅ *تم الحذف بنجاح*\n\n"
                f"🏥 تقارير الرعاية الصحية\n"
                f"📅 {month_name} {year}\n"
                f"🗑️ عدد التقارير المحذوفة: {deleted}",
                parse_mode=ParseMode.MARKDOWN,
            )

            logger.info(f"[del_menu] Deleted {deleted} healthcare records for {month}/{year}")
        except Exception as exc:
            logger.error(f"[del_menu] Healthcare deletion failed: {exc}")
            try:
                await query.edit_message_text("❌ فشل الحذف. حاول مرة أخرى.")
            except Exception:
                pass


async def handle_services_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle services deletion callbacks (del_svc:*)"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data.startswith("del_svc:year:"):
        # Year selected - show months
        year = int(data.split(":")[2])
        context.user_data["_svc_year"] = year

        buttons = []
        months = list(range(1, 13))
        for i in range(0, len(months), 3):
            row = []
            for month in months[i:i+3]:
                month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]
                row.append(InlineKeyboardButton(f"{month_name[:3]}", callback_data=f"del_svc:month:{year}:{month}"))
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])

        try:
            await query.edit_message_text(
                f"🛠️ *اختر الشهر* - {year}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    elif data.startswith("del_svc:month:"):
        # Month selected - confirm deletion
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from db.session import SessionLocal
        from db.models import PublicServiceRecord
        from sqlalchemy import extract

        with SessionLocal() as s:
            count = s.query(PublicServiceRecord).filter(
                extract('year', PublicServiceRecord.created_at) == year,
                extract('month', PublicServiceRecord.created_at) == month,
            ).count()

        month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                     "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]

        buttons = [
            [
                InlineKeyboardButton("✅ نعم، احذف الكل", callback_data=f"del_svc:confirm:{year}:{month}"),
                InlineKeyboardButton("❌ رجوع", callback_data=f"{_PFX}:cancel")
            ]
        ]

        try:
            await query.edit_message_text(
                f"⚠️ *تأكيد حذف تقارير الخدمات*\n\n"
                f"📅 {month_name} {year}\n"
                f"📊 عدد التقارير: {count}\n\n"
                f"⚠️ هذا الإجراء **لا يمكن التراجع عنه!**",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    elif data.startswith("del_svc:confirm:"):
        # Confirm deletion
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from db.session import SessionLocal
        from db.models import PublicServiceRecord
        from sqlalchemy import extract

        try:
            with SessionLocal() as s:
                deleted = s.query(PublicServiceRecord).filter(
                    extract('year', PublicServiceRecord.created_at) == year,
                    extract('month', PublicServiceRecord.created_at) == month,
                ).delete()
                s.commit()

            month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                         "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]

            await query.edit_message_text(
                f"✅ *تم الحذف بنجاح*\n\n"
                f"🛠️ تقارير الخدمات العامة\n"
                f"📅 {month_name} {year}\n"
                f"🗑️ عدد التقارير المحذوفة: {deleted}",
                parse_mode=ParseMode.MARKDOWN,
            )

            logger.info(f"[del_menu] Deleted {deleted} service records for {month}/{year}")
        except Exception as exc:
            logger.error(f"[del_menu] Services deletion failed: {exc}")
            try:
                await query.edit_message_text("❌ فشل الحذف. حاول مرة أخرى.")
            except Exception:
                pass


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register delete reports menu handler."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^🗑️ حذف التقارير$"),
                start_delete_reports_menu,
            ),
        ],
        states={
            SHOW_MENU: [
                CallbackQueryHandler(handle_menu_choice, pattern=rf"^{_PFX}:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="delete_reports_menu_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(conv)

    # Register healthcare deletion callbacks
    app.add_handler(CallbackQueryHandler(handle_healthcare_callback, pattern=r"^del_hc:"))

    # Register services deletion callbacks
    app.add_handler(CallbackQueryHandler(handle_services_callback, pattern=r"^del_svc:"))

    logger.info("[del_menu] ConversationHandler registered for delete menu")
