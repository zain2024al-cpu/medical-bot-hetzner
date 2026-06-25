# ================================================
# services/reporting_engine/filters/translator_filter.py
# 👨‍💼 Translator Filter
# ================================================

from typing import Optional, List, Dict, Any
import logging

from db.models import Report
from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class TranslatorFilter(BaseFilter):
    """فلتر المترجم"""
    
    def __init__(self, translator_id: Optional[int] = None, translator_ids: Optional[List[int]] = None):
        super().__init__("TranslatorFilter")
        self.translator_id = translator_id
        self.translator_ids = translator_ids or []
        
        if translator_id and translator_id not in self.translator_ids:
            self.translator_ids.append(translator_id)
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return len(self.translator_ids) > 0
    
    def add_translator(self, translator_id: int):
        """إضافة مترجم"""
        if translator_id not in self.translator_ids:
            self.translator_ids.append(translator_id)
    
    def remove_translator(self, translator_id: int):
        """إزالة مترجم"""
        if translator_id in self.translator_ids:
            self.translator_ids.remove(translator_id)
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        self.log_application()
        
        return query.filter(Report.translator_id.in_(self.translator_ids))
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "translator",
            "translator_ids": self.translator_ids,
            "count": len(self.translator_ids),
        }
