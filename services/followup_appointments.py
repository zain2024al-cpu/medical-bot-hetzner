#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅 نظام مواعيد المتابعة الذكي
Smart Follow-up Appointments System
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Dict
from db.session import SessionLocal
from db.models import Report, Patient, FollowupTracking

logger = logging.getLogger(__name__)

async def extract_and_create_followups_from_today_reports(bot, admin_ids: List[int]):
    """
    استخراج المواعيد من تقارير اليوم وإنشاء متابعات تلقائياً
    
    Args:
        bot: Telegram bot instance
        admin_ids: قائمة IDs الأدمن
    """
    try:
        today = datetime.now().date()
        db = SessionLocal()
        
        new_followups = []
        
        try:
            # جلب تقارير اليوم التي تحتوي على قرارات متابعة
            today_reports = db.query(Report).filter(
                Report.report_date == today
            ).all()
            
            for report in today_reports:
                # فحص إذا القرار يحتوي على "متابعة" أو "موعد"
                decision = report.doctor_decision or ""
                decision_lower = decision.lower()
                
                if any(word in decision_lower for word in ['متابعة', 'موعد', 'follow', 'appointment', 'مراجعة']):
                    # فحص إذا لا يوجد متابعة مسجلة لهذا التقرير
                    existing = db.query(FollowupTracking).filter_by(
                        report_id=report.id
                    ).first()
                    
                    if not existing:
                        # استخراج تاريخ المتابعة من النص
                        followup_date = extract_followup_date(decision)
                        
                        if not followup_date:
                            # إذا لم يحدد تاريخ، افترض بعد أسبوع
                            followup_date = today + timedelta(days=7)
                        
                        # إنشاء متابعة جديدة
                        followup = FollowupTracking(
                            patient_id=report.patient_id,
                            report_id=report.id,
                            followup_date=followup_date,
                            followup_type='مراجعة دورية',
                            priority='متوسطة',
                            status='مجدولة',
                            notes=f"متابعة من تقرير {today.strftime('%Y-%m-%d')}",
                            created_at=datetime.now()
                        )
                        
                        db.add(followup)
                        
                        # معلومات المريض
                        patient = db.get(Patient, report.patient_id) if report.patient_id else None
                        patient_name = patient.full_name if patient else 'غير محدد'
                        
                        new_followups.append({
                            'patient': patient_name,
                            'date': followup_date,
                            'type': 'مراجعة دورية'
                        })
            
            db.commit()
            
            # إرسال تقرير للأدمن بالمتابعات الجديدة
            if new_followups:
                message = f"""
📅 متابعات جديدة من تقارير اليوم

📊 تم إنشاء {len(new_followups)} موعد متابعة تلقائياً:

"""
                for i, f in enumerate(new_followups[:10], 1):
                    message += f"{i}. {f['patient']} - {f['date'].strftime('%Y-%m-%d')}\n"
                
                if len(new_followups) > 10:
                    message += f"\n... و {len(new_followups) - 10} متابعة إضافية"
                
                message += "\n\n✅ تم جدولتها تلقائياً في النظام"
                
                for admin_id in admin_ids:
                    try:
                        await bot.send_message(chat_id=admin_id, text=message)
                    except Exception:
                        pass
                
                logger.info(f"✅ تم إنشاء {len(new_followups)} متابعة من تقارير اليوم")
        
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ خطأ في استخراج المتابعات: {e}")


def extract_followup_date(text: str) -> date:
    """
    استخراج تاريخ المتابعة من النص
    
    Args:
        text: نص القرار الطبي
    
    Returns:
        date: تاريخ المتابعة أو None
    """
    try:
        text_lower = text.lower()
        today = datetime.now().date()
        
        # البحث عن كلمات مفتاحية
        if 'غداً' in text_lower or 'غدا' in text_lower or 'tomorrow' in text_lower:
            return today + timedelta(days=1)
        
        elif 'بعد يومين' in text_lower or 'يومين' in text_lower:
            return today + timedelta(days=2)
        
        elif 'بعد 3 أيام' in text_lower or 'ثلاث' in text_lower or 'ثلاثة' in text_lower:
            return today + timedelta(days=3)
        
        elif 'أسبوع' in text_lower or 'week' in text_lower:
            return today + timedelta(days=7)
        
        elif 'أسبوعين' in text_lower or 'two weeks' in text_lower:
            return today + timedelta(days=14)
        
        elif 'شهر' in text_lower or 'month' in text_lower:
            return today + timedelta(days=30)
        
        # محاولة استخراج رقم
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            days = int(numbers[0])
            if days <= 365:  # منطقي
                return today + timedelta(days=days)
        
        return None
        
    except Exception:
        return None


async def send_daily_followups_reminder(bot, admin_ids: List[int]):
    """
    إرسال تذكير يومي بمواعيد المتابعة
    
    Args:
        bot: Telegram bot instance
        admin_ids: قائمة IDs الأدمن
    """
    try:
        today = datetime.now().date()
        db = SessionLocal()
        
        try:
            # جلب متابعات اليوم
            today_followups = db.query(FollowupTracking).filter(
                FollowupTracking.followup_date == today,
                FollowupTracking.status.in_(['مجدولة', 'قيد الانتظار'])
            ).all()
            
            if today_followups:
                message = f"""
📅 مواعيد المتابعة اليوم

📊 لديك {len(today_followups)} موعد متابعة اليوم:

"""
                for i, f in enumerate(today_followups[:15], 1):
                    patient = db.get(Patient, f.patient_id) if f.patient_id else None
                    patient_name = patient.full_name if patient else 'غير محدد'
                    
                    priority_icon = {
                        'عالية': '🔴',
                        'متوسطة': '🟡',
                        'منخفضة': '🟢'
                    }.get(f.priority, '⚪')
                    
                    message += f"{i}. {priority_icon} {patient_name} - {f.followup_type}\n"
                
                if len(today_followups) > 15:
                    message += f"\n... و {len(today_followups) - 15} موعد إضافي"
                
                message += "\n\n📱 للعرض الكامل: /admin → 📅 المتابعات"
                
                for admin_id in admin_ids:
                    try:
                        await bot.send_message(chat_id=admin_id, text=message)
                    except Exception:
                        pass
                
                logger.info(f"✅ تم إرسال تذكير المتابعات اليومي: {len(today_followups)} موعد")
        
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ خطأ في تذكير المتابعات: {e}")


if __name__ == "__main__":
    # اختبار استخراج التاريخ
    test_texts = [
        "متابعة بعد أسبوع",
        "مراجعة غداً",
        "موعد بعد 3 أيام",
        "follow-up after one month",
        "متابعة بعد 10 أيام"
    ]
    
    print("🧪 اختبار استخراج تواريخ المتابعة:\n")
    for text in test_texts:
        result = extract_followup_date(text)
        print(f"'{text}' → {result}")
























