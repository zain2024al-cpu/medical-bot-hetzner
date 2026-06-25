# ================================================
# services/reporting_engine/filters/hospital_filter.py
# 🏥 Hospital Filter
# ================================================

from typing import Optional, List, Dict, Any
import logging

from db.models import Report
from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class HospitalFilter(BaseFilter):
    """فلتر المستشفى"""
    
    def __init__(self, hospital_id: Optional[int] = None, hospital_ids: Optional[List[int]] = None):
        super().__init__("HospitalFilter")
        self.hospital_id = hospital_id
        self.hospital_ids = hospital_ids or []
        
        if hospital_id and hospital_id not in self.hospital_ids:
            self.hospital_ids.append(hospital_id)
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return len(self.hospital_ids) > 0
    
    def add_hospital(self, hospital_id: int):
        """إضافة مستشفى"""
        if hospital_id not in self.hospital_ids:
            self.hospital_ids.append(hospital_id)
    
    def remove_hospital(self, hospital_id: int):
        """إزالة مستشفى"""
        if hospital_id in self.hospital_ids:
            self.hospital_ids.remove(hospital_id)
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        self.log_application()
        
        return query.filter(Report.hospital_id.in_(self.hospital_ids))
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "hospital",
            "hospital_ids": self.hospital_ids,
            "count": len(self.hospital_ids),
        }
