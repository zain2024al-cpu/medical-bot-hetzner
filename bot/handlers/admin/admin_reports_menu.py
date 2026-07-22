# bot/handlers/admin/admin_reports_menu.py
#
# Entry point for reporting system. Routes to either:
#   📊 Comprehensive Report (all patients in date range)
#   👤 Patient Report (single patient with filters)
#
# Replaces: ReplyKeyboard direct linking to admin_patient_report.py
#
# Dialog flow:
#   "🖨️ طباعة التقارير" button
#       ↓
#   Choose type: [📊 Comprehensive] [👤 Patient]
#       ↓ (branching delegates to appropriate handler)

from __future__ import annotations

import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from bot.shared_auth import is_admin
from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
MENU_CHOOSE_TYPE = 800

_PFX = "report_menu"  # Note: patterns in universal_fallback are "report_menu:"

# ── Keyboard ──────────────────────────────────────────────────────────────────

def _type_kb() -> InlineKeyboardMarkup:
    """Choose report type."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقرير شامل", callback_data=f"{_PFX}:comp")],
        [InlineKeyboardButton("👤 تقرير مريض", callback_data=f"{_PFX}:patient")],
        [InlineKeyboardButton("📎 كل مرفقات مريض", callback_data=f"{_PFX}:attachments")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Entry ─────────────────────────────────────────────────────────────────────

async def start_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry from ReplyKeyboard button '🖨️ طباعة التقارير'."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "🖨️ *نظام التقارير الاحترافي*\n\n"
        "اختر نوع التقرير المطلوب:",
        reply_markup=_type_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return MENU_CHOOSE_TYPE


# ── Callback handler ──────────────────────────────────────────────────────────

@require_admin
async def handle_type_selection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User picked type. Delegate to respective handler."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم إلغاء العملية.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    # ✅ كل تفويض هنا محاط بـ try/except صراحة: بدونها، أي استثناء غير متوقع
    # في المسار المُفوَّض (تعليق شبكة، خطأ قاعدة بيانات، إلخ) كان سيتسرّب
    # قبل الوصول لـ return ConversationHandler.END — فيبقى هذا الـ
    # ConversationHandler عالقاً في حالة MENU_CHOOSE_TYPE لهذا المستخدم إلى
    # الأبد (allow_reentry=False يمنع إعادة تشغيله بالضغط على الزر مجدداً،
    # وزر "🖨️ طباعة التقارير" غير مسجَّل في قائمة أزرار المقاطعة group -2
    # التي تصفّر المحادثات العالقة). أي خطأ الآن يُبلَّغ للمستخدم بدل أن
    # يُعطِّل الزر بصمت حتى إعادة تشغيل البوت.
    if data == f"{_PFX}:comp":
        context.user_data["_report_type"] = "comprehensive"
        try:
            from . import admin_comprehensive_report
            # Show period menu - this handler will take over from here
            await admin_comprehensive_report.show_period_menu(update, context)
        except Exception:
            logger.exception("[reports_menu] فشل عرض قائمة التقرير الشامل")
            try:
                await query.edit_message_text("❌ حدث خطأ. حاول الضغط على '🖨️ طباعة التقارير' مرة أخرى.")
            except Exception:
                pass
        return ConversationHandler.END

    if data == f"{_PFX}:patient":
        context.user_data["_report_type"] = "patient"
        try:
            from . import admin_patient_report_v2
            # ✅ admin_patient_report_v2 يدير حالته بنفسه عبر CallbackQueryHandler
            # مستقلة (context.user_data)، وليس عبر ConversationHandler متداخل —
            # نفس نمط فرعي "comp"/"attachments" أدناه بالضبط. إعادة قيمة الحالة
            # الداخلية (PR_SHOW_SELECTOR=0) هنا كانت الخطأ: هذه القيمة غير
            # مسجَّلة ضمن states الخاصة بـ reports_menu_conv، فيسجّلها PTB
            # كحالة "عالقة" لهذا المستخدم (تحذير PTBUserWarning فقط، لا خطأ) —
            # ونتيجة allow_reentry=False تُقفَل كل التفاعلات اللاحقة مع هذا الزر
            # صامتة تماماً حتى إعادة تشغيل البوت (نفس عرَض "يعمل أول مرة ثم
            # يتوقف" الذي أبلغ عنه المستخدم). يجب إنهاء المحادثة الخارجية دوماً
            # بعد التفويض، تماماً كبقية الفروع.
            await admin_patient_report_v2.show_patient_selector(update, context)
        except Exception:
            logger.exception("[reports_menu] فشل عرض منتقي المريض (تقرير مريض)")
            try:
                await query.edit_message_text("❌ حدث خطأ. حاول الضغط على '🖨️ طباعة التقارير' مرة أخرى.")
            except Exception:
                pass
        return ConversationHandler.END

    if data == f"{_PFX}:attachments":
        # Delegate to attachments-bundle handler — no further states needed,
        # it does everything (patient pick → merge → send) via result_router.
        context.user_data["_report_type"] = "attachments"
        try:
            from . import admin_patient_attachments_bundle
            await admin_patient_attachments_bundle.show_patient_selector(update, context)
        except Exception:
            logger.exception("[reports_menu] فشل عرض منتقي المريض (كل المرفقات)")
            try:
                await query.edit_message_text("❌ حدث خطأ. حاول الضغط على '🖨️ طباعة التقارير' مرة أخرى.")
            except Exception:
                pass
        return ConversationHandler.END

    return MENU_CHOOSE_TYPE


# ── Cancel ────────────────────────────────────────────────────────────────────

@require_admin
async def cancel_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel from any state."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register reports menu handler as entry point."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^🖨️ طباعة التقارير$"),
                start_reports_menu,
            ),
        ],
        states={
            MENU_CHOOSE_TYPE: [
                CallbackQueryHandler(handle_type_selection, pattern=rf"^{_PFX}:"),
            ],
            # Note: PR_SHOW_SELECTOR and other states from delegated handlers
            # are NOT defined here - those handlers manage their own states
        },
        fallbacks=[
            CallbackQueryHandler(cancel_reports_menu, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="reports_menu_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=False,  # Don't re-enter once delegated
    )
    app.add_handler(conv)
    logger.info("[reports_menu] ConversationHandler registered  button=🖨️ طباعة التقارير")
