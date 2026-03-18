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
                # Send a message saying no appointments to reassure admins
                message = f"📅 **مواعيد يوم غد ({tomorrow_str})**\n\n"
                message += "لا توجد مواعيد أو عودات مسجلة ليوم غد في التقارير.\n"
                message += "──────────────────"
                
                bot = application.bot
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"❌ Failed to send 'No appointments' to admin {admin_id}: {e}")
                return

            # Group appointments by patient or type if needed, or just list them
            message = f"📅 **مواعيد يوم غد ({tomorrow_str})**\n\n"
            message += f"تم العثور على `{len(reports)}` موعد/عودة:\n\n"
            
            for i, report in enumerate(reports, 1):
                patient_name = report.patient_name or "غير معروف"
                translator = report.translator_name or "غير معروف"
                hospital = report.hospital_name or "غير معروف"
                
                # Determine which date matched
                reason = "متابعة"
                if report.app_reschedule_return_date and report.app_reschedule_return_date.date() == tomorrow:
                    reason = "تأجيل موعد (عودة)"
                elif report.radiation_therapy_return_date and report.radiation_therapy_return_date.date() == tomorrow:
                    reason = "جلسة إشعاعي (عودة)"
                elif report.radiology_delivery_date and report.radiology_delivery_date.date() == tomorrow:
                    reason = "استلام أشعة"
                elif report.medical_action:
                    reason = report.medical_action
                
                message += f"{i}. 👤 **المريض:** {patient_name}\n"
                message += f"   🏥 **المستشفى:** {hospital}\n"
                message += f"   🔄 **النوع:** {reason}\n"
                message += f"   👨‍💼 **المترجم:** {translator}\n"
                
                if report.followup_time:
                    message += f"   🕒 **الوقت:** {report.followup_time}\n"
                
                if report.room_number:
                    message += f"   🏢 **الغرفة:** {report.room_number}\n"
                
                message += "──────────────────\n"

            # Send to all admins
            bot = application.bot
            success_count = 0
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to send reminder to admin {admin_id}: {e}")
            
            logger.info(f"✅ Daily reminder sent successfully to {success_count} admins.")

            logger.info(f"✅ Daily reminder sent to {success_count}/{len(ADMIN_IDS)} admins.")

    except Exception as e:
        logger.error(f"❌ Error in send_daily_appointments_reminder: {e}", exc_info=True)
