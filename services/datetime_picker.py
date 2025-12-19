#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅🕐 نظام اختيار التاريخ والوقت التفاعلي
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
from services.inline_calendar import (
    create_quick_date_buttons,
    create_calendar_keyboard,
    format_date_arabic,
    DAYS_AR_FULL
)


def create_datetime_picker_keyboard(callback_prefix="datetime", show_cancel=True):
    """إنشاء لوحة اختيار التاريخ والوقت"""
    keyboard = create_quick_date_buttons(callback_prefix)
    
    if show_cancel:
        keyboard.append([
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ])
    
    return InlineKeyboardMarkup(keyboard)


def create_time_selection_keyboard(selected_date_str, callback_prefix="datetime"):
    """إنشاء أزرار اختيار الوقت"""
    
    # أوقات شائعة
    common_times = [
        ("🌅 صباحاً 9:00", "09:00"),
        ("☀️ ظهراً 12:00", "12:00"),
        ("🌆 عصراً 3:00", "15:00"),
        ("🌃 مساءً 6:00", "18:00"),
    ]
    
    keyboard = []
    
    # صف الأوقات الشائعة (صفين)
    row1 = [
        InlineKeyboardButton(
            common_times[0][0],
            callback_data=f"{callback_prefix}:time:{selected_date_str}|{common_times[0][1]}"
        ),
        InlineKeyboardButton(
            common_times[1][0],
            callback_data=f"{callback_prefix}:time:{selected_date_str}|{common_times[1][1]}"
        )
    ]
    
    row2 = [
        InlineKeyboardButton(
            common_times[2][0],
            callback_data=f"{callback_prefix}:time:{selected_date_str}|{common_times[2][1]}"
        ),
        InlineKeyboardButton(
            common_times[3][0],
            callback_data=f"{callback_prefix}:time:{selected_date_str}|{common_times[3][1]}"
        )
    ]
    
    keyboard.append(row1)
    keyboard.append(row2)
    
    # أوقات إضافية
    keyboard.append([
        InlineKeyboardButton(
            "🕐 الآن",
            callback_data=f"{callback_prefix}:time:{selected_date_str}|now"
        )
    ])
    
    # زر الرجوع
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع للتاريخ", callback_data=f"{callback_prefix}:back_date")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def parse_datetime_callback(callback_data):
    """
    تحليل callback_data للتاريخ والوقت
    
    Returns:
        tuple: (action, data)
    """
    parts = callback_data.split(":", 2)
    
    if len(parts) < 2:
        return None, None
    
    action = parts[1]
    data = parts[2] if len(parts) > 2 else None
    
    return action, data


def format_datetime_arabic(dt):
    """تنسيق التاريخ والوقت بالعربي"""
    if not dt:
        return "—"
    
    day_name = DAYS_AR_FULL.get(dt.weekday(), '')
    
    # تنسيق الوقت
    hour = dt.hour
    minute = dt.minute
    
    # تحديد الفترة
    if hour < 12:
        period = "صباحاً"
    elif hour < 17:
        period = "ظهراً"
    else:
        period = "مساءً"
    
    # تحويل إلى 12 ساعة
    display_hour = hour if hour <= 12 else hour - 12
    if display_hour == 0:
        display_hour = 12
    
    time_str = f"{display_hour}:{minute:02d} {period}"
    
    return f"{dt.day}/{dt.month}/{dt.year} ({day_name}) الساعة {time_str}"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧪 اختبار
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    print("="*70)
    print("📅🕐 اختبار نظام التاريخ والوقت")
    print("="*70)
    
    # اختبار التنسيق
    test_dt = datetime.now()
    print(f"\n✅ {test_dt}")
    print(f"   → {format_datetime_arabic(test_dt)}")
    
    print("\n" + "="*70)

















