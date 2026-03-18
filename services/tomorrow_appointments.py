#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅 نظام تنبيهات مواعيد الغد للأدمن
Tomorrow's Appointments Admin Notification System
"""

import logging
from datetime import datetime, timedelta
from db.session import SessionLocal
from db.models import FollowupTracking
from sqlalchemy import func

logger = logging.getLogger(__name__)

async def notify_admins_of_tomorrow_appointments(bot, admin_ids):
    """
    إرسال تنبيه لجميع الأدمن بمواعيد يوم غد
    """
    try:
        # تحديد تاريخ الغد
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        db = SessionLocal()
        try:
            # جلب المواعيد المجدولة لتاريخ الغد
            # نستخدم func.date() للتحقق من التاريخ فقط بغض النظر عن الوقت
            appointments = db.query(FollowupTracking).filter(
                func.date(FollowupTracking.followup_date) == tomorrow
            ).all()
            
            if not appointments:
                # إذا لم توجد مواعيد، يمكن إرسال رسالة تفيد بذلك أو عدم الإرسال
                # حسب رغبة المستخدم "ياخذ المواعيد من تاريخ العوده من خلال التقارير"
                # إذا لم توجد مواعيد، لن نرسل شيئاً لتجنب الإزعاج، أو نرسل رسالة بسيطة
                logger.info(f"No appointments found for {tomorrow_str}")
                return

            # تنسيق الرسالة
            message = f"📅 **تنبيه بمواعيد يوم غد**\n"
            message += f"🗓️ التاريخ: `{tomorrow_str}`\n"
            message += f"📊 إجمالي المواعيد: `{len(appointments)}`\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for i, appt in enumerate(appointments, 1):
                p_name = appt.patient_name or "غير محدد"
                dept = appt.department or "غير محدد"
                # محاولة الحصول على الوقت إذا كان موجوداً
                time_str = appt.followup_date.strftime("%H:%M") if appt.followup_date and appt.followup_date.hour != 0 else "غير محدد"
                translator = appt.translator_name or "غير محدد"
                
                message += f"{i}. 👤 **المريض:** {p_name}\n"
                message += f"   🏢 **القسم:** {dept}\n"
                message += f"   ⏰ **الوقت:** {time_str}\n"
                message += f"   👨‍🏫 **المترجم:** {translator}\n"
                message += "━━━━━━━━━━━━━━━━━━━━━━━\n"

            message += "\n✅ تم استخراج هذه المواعيد من تقارير المتابعة."

            # إرسال لكل الأدمن
            sent_count = 0
            for admin_id in admin_ids:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending tomorrow appointments to admin {admin_id}: {e}")
            
            logger.info(f"Sent tomorrow appointments notification to {sent_count} admins.")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in notify_admins_of_tomorrow_appointments: {e}")
