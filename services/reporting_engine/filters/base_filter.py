# ================================================
# services/reporting_engine/filters/base_filter.py
# 📋 Base Filter - الفلتر الأساسي
# ================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseFilter(ABC):
    """
    الفلتر الأساسي - يرث جميع الفلاتر منه
    
    كل فلتر يجب أن يطبق:
    - apply(): تطبيق الفلتر على استعلام SQLAlchemy
    - is_active(): هل الفلتر فعال
    - to_dict(): تحويل إلى قاموس
    """
    
    def __init__(self, name: str):
        self.name = name
        self._active = False
    
    @abstractmethod
    def apply(self, query):
        """
        تطبيق الفلتر على استعلام SQLAlchemy
        
        Args:
            query: SQLAlchemy query object
            
        Returns:
            Modified query object
        """
        pass
    
    @abstractmethod
    def is_active(self) -> bool:
        """
        هل الفلتر فعال ويجب تطبيقه؟
        
        Returns:
            bool
        """
        pass
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        تحويل الفلتر إلى قاموس
        
        Returns:
            dict
        """
        pass
    
    def validate(self) -> bool:
        """
        التحقق من صحة الفلتر
        
        Override في الفلاتر المشتقة إذا لزم الأمر
        
        Returns:
            bool
        """
        return True
    
    def log_application(self):
        """تسجيل تطبيق الفلتر"""
        if self.is_active():
            logger.info(f"✅ تطبيق الفلتر: {self.name}")
