# services/residency_missing_items_service.py
# التذكير اليومي بالطلبات/المستندات الناقصة لملفات الإقامة (5:00 مساءً).
#
# نفس بنية services/residency_alerts_service.py عمداً — نفس المستلمين
# ونفس منطق "لا رسالة إن لم يوجد شيء" حتى لا يُفرَغ التذكير من قيمته.

import logging

logger = logging.getLogger(__name__)

_MODULE_KEY = "residency"
_MAX_ITEMS = 60   # حدّ أمان لطول رسالة تيليجرام (4096 حرفاً)


def _resolve_recipients() -> tuple[str, list[int]]:
    from config.settings import RESIDENCY_GROUP_ID, ADMIN_IDS
    from core.access.access_service import list_users_with_module

    users: list[int] = []
    for uid in list(list_users_with_module(_MODULE_KEY)) + list(ADMIN_IDS or []):
        if uid and uid not in users:
            users.append(uid)
    return (RESIDENCY_GROUP_ID or ""), users


def _get_pending_items_with_names() -> list[tuple[str, str, int]]:
    """[(اسم المريض, الوصف, أيام منذ التسجيل), …] لكل طلب ناقص لم يُغلَق."""
    from datetime import datetime
    from db.session import get_db
    from db.models import ResidencyMissingItem, ResidencyProfile

    out: list[tuple[str, str, int]] = []
    today = datetime.utcnow()
    with get_db() as db:
        rows = (
            db.query(ResidencyMissingItem)
            .filter(ResidencyMissingItem.status == "pending")
            .order_by(ResidencyMissingItem.created_at.asc())
            .all()
        )
        for r in rows:
            profile = db.query(ResidencyProfile).filter(ResidencyProfile.id == r.profile_id).first()
            name = profile.name if profile else "—"
            days = (today - r.created_at).days if r.created_at else 0
            out.append((name, r.description or "—", days))
    return out


def build_missing_items_message() -> str | None:
    """
    نصّ التذكير، أو None إن لم يوجد طلب ناقص (فلا تُرسَل رسالة يومية فارغة).
    مفصول عن الإرسال عمداً — يجعل المحتوى قابلاً للاختبار بلا بوت.
    """
    items = _get_pending_items_with_names()
    if not items:
        return None

    lines = [
        "📋 **تذكير — طلبات ناقصة بانتظار المتابعة**",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"يوجد {len(items)} طلب لم يُرفَع بعد:",
        "",
    ]
    for name, desc, days in items[:_MAX_ITEMS]:
        age = f"منذ {days} يوم" if days > 0 else "اليوم"
        lines.append(f"• {name} — {desc}  ({age})")
    if len(items) > _MAX_ITEMS:
        lines.append(f"… و{len(items) - _MAX_ITEMS} طلب آخر")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━",
              "افتح ملف المريض من 🪪 الإقامة ← 📁 أرشيف المرضى لرفع المستند."]
    return "\n".join(lines)


async def send_daily_missing_items_reminder(application) -> None:
    """يُستدعى من app.py عبر job_queue.run_daily الساعة 5:00 مساءً."""
    logger.info("📋 Starting daily missing-items reminder…")

    try:
        message = build_missing_items_message()
    except Exception:
        logger.exception("[residency.missing_items] failed to build message — skipping")
        return

    if message is None:
        logger.info("[residency.missing_items] nothing pending — no message sent")
        return

    group_id, users = _resolve_recipients()
    if not group_id and not users:
        logger.warning(
            "[residency.missing_items] no recipients: RESIDENCY_GROUP_ID unset and "
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
            logger.error(f"[residency.missing_items] failed to send to group {group_id}: {exc}")

    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="Markdown")
            sent += 1
        except Exception as exc:
            logger.warning(f"[residency.missing_items] failed to send to user {uid}: {exc}")

    logger.info(
        f"[residency.missing_items] sent to {sent} recipient(s) "
        f"(group={'yes' if group_id else 'no'}, users={len(users)})"
    )
