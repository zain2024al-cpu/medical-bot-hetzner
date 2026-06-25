# ================================================
# db/repositories/statistics_repository.py
# 📊 استعلامات الإحصائيات المتقدمة
# ================================================

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import func, and_, or_

from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor
from services.reporting_engine.filters import CompositeFilter

logger = logging.getLogger(__name__)


class StatisticsRepository:
    """استعلامات إحصائية متقدمة"""
    
    @staticmethod
    def get_hospital_statistics(filters: CompositeFilter) -> List[Dict[str, Any]]:
        """إحصائيات المستشفيات"""
        logger.info("🏥 جلب إحصائيات المستشفيات")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            stats = query.with_entities(
                Report.hospital_name,
                Report.hospital_id,
                func.count(Report.id).label("count")
            ).group_by(
                Report.hospital_id,
                Report.hospital_name
            ).order_by(
                func.count(Report.id).desc()
            ).all()
            
            result = [
                {
                    "name": s[0] or "غير محدد",
                    "id": s[1],
                    "count": s[2]
                }
                for s in stats
            ]
            
            logger.info(f"✅ تم جلب {len(result)} مستشفى")
            return result
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def get_department_statistics(filters: CompositeFilter) -> List[Dict[str, Any]]:
        """إحصائيات الأقسام"""
        logger.info("🏢 جلب إحصائيات الأقسام")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            stats = query.with_entities(
                Report.department,
                Report.department_id,
                func.count(Report.id).label("count")
            ).group_by(
                Report.department_id,
                Report.department
            ).order_by(
                func.count(Report.id).desc()
            ).all()
            
            result = [
                {
                    "name": s[0] or "غير محدد",
                    "id": s[1],
                    "count": s[2]
                }
                for s in stats
            ]
            
            logger.info(f"✅ تم جلب {len(result)} قسم")
            return result
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def get_action_statistics(filters: CompositeFilter) -> List[Dict[str, Any]]:
        """إحصائيات الإجراءات الطبية"""
        logger.info("💉 جلب إحصائيات الإجراءات")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            stats = query.with_entities(
                Report.medical_action,
                func.count(Report.id).label("count")
            ).group_by(
                Report.medical_action
            ).order_by(
                func.count(Report.id).desc()
            ).all()
            
            result = [
                {
                    "name": s[0] or "غير محدد",
                    "count": s[1]
                }
                for s in stats
            ]
            
            logger.info(f"✅ تم جلب {len(result)} إجراء")
            return result
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def get_patient_statistics(patient_id: int, filters: CompositeFilter) -> Dict[str, Any]:
        """إحصائيات مريض معين"""
        logger.info(f"👤 جلب إحصائيات المريض {patient_id}")
        
        try:
            session = SessionLocal()
            
            # جلب بيانات المريض
            patient = session.query(Patient).filter(Patient.id == patient_id).first()
            
            if not patient:
                logger.warning(f"⚠️ المريض {patient_id} غير موجود")
                return {}
            
            # جلب تقارير المريض
            query = session.query(Report).filter(Report.patient_id == patient_id)
            query = filters.apply(query)
            reports = query.all()
            
            return {
                "patient_id": patient_id,
                "patient_name": patient.full_name,
                "total_reports": len(reports),
                "hospitals": list(set(r.hospital_name for r in reports if r.hospital_name)),
                "departments": list(set(r.department for r in reports if r.department)),
                "actions": list(set(r.medical_action for r in reports if r.medical_action)),
            }
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return {}
        finally:
            session.close()
    
    @staticmethod
    def get_doctor_statistics(filters: CompositeFilter) -> List[Dict[str, Any]]:
        """إحصائيات الأطباء"""
        logger.info("👨‍⚕️ جلب إحصائيات الأطباء")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            stats = query.with_entities(
                Report.doctor_name,
                Report.doctor_id,
                func.count(Report.id).label("count")
            ).group_by(
                Report.doctor_id,
                Report.doctor_name
            ).order_by(
                func.count(Report.id).desc()
            ).all()
            
            result = [
                {
                    "name": s[0] or "غير محدد",
                    "id": s[1],
                    "count": s[2]
                }
                for s in stats
            ]
            
            logger.info(f"✅ تم جلب {len(result)} طبيب")
            return result
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def get_translator_statistics(filters: CompositeFilter) -> List[Dict[str, Any]]:
        """إحصائيات المترجمين"""
        logger.info("👨‍💼 جلب إحصائيات المترجمين")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            stats = query.with_entities(
                Report.translator_name,
                Report.translator_id,
                func.count(Report.id).label("count")
            ).group_by(
                Report.translator_id,
                Report.translator_name
            ).order_by(
                func.count(Report.id).desc()
            ).all()
            
            result = [
                {
                    "name": s[0] or "غير محدد",
                    "id": s[1],
                    "count": s[2]
                }
                for s in stats
            ]
            
            logger.info(f"✅ تم جلب {len(result)} مترجم")
            return result
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return []
        finally:
            session.close()
    
    @staticmethod
    def get_timeline_statistics(filters: CompositeFilter) -> Dict[str, int]:
        """إحصائيات التوزيع الزمني"""
        logger.info("⏱️ جلب إحصائيات التوزيع الزمني")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            stats = query.with_entities(
                func.date(Report.report_date).label("date"),
                func.count(Report.id).label("count")
            ).group_by(
                func.date(Report.report_date)
            ).order_by(
                func.date(Report.report_date)
            ).all()
            
            result = {
                s[0].isoformat(): s[1]
                for s in stats
            }
            
            logger.info(f"✅ تم جلب {len(result)} يوم")
            return result
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return {}
        finally:
            session.close()
    
    @staticmethod
    def get_summary_statistics(filters: CompositeFilter) -> Dict[str, Any]:
        """إحصائيات ملخصة عامة"""
        logger.info("📊 جلب الإحصائيات الملخصة")
        
        try:
            session = SessionLocal()
            query = session.query(Report)
            query = filters.apply(query)
            
            total = query.count()
            
            unique_patients = query.with_entities(
                func.count(func.distinct(Report.patient_id))
            ).scalar() or 0
            
            unique_hospitals = query.with_entities(
                func.count(func.distinct(Report.hospital_id))
            ).scalar() or 0
            
            unique_departments = query.with_entities(
                func.count(func.distinct(Report.department_id))
            ).scalar() or 0
            
            return {
                "total_records": total,
                "total_patients": unique_patients,
                "total_hospitals": unique_hospitals,
                "total_departments": unique_departments,
            }
        
        except Exception as e:
            logger.error(f"❌ خطأ: {e}")
            return {}
        finally:
            session.close()
