# services/residency_reminders_service.py
# التذكير اليومي بتقديم طلب الإقامة — لكل ملف اختار مستخدم الإقامة له
# تاريخ تنبيه يدوياً من التقويم، تصل رسالة يومية لمجموعة الإقامة بدءاً
# من ذلك التاريخ، حتى يضغط الأدمن "✅ تم تقديم طلب الإقامة".

import logging

logger = logging.getLogger(__name__)


def build_reminder_message() -> str | None:
    """مفصول عن الإرسال عمداً — يجعل المحتوى قابلاً للاختبار بلا بوت."""
    from modules.residency.repository import get_due_reminders

    due = get_due_reminders()
    if not due:
        return None

    lines = ["🔔 **تذكير: تقديم طلبات الإقامة**", "━━━━━━━━━━━━━━━━━━━━", ""]
    for p in due:
        who = p.name
        if p.companions:
            who += "  (ومرافقوه: " + "، ".join(p.companions) + ")"
        lines.append(f"• {who}  —  تاريخ التنبيه: {p.reminder_date}")

    lines += ["", "━━━━━━━━━━━━━━━━━━━━", "افتح 🪪 الإقامة لمتابعة الملفات."]
    return "\n".join(lines)


async def send_daily_residency_reminders(application) -> None:
    """يُستدعى من app.py عبر job_queue.run_daily. يرسل رسالة واحدة
    مجمَّعة لمجموعة الإقامة فقط (RESIDENCY_GROUP_ID)."""
    logger.info("🔔 Starting daily residency reminders…")

    try:
        message = build_reminder_message()
    except Exception:
        logger.exception("[residency.reminders] failed to build message — skipping")
        return

    if message is None:
        logger.info("[residency.reminders] nothing due — no message sent")
        return

    from config.settings import RESIDENCY_GROUP_ID

    if not RESIDENCY_GROUP_ID:
        logger.warning("[residency.reminders] RESIDENCY_GROUP_ID not set — skipping")
        return

    try:
        await application.bot.send_message(
            chat_id=RESIDENCY_GROUP_ID, text=message, parse_mode="Markdown",
        )
        logger.info(f"[residency.reminders] sent to group {RESIDENCY_GROUP_ID}")
    except Exception as exc:
        logger.error(f"[residency.reminders] failed to send to group {RESIDENCY_GROUP_ID}: {exc}")
