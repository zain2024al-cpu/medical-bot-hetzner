# ================================================
# services/reporting_engine/filters/doctor_filter.py
# 👨‍⚕️ Doctor Filter
# ================================================

from typing import Optional, List, Dict, Any
import logging

from db.models import Report
from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class DoctorFilter(BaseFilter):
    """فلتر الطبيب"""
    
    def __init__(self, doctor_id: Optional[int] = None, doctor_ids: Optional[List[int]] = None):
        super().__init__("DoctorFilter")
        self.doctor_id = doctor_id
        self.doctor_ids = doctor_ids or []
        
        if doctor_id and doctor_id not in self.doctor_ids:
            self.doctor_ids.append(doctor_id)
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return len(self.doctor_ids) > 0
    
    def add_doctor(self, doctor_id: int):
        """إضافة طبيب"""
        if doctor_id not in self.doctor_ids:
            self.doctor_ids.append(doctor_id)
    
    def remove_doctor(self, doctor_id: int):
        """إزالة طبيب"""
        if doctor_id in self.doctor_ids:
            self.doctor_ids.remove(doctor_id)
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        self.log_application()
        
        return query.filter(Report.doctor_id.in_(self.doctor_ids))
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "doctor",
            "doctor_ids": self.doctor_ids,
            "count": len(self.doctor_ids),
        }
