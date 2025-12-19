# =============================
# bot/keyboards.py
# 🧭 لوحات الأزرار (الإدمن والمستخدم) + أزرار عامة
# =============================

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


# ❌ زر الإلغاء (اختياري)
def cancel_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ إلغاء المحادثة")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


# 🧩 زر الإلغاء (inline)
def cancel_inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء المحادثة", callback_data="abort")]
    ])


# 🧑‍💻 لوحة المستخدم الرئيسية - تم نقلها إلى bot/keyboards.py
# استخدم: from bot.keyboards import user_main_kb


# ▶️ لوحة المستخدم الجديد (قبل القبول)
def user_welcome_kb():
    kb = [
        [KeyboardButton("▶️ ابدأ التسجيل")],
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


# 👑 لوحة الإدمن - تم نقلها إلى bot/keyboards.py
# استخدم: from bot.keyboards import admin_main_kb


# ✅❌ لوحة inline (نعم / لا)
def yes_no_inline_kb(cb_yes: str, cb_no: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ نعم", callback_data=cb_yes),
            InlineKeyboardButton("❌ لا", callback_data=cb_no)
        ]
    ])
