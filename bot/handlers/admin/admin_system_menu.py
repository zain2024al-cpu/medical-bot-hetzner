# bot/handlers/admin/admin_system_menu.py
#
# قائمة "إدارة النظام" - موزّع (dispatcher) يجمع أدوات الإدارة التأسيسية:
# المستشفيات، المرضى، الجداول، الحسابات (مستخدمين/أدمنين/صلاحيات)، المواعيد القادمة.
#
# ✅ ملاحظة معمارية (نفس نمط admin_evaluation_menu.py و admin_delete_reports_menu.py):
# هذا الملف لا يحتوي على أي منطق عمل خاص به ولا يحتاج ConversationHandler.
# كل الأزرار تشير مباشرة إلى نقاط الدخول الحقيقية للأنظمة المسؤولة فعلياً،
# معظمها callback_data موجود ويعمل مسبقاً بلا أي تعديل:
#   - "manage_hospitals"  → admin_hospitals_management.py (CallbackQueryHandler مستقل)
#   - "manage_patients"   → admin_schedule_management.py (CallbackQueryHandler مستقل)
#   - "goto:schedule"     → admin_schedule_management.py (entry_point جديد أُضيف لهذا الغرض)
#   - "goto:appointments" → admin_upcoming_appointments.py (entry_point جديد أُضيف لهذا الغرض)
#   - "aum:home"          → admin_users_management.py (CallbackQueryHandler مستقل، group=1)
#   - "admin:manage_admins" → admin_admins.py (CallbackQueryHandler مستقل ضمن ConversationHandler الخاص به)
#   - "aum:permlist:0"    → admin_users_management.py (قائمة مستخدمين مخصَّصة
#     لإدارة الصلاحيات مباشرة — اختيار اسم يفتح amod:list:<tg_id> مباشرة
#     بدون المرور بشاشة قبول/رفض/تجميد الخاصة بـ"إدارة المستخدمين" العادية)
#   - "pndrep:page:0"     → admin_pending_reports.py (شاشة متابعة يدوية
#     للتقارير الطبية المعلقة — بديل/مكمّل لتنبيه الساعة 9 مساءً التلقائي)
#
# استُخدمت بادئة "sys_menu:" و"goto:" (وليس "admin:") لتفادي تصادم مع
# المعالج العام في admin_start.py (`^admin:(?!evaluation$|manage_admins$)`)
# الذي قد يخطف أي callback_data يبدأ بـ "admin:" غير مستثنى صراحةً.

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

_PFX = "sys_menu"


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """القائمة الرئيسية لإدارة النظام."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏥 إدارة المستشفيات", callback_data="manage_hospitals")],
        [InlineKeyboardButton("📝 إدارة المرضى", callback_data="manage_patients")],
        [InlineKeyboardButton("📅 إدارة الجداول", callback_data="goto:schedule")],
        [InlineKeyboardButton("👥 إدارة الحسابات", callback_data=f"{_PFX}:accounts")],
        [InlineKeyboardButton("📆 المواعيد القادمة", callback_data="goto:appointments")],
        [InlineKeyboardButton("📋 التقارير المعلقة", callback_data="pndrep:page:0")],
        [InlineKeyboardButton("❌ إغلاق", callback_data=f"{_PFX}:close")],
    ])


def _accounts_kb() -> InlineKeyboardMarkup:
    """القائمة الفرعية لإدارة الحسابات (مستخدمين / أدمنين / صلاحيات)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="aum:home")],
        [InlineKeyboardButton("👑 إدارة الأدمنين", callback_data="admin:manage_admins")],
        [InlineKeyboardButton("🔐 إدارة الصلاحيات", callback_data="aum:permlist:0")],
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:back")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_system_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """نقطة الدخول: زر '🛠️ إدارة النظام' في القائمة الرئيسية للأدمن."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    try:
        await update.message.reply_text(
            "🛠️ *إدارة النظام*\n\n"
            "اختر القسم المطلوب:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[sys_menu] Failed to show menu: {exc}")


async def handle_system_menu_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """معالجة أزرار 'إدارة النظام' و'إدارة الحسابات' فقط.

    باقي الأزرار (manage_hospitals / manage_patients / goto:schedule /
    goto:appointments / aum:* / admin:manage_admins) لا تصل إلى هذه
    الدالة إطلاقاً — تُلتقط مباشرة من قِبل معالجاتها الحقيقية المسجَّلة
    بشكل مستقل في ملفاتها الأصلية.
    """
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:close":
        try:
            await query.edit_message_text("✅ تم الإغلاق.")
        except Exception:
            pass
        return

    if data == f"{_PFX}:accounts":
        try:
            await query.edit_message_text(
                "👥 *إدارة الحسابات*\n\nاختر القسم المطلوب:",
                reply_markup=_accounts_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            logger.error(f"[sys_menu] Failed to show accounts submenu: {exc}")
        return

    if data == f"{_PFX}:back":
        try:
            await query.edit_message_text(
                "🛠️ *إدارة النظام*\n\nاختر القسم المطلوب:",
                reply_markup=_menu_kb(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            logger.error(f"[sys_menu] Failed to go back to main menu: {exc}")
        return


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """تسجيل معالجات قائمة إدارة النظام (بدون ConversationHandler)."""
    app.add_handler(
        MessageHandler(filters.Regex(r"^🛠️ إدارة النظام$"), start_system_menu)
    )
    app.add_handler(
        CallbackQueryHandler(handle_system_menu_choice, pattern=rf"^{_PFX}:")
    )
    logger.info("[sys_menu] System management menu handlers registered")
