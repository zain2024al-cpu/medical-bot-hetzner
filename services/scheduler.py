# services/scheduler.py
"""
Scheduler service (compatible with python-telegram-bot 20+).
Uses APScheduler AsyncIOScheduler to schedule async tasks.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio

# مثال دالة مهمة مجدولة (غير مرتبطة بالـ bot مباشرة)
async def _example_job():
    # هنا تضع ما تريد تنفيذه مجدولاً (إرسال رسالة، تنظيف بيانات، ...)
        print("Example scheduled job running...")

# دالة تتبع الجدول اليومي
async def _schedule_tracking_job():
    """مهمة تتبع الجدول اليومي"""
    try:
        from services.schedule_tracker import schedule_tracker
        
        # تحديث عدد التقارير
        await schedule_tracker.update_daily_reports_count()
        
        # فحص وإرسال التذكيرات
        await schedule_tracker.check_and_send_reminders()
        
        # إرسال الملخص اليومي
        await schedule_tracker.send_daily_summary_to_admin()
        
        print("Schedule tracking job completed.")
        
    except Exception as e:
        print(f"Error in schedule tracking job: {e}")

# دالة التقييم الشهري التلقائي
async def _monthly_evaluation_job():
    """مهمة التقييم الشهري التلقائي"""
    try:
        from services.evaluation_service import evaluation_service
        from db.session import SessionLocal
        from db.models import DailyReportTracking, TranslatorDirectory
        from datetime import date
        
        # تشغيل في أول يوم من كل شهر
        current_date = date.today()
        if current_date.day == 1:
            print("Starting monthly evaluation...")
            
            # جلب جميع المترجمين
            with SessionLocal() as s:
                translators = s.query(
                    DailyReportTracking.translator_id,
                    DailyReportTracking.translator_name
                ).distinct().all()
                
                for translator_id, translator_name in translators:
                    resolved_name = translator_name
                    if translator_id and not resolved_name:
                        translator = s.query(TranslatorDirectory).filter_by(translator_id=translator_id).first()
                        resolved_name = translator.name if translator else None
                    
                    monthly_eval = evaluation_service.generate_monthly_evaluation(
                        translator_id,
                        resolved_name,
                        current_date.year,
                        current_date.month - 1
                    )
                    
                    if monthly_eval:
                        display_name = resolved_name or "غير محدد"
                        print(f"Generated monthly evaluation for {display_name}")
            
            print("Monthly evaluation completed.")
        
    except Exception as e:
        print(f"Error in monthly evaluation job: {e}")

# دالة فحص مواعيد العودة
async def _followup_reminder_job(app):
    """مهمة تنبيهات مواعيد العودة"""
    try:
        from services.followup_reminder import check_and_send_followup_reminders
        
        if app and hasattr(app, 'bot'):
            await check_and_send_followup_reminders(app.bot)
            print("Followup reminders sent successfully.")
        
    except Exception as e:
        print(f"Error in followup reminder job: {e}")

async def _translator_reminder_job(app):
    """مهمة تنبيهات المترجمين"""
    try:
        from services.translator_reminders import check_and_send_reminders
        if app and hasattr(app, 'bot'):
            await check_and_send_reminders(app.bot)
    except Exception as e:
        print(f"Error in translator reminder: {e}")

async def _daily_followups_job(app):
    """مهمة استخراج ورفع المواعيد من تقارير اليوم"""
    try:
        from services.followup_appointments import extract_and_create_followups_from_today_reports
        from config.settings import ADMIN_IDS
        if app and hasattr(app, 'bot'):
            await extract_and_create_followups_from_today_reports(app.bot, ADMIN_IDS)
    except Exception as e:
        print(f"Error in daily followups: {e}")

async def _sqlite_quick_backup_job():
    """مهمة النسخ الاحتياطي السريع كل 10 دقائق"""
    try:
        # النسخة المحلية الآمنة أولاً (SQLite backup API + integrity_check)
        from services.render_backup import create_local_backup
        backup_path = await asyncio.to_thread(create_local_backup, "quick")
        if backup_path:
            print(f"Local quick backup completed: {backup_path}")
        else:
            print("Local quick backup failed")

        # محاولة رفع نسخة إلى GCS (اختياري)
        try:
            from services.sqlite_backup import get_backup_service
            backup_service = get_backup_service()
            await asyncio.to_thread(backup_service.quick_backup)
            print("SQLite quick backup to GCS completed.")
        except Exception as gcs_error:
            print(f"GCS quick backup skipped: {gcs_error}")
    except Exception as e:
        print(f"Error in quick backup: {e}")

async def _sqlite_daily_backup_job():
    """مهمة النسخ الاحتياطي اليومي"""
    try:
        from datetime import datetime
        from services.render_backup import create_local_backup, create_monthly_archive

        # النسخة المحلية الآمنة اليومية
        backup_path = await asyncio.to_thread(create_local_backup, "daily")
        if backup_path:
            print(f"Local daily backup completed: {backup_path}")
        else:
            print("Local daily backup failed")

        # في أول يوم من الشهر: أنشئ أرشيف الشهر السابق
        now = datetime.utcnow()
        if now.day == 1:
            archive_path = await asyncio.to_thread(create_monthly_archive)
            if archive_path:
                print(f"Monthly archive completed: {archive_path}")
            else:
                print("Monthly archive failed")

        # محاولة رفع النسخة إلى GCS (اختياري)
        try:
            from services.sqlite_backup import get_backup_service
            backup_service = get_backup_service()
            await asyncio.to_thread(lambda: backup_service.backup_database(backup_type="daily"))
            print("SQLite daily backup to GCS completed.")
        except Exception as gcs_error:
            print(f"GCS daily backup skipped: {gcs_error}")
    except Exception as e:
        print(f"Error in daily backup: {e}")


def start_scheduler(app=None):
    """
    ابدأ المجدول مع الميزات الجديدة
    """
    try:
        scheduler = AsyncIOScheduler(timezone='UTC')
        
        from apscheduler.triggers.cron import CronTrigger
        
        if app:
            # 1. تنبيهات مواعيد العودة (6:00 مساءً)
            scheduler.add_job(
                _followup_reminder_job,
                trigger=CronTrigger(hour=18, minute=0, timezone='UTC'),
                args=[app],
                id='followup_reminder'
            )
            try:
                print("✅ Followup reminder: 6:00 PM daily")
            except UnicodeEncodeError:
                print("[OK] Followup reminder: 6:00 PM daily")
            
            # 2. تنبيهات المترجمين (3 مرات يومياً)
            scheduler.add_job(
                _translator_reminder_job,
                trigger=CronTrigger(hour=14, minute=0, timezone='UTC'),  # 2:00 PM
                args=[app],
                id='translator_reminder_1'
            )
            scheduler.add_job(
                _translator_reminder_job,
                trigger=CronTrigger(hour=16, minute=0, timezone='UTC'),  # 4:00 PM
                args=[app],
                id='translator_reminder_2'
            )
            scheduler.add_job(
                _translator_reminder_job,
                trigger=CronTrigger(hour=18, minute=0, timezone='UTC'),  # 6:00 PM
                args=[app],
                id='translator_reminder_3'
            )
            try:
                print("✅ Translator reminders: 2 PM, 4 PM, 6 PM daily")
            except UnicodeEncodeError:
                print("[OK] Translator reminders: 2 PM, 4 PM, 6 PM daily")

            # 2.5. التنبيهات اليومية للمتابعة (4:00 عصرًا)
            scheduler.add_job(
                _daily_reminder_job,
                trigger=CronTrigger(hour=16, minute=0, timezone='UTC'),  # 4:00 PM (16:00 UTC)
                args=[app],
                id='daily_reminder'
            )
            try:
                print("✅ Daily reminder system: 4:00 PM daily")
            except UnicodeEncodeError:
                print("[OK] Daily reminder system: 4:00 PM daily")

            # 3. رفع مواعيد المرضى من تقارير اليوم (9:00 مساءً)
            scheduler.add_job(
                _daily_followups_job,
                trigger=CronTrigger(hour=21, minute=0, timezone='UTC'),  # 9:00 PM
                args=[app],
                id='daily_followups'
            )
            try:
                print("✅ Daily followups extraction: 9:00 PM daily")
            except UnicodeEncodeError:
                print("[OK] Daily followups extraction: 9:00 PM daily")
        
        # 4. النسخ الاحتياطي السريع كل 10 دقائق
        scheduler.add_job(
            _sqlite_quick_backup_job,
            trigger=IntervalTrigger(minutes=10),
            id='sqlite_quick_backup',
            max_instances=1,
            coalesce=True
        )
        try:
            print("✅ SQLite quick backup: Every 10 minutes")
        except UnicodeEncodeError:
            print("[OK] SQLite quick backup: Every 10 minutes")
        
        # 5. النسخ الاحتياطي اليومي عند الساعة 3 صباحاً
        scheduler.add_job(
            _sqlite_daily_backup_job,
            trigger=CronTrigger(hour=3, minute=0, timezone='UTC'),  # 3:00 AM
            id='sqlite_daily_backup',
            max_instances=1,
            coalesce=True
        )
        try:
            print("✅ SQLite daily backup: Daily at 3:00 AM")
        except UnicodeEncodeError:
            print("[OK] SQLite daily backup: Daily at 3:00 AM")
        
        # تعطيل المجدول الأخرى مؤقتاً
        # scheduler.add_job(_example_job, trigger=IntervalTrigger(minutes=5))
        # scheduler.add_job(_schedule_tracking_job, trigger=IntervalTrigger(minutes=1))
        # scheduler.add_job(_monthly_evaluation_job, trigger=IntervalTrigger(days=1))
        
        scheduler.start()
        print("Scheduler started successfully.")
        
    except Exception as e:
        print("Failed to start scheduler:", e)
