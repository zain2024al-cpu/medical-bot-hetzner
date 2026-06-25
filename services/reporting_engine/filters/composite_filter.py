# ================================================
# services/reporting_engine/filters/composite_filter.py
# 🔗 Composite Filter - دمج الفلاتر
# ================================================

from typing import Dict, List, Any, Optional
import logging

from .base_filter import BaseFilter

logger = logging.getLogger(__name__)


class CompositeFilter:
    """
    دمج عدة فلاتر معاً
    
    يسمح بتطبيق عدة فلاتر على نفس الاستعلام
    """
    
    def __init__(self):
        self.filters: Dict[str, BaseFilter] = {}
    
    def add(self, name: str, filter: BaseFilter):
        """إضافة فلتر"""
        if not isinstance(filter, BaseFilter):
            raise TypeError(f"الفلتر يجب أن يكون من نوع BaseFilter")
        
        self.filters[name] = filter
        logger.info(f"✅ إضافة فلتر: {name}")
    
    def remove(self, name: str):
        """إزالة فلتر"""
        if name in self.filters:
            del self.filters[name]
            logger.info(f"✅ إزالة فلتر: {name}")
    
    def get(self, name: str) -> Optional[BaseFilter]:
        """الحصول على فلتر بالاسم"""
        return self.filters.get(name)
    
    def apply(self, query):
        """
        تطبيق جميع الفلاتر الفعالة على الاستعلام
        
        Args:
            query: SQLAlchemy query object
            
        Returns:
            Modified query object
        """
        active_filters = [f for f in self.filters.values() if f.is_active()]
        
        if not active_filters:
            logger.info("⚠️ لا توجد فلاتر فعالة")
            return query
        
        logger.info(f"🔍 تطبيق {len(active_filters)} من الفلاتر الفعالة")
        
        for filter in active_filters:
            query = filter.apply(query)
        
        return query
    
    def is_empty(self) -> bool:
        """هل لا توجد فلاتر على الإطلاق؟"""
        return len(self.filters) == 0
    
    def has_active_filters(self) -> bool:
        """هل توجد فلاتر فعالة؟"""
        return any(f.is_active() for f in self.filters.values())
    
    def get_active_filters(self) -> List[str]:
        """الحصول على أسماء الفلاتر الفعالة"""
        return [name for name, f in self.filters.items() if f.is_active()]
    
    def clear(self):
        """مسح جميع الفلاتر"""
        self.filters.clear()
        logger.info("✅ تم مسح جميع الفلاتر")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        تحويل جميع الفلاتر إلى قاموس
        
        Returns:
            dict with all filters
        """
        return {
            name: filter.to_dict()
            for name, filter in self.filters.items()
            if filter.is_active()
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """الحصول على ملخص الفلاتر"""
        active = self.get_active_filters()
        
        return {
            "total_filters": len(self.filters),
            "active_filters": len(active),
            "active_filter_names": active,
            "filters": self.to_dict(),
        }
