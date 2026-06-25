# ================================================
# services/reporting_engine/filters/patient_filter.py
# 👤 Patient Filter
# ================================================

from typing import Optional, List, Dict, Any
import logging

from db.models import Report
from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class PatientFilter(BaseFilter):
    """فلتر المريض"""
    
    def __init__(self, patient_id: Optional[int] = None, patient_ids: Optional[List[int]] = None):
        super().__init__("PatientFilter")
        self.patient_id = patient_id
        self.patient_ids = patient_ids or []
        
        if patient_id and patient_id not in self.patient_ids:
            self.patient_ids.append(patient_id)
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return len(self.patient_ids) > 0
    
    def add_patient(self, patient_id: int):
        """إضافة مريض"""
        if patient_id not in self.patient_ids:
            self.patient_ids.append(patient_id)
    
    def remove_patient(self, patient_id: int):
        """إزالة مريض"""
        if patient_id in self.patient_ids:
            self.patient_ids.remove(patient_id)
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        self.log_application()
        
        return query.filter(Report.patient_id.in_(self.patient_ids))
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "patient",
            "patient_ids": self.patient_ids,
            "count": len(self.patient_ids),
        }
