#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🕐 نظام اختيار الوقت البسيط
من 8 صباحاً إلى 8 مساءً
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime


def create_simple_time_keyboard(selected_date_str, callback_prefix="followup_dt"):
    """إنشاء لوحة اختيار الوقت - من 8 ص إلى 8 م"""
    
    keyboard = []
    
    # 🌅 الصباح: 8:00 ص - 11:30 ص
    keyboard.append([
        InlineKeyboardButton("🌅 8:00 ص", callback_data=f"{callback_prefix}:time:{selected_date_str}|08:00"),
        InlineKeyboardButton("🌅 9:00 ص", callback_data=f"{callback_prefix}:time:{selected_date_str}|09:00"),
        InlineKeyboardButton("🌅 10:00 ص", callback_data=f"{callback_prefix}:time:{selected_date_str}|10:00"),
    ])
    
    keyboard.append([
        InlineKeyboardButton("🌅 10:30 ص", callback_data=f"{callback_prefix}:time:{selected_date_str}|10:30"),
        InlineKeyboardButton("🌅 11:00 ص", callback_data=f"{callback_prefix}:time:{selected_date_str}|11:00"),
        InlineKeyboardButton("🌅 11:30 ص", callback_data=f"{callback_prefix}:time:{selected_date_str}|11:30"),
    ])
    
    # ☀️ الظهر: 12:00 ظ - 1:30 ع
    keyboard.append([
        InlineKeyboardButton("☀️ 12:00 ظ", callback_data=f"{callback_prefix}:time:{selected_date_str}|12:00"),
        InlineKeyboardButton("☀️ 12:30 ظ", callback_data=f"{callback_prefix}:time:{selected_date_str}|12:30"),
        InlineKeyboardButton("☀️ 1:00 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|13:00"),
    ])
    
    keyboard.append([
        InlineKeyboardButton("☀️ 1:30 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|13:30"),
        InlineKeyboardButton("☀️ 2:00 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|14:00"),
        InlineKeyboardButton("☀️ 2:30 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|14:30"),
    ])
    
    # 🌆 العصر: 3:00 ع - 5:30 ع
    keyboard.append([
        InlineKeyboardButton("🌆 3:00 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|15:00"),
        InlineKeyboardButton("🌆 3:30 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|15:30"),
        InlineKeyboardButton("🌆 4:00 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|16:00"),
    ])
    
    keyboard.append([
        InlineKeyboardButton("🌆 4:30 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|16:30"),
        InlineKeyboardButton("🌆 5:00 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|17:00"),
        InlineKeyboardButton("🌆 5:30 ع", callback_data=f"{callback_prefix}:time:{selected_date_str}|17:30"),
    ])
    
    # 🌃 المساء: 6:00 م - 8:00 م
    keyboard.append([
        InlineKeyboardButton("🌃 6:00 م", callback_data=f"{callback_prefix}:time:{selected_date_str}|18:00"),
        InlineKeyboardButton("🌃 6:30 م", callback_data=f"{callback_prefix}:time:{selected_date_str}|18:30"),
        InlineKeyboardButton("🌃 7:00 م", callback_data=f"{callback_prefix}:time:{selected_date_str}|19:00"),
    ])
    
    keyboard.append([
        InlineKeyboardButton("🌃 7:30 م", callback_data=f"{callback_prefix}:time:{selected_date_str}|19:30"),
        InlineKeyboardButton("🌃 8:00 م", callback_data=f"{callback_prefix}:time:{selected_date_str}|20:00"),
    ])
    
    # زر الآن + الرجوع
    keyboard.append([
        InlineKeyboardButton("🕐 الآن (الوقت الحالي)", callback_data=f"{callback_prefix}:time:{selected_date_str}|now")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع للتقويم", callback_data=f"{callback_prefix}:back_date")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def format_time_arabic(time_str):
    """تنسيق الوقت بالعربي"""
    try:
        if time_str == "now":
            now = datetime.now()
            hour = now.hour
            minute = now.minute
        else:
            hour, minute = map(int, time_str.split(':'))
        
        # تحويل للصيغة 12 ساعة
        if hour == 0:
            hour_12 = 12
            period = "منتصف الليل"
        elif hour < 8:
            hour_12 = hour
            period = "صباحاً"
        elif hour < 12:
            hour_12 = hour
            period = "صباحاً"
        elif hour == 12:
            hour_12 = 12
            period = "ظهراً"
        elif hour < 14:
            hour_12 = hour - 12
            period = "عصراً"
        elif hour < 18:
            hour_12 = hour - 12
            period = "عصراً"
        elif hour < 21:
            hour_12 = hour - 12
            period = "مساءً"
        else:
            hour_12 = hour - 12
            period = "ليلاً"
        
        return f"{hour_12}:{minute:02d} {period}"
        
    except Exception:
        return time_str

















