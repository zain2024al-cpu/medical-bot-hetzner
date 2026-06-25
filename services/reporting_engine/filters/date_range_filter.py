# ================================================
# services/reporting_engine/filters/date_range_filter.py
# 📅 Date Range Filter
# ================================================

from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, Tuple
import logging

from db.models import Report
from .base_filter import BaseFilter
from shared.report_constants import DateRangePreset

logger = logging.getLogger(__name__)


class DateRangeFilter(BaseFilter):
    """فلتر الفترة الزمنية"""
    
    def __init__(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        preset: Optional[DateRangePreset] = None,
    ):
        super().__init__("DateRangeFilter")
        self.start_date = start_date
        self.end_date = end_date
        self.preset = preset
        
        # معالجة Preset
        if preset:
            self.start_date, self.end_date = self._get_preset_dates(preset)
    
    @staticmethod
    def _get_preset_dates(preset: DateRangePreset) -> Tuple[date, date]:
        """حساب التواريخ بناءً على Preset"""
        now = datetime.now()
        today = now.date()
        
        if preset == DateRangePreset.LAST_WEEK:
            start = today - timedelta(days=7)
            end = today
        elif preset == DateRangePreset.LAST_MONTH:
            start = today - timedelta(days=30)
            end = today
        elif preset == DateRangePreset.LAST_3_MONTHS:
            start = today - timedelta(days=90)
            end = today
        elif preset == DateRangePreset.LAST_6_MONTHS:
            start = today - timedelta(days=180)
            end = today
        elif preset == DateRangePreset.THIS_YEAR:
            start = date(today.year, 1, 1)
            end = today
        elif preset == DateRangePreset.LAST_YEAR:
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
        elif preset == DateRangePreset.ALL_TIME:
            start = date(2000, 1, 1)
            end = today
        else:
            start = today - timedelta(days=30)
            end = today
        
        return start, end
    
    def is_active(self) -> bool:
        """هل الفلتر فعال؟"""
        return self.start_date is not None and self.end_date is not None
    
    def validate(self) -> bool:
        """التحقق من صحة الفلتر"""
        if not self.is_active():
            return True
        
        if self.start_date > self.end_date:
            logger.warning("⚠️ تاريخ البداية أكبر من تاريخ النهاية")
            return False
        
        return True
    
    def apply(self, query):
        """تطبيق الفلتر على الاستعلام"""
        if not self.is_active():
            return query
        
        if not self.validate():
            logger.error("❌ فلتر غير صحيح")
            return query
        
        # تحويل التواريخ إلى datetime
        start_dt = datetime.combine(self.start_date, datetime.min.time())
        end_dt = datetime.combine(self.end_date, datetime.max.time())
        
        self.log_application()
        
        return query.filter(
            Report.report_date >= start_dt,
            Report.report_date <= end_dt
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """تحويل إلى قاموس"""
        return {
            "type": "date_range",
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "preset": self.preset.value if self.preset else None,
        }
