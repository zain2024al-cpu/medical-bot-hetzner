#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔔 تنبيهات المترجمين
Translator Reminders System
"""

import logging
from datetime import datetime, time, timedelta
from typing import List
from db.session import SessionLocal
from db.models import Translator, Report, DailyReportTracking

logger = logging.getLogger(__name__)

# إعدادات التنبيهات
REMINDER_TIME_1 = time(14, 0)  # 2:00 PM
REMINDER_TIME_2 = time(16, 0)  # 4:00 PM
REMINDER_TIME_3 = time(18, 0)  # 6:00 PM
REPORT_DEADLINE = time(20, 0)  # 8:00 PM

async def check_and_send_reminders(bot):
    """
    فحص المترجمين وإرسال تنبيهات لمن لم ينزل تقاريره
    
    Args:
        bot: Telegram bot instance
    """
    try:
        current_time = datetime.now().time()
        today = datetime.now().date()
        
        db = SessionLocal()
        try:
            # جلب جميع المترجمين النشطين
            translators = db.query(Translator).filter_by(is_active=True).all()
            
            for translator in translators:
                # فحص إذا أنزل تقرير اليوم
                today_reports = db.query(Report).filter(
                    Report.translator_id == translator.id,
                    Report.report_date == today
                ).count()
                
                # فحص سجل التتبع
                tracking = db.query(DailyReportTracking).filter_by(
                    translator_id=translator.id,
                    date=today
                ).first()
                
                # تحديد إذا يحتاج تنبيه
                needs_reminder = False
                reminder_message = ""
                
                if today_reports == 0:
                    # لم ينزل أي تقرير
                    if current_time >= REMINDER_TIME_1 and current_time < REMINDER_TIME_2:
                        # تنبيه أول (2 PM)
                        if not tracking or not tracking.reminder_sent:
                            needs_reminder = True
                            reminder_message = f"""
⏰ تنبيه أول

مرحباً {translator.full_name}،

لم يتم رفع تقارير اليوم بعد ({today.strftime('%Y-%m-%d')})

⏰ الوقت الآن: {current_time.strftime('%H:%M')}
⏳ الموعد النهائي: 8:00 مساءً

✅ يرجى رفع التقارير في أقرب وقت.

📝 للرفع: /admin → 📝 إضافة تقرير
"""
                    
                    elif current_time >= REMINDER_TIME_2 and current_time < REMINDER_TIME_3:
                        # تنبيه ثاني (4 PM)
                        needs_reminder = True
                        reminder_message = f"""
⚠️ تنبيه ثاني

{translator.full_name}،

لا يزال لم يتم رفع تقارير اليوم!

⏰ الوقت: {current_time.strftime('%H:%M')}
⏳ باقي {(datetime.combine(today, REPORT_DEADLINE) - datetime.now()).seconds // 3600} ساعات على الموعد النهائي

⚠️ يرجى الإسراع في رفع التقارير.
"""
                    
                    elif current_time >= REMINDER_TIME_3 and current_time < REPORT_DEADLINE:
                        # تنبيه أخير (6 PM)
                        needs_reminder = True
                        reminder_message = f"""
🔴 تنبيه أخير

{translator.full_name}،

لم يتم رفع تقارير اليوم حتى الآن!

⏰ الوقت: {current_time.strftime('%H:%M')}
🔴 باقي ساعتين فقط على الموعد النهائي!

⚠️ يرجى الرفع فوراً لتجنب التأخير.
"""
                
                # إرسال التنبيه
                if needs_reminder and translator.tg_user_id:
                    try:
                        await bot.send_message(
                            chat_id=translator.tg_user_id,
                            text=reminder_message
                        )
                        
                        # تحديث سجل التتبع
                        if not tracking:
                            tracking = DailyReportTracking(
                                translator_id=translator.id,
                                date=today,
                                reminder_sent=True
                            )
                            db.add(tracking)
                        else:
                            tracking.reminder_sent = True
                        
                        db.commit()
                        logger.info(f"✅ تم إرسال تنبيه لـ {translator.full_name}")
                        
                    except Exception as e:
                        logger.error(f"❌ خطأ في إرسال تنبيه: {e}")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ خطأ في نظام التنبيهات: {e}")


async def send_late_warning_to_admin(bot, admin_ids: List[int]):
    """
    إرسال تنبيه للأدمن بالمترجمين المتأخرين
    
    Args:
        bot: Telegram bot instance
        admin_ids: قائمة IDs الأدمن
    """
    try:
        today = datetime.now().date()
        current_time = datetime.now().time()
        
        # فحص بعد الموعد النهائي فقط
        if current_time < REPORT_DEADLINE:
            return
        
        db = SessionLocal()
        try:
            # جلب المترجمين الذين لم ينزلوا تقارير
            late_translators = []
            
            translators = db.query(Translator).filter_by(is_active=True).all()
            
            for translator in translators:
                today_reports = db.query(Report).filter(
                    Report.translator_id == translator.id,
                    Report.report_date == today
                ).count()
                
                if today_reports == 0:
                    late_translators.append(translator.full_name)
            
            # إرسال تقرير للأدمن
            if late_translators:
                message = f"""
🔴 تقرير المترجمين المتأخرين

📅 التاريخ: {today.strftime('%Y-%m-%d')}
⏰ الوقت: {current_time.strftime('%H:%M')}

⚠️ المترجمون الذين لم ينزلوا تقارير اليوم:

"""
                for i, name in enumerate(late_translators, 1):
                    message += f"{i}. {name}\n"
                
                message += f"\n📊 الإجمالي: {len(late_translators)} مترجم\n"
                message += "\n⚠️ يرجى المتابعة معهم."
                
                for admin_id in admin_ids:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=message
                        )
                    except:
                        pass
                
                logger.info(f"✅ تم إرسال تقرير التأخير للأدمن: {len(late_translators)} متأخر")
        
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ خطأ في تنبيه الأدمن: {e}")


def get_translator_status() -> dict:
    """
    الحصول على حالة جميع المترجمين اليوم
    
    Returns:
        dict: إحصائيات المترجمين
    """
    try:
        today = datetime.now().date()
        db = SessionLocal()
        
        try:
            translators = db.query(Translator).filter_by(is_active=True).all()
            
            stats = {
                'total': len(translators),
                'submitted': 0,
                'pending': 0,
                'late': []
            }
            
            for translator in translators:
                reports_count = db.query(Report).filter(
                    Report.translator_id == translator.id,
                    Report.report_date == today
                ).count()
                
                if reports_count > 0:
                    stats['submitted'] += 1
                else:
                    stats['pending'] += 1
                    stats['late'].append({
                        'name': translator.full_name,
                        'telegram_id': translator.tg_user_id
                    })
            
            return stats
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"خطأ في get_translator_status: {e}")
        return {'total': 0, 'submitted': 0, 'pending': 0, 'late': []}
























