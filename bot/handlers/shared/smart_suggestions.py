#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💡 اقتراحات ذكية للإجراءات الطبية
Smart Medical Procedures Suggestions
"""

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from services.medical_procedures_suggestions import (
    get_procedure_suggestions,
    get_common_procedures,
    MEDICAL_PROCEDURES
)

async def show_procedure_suggestions(
    message, 
    context: ContextTypes.DEFAULT_TYPE,
    search_query: str = ""
) -> None:
    """
    عرض اقتراحات الإجراءات الطبية
    
    Args:
        message: Telegram message
        context: Conversation context
        search_query: نص البحث (اختياري)
    """
    try:
        # الحصول على الاقتراحات
        suggestions = get_procedure_suggestions(search_query)
        
        # بناء لوحة المفاتيح
        keyboard = []
        
        # عرض أول 10 اقتراحات
        for procedure in suggestions[:10]:
            keyboard.append([
                InlineKeyboardButton(
                    f"💉 {procedure}", 
                    callback_data=f"suggest:{procedure[:50]}"  # تقصير للحد من طول callback_data
                )
            ])
        
        # أزرار إضافية
        action_row = []
        action_row.append(InlineKeyboardButton("🔍 بحث", callback_data="suggest:search"))
        action_row.append(InlineKeyboardButton("✏️ إدخال يدوي", callback_data="suggest:manual"))
        keyboard.append(action_row)
        
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="suggest:cancel")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # إرسال الرسالة
        title = "💡 **اقتراحات الإجراءات الطبية**\n\n"
        if search_query:
            title += f"🔍 البحث: {search_query}\n\n"
        title += "اختر إجراء أو ابحث:"
        
        await message.reply_text(
            title,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        print(f"❌ خطأ في show_procedure_suggestions: {e}")


async def handle_procedure_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    target_field: str = "case_status"
) -> str:
    """
    معالجة اختيار إجراء من الاقتراحات
    
    Args:
        update: Telegram update
        context: Conversation context
        target_field: الحقل المستهدف في report_tmp
    
    Returns:
        str: الإجراء المختار
    """
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "suggest:search":
        # طلب البحث
        await query.edit_message_text(
            "🔍 **بحث في الإجراءات الطبية**\n\n"
            "أدخل كلمة البحث (عربي أو إنجليزي):",
            parse_mode="Markdown"
        )
        # سيتم معالجتها في handler النص
        return "SEARCH"
    
    elif callback_data == "suggest:manual":
        # إدخال يدوي
        await query.edit_message_text(
            "✏️ **إدخال يدوي**\n\n"
            "أدخل الإجراء الطبي:",
            parse_mode="Markdown"
        )
        return "MANUAL"
    
    elif callback_data == "suggest:cancel":
        # إلغاء
        await query.edit_message_text("❌ تم الإلغاء")
        return "CANCEL"
    
    else:
        # اختيار إجراء
        procedure = callback_data.replace("suggest:", "")
        context.user_data["report_tmp"][target_field] = procedure
        
        await query.edit_message_text(
            f"✅ تم الاختيار:\n\n{procedure}",
            parse_mode="Markdown"
        )
        return procedure


# اقتراحات سريعة للشائع
QUICK_PROCEDURES = [
    "فحص سريري - Clinical Examination",
    "تحاليل دم - Blood Tests",
    "أشعة سينية - X-Ray",
    "ECG - تخطيط قلب",
    "صرف أدوية - Medication",
    "متابعة - Follow-up",
    "إدخال - Hospital Admission",
    "إخراج - Discharge",
]


def get_quick_procedure_keyboard():
    """
    لوحة مفاتيح سريعة للإجراءات الشائعة
    """
    keyboard = []
    
    for procedure in QUICK_PROCEDURES:
        keyboard.append([
            InlineKeyboardButton(
                f"⚡ {procedure.split(' - ')[0]}", 
                callback_data=f"quick:{procedure[:50]}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("💡 المزيد", callback_data="suggest:more"),
        InlineKeyboardButton("✏️ يدوي", callback_data="suggest:manual")
    ])
    
    return InlineKeyboardMarkup(keyboard)


async def show_quick_procedures(message, context: ContextTypes.DEFAULT_TYPE):
    """عرض الإجراءات السريعة الشائعة"""
    keyboard = get_quick_procedure_keyboard()
    
    await message.reply_text(
        "⚡ **إجراءات سريعة**\n\n"
        "اختر من الشائع:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
























