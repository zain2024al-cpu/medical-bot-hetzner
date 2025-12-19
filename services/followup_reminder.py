# =============================
# services/followup_reminder.py
# 📅 نظام تنبيهات مواعيد العودة
# =============================

from db.session import SessionLocal
from db.models import Report, Patient
from config.settings import ADMIN_IDS
from telegram import Bot
from telegram.constants import ParseMode
from datetime import date, timedelta


async def check_and_send_followup_reminders(bot: Bot):
    """
    فحص مواعيد العودة وإرسال تنبيهات
    يتم تشغيلها يومياً في المساء (مثلاً 6 مساءً)
    """
    tomorrow = date.today() + timedelta(days=1)
    
    with SessionLocal() as s:
        # البحث عن التقارير التي لها موعد عودة غداً
        reports_tomorrow = s.query(Report).filter(
            Report.followup_date >= tomorrow,
            Report.followup_date < tomorrow + timedelta(days=1)
        ).all()
        
        if not reports_tomorrow:
            print("لا توجد مواعيد عودة غدا")
            return
        
        # تنسيق الرسالة
        message = "📅 **تذكير: مواعيد عودة غداً**\n"
        message += f"━━━━━━━━━━━━━━━━\n\n"
        message += f"📌 **التاريخ:** {tomorrow.strftime('%Y-%m-%d')}\n"
        message += f"📊 **عدد المواعيد:** {len(reports_tomorrow)}\n\n"
        
        for i, report in enumerate(reports_tomorrow, 1):
            # الحصول على اسم المريض
            patient = s.query(Patient).filter_by(id=report.patient_id).first()
            patient_name = patient.full_name if patient else "غير محدد"
            
            message += f"{i}. 👤 **{patient_name}**\n"
            
            if report.followup_reason:
                message += f"   ✍️ السبب: {report.followup_reason}\n"
            
            # معلومات إضافية من التقرير الأصلي
            if hasattr(report, 'hospital') and report.hospital:
                message += f"   🏥 المستشفى: {report.hospital.name}\n"
            
            if hasattr(report, 'translator') and report.translator:
                message += f"   👨‍⚕️ المترجم: {report.translator.full_name}\n"
            
            message += "\n"
        
        message += "━━━━━━━━━━━━━━━━\n"
        message += "⏰ **يرجى الاستعداد والتحضير للمواعيد**"
        
        # إرسال التنبيه للأدمن
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                print(f"تم ارسال تنبيه المواعيد الى الادمن {admin_id}")
            except Exception as e:
                print(f"فشل ارسال التنبيه الى الادمن {admin_id}: {e}")


async def send_daily_followup_summary(bot: Bot):
    """
    إرسال ملخص يومي بجميع مواعيد العودة القادمة
    """
    today = date.today()
    next_week = today + timedelta(days=7)
    
    with SessionLocal() as s:
        # البحث عن جميع مواعيد العودة في الأسبوع القادم
        upcoming_reports = s.query(Report).filter(
            Report.followup_date >= today,
            Report.followup_date < next_week
        ).order_by(Report.followup_date).all()
        
        if not upcoming_reports:
            return
        
        # تنسيق الرسالة
        message = "📊 **ملخص مواعيد العودة - الأسبوع القادم**\n"
        message += f"━━━━━━━━━━━━━━━━\n\n"
        message += f"📅 من {today.strftime('%Y-%m-%d')} إلى {next_week.strftime('%Y-%m-%d')}\n"
        message += f"📊 **إجمالي المواعيد:** {len(upcoming_reports)}\n\n"
        
        # تجميع حسب التاريخ
        grouped_by_date = {}
        for report in upcoming_reports:
            followup_date = report.followup_date.date() if hasattr(report.followup_date, 'date') else report.followup_date
            if followup_date not in grouped_by_date:
                grouped_by_date[followup_date] = []
            grouped_by_date[followup_date].append(report)
        
        # عرض المواعيد مجمعة حسب التاريخ
        for followup_date, reports in sorted(grouped_by_date.items()):
            message += f"📅 **{followup_date.strftime('%Y-%m-%d')}** ({len(reports)} موعد)\n"
            
            for report in reports:
                patient = s.query(Patient).filter_by(id=report.patient_id).first()
                patient_name = patient.full_name if patient else "غير محدد"
                message += f"   • {patient_name}"
                
                if report.followup_reason:
                    message += f" - {report.followup_reason}"
                
                message += "\n"
            
            message += "\n"
        
        message += "━━━━━━━━━━━━━━━━"
        
        # إرسال للأدمن فقط
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                print(f"تم ارسال ملخص المواعيد الى الادمن {admin_id}")
            except Exception as e:
                print(f"فشل ارسال الملخص الى الادمن {admin_id}: {e}")




















