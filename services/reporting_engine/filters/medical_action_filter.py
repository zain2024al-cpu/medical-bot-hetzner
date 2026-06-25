# ================================================
# services/reporting_engine/filters/medical_action_filter.py
# 💉 Medical Action Filter
# ================================================

from typing import Optional, List, Dict, Any
import logging

from db.models import Report
from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class MedicalActionFilter(BaseFilter):
    """فلتر نوع الإجراء الطبي"""
    
    def __init__(self, action: Optional[str] = None, actions: Optional[List[str]] = None):
        super().__init__("MedicalActionFilter")
        self.action = action
        self.actions = actions or []
        
        if action and action not in self.actions:
            self.actions.append(action)
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return len(self.actions) > 0
    
    def add_action(self, action: str):
        """إضافة إجراء"""
        if action and action not in self.actions:
            self.actions.append(action)
    
    def remove_action(self, action: str):
        """إزالة إجراء"""
        if action in self.actions:
            self.actions.remove(action)
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        self.log_application()
        
        return query.filter(Report.medical_action.in_(self.actions))
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "medical_action",
            "actions": self.actions,
            "count": len(self.actions),
        }
