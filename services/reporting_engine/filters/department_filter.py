# ================================================
# services/reporting_engine/filters/department_filter.py
# 🏢 Department Filter
# ================================================

from typing import Optional, List, Dict, Any
import logging

from db.models import Report
from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class DepartmentFilter(BaseFilter):
    """فلتر القسم"""
    
    def __init__(self, department_id: Optional[int] = None, department_ids: Optional[List[int]] = None):
        super().__init__("DepartmentFilter")
        self.department_id = department_id
        self.department_ids = department_ids or []
        
        if department_id and department_id not in self.department_ids:
            self.department_ids.append(department_id)
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return len(self.department_ids) > 0
    
    def add_department(self, department_id: int):
        """إضافة قسم"""
        if department_id not in self.department_ids:
            self.department_ids.append(department_id)
    
    def remove_department(self, department_id: int):
        """إزالة قسم"""
        if department_id in self.department_ids:
            self.department_ids.remove(department_id)
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        self.log_application()
        
        return query.filter(Report.department_id.in_(self.department_ids))
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "department",
            "department_ids": self.department_ids,
            "count": len(self.department_ids),
        }
