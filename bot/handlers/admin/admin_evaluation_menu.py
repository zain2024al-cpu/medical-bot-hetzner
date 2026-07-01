# bot/handlers/admin/admin_evaluation_menu.py
#
# قائمة التقييم - توحيد خيارات التقييم المختلفة
# يفتح قائمة بخيارين:
# 1. تقييم المترجمين
# 2. تقرير تقييم الرعاية الصحية
#
# ✅ ملاحظة معمارية:
# هذه القائمة عبارة عن "موزّع" (dispatcher) بسيط فقط — لا تحتوي على أي
# منطق عمل خاص بها ولا تحتاج لتتبع حالة محادثة (ConversationHandler).
# الأزرار تشير مباشرة إلى نقاط الدخول الحقيقية للأنظمة المسؤولة فعلياً:
#   - "admin:evaluation" → نقطة دخول translator_evaluation_conv (admin_evaluation.py)
#   - "hceval:start"     → نقطة دخول تقييم الرعاية الصحية (modules/healthcare/evaluation/flow.py)
# بهذا الشكل يحافظ كل نظام على تتبعه الداخلي الصحيح دون أي "تفويض" يدوي
# قد يستدعي دوالاً غير موجودة أو يكسر تتبع الحالة.
#
# تم تعمّد عدم استخدام ConversationHandler هنا: لو استُخدم، كان سيبقى
# "عالقاً" في حالة القائمة (MENU) إلى الأبد بعد الضغط على أي من الزرين،
# لأن callback_data الخاص بهما لا يطابق نمط "eval_menu:" الذي تتوقعه
# محادثة القائمة، فلا تصل أبداً لإرجاع ConversationHandler.END.

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

_PFX = "eval_menu"


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """Evaluation menu options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقييم المترجمين", callback_data="admin:evaluation")],
        [InlineKeyboardButton("📊 تقرير تقييم الرعاية الصحية", callback_data="hceval:start")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_evaluation_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show evaluation menu (entry point — plain MessageHandler, no conversation state)."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    try:
        await update.message.reply_text(
            "📊 *قائمة التقييم*\n\n"
            "اختر نوع التقييم المطلوب:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[eval_menu] Failed to show menu: {exc}")


async def handle_menu_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the cancel button only.

    الأزرار الأخرى ("admin:evaluation" و "hceval:start") لا تصل إلى هذه
    الدالة أبداً لأن نمط التسجيل أدناه محدد بـ "^eval_menu:cancel$" فقط —
    تُترك لتيليجرام لتمريرها مباشرة لمعالجاتها الحقيقية المسجّلة بشكل
    مستقل في أماكن أخرى.
    """
    query = update.callback_query
    if not query:
        return
    try:
        await query.answer()
    except Exception:
        pass
    try:
        await query.edit_message_text("✅ تم الإلغاء.")
    except Exception:
        pass


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register evaluation menu handlers (plain handlers, no ConversationHandler)."""
    app.add_handler(
        MessageHandler(filters.Regex(r"^📊 التقييم$"), start_evaluation_menu)
    )
    app.add_handler(
        CallbackQueryHandler(handle_menu_cancel, pattern=rf"^{_PFX}:cancel$")
    )
    logger.info("[eval_menu] Evaluation menu handlers registered")
