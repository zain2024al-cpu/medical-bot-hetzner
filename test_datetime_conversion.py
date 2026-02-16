#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
اختبار تحويل التواريخ للتحقق من إصلاح خطأ SQLite DateTime
"""

from datetime import datetime, date
from zoneinfo import ZoneInfo

def to_naive_datetime(dt):
    """تحويل datetime/string إلى naive datetime"""
    if dt is None:
        return None
    
    # ✅ إذا كان نصاً، حاول تحويله إلى datetime
    if isinstance(dt, str):
        if not dt or dt.strip() == "":
            return None
        try:
            # صيغة: YYYY-MM-DD HH:MM:SS أو YYYY-MM-DD HH:MM
            if ' ' in dt:
                try:
                    return datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    try:
                        return datetime.strptime(dt, '%Y-%m-%d %H:%M')
                    except ValueError:
                        pass
            # صيغة: YYYY-MM-DD
            try:
                return datetime.strptime(dt, '%Y-%m-%d')
            except ValueError:
                pass
            # صيغة: DD/MM/YYYY
            try:
                return datetime.strptime(dt, '%d/%m/%Y')
            except ValueError:
                pass
            # صيغة: DD-MM-YYYY
            try:
                return datetime.strptime(dt, '%d-%m-%Y')
            except ValueError:
                pass
            print(f"⚠️ Could not parse date string: {dt}")
            return None
        except Exception as e:
            print(f"❌ Error parsing date string '{dt}': {e}")
            return None
    
    # ✅ إذا كان date (وليس datetime)، حوله إلى datetime
    if hasattr(dt, 'year') and not hasattr(dt, 'hour'):
        return datetime.combine(dt, datetime.min.time())
    
    # ✅ إذا كان datetime مع tzinfo، أزل tzinfo
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
    
    return dt


def test_conversions():
    """اختبار جميع أنواع التحويلات"""
    
    print("="*80)
    print("🧪 اختبار تحويل التواريخ")
    print("="*80)
    
    test_cases = [
        # (المدخل, الوصف)
        (None, "None"),
        ("", "Empty string"),
        ("2026-01-17", "YYYY-MM-DD format"),
        ("2026-01-17 14:30:00", "YYYY-MM-DD HH:MM:SS format"),
        ("2026-01-17 14:30", "YYYY-MM-DD HH:MM format"),
        ("17/01/2026", "DD/MM/YYYY format"),
        ("17-01-2026", "DD-MM-YYYY format"),
        (datetime.now(), "datetime object"),
        (datetime.now(ZoneInfo('UTC')), "datetime with tzinfo"),
        (date.today(), "date object"),
    ]
    
    all_passed = True
    
    for value, description in test_cases:
        result = to_naive_datetime(value)
        
        # تحقق من النوع
        if result is None:
            status = "✅" if value is None or value == "" else "⚠️"
            type_str = "None"
        elif isinstance(result, datetime):
            # تحقق من أنه naive (بدون tzinfo)
            if result.tzinfo is None:
                status = "✅"
            else:
                status = "❌"
                all_passed = False
            type_str = "datetime (naive)" if result.tzinfo is None else "datetime (has tzinfo!)"
        else:
            status = "❌"
            type_str = type(result).__name__
            all_passed = False
        
        print(f"{status} {description:30} | Input: {repr(value)[:40]:40} | Output: {result} ({type_str})")
    
    print("="*80)
    if all_passed:
        print("🎉 جميع الاختبارات نجحت! SQLite سيقبل جميع القيم")
    else:
        print("❌ بعض الاختبارات فشلت!")
    
    return all_passed


if __name__ == "__main__":
    test_conversions()