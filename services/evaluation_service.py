# ================================================
# services/evaluation_service.py
# 🔹 خدمة التقييم التلقائي للمترجمين
# ================================================

from datetime import datetime, date, time
from db.session import SessionLocal
from db.models import (
    DailyReportTracking, TranslatorEvaluation, MonthlyEvaluation, 
    Translator, Report
)

class EvaluationService:
    """خدمة التقييم التلقائي للمترجمين"""
    
    def __init__(self):
        pass
    
    def evaluate_report_timing(self, report_date: datetime) -> dict:
        """تقييم توقيت رفع التقرير"""
        report_time = report_date.time()
        
        # تحديد نقاط التوقيت
        if report_time <= time(18, 0):  # قبل 6:00 مساءً
            timing_score = 10
            timing_level = "ممتاز"
            timing_notes = "تم رفع التقرير في الوقت المحدد"
        elif report_time <= time(20, 0):  # بين 6:00-8:00 مساءً
            timing_score = 7
            timing_level = "جيد"
            timing_notes = "تم رفع التقرير في الوقت المسموح"
        else:  # بعد 8:00 مساءً
            timing_score = 0
            timing_level = "مخالف"
            timing_notes = "تم رفع التقرير بعد الوقت المحدد"
        
        return {
            'score': timing_score,
            'level': timing_level,
            'notes': timing_notes
        }
    
    def evaluate_report_quality(self, report: Report) -> dict:
        """تقييم جودة التقرير"""
        quality_score = 7  # افتراضياً 7 نقاط
        quality_notes = "تقرير جيد"
        
        # فحص اكتمال البيانات
        if report.complaint_text and len(report.complaint_text.strip()) > 10:
            quality_score += 1
        
        if report.doctor_decision and len(report.doctor_decision.strip()) > 10:
            quality_score += 1
        
        if report.medical_action and len(report.medical_action.strip()) > 5:
            quality_score += 1
        
        # تحديد مستوى الجودة
        if quality_score >= 9:
            quality_level = "ممتاز"
            quality_notes = "تقرير مكتمل ومفصل"
        elif quality_score >= 7:
            quality_level = "جيد"
            quality_notes = "تقرير جيد مع تفاصيل كافية"
        elif quality_score >= 5:
            quality_level = "مقبول"
            quality_notes = "تقرير مقبول مع نقاط للتحسين"
        else:
            quality_level = "ضعيف"
            quality_notes = "تقرير ناقص يحتاج تحسين"
        
        return {
            'score': min(quality_score, 10),  # حد أقصى 10 نقاط
            'level': quality_level,
            'notes': quality_notes
        }
    
    def evaluate_translator_regularity(self, translator_name: str, target_date: date) -> dict:
        """تقييم انتظام المترجم"""
        with SessionLocal() as s:
            # جلب سجل التتبع للمترجم في اليوم
            tracking_record = s.query(DailyReportTracking).filter_by(
                translator_name=translator_name,
                date=target_date
            ).first()
            
            if not tracking_record:
                return {
                    'score': 0,
                    'level': "غير متاح",
                    'notes': "لا توجد بيانات للمترجم في هذا اليوم"
                }
            
            # حساب نسبة الإنجاز
            if tracking_record.expected_reports > 0:
                completion_ratio = tracking_record.actual_reports / tracking_record.expected_reports
                
                if completion_ratio >= 1.0:
                    regularity_score = 10
                    regularity_level = "ممتاز"
                    regularity_notes = "تم إنجاز جميع التقارير المطلوبة"
                elif completion_ratio >= 0.8:
                    regularity_score = 7
                    regularity_level = "جيد"
                    regularity_notes = "تم إنجاز معظم التقارير المطلوبة"
                elif completion_ratio >= 0.6:
                    regularity_score = 5
                    regularity_level = "مقبول"
                    regularity_notes = "تم إنجاز جزء من التقارير المطلوبة"
                else:
                    regularity_score = 2
                    regularity_level = "ضعيف"
                    regularity_notes = "لم يتم إنجاز معظم التقارير المطلوبة"
            else:
                regularity_score = 5
                regularity_level = "غير محدد"
                regularity_notes = "لا توجد تقارير مطلوبة"
            
            return {
                'score': regularity_score,
                'level': regularity_level,
                'notes': regularity_notes
            }
    
    def create_daily_evaluation(self, report: Report, translator_name: str) -> TranslatorEvaluation:
        """إنشاء تقييم يومي للتقرير"""
        with SessionLocal() as s:
            # تقييم التوقيت
            timing_eval = self.evaluate_report_timing(report.report_date)
            
            # تقييم الجودة
            quality_eval = self.evaluate_report_quality(report)
            
            # تقييم الانتظام
            regularity_eval = self.evaluate_translator_regularity(translator_name, report.report_date.date())
            
            # حساب النقاط الإجمالية
            total_score = timing_eval['score'] + quality_eval['score'] + regularity_eval['score']
            
            # إنشاء التقييم
            evaluation = TranslatorEvaluation(
                translator_name=translator_name,
                report_id=report.id,
                timing_score=timing_eval['score'],
                quality_score=quality_eval['score'],
                regularity_score=regularity_eval['score'],
                total_score=total_score,
                timing_notes=timing_eval['notes'],
                quality_notes=quality_eval['notes'],
                general_notes=regularity_eval['notes'],
                is_manual=False
            )
            
            s.add(evaluation)
            s.commit()
            s.refresh(evaluation)
            
            return evaluation
    
    def generate_monthly_evaluation(self, translator_name: str, year: int, month: int) -> MonthlyEvaluation:
        """توليد التقييم الشهري للمترجم"""
        with SessionLocal() as s:
            # جلب جميع التقييمات اليومية للشهر
            daily_evaluations = s.query(TranslatorEvaluation).filter(
                TranslatorEvaluation.translator_name == translator_name,
                TranslatorEvaluation.evaluation_date >= datetime(year, month, 1),
                TranslatorEvaluation.evaluation_date < datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
            ).all()
            
            if not daily_evaluations:
                return None
            
            # حساب المتوسطات
            avg_timing = sum(e.timing_score for e in daily_evaluations) / len(daily_evaluations)
            avg_quality = sum(e.quality_score for e in daily_evaluations) / len(daily_evaluations)
            avg_regularity = sum(e.regularity_score for e in daily_evaluations) / len(daily_evaluations)
            avg_total = sum(e.total_score for e in daily_evaluations) / len(daily_evaluations)
            
            # جلب إحصائيات التتبع
            tracking_records = s.query(DailyReportTracking).filter(
                DailyReportTracking.translator_name == translator_name,
                DailyReportTracking.date >= date(year, month, 1),
                DailyReportTracking.date < date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
            ).all()
            
            total_reports = len(tracking_records)
            on_time_reports = sum(1 for r in tracking_records if r.is_completed and not r.reminder_sent)
            late_reports = total_reports - on_time_reports
            
            # تحديد التقييم النهائي
            if avg_total >= 27:
                final_rating = 5
                performance_level = "ممتاز"
            elif avg_total >= 24:
                final_rating = 4
                performance_level = "جيد جداً"
            elif avg_total >= 21:
                final_rating = 3
                performance_level = "جيد"
            elif avg_total >= 18:
                final_rating = 2
                performance_level = "مقبول"
            else:
                final_rating = 1
                performance_level = "ضعيف"
            
            # إنشاء أو تحديث التقييم الشهري
            monthly_eval = s.query(MonthlyEvaluation).filter_by(
                translator_name=translator_name,
                year=year,
                month=month
            ).first()
            
            if monthly_eval:
                # تحديث التقييم الموجود
                monthly_eval.total_reports = total_reports
                monthly_eval.on_time_reports = on_time_reports
                monthly_eval.late_reports = late_reports
                monthly_eval.timing_points = round(avg_timing, 1)
                monthly_eval.quality_points = round(avg_quality, 1)
                monthly_eval.regularity_points = round(avg_regularity, 1)
                monthly_eval.total_points = round(avg_total, 1)
                monthly_eval.final_rating = final_rating
                monthly_eval.performance_level = performance_level
                monthly_eval.updated_at = datetime.now()
            else:
                # إنشاء تقييم جديد
                monthly_eval = MonthlyEvaluation(
                    translator_name=translator_name,
                    year=year,
                    month=month,
                    total_reports=total_reports,
                    on_time_reports=on_time_reports,
                    late_reports=late_reports,
                    timing_points=round(avg_timing, 1),
                    quality_points=round(avg_quality, 1),
                    regularity_points=round(avg_regularity, 1),
                    total_points=round(avg_total, 1),
                    final_rating=final_rating,
                    performance_level=performance_level
                )
                s.add(monthly_eval)
            
            s.commit()
            s.refresh(monthly_eval)
            
            return monthly_eval

# إنشاء مثيل عام للخدمة
evaluation_service = EvaluationService()



