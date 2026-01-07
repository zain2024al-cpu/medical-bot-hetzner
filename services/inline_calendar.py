#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📅 نظام التقويم التفاعلي (Inline Calendar)
يوفر واجهة سهلة لاختيار التاريخ بدون كتابة يدوية
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import calendar

# أسماء الأيام والشهور بالعربي
# ترتيب Python weekday(): 0=الاثنين, 1=الثلاثاء, 2=الأربعاء, 3=الخميس, 4=الجمعة, 5=السبت, 6=الأحد
# calendar.monthcalendar() الافتراضي يبدأ بالاثنين
DAYS_AR = ["ن", "ث", "ر", "خ", "ج", "س", "ح"]  # الاثنين, الثلاثاء, الأربعاء, الخميس, الجمعة, السبت, الأحد
MONTHS_AR = [
    "", "يناير", "فبراير", "مارس", "إبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
]

DAYS_AR_FULL = {
    0: 'الاثنين',
    1: 'الثلاثاء', 
    2: 'الأربعاء',
    3: 'الخميس',
    4: 'الجمعة',
    5: 'السبت',
    6: 'الأحد'
}


def create_quick_date_buttons(callback_prefix="date"):
    """إنشاء أزرار التواريخ السريعة"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    three_days = today - timedelta(days=3)
    
    # أسماء الأيام
    today_name = DAYS_AR_FULL.get(today.weekday(), '')
    yesterday_name = DAYS_AR_FULL.get(yesterday.weekday(), '')
    
    # تحديد إذا كان هذا للمواعيد المستقبلية (followup) - لا نعرض التواريخ القديمة أو زر "اليوم"
    is_followup = callback_prefix.startswith("followup") or callback_prefix.startswith("followup_dt")
    
    keyboard = []
    
    # فقط إذا لم تكن موعد مستقبلي، نعرض زر "اليوم" والتواريخ القديمة
    if not is_followup:
        # دائماً نعرض "اليوم" للتقارير (وليس للمواعيد)
        keyboard.append([
            InlineKeyboardButton(
                f"📅 اليوم ({today_name})",
                callback_data=f"{callback_prefix}:quick:{today.strftime('%Y-%m-%d')}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"📅 أمس ({yesterday_name})",
                callback_data=f"{callback_prefix}:quick:{yesterday.strftime('%Y-%m-%d')}"
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                f"📅 قبل يومين",
                callback_data=f"{callback_prefix}:quick:{day_before.strftime('%Y-%m-%d')}"
            ),
            InlineKeyboardButton(
                f"📅 قبل 3 أيام",
                callback_data=f"{callback_prefix}:quick:{three_days.strftime('%Y-%m-%d')}"
            )
        ])
    
    # زر التقويم (دائماً متاح)
    keyboard.append([
        InlineKeyboardButton(
            "📆 اختيار من التقويم",
            callback_data=f"{callback_prefix}:calendar"
        )
    ])
    
    return keyboard


def create_calendar_keyboard(year=None, month=None, callback_prefix="date", allow_future=None):
    """إنشاء تقويم شهري تفاعلي
    
    Args:
        allow_future: True = فقط المستقبل، False = فقط الماضي، None = الكل
    """
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    # تحديد تلقائي: followup = مستقبل، date = ماضي
    if allow_future is None:
        allow_future = callback_prefix.startswith("followup")
    
    # عنوان الشهر
    month_name = MONTHS_AR[month]
    header = f"📅 {month_name} {year}"
    
    keyboard = []
    
    # الصف الأول: أزرار التنقل
    nav_row = []
    if month > 1 or year > now.year - 5:
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        nav_row.append(
            InlineKeyboardButton("◀️", callback_data=f"{callback_prefix}:month:{prev_year}-{prev_month}")
        )
    
    nav_row.append(
        InlineKeyboardButton(header, callback_data="noop")
    )
    
    if month < 12 or year < now.year + 1:
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        nav_row.append(
            InlineKeyboardButton("▶️", callback_data=f"{callback_prefix}:month:{next_year}-{next_month}")
        )
    
    keyboard.append(nav_row)
    
    # الصف الثاني: أيام الأسبوع
    keyboard.append([InlineKeyboardButton(day, callback_data="noop") for day in DAYS_AR])
    
    # أيام الشهر
    cal = calendar.monthcalendar(year, month)
    
    for week in cal:
        week_buttons = []
        for day in week:
            if day == 0:
                week_buttons.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                
                # تحديد إذا كان التاريخ قابل للاختيار
                is_clickable = True
                if allow_future is True:
                    # للمواعيد المستقبلية: فقط من اليوم وما بعد
                    is_clickable = date_obj >= now.date()
                elif allow_future is False:
                    # للتقارير: فقط حتى اليوم
                    is_clickable = date_obj <= now.date()
                # إذا allow_future = None: كل التواريخ قابلة للضغط
                
                if not is_clickable:
                    week_buttons.append(InlineKeyboardButton(f"·{day}·", callback_data="noop"))
                else:
                    week_buttons.append(
                        InlineKeyboardButton(
                            str(day),
                            callback_data=f"{callback_prefix}:select:{date_str}"
                        )
                    )
        keyboard.append(week_buttons)
    
    # زر الرجوع
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع للخيارات السريعة", callback_data=f"{callback_prefix}:back_quick")
    ])
    
    return keyboard


def create_date_selection_keyboard(callback_prefix="date", show_cancel=True):
    """إنشاء لوحة اختيار التاريخ الكاملة"""
    keyboard = create_quick_date_buttons(callback_prefix)
    
    if show_cancel:
        keyboard.append([
            InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
        ])
    
    return InlineKeyboardMarkup(keyboard)


def format_date_arabic(date_obj):
    """تنسيق التاريخ بالعربي"""
    if not date_obj:
        return "—"
    
    day_name = DAYS_AR_FULL.get(date_obj.weekday(), '')
    month_name = MONTHS_AR[date_obj.month]
    
    return f"{date_obj.day} {month_name} {date_obj.year} ({day_name})"


def parse_date_callback(callback_data):
    """
    تحليل callback_data للتاريخ
    
    Returns:
        tuple: (action, date_str or None)
        
    Examples:
        "date:quick:2024-11-05" → ("quick", "2024-11-05")
        "date:calendar" → ("calendar", None)
        "date:select:2024-11-05" → ("select", "2024-11-05")
        "date:month:2024-11" → ("month", "2024-11")
    """
    parts = callback_data.split(":", 2)
    
    if len(parts) < 2:
        return None, None
    
    action = parts[1]
    data = parts[2] if len(parts) > 2 else None
    
    return action, data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧪 اختبار
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    print("="*70)
    print("📅 اختبار نظام التقويم")
    print("="*70)
    
    # اختبار 1: الأزرار السريعة
    print("\n1️⃣ الأزرار السريعة:")
    quick_buttons = create_quick_date_buttons()
    for row in quick_buttons:
        for btn in row:
            print(f"   {btn.text} → {btn.callback_data}")
    
    # اختبار 2: التقويم
    print("\n2️⃣ التقويم:")
    cal_keyboard = create_calendar_keyboard()
    for row in cal_keyboard[:3]:
        print("   " + " | ".join([btn.text for btn in row]))
    
    # اختبار 3: تنسيق التاريخ
    print("\n3️⃣ تنسيق التاريخ:")
    test_date = datetime.now().date()
    print(f"   {test_date} → {format_date_arabic(test_date)}")
    
    print("\n" + "="*70)
    print("✅ اكتمل الاختبار")

