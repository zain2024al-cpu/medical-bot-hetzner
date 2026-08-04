# services/residency_alerts_service.py
# التنبيه اليومي لانتهاء الإقامات والجوازات.
#
# البيانات تنساب هكذا:
#   الواصلون (إدخال) → res_profiles/res_companions (إنشاء تلقائي عند النشر)
#   → هذا التنبيه (فلترة يومية حسب العتبات)
#
# العتبتان معرَّفتان في modules/residency/constants.py:
#   EXPIRING_SOON_DAYS          = 30   (الإقامة: شهر)
#   PASSPORT_EXPIRING_SOON_DAYS = 180  (الجواز: 6 أشهر)

import logging

logger = logging.getLogger(__name__)

_MODULE_KEY = "residency"
_MAX_PER_SECTION = 40   # حد أمان لطول رسالة تيليجرام (4096 حرفاً)


def _resolve_recipients() -> tuple[str, list[int]]:
    """
    (معرّف المجموعة, قائمة المستخدمين) — المجموعة + كل من لديه وحدة الإقامة
    + الأدمن، بلا تكرار.
    """
    from config.settings import RESIDENCY_GROUP_ID, ADMIN_IDS
    from core.access.access_service import list_users_with_module

    users: list[int] = []
    for uid in list(list_users_with_module(_MODULE_KEY)) + list(ADMIN_IDS or []):
        if uid and uid not in users:
            users.append(uid)
    return (RESIDENCY_GROUP_ID or ""), users


def _fmt_line(e, *, is_passport: bool) -> str:
    """سطر واحد لشخص — يوضّح المرافق بربطه بمريضه."""
    from modules.residency.views import format_expiry_date

    who = f"{e.companion_name} (مرافق {e.name})" if e.is_companion else e.name
    d = e.days_remaining
    if d < 0:
        when = f"⛔ منتهية منذ {abs(d)} يوم"
    elif d == 0:
        when = "⛔ تنتهي اليوم"
    else:
        when = f"{d} يوم"
    return f"• {who} — {format_expiry_date(e.expiry_date)}  ({when})"


def build_alert_message() -> str | None:
    """
    يبني نص التنبيه، أو None إن لم يكن هناك ما يُنبَّه عنه (فلا تُرسَل رسالة
    يومية فارغة تُفقد التنبيه قيمته).

    مفصول عن الإرسال عمداً — يجعل المحتوى قابلاً للاختبار بلا بوت.
    """
    from modules.residency.followup.repository import (
        get_expiring_soon, get_passport_expiring_soon,
    )
    from modules.residency.constants import (
        EXPIRING_SOON_DAYS, PASSPORT_EXPIRING_SOON_DAYS,
    )

    residency = get_expiring_soon()
    passports = get_passport_expiring_soon()

    if not residency and not passports:
        return None

    lines = ["🔔 **تنبيه الإقامات والجوازات**", "━━━━━━━━━━━━━━━━━━━━"]

    if residency:
        lines += ["", f"🪪 **إقامات تنتهي خلال {EXPIRING_SOON_DAYS} يوم** ({len(residency)})", ""]
        lines += [_fmt_line(e, is_passport=False) for e in residency[:_MAX_PER_SECTION]]
        if len(residency) > _MAX_PER_SECTION:
            lines.append(f"… و{len(residency) - _MAX_PER_SECTION} حالة أخرى")

    if passports:
        months = PASSPORT_EXPIRING_SOON_DAYS // 30
        lines += ["", "─────────────────────", "",
                  f"🛂 **جوازات تنتهي خلال {months} أشهر** ({len(passports)})", ""]
        lines += [_fmt_line(e, is_passport=True) for e in passports[:_MAX_PER_SECTION]]
        if len(passports) > _MAX_PER_SECTION:
            lines.append(f"… و{len(passports) - _MAX_PER_SECTION} حالة أخرى")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━",
              "افتح 🪪 الإقامة ← ⏰ المتابعة للتفاصيل والإجراءات."]
    return "\n".join(lines)


async def send_daily_residency_alerts(application) -> None:
    """
    يُرسل تنبيهاً يومياً واحداً مجمَّعاً لمجموعة الإقامات ولكل من يملك
    الوحدة. يُستدعى من app.py عبر job_queue.run_daily.

    فشل الإرسال لمستلم واحد لا يمنع البقية (كل إرسال في try مستقل).
    """
    logger.info("🔔 Starting daily residency/passport expiry alerts…")

    try:
        message = build_alert_message()
    except Exception:
        logger.exception("[residency.alerts] failed to build message — skipping")
        return

    if message is None:
        logger.info("[residency.alerts] nothing expiring — no message sent")
        return

    group_id, users = _resolve_recipients()
    if not group_id and not users:
        logger.warning(
            "[residency.alerts] no recipients: RESIDENCY_GROUP_ID unset and "
            "no user holds the 'residency' module"
        )
        return

    bot = application.bot
    sent = 0

    if group_id:
        try:
            await bot.send_message(chat_id=group_id, text=message, parse_mode="Markdown")
            sent += 1
        except Exception as exc:
            logger.error(f"[residency.alerts] failed to send to group {group_id}: {exc}")

    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="Markdown")
            sent += 1
        except Exception as exc:
            # مستخدم لم يبدأ محادثة مع البوت / حظره — متوقّع، لا يوقف البقية
            logger.warning(f"[residency.alerts] failed to send to user {uid}: {exc}")

    logger.info(
        f"[residency.alerts] sent to {sent} recipient(s) "
        f"(group={'yes' if group_id else 'no'}, users={len(users)})"
    )
