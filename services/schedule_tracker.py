# ================================================
# services/schedule_tracker.py
# 🔹 نظام تتبع التقارير التلقائي للمترجمين
# ================================================

from datetime import datetime, date, time
from db.session import SessionLocal
from db.models import (
    DailyReportTracking, TranslatorNotification, 
    Translator, Report
)
from telegram import Bot
from config.settings import BOT_TOKEN
import asyncio

class ScheduleTracker:
    """نظام تتبع التقارير اليومية للمترجمين"""
    
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
    
    async def update_daily_reports_count(self):
        """تحديث عدد التقارير الفعلية للمترجمين"""
        today = date.today()
        
        with SessionLocal() as s:
            # جلب جميع سجلات التتبع لليوم
            tracking_records = s.query(DailyReportTracking).filter_by(date=today).all()
            
            for record in tracking_records:
                # البحث عن المترجم
                translator = s.query(Translator).filter_by(full_name=record.translator_name).first()
                
                if translator:
                    # عد التقارير التي رفعها المترجم اليوم
                    today_reports = s.query(Report).filter(
                        Report.translator_id == translator.id,
                        Report.report_date >= datetime.combine(today, time.min),
                        Report.report_date <= datetime.combine(today, time.max)
                    ).count()
                    
                    # تحديث العدد الفعلي
                    record.actual_reports = today_reports
                    
                    # تحديث حالة الإنجاز
                    if today_reports >= record.expected_reports:
                        record.is_completed = True
                    else:
                        record.is_completed = False
                    
                    record.updated_at = datetime.now()
            
            s.commit()
    
    async def check_and_send_reminders(self):
        """فحص وإرسال تذكيرات للمترجمين المتأخرين"""
        today = date.today()
        current_time = datetime.now().time()
        
        # إرسال التذكير في الساعة 2:00 مساءً
        if current_time.hour == 14 and current_time.minute == 0:
            await self._send_afternoon_reminders(today)
        
        # إرسال تذكير نهائي في الساعة 6:00 مساءً
        elif current_time.hour == 18 and current_time.minute == 0:
            await self._send_final_reminders(today)
    
    async def _send_afternoon_reminders(self, target_date):
        """إرسال تذكيرات بعد الظهر"""
        with SessionLocal() as s:
            # البحث عن المترجمين الذين لم يكملوا تقاريرهم ولم يتم إرسال تذكير لهم
            incomplete_records = s.query(DailyReportTracking).filter(
                DailyReportTracking.date == target_date,
                DailyReportTracking.is_completed == False,
                DailyReportTracking.reminder_sent == False
            ).all()
            
            for record in incomplete_records:
                # البحث عن المترجم
                translator = s.query(Translator).filter_by(full_name=record.translator_name).first()
                
                if translator:
                    # إرسال التذكير
                    message = (
                        f"🔔 **تذكير بعد الظهر**\n\n"
                        f"مرحباً {record.translator_name}\n\n"
                        f"📅 التاريخ: {target_date.strftime('%Y-%m-%d')}\n"
                        f"📝 التقارير المطلوبة: {record.expected_reports}\n"
                        f"📊 التقارير المرفوعة: {record.actual_reports}\n\n"
                        f"⚠️ يرجى رفع التقارير المتبقية قبل الساعة 6:00 مساءً"
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=translator.tg_user_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        
                        # تسجيل التذكير
                        notification = TranslatorNotification(
                            translator_name=record.translator_name,
                            notification_type="reminder",
                            message=message,
                            is_sent=True,
                            sent_at=datetime.now()
                        )
                        s.add(notification)
                        
                        # تحديث سجل التتبع
                        record.reminder_sent = True
                        
                    except Exception as e:
                        print(f"❌ فشل إرسال تذكير لـ {record.translator_name}: {e}")
            
            s.commit()
    
    async def _send_final_reminders(self, target_date):
        """إرسال تذكيرات نهائية"""
        with SessionLocal() as s:
            # البحث عن المترجمين الذين لم يكملوا تقاريرهم
            incomplete_records = s.query(DailyReportTracking).filter(
                DailyReportTracking.date == target_date,
                DailyReportTracking.is_completed == False
            ).all()
            
            for record in incomplete_records:
                # البحث عن المترجم
                translator = s.query(Translator).filter_by(full_name=record.translator_name).first()
                
                if translator:
                    # إرسال التذكير النهائي
                    message = (
                        f"🚨 **تذكير نهائي**\n\n"
                        f"مرحباً {record.translator_name}\n\n"
                        f"📅 التاريخ: {target_date.strftime('%Y-%m-%d')}\n"
                        f"📝 التقارير المطلوبة: {record.expected_reports}\n"
                        f"📊 التقارير المرفوعة: {record.actual_reports}\n\n"
                        f"⚠️ هذا تذكير نهائي لرفع التقارير المتبقية"
                    )
                    
                    try:
                        await self.bot.send_message(
                            chat_id=translator.tg_user_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        
                        # تسجيل التذكير
                        notification = TranslatorNotification(
                            translator_name=record.translator_name,
                            notification_type="final_reminder",
                            message=message,
                            is_sent=True,
                            sent_at=datetime.now()
                        )
                        s.add(notification)
                        
                    except Exception as e:
                        print(f"❌ فشل إرسال تذكير نهائي لـ {record.translator_name}: {e}")
            
            s.commit()
    
    async def send_daily_summary_to_admin(self):
        """إرسال ملخص يومي للأدمن"""
        today = date.today()
        current_time = datetime.now().time()
        
        # إرسال الملخص في الساعة 7:00 مساءً
        if current_time.hour == 19 and current_time.minute == 0:
            await self._create_and_send_daily_summary(today)
    
    async def _create_and_send_daily_summary(self, target_date):
        """إنشاء وإرسال الملخص اليومي"""
        from config.settings import ADMIN_IDS
        
        with SessionLocal() as s:
            # جلب إحصائيات اليوم
            tracking_records = s.query(DailyReportTracking).filter_by(date=target_date).all()
            
            if not tracking_records:
                return
            
            # حساب الإحصائيات
            total_translators = len(tracking_records)
            completed = sum(1 for r in tracking_records if r.is_completed)
            pending = total_translators - completed
            
            # إنشاء الملخص
            summary = f"📊 **التقرير اليومي - {target_date.strftime('%Y-%m-%d')}**\n\n"
            summary += f"👥 **إجمالي المترجمين:** {total_translators}\n"
            summary += f"✅ **مكتمل:** {completed}\n"
            summary += f"⏳ **متأخر:** {pending}\n\n"
            
            # تفاصيل المترجمين المتأخرين
            if pending > 0:
                summary += "⚠️ **المترجمين المتأخرين:**\n"
                for record in tracking_records:
                    if not record.is_completed:
                        summary += f"• {record.translator_name}: {record.actual_reports}/{record.expected_reports}\n"
            
            # إرسال للأدمن
            for admin_id in ADMIN_IDS.split(','):
                try:
                    await self.bot.send_message(
                        chat_id=int(admin_id.strip()),
                        text=summary,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    print(f"❌ فشل إرسال الملخص للأدمن {admin_id}: {e}")

# إنشاء مثيل عام للمتعقب
schedule_tracker = ScheduleTracker()

async def run_daily_tracking():
    """تشغيل تتبع يومي"""
    while True:
        try:
            # تحديث عدد التقارير
            await schedule_tracker.update_daily_reports_count()
            
            # فحص وإرسال التذكيرات
            await schedule_tracker.check_and_send_reminders()
            
            # إرسال الملخص اليومي
            await schedule_tracker.send_daily_summary_to_admin()
            
            # انتظار دقيقة قبل الفحص التالي
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"❌ خطأ في تتبع الجدول: {e}")
            await asyncio.sleep(60)



