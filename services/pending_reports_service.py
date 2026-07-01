# services/pending_reports_service.py
"""
خدمة إدارة التقارير الطبية المعلقة (بدون مرافقات جاهزة)

وظائفها:
1. حفظ التقارير المعلقة عند الكتابة
2. تحديث الحالة عند إرفاق المرافقات
3. حساب عدد أيام الانتظار
4. توليد تقارير يومية للأدمن
"""

import logging
from datetime import datetime, date, timedelta
from db.session import SessionLocal
from db.models import PendingReport, Report

logger = logging.getLogger(__name__)


def add_pending_report(
    report_id: int,
    patient_id: int,
    patient_name: str,
    department: str,
    translator_id: int,
    translator_name: str,
    no_report_reason: str
) -> bool:
    """إضافة تقرير معلق جديد"""
    try:
        with SessionLocal() as session:
            # تحقق من عدم وجود سجل معلق نشط لنفس التقرير
            existing = session.query(PendingReport).filter(
                PendingReport.report_id == report_id,
                PendingReport.status == "pending"
            ).first()

            if existing:
                logger.warning(f"⚠️ Pending report already exists for report_id={report_id}")
                return False

            # إنشاء سجل معلق جديد
            pending = PendingReport(
                report_id=report_id,
                patient_id=patient_id,
                patient_name=patient_name,
                department=department,
                translator_id=translator_id,
                translator_name=translator_name,
                no_report_reason=no_report_reason,
                status="pending",
                created_at=datetime.utcnow()
            )
            session.add(pending)
            session.commit()

            logger.info(f"✅ Pending report added: patient={patient_name}, dept={department}")
            return True

    except Exception as e:
        logger.error(f"❌ Error adding pending report: {e}", exc_info=True)
        return False


def mark_report_completed(report_id: int) -> bool:
    """تحديث التقرير المعلق إلى "مكتمل" عند إرفاق المرافقات"""
    try:
        with SessionLocal() as session:
            pending = session.query(PendingReport).filter(
                PendingReport.report_id == report_id,
                PendingReport.status == "pending"
            ).first()

            if not pending:
                logger.warning(f"⚠️ No pending report found for report_id={report_id}")
                return False

            pending.status = "completed"
            pending.completed_at = datetime.utcnow()
            session.commit()

            days_waiting = (pending.completed_at - pending.created_at).days
            logger.info(
                f"✅ Pending report marked completed: patient={pending.patient_name}, "
                f"days_waiting={days_waiting}"
            )
            return True

    except Exception as e:
        logger.error(f"❌ Error marking report completed: {e}", exc_info=True)
        return False


def get_pending_reports() -> list:
    """جلب جميع التقارير المعلقة النشطة"""
    try:
        with SessionLocal() as session:
            pending_list = session.query(PendingReport).filter(
                PendingReport.status == "pending"
            ).order_by(PendingReport.created_at.desc()).all()

            # حساب عدد أيام الانتظار لكل تقرير
            result = []
            for p in pending_list:
                days_waiting = (datetime.utcnow() - p.created_at).days
                result.append({
                    'id': p.id,
                    'report_id': p.report_id,
                    'patient_name': p.patient_name,
                    'department': p.department,
                    'translator_name': p.translator_name,
                    'no_report_reason': p.no_report_reason,
                    'days_waiting': days_waiting,
                    'created_at': p.created_at
                })

            logger.info(f"✅ Fetched {len(result)} pending reports")
            return result

    except Exception as e:
        logger.error(f"❌ Error fetching pending reports: {e}", exc_info=True)
        return []


def get_pending_reports_by_translator(translator_name: str) -> list:
    """جلب التقارير المعلقة لمترجم معين"""
    try:
        with SessionLocal() as session:
            pending_list = session.query(PendingReport).filter(
                PendingReport.translator_name == translator_name,
                PendingReport.status == "pending"
            ).order_by(PendingReport.created_at.desc()).all()

            result = []
            for p in pending_list:
                days_waiting = (datetime.utcnow() - p.created_at).days
                result.append({
                    'id': p.id,
                    'patient_name': p.patient_name,
                    'department': p.department,
                    'days_waiting': days_waiting,
                    'created_at': p.created_at
                })

            return result

    except Exception as e:
        logger.error(f"❌ Error fetching translator pending reports: {e}", exc_info=True)
        return []


def get_pending_reports_summary_text() -> str:
    """إنشاء نص تقرير التقارير المعلقة للأدمن"""
    pending_list = get_pending_reports()

    if not pending_list:
        return "✅ **لا توجد تقارير معلقة** - جميع التقارير جاهزة!"

    # ترتيب حسب عدد أيام الانتظار (الأقدم أولاً)
    pending_list.sort(key=lambda x: x['days_waiting'], reverse=True)

    text = "📋 **التقارير الطبية المعلقة**\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    text += f"📊 **العدد الإجمالي:** {len(pending_list)} تقرير معلق\n\n"

    # تصنيف حسب الانتظار
    overdue_3plus = [p for p in pending_list if p['days_waiting'] >= 3]
    overdue_2 = [p for p in pending_list if p['days_waiting'] == 2]
    overdue_1 = [p for p in pending_list if p['days_waiting'] == 1]
    today = [p for p in pending_list if p['days_waiting'] == 0]

    # التقارير المتأخرة أكثر من 3 أيام
    if overdue_3plus:
        text += "🔴 **متأخرة أكثر من 3 أيام:**\n"
        for p in overdue_3plus:
            text += (
                f"  • {p['patient_name']}\n"
                f"    القسم: {p['department']} | {p['days_waiting']} أيام\n"
                f"    المترجم: {p['translator_name']}\n\n"
            )

    # متأخرة يومين
    if overdue_2:
        text += "⚠️ **متأخرة يومين:**\n"
        for p in overdue_2:
            text += f"  • {p['patient_name']} - {p['department']}\n"

    # متأخرة يوم واحد
    if overdue_1:
        text += "🟡 **منذ يوم واحد:**\n"
        for p in overdue_1:
            text += f"  • {p['patient_name']} - {p['department']}\n"

    # اليوم
    if today:
        text += "🟢 **اليوم (للتو):**\n"
        for p in today:
            text += f"  • {p['patient_name']} - {p['department']}\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "💡 تم إنشاء هذا التقرير تلقائياً كل يوم لمتابعة التقارير المعلقة."

    return text


async def send_pending_reports_daily_report(bot, admin_ids: list):
    """إرسال تقرير يومي بالتقارير المعلقة للأدمن"""
    try:
        report_text = get_pending_reports_summary_text()

        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=report_text,
                    parse_mode="Markdown"
                )
                logger.info(f"✅ Pending reports daily report sent to admin {admin_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send report to admin {admin_id}: {e}")

    except Exception as e:
        logger.error(f"❌ Error in send_pending_reports_daily_report: {e}", exc_info=True)
