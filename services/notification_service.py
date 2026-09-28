# ================================================
# services/notification_service.py
# 🔹 Daily Notifications & Reminders Service
# ================================================

import logging
from datetime import datetime, timedelta, date
from sqlalchemy import or_
from telegram import Bot
from telegram.constants import ParseMode
from db.session import SessionLocal
from db.models import Report
from config.settings import BOT_TOKEN, ADMIN_IDS, TIMEZONE
import pytz

logger = logging.getLogger(__name__)

# ⚠️ حدّ رسالة تليجرام ٤٠٩٦ حرفاً. كانت كل مواعيد الغد تُجمَع في **رسالة
# واحدة** بلا حدّ — رُصِد فعلياً في تقرير أخطاء البوت: ٤ مواعيد أو أكثر
# في يوم واحد كافية لتجاوز الحدّ، فترفض تليجرام الرسالة **كاملةً** لكل
# الأدمن الأربعة معاً (نفس الخطأ ٤ مرات في نفس الثانية) — أي أن مواعيد
# الغد لا تصل أحداً في اليوم المزدحم بالذات، وهو أكثر يوم يحتاجها الأدمن.
# نفس نمط تقسيم عودات تشناي (services/chennai_daily_returns.py) —
# تُقسَّم على عدة رسائل عند الحاجة، بحدّ الموعد لا بمنتصف موعد.
_MAX_CHARS = 3500

_DIV = "━━━━━━━━━━━━━━━━━━━━"
_THIN = "──────────────────"

# ⚠️ محارف Markdown في قيمة من قاعدة البيانات (اسم مريض/مستشفى/مترجم)
# تُفشِل **الرسالة كلها** بـ`can't parse entities` — نفس الدرس المُثبَت
# مراراً في هذا المشروع (تنبيهات تشناي، نشر الإقامات، نشر الوصول).
_MD_UNSAFE = "*_`[]"


def _safe(text) -> str:
    t = str(text or "").strip()
    for ch in _MD_UNSAFE:
        t = t.replace(ch, "")
    return t


def _report_reason(report, tomorrow) -> str:
    """أيّ تاريخ من الأربعة طابق الغد — يقرّر تسمية النوع المعروضة."""
    if report.app_reschedule_return_date and report.app_reschedule_return_date.date() == tomorrow:
        return "تأجيل موعد (عودة)"
    if report.radiation_therapy_return_date and report.radiation_therapy_return_date.date() == tomorrow:
        return "جلسة إشعاعي (عودة)"
    if report.radiology_delivery_date and report.radiology_delivery_date.date() == tomorrow:
        return "استلام أشعة"
    if report.medical_action:
        return report.medical_action
    return "متابعة"


def _report_block(index: int, report, tomorrow) -> str:
    """كتلة نصّ موعد واحد — وحدة التقسيم، لا تُقسَّم أبداً منتصفها."""
    lines = [
        f"{index}. 👤 **المريض:** {_safe(report.patient_name) or 'غير معروف'}",
        f"   🏥 **المستشفى:** {_safe(report.hospital_name) or 'غير معروف'}",
        f"   🔄 **النوع:** {_safe(_report_reason(report, tomorrow))}",
        f"   👨‍💼 **المترجم:** {_safe(report.translator_name) or 'غير معروف'}",
    ]
    if report.followup_time:
        lines.append(f"   🕒 **الوقت:** {_safe(report.followup_time)}")
    if report.room_number:
        lines.append(f"   🏢 **الغرفة:** {_safe(report.room_number)}")
    lines.append(_THIN)
    return "\n".join(lines)


def build_reminder_messages(reports: list, tomorrow, tomorrow_str: str) -> list[str]:
    """رسالة أو أكثر لمواعيد الغد — دالّة نقية بلا Telegram/DB، تُختبَر
    مباشرة بلا محاكاة. تُقسَّم على حدّ الموعد لا حرفياً في المنتصف."""
    header = [_DIV, f"📅 **مواعيد يوم غد ({tomorrow_str})**"]

    if not reports:
        return ["\n".join(header + ["", "لا توجد مواعيد أو عودات مسجلة ليوم غد في التقارير.",
                                    _THIN])]

    blocks = [_report_block(i, r, tomorrow) for i, r in enumerate(reports, 1)]

    # تُجمَّع الكتل في رسائل لا تتجاوز الحدّ — كتلة كاملة أو لا شيء منها.
    chunks: list[list[str]] = []
    cur: list[str] = []
    cur_len = 0
    for block in blocks:
        if cur and cur_len + len(block) > _MAX_CHARS:
            chunks.append(cur)
            cur, cur_len = [], 0
        cur.append(block)
        cur_len += len(block) + 2
    if cur:
        chunks.append(cur)

    out = []
    for ci, chunk in enumerate(chunks):
        lines = list(header)
        if len(chunks) > 1:
            lines.append(f"الجزء {ci + 1} من {len(chunks)}")
        lines.append(f"تم العثور على `{len(reports)}` موعد/عودة:")
        lines.append("")
        lines.extend(chunk)
        out.append("\n".join(lines))
    return out


async def _send_reminder_text(bot, chat_id, text: str) -> bool:
    """Markdown ثم نصّ عادي عند الرفض — احتياط إضافي بجانب `_safe()`،
    لا بديل عنها: قيمة جديدة يوماً قد تحمل محرفاً لم يُتوقَّع."""
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        return True
    except Exception as first:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            logger.warning(f"⚠️ Markdown رُفض لتذكير الأدمن {chat_id} ({first}) — وصل نصّاً عادياً")
            return True
        except Exception as second:
            logger.error(f"❌ Failed to send reminder to admin {chat_id}: {first} / {second}")
            return False


async def send_daily_appointments_reminder(application):
    """
    Sends a daily reminder to all admins about tomorrow's appointments.
    Fetches data from 'followup_date', 'app_reschedule_return_date',
    'radiation_therapy_return_date', and 'radiology_delivery_date'.
    """
    logger.info("⏰ Starting daily appointments reminder task...")

    if not ADMIN_IDS:
        logger.warning("⚠️ No ADMIN_IDS configured. Skipping notification.")
        return

    # Calculate tomorrow's date in the configured timezone
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    tomorrow = (now + timedelta(days=1)).date()
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    # Tomorrow's start and end for query
    start_dt = datetime.combine(tomorrow, datetime.min.time())
    end_dt = datetime.combine(tomorrow, datetime.max.time())

    try:
        with SessionLocal() as session:
            # Query for reports with any return/followup date matching tomorrow
            reports = session.query(Report).filter(
                or_(
                    Report.followup_date.between(start_dt, end_dt),
                    Report.app_reschedule_return_date.between(start_dt, end_dt),
                    Report.radiation_therapy_return_date.between(start_dt, end_dt),
                    Report.radiology_delivery_date.between(start_dt, end_dt)
                )
            ).all()

            if not reports:
                logger.info(f"📅 No appointments found for tomorrow ({tomorrow_str}).")
            messages = build_reminder_messages(reports, tomorrow, tomorrow_str)

            bot = application.bot
            success_count = 0
            for admin_id in ADMIN_IDS:
                ok = True
                for msg in messages:
                    ok = await _send_reminder_text(bot, admin_id, msg) and ok
                if ok:
                    success_count += 1

            logger.info(f"✅ Daily reminder sent to {success_count}/{len(ADMIN_IDS)} admins "
                        f"({len(messages)} part(s), {len(reports)} appointment(s)).")

    except Exception as e:
        logger.error(f"❌ Error in send_daily_appointments_reminder: {e}", exc_info=True)
