# ================================================
# bot/examples/navigation_example.py
# 📚 مثال عملي على استخدام نظام زر الرجوع الذكي
# ================================================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from bot.user_navigation import (
    go_to_state,
    go_back,
    clear_navigation,
    NavigationNamespace,
    create_nav_buttons,
    create_back_button,
    add_back_button,
    handle_back_button,
    handle_cancel_button
)

# تعريف States (مثال)
STATE_START, STATE_STEP1, STATE_STEP2, STATE_STEP3 = range(4)


# ================================================
# مثال 1: استخدام بسيط
# ================================================

async def start_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء العملية - تنظيف التاريخ أولاً"""
    # تنظيف أي تاريخ سابق
    clear_navigation(context, NavigationNamespace.DEFAULT)
    
    # الانتقال للخطوة الأولى
    go_to_state(context, STATE_STEP1, NavigationNamespace.DEFAULT)
    
    # إنشاء لوحة المفاتيح مع أزرار التنقل
    keyboard = [
        [InlineKeyboardButton("الخطوة 1", callback_data="step1")],
        [InlineKeyboardButton("الخطوة 2", callback_data="step2")]
    ]
    keyboard.extend(create_nav_buttons(show_back=False, show_cancel=True))
    
    await update.message.reply_text(
        "مرحباً! اختر الخطوة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return STATE_STEP1


async def handle_step1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الخطوة 1"""
    query = update.callback_query
    await query.answer()
    
    # الانتقال للخطوة 2
    go_to_state(context, STATE_STEP2, NavigationNamespace.DEFAULT)
    
    # إنشاء لوحة المفاتيح مع زر الرجوع
    keyboard = [
        [InlineKeyboardButton("الخطوة 2", callback_data="step2")],
        [InlineKeyboardButton("الخطوة 3", callback_data="step3")]
    ]
    keyboard.extend(create_nav_buttons())
    
    await query.edit_message_text(
        "أنت في الخطوة 1\n\n"
        "اختر الخطوة التالية:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return STATE_STEP2


async def handle_step2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الخطوة 2"""
    query = update.callback_query
    await query.answer()
    
    # الانتقال للخطوة 3
    go_to_state(context, STATE_STEP3, NavigationNamespace.DEFAULT)
    
    # استخدام add_back_button لإضافة زر الرجوع
    keyboard = [
        [InlineKeyboardButton("إنهاء", callback_data="finish")]
    ]
    keyboard = add_back_button(keyboard)
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")])
    
    await query.edit_message_text(
        "أنت في الخطوة 2\n\n"
        "اختر الإجراء:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return STATE_STEP3


# ================================================
# مثال 2: استخدام مع Renderers
# ================================================

from bot.shared_navigation import NavigationRenderer, handle_smart_back

# إنشاء renderer
renderer = NavigationRenderer()

# تسجيل renderers
async def render_step1(message, context):
    keyboard = [
        [InlineKeyboardButton("الخطوة 1", callback_data="step1")]
    ]
    keyboard.extend(create_nav_buttons())
    
    await message.reply_text(
        "شاشة الخطوة 1",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def render_step2(message, context):
    keyboard = [
        [InlineKeyboardButton("الخطوة 2", callback_data="step2")]
    ]
    keyboard.extend(create_nav_buttons())
    
    await message.reply_text(
        "شاشة الخطوة 2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# تسجيل renderers
renderer.register_state(STATE_STEP1, render_step1, "الخطوة 1")
renderer.register_state(STATE_STEP2, render_step2, "الخطوة 2")


async def handle_back_with_renderer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الرجوع مع renderer"""
    return await handle_smart_back(
        update,
        context,
        namespace=NavigationNamespace.DEFAULT,
        renderer=renderer
    )


# ================================================
# مثال 3: تسجيل Handlers
# ================================================

def register_example_handlers(app):
    """تسجيل handlers مع نظام التنقل"""
    
    # ConversationHandler مع معالجة زر الرجوع
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^بدء$"), start_example)
        ],
        states={
            STATE_STEP1: [
                CallbackQueryHandler(handle_step1, pattern="^step1$"),
                CallbackQueryHandler(
                    lambda u, c: handle_back_button(u, c, NavigationNamespace.DEFAULT),
                    pattern="^nav:back$"
                ),
                CallbackQueryHandler(
                    lambda u, c: handle_cancel_button(u, c, NavigationNamespace.DEFAULT),
                    pattern="^nav:cancel$"
                )
            ],
            STATE_STEP2: [
                CallbackQueryHandler(handle_step2, pattern="^step2$"),
                CallbackQueryHandler(
                    lambda u, c: handle_back_button(u, c, NavigationNamespace.DEFAULT),
                    pattern="^nav:back$"
                ),
                CallbackQueryHandler(
                    lambda u, c: handle_cancel_button(u, c, NavigationNamespace.DEFAULT),
                    pattern="^nav:cancel$"
                )
            ],
            STATE_STEP3: [
                CallbackQueryHandler(
                    lambda u, c: handle_back_button(u, c, NavigationNamespace.DEFAULT),
                    pattern="^nav:back$"
                ),
                CallbackQueryHandler(
                    lambda u, c: handle_cancel_button(u, c, NavigationNamespace.DEFAULT),
                    pattern="^nav:cancel$"
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(
                lambda u, c: handle_cancel_button(u, c, NavigationNamespace.DEFAULT),
                pattern="^nav:cancel$"
            )
        ]
    )
    
    app.add_handler(conv_handler)


# ================================================
# مثال 4: استخدام مع namespace مختلف
# ================================================

async def start_reports_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تدفق التقارير مع namespace خاص"""
    # استخدام namespace خاص بالتقارير
    clear_navigation(context, NavigationNamespace.REPORTS)
    go_to_state(context, STATE_STEP1, NavigationNamespace.REPORTS)
    
    # ... باقي الكود


async def handle_reports_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الرجوع في نظام التقارير"""
    return await handle_back_button(update, context, NavigationNamespace.REPORTS)


# ================================================
# مثال 5: التحقق من وجود تاريخ قبل الرجوع
# ================================================

from bot.user_navigation import has_navigation_history

async def conditional_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع فقط إذا كان هناك تاريخ"""
    if has_navigation_history(context, NavigationNamespace.DEFAULT):
        return await handle_back_button(update, context, NavigationNamespace.DEFAULT)
    else:
        query = update.callback_query
        await query.answer("⚠️ لا يمكن الرجوع - أنت في البداية", show_alert=True)
        return ConversationHandler.END





