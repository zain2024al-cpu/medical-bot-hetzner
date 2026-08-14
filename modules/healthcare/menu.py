# modules/healthcare/menu.py
# Healthcare reply-keyboard button handler.
#
# ⚠️ "▶️ ابدأ الآن" لم تعد مُسجَّلة هنا — صار معالِجها العام الوحيد في
# bot/handlers/user/user_start.py::register() (إعادة تشغيل كاملة عبر
# user_start، بنفس سلوك "🚀 ابدأ" في بوت المترجمين، وبنفس النص في
# general_services وresidency أيضاً).
#
# ⚠️ خلل حقيقي مكتشَف بعد التوحيد: "▶️ ابدأ الآن" كانت **الزر الوحيد** في
# لوحة مفاتيح مستخدم الرعاية الصحية (`core/modules_bootstrap.py`) — كانت
# تفتح قائمة الرعاية الصحية مباشرة (`_show_menu` المحذوفة)، فحين صار
# سلوكها إعادة تشغيل كاملة فقط (نفس بقية الوحدات)، لم يبقَ **أي زر آخر**
# يفتح قائمة التقارير الفعلية — عكس general_services/residency اللذين
# يملكان زرّاً منفصلاً ("🔧 الخدمات العامة"/"🪪 الإقامة") إلى جانب "▶️ ابدأ
# الآن". أُعيد الآن بزرّ منفصل جديد بنفس نمط زر تشناي أدناه بالضبط.
import logging

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

HEALTHCARE_BUTTON = "🏥 الرعاية الصحية"
CHENNAI_HEALTHCARE_BUTTON = "🏙️ الرعاية الصحية - تشناي"


async def _show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Show the healthcare menu (المجارحة/المتابعة الطبية/صرف الأدوية/
    المستلزمات/إجراءات أخرى) — نفس نمط `_show_menu_chennai` تماماً، بلا
    تحديد مدينة (city=None، السلوك الافتراضي).

    RBAC-gated on "healthcare".
    """
    tg_id = update.effective_user.id

    from core.access.access_service import user_has_module
    if not user_has_module(tg_id, "healthcare"):
        logger.warning(
            f"[healthcare] {HEALTHCARE_BUTTON!r} pressed by non-healthcare "
            f"user={tg_id} — re-routing to user_start"
        )
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
        return

    logger.info(f"[healthcare] {HEALTHCARE_BUTTON!r} pressed  user={tg_id}")
    from modules.healthcare.views import build_healthcare_menu
    text, kb = build_healthcare_menu()
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
