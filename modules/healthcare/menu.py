# modules/healthcare/menu.py
# Healthcare reply-keyboard button handler.
# Fires when an authorized user presses "▶️ ابدأ الآن" on the reply keyboard.

import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

HEALTHCARE_BUTTON = "▶️ ابدأ الآن"
CHENNAI_HEALTHCARE_BUTTON = "🏙️ الرعاية الصحية - تشناي"


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the healthcare module menu directly (RBAC-gated).

    This handler fires for the reply-keyboard button "▶️ ابدأ الآن".
    It shows the healthcare menu immediately without going through the full
    /start flow — pressing this button is "go back to the healthcare menu",
    not "re-run onboarding".

    If a non-healthcare user somehow triggers this button (stale keyboard),
    they are silently re-routed to their role-appropriate /start screen.

    ✅ يُصفّر context.user_data["hc_city"] دائماً (ما لم يُمرَّر عبر
    "_force_hc_city" من مدخل تشناي) — بنفس آلية report_city/_force_report_city
    في نظام التقارير. هذا يمنع تسرّب قيد "chennai" من جلسة سابقة إن دخل
    المستخدم القائمة الاعتيادية بعد قسم تشناي.
    """
    tg_id = update.effective_user.id
    context.user_data["hc_city"] = context.user_data.pop("_force_hc_city", None)

    from core.access.access_service import user_has_module
    if not user_has_module(tg_id, "healthcare"):
        logger.warning(
            f"[healthcare] ▶️ ابدأ الآن pressed by non-healthcare user={tg_id} "
            f"— re-routing to user_start"
        )
        # Late import to avoid circular dependency (modules/ → bot/).
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
        return

    logger.info(f"[healthcare] ▶️ ابدأ الآن pressed  user={tg_id}")
    from modules.healthcare.views import build_healthcare_menu
    text, kb = build_healthcare_menu(city=context.user_data.get("hc_city"))
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def _show_menu_chennai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the Chennai healthcare menu — same 5 sub-sections (المجارحة/المتابعة
    الطبية/صرف الأدوية/المستلزمات/إجراءات أخرى) reusing the exact same "hc:"
    callback routing, but scoped to Chennai patients and Chennai group
    publishing via context.user_data["hc_city"]="chennai".

    RBAC-gated on "chennai_healthcare" — independent of "healthcare"; a
    user may hold either grant, or both.
    """
    tg_id = update.effective_user.id

    from core.access.access_service import user_has_module
    if not user_has_module(tg_id, "chennai_healthcare"):
        logger.warning(
            f"[healthcare] {CHENNAI_HEALTHCARE_BUTTON!r} pressed by non-chennai_healthcare "
            f"user={tg_id} — re-routing to user_start"
        )
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
        return

    context.user_data["hc_city"] = "chennai"
    logger.info(f"[healthcare] {CHENNAI_HEALTHCARE_BUTTON!r} pressed  user={tg_id}")
    from modules.healthcare.views import build_healthcare_menu
    text, kb = build_healthcare_menu(city="chennai")
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")


def register_menu_handler(app) -> None:
    """Register the reply-keyboard button handlers in group 0."""
    app.add_handler(
        MessageHandler(
            filters.Text([HEALTHCARE_BUTTON]),
            _show_menu,
        ),
        group=0,
    )
    app.add_handler(
        MessageHandler(
            filters.Text([CHENNAI_HEALTHCARE_BUTTON]),
            _show_menu_chennai,
        ),
        group=0,
    )
    logger.info(
        f"[healthcare] menu handlers registered"
        f"  buttons={HEALTHCARE_BUTTON!r}, {CHENNAI_HEALTHCARE_BUTTON!r}"
    )
