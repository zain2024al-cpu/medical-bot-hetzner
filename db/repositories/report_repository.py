# ================================================
# db/repositories/report_repository.py
# 🔹 Report Repository - SQLite/SQLAlchemy Data Access
# ================================================

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_

from db.session import get_db
from db.models import Report

logger = logging.getLogger(__name__)

class ReportRepository:
    """
    Repository for Medical Reports
    
    Provides:
    - Report CRUD operations
    - Advanced filtering and search
    - Statistics and analytics
    - Date-based queries
    """
    
    # ================================================
    # CREATE
    # ================================================
    
    def create_report(self, **report_data) -> Optional[int]:
        """
        Create a new medical report
        
        Args:
            **report_data: Report information as keyword arguments
            
        Returns:
            Report ID (int) or None if failed
        """
        try:
            with get_db() as db:
                # Add metadata
                report_data["created_at"] = datetime.utcnow()
                report_data["updated_at"] = datetime.utcnow()
                
                # Ensure report_date exists (use IST local time, not UTC)
                if "report_date" not in report_data:
                    from db.models import _now_ist_naive
                    report_data["report_date"] = _now_ist_naive()
                
                report = Report(**report_data)
                db.add(report)
                db.commit()
                db.refresh(report)
                
                logger.info(f"✅ Report created: {report.id}")
                return report.id
                
        except Exception as e:
            logger.error(f"❌ Error creating report: {e}")
            return None
    
    # ================================================
    # READ
    # ================================================
    
    def get_by_id(self, report_id: int) -> Optional[Report]:
        """Get report by ID"""
        try:
            with get_db() as db:
                return db.query(Report).filter(Report.id == report_id).first()
        except Exception as e:
            logger.error(f"❌ Error getting report: {e}")
            return None
    
    def get_by_translator(self, translator_id: int, limit: int = 100) -> List[Report]:
        """Get all reports by a specific translator"""
        try:
            with get_db() as db:
                return db.query(Report).filter(
                    Report.translator_id == translator_id
                ).order_by(Report.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"❌ Error getting translator reports: {e}")
            return []
    
    def get_by_patient(self, patient_id: int, limit: int = 100) -> List[Report]:
        """Get all reports for a specific patient"""
        try:
            with get_db() as db:
                return db.query(Report).filter(
                    Report.patient_id == patient_id
                ).order_by(Report.report_date.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"❌ Error getting patient reports: {e}")
            return []
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Report]:
        """Get reports within a date range"""
        try:
            with get_db() as db:
                return db.query(Report).filter(
                    and_(
                        Report.report_date >= start_date,
                        Report.report_date <= end_date
                    )
                ).order_by(Report.report_date.desc()).all()
        except Exception as e:
            logger.error(f"❌ Error getting reports by date range: {e}")
            return []
    
    def get_today_reports(self, translator_id: Optional[int] = None) -> List[Report]:
        """Get today's reports (optionally filtered by translator)"""
        try:
            with get_db() as db:
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)
                
                query = db.query(Report).filter(
                    and_(
                        Report.report_date >= today_start,
                        Report.report_date < today_end
                    )
                )
                
                if translator_id:
                    query = query.filter(Report.translator_id == translator_id)
                
                return query.order_by(Report.created_at.desc()).all()
                
        except Exception as e:
            logger.error(f"❌ Error getting today's reports: {e}")
            return []
    
    def get_recent_reports(self, limit: int = 50) -> List[Report]:
        """Get most recent reports"""
        try:
            with get_db() as db:
                return db.query(Report).order_by(Report.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"❌ Error getting recent reports: {e}")
            return []
    
    # ================================================
    # UPDATE
    # ================================================
    
    def update_report(self, report_id: int, **update_data) -> bool:
        """Update a report"""
        try:
            with get_db() as db:
                report = db.query(Report).filter(Report.id == report_id).first()
                
                if not report:
                    logger.warning(f"⚠️ Report not found: {report_id}")
                    return False
                
                # Update fields
                for key, value in update_data.items():
                    if hasattr(report, key):
                        setattr(report, key, value)
                
                report.updated_at = datetime.utcnow()
                
                db.commit()
                logger.info(f"✅ Report updated: {report_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating report: {e}")
            return False
    
    # ================================================
    # DELETE
    # ================================================
    
    def delete_report(self, report_id: int) -> bool:
        """Delete a report"""
        try:
            with get_db() as db:
                report = db.query(Report).filter(Report.id == report_id).first()
                
                if not report:
                    logger.warning(f"⚠️ Report not found: {report_id}")
                    return False
                
                db.delete(report)
                db.commit()
                
                logger.info(f"✅ Report deleted: {report_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error deleting report: {e}")
            return False
    
    # ================================================
    # SEARCH & FILTER
    # ================================================
    
    def search_by_patient_name(self, patient_name: str, limit: int = 50) -> List[Report]:
        """Search reports by patient name"""
        try:
            with get_db() as db:
                search_pattern = f"%{patient_name}%"
                return db.query(Report).filter(
                    Report.patient_name.ilike(search_pattern)
                ).order_by(Report.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"❌ Error searching reports: {e}")
            return []
    
    def get_upcoming_followups(self, days_ahead: int = 7) -> List[Report]:
        """Get reports with upcoming follow-up appointments"""
        try:
            with get_db() as db:
                today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                future_date = today + timedelta(days=days_ahead)
                
                return db.query(Report).filter(
                    and_(
                        Report.followup_date != None,
                        Report.followup_date >= today,
                        Report.followup_date <= future_date
                    )
                ).order_by(Report.followup_date).all()
                
        except Exception as e:
            logger.error(f"❌ Error getting follow-ups: {e}")
            return []
    
    # ================================================
    # STATISTICS
    # ================================================
    
    def get_total_count(self) -> int:
        """Get total number of reports"""
        try:
            with get_db() as db:
                return db.query(Report).count()
        except Exception as e:
            logger.error(f"❌ Error counting reports: {e}")
            return 0
    
    def get_count_by_translator(self, translator_id: int) -> int:
        """Get number of reports by translator"""
        try:
            with get_db() as db:
                return db.query(Report).filter(Report.translator_id == translator_id).count()
        except Exception as e:
            return 0
    
    def get_count_by_date_range(self, start_date: datetime, end_date: datetime) -> int:
        """Get count of reports in date range"""
        try:
            with get_db() as db:
                return db.query(Report).filter(
                    and_(
                        Report.report_date >= start_date,
                        Report.report_date <= end_date
                    )
                ).count()
        except Exception as e:
            return 0


# Global instance
_report_repo = None

def get_report_repository() -> ReportRepository:
    """Get the global ReportRepository instance"""
    global _report_repo
    if _report_repo is None:
        _report_repo = ReportRepository()
    return _report_repo
