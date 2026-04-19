# ================================================
# bot/keyboards.py
# 🔹 لوحات الأزرار للمستخدم + الأدمن
# ================================================

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


# ✅ لوحة الأدمن الرئيسية - منظمة بشكل احترافي
def admin_main_kb():
    from bot.broadcast_control import is_broadcast_enabled
    broadcast_status = "🔴 إيقاف إرسال التقارير" if is_broadcast_enabled() else "🟢 تفعيل إرسال التقارير"
    keyboard = [
        ["➕ إضافة حالة أولية", "🖨️ طباعة التقارير"],
        ["👥 إدارة المستخدمين", "📊 تقييم المترجمين"],
        ["👑 إدارة الأدمنين", "📊 تحليل البيانات"],
        ["📅 إدارة الجدول", "🗑️ حذف التقارير"],
        ["📋 لصق تقرير جاهز"],
        ["🔄 تحديث الصفحة", broadcast_status]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)




# ✅ لوحة المستخدم الرئيسية - منظمة بشكل احترافي
def user_main_kb():
    keyboard = [
        # الصف الأول: الإضافة (الأكثر استخداماً)
        ["📝 إضافة تقرير جديد"],
        # الصف الثاني: الجدول وابدأ
        ["📅 جدول اليوم", "🚀 ابدأ"],
        # الصف الثالث: التعديل والحذف
        ["✏️ تعديل التقارير", "🗑️ حذف التقارير"]
    ]
    return ReplyKeyboardMarkup(
        keyboard, 
        resize_keyboard=True,
        one_time_keyboard=False  # يبقى مرئياً دائماً
    )

# ✅ لوحة المستخدم الجديد (بدون أزرار)
def new_user_kb():
    keyboard = [
        ["🚀 أبدا استخدام النظام"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ✅ لوحة إلغاء العملية (للتراجع أثناء المحادثة)
def cancel_kb():
    return ReplyKeyboardMarkup([["❌ إلغاء العملية الحالية"]], resize_keyboard=True)


# ✅ لوحة زر /start الثابت (يظهر دائماً في أسفل الشاشة)
def start_persistent_kb():
    """
    لوحة مفاتيح ثابتة مع زر /start فقط
    - يظهر دائماً في أسفل الشاشة
    - لا يختفي بعد الاستخدام (one_time_keyboard=False)
    """
    keyboard = [
        ["/start"]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False  # يبقى مرئياً دائماً
    )


# ================================================
# 🎨 Inline Keyboards - أزرار احترافية مضمنة
# ================================================

# ✅ القائمة الرئيسية للمستخدم (Inline)
def user_main_inline_kb():
    """
    لوحة مستخدم احترافية بأزرار مضمنة
    - تظهر وتختفي حسب الحاجة
    - لا تأخذ مساحة دائمة
    - أكثر مرونة واحترافية
    """
    keyboard = [
        # الصف الأول
        [
            InlineKeyboardButton("⚡ تقاريري اليوم", callback_data="user_action:my_today"),
            InlineKeyboardButton("📝 إضافة تقرير", callback_data="user_action:add_report"),
        ],
        # الصف الثاني: العمليات الأساسية
        [
            InlineKeyboardButton("✏️ تعديل", callback_data="user_action:edit"),
            InlineKeyboardButton("📅 جدول اليوم", callback_data="user_action:schedule"),
        ],
        # الصف الثالث: الإحصائيات والسجل
        [
            InlineKeyboardButton("📊 إحصائياتي", callback_data="user_action:my_stats"),
            InlineKeyboardButton("📜 السجل", callback_data="user_action:history"),
        ],
        # الصف الرابع: المساعدة والتحديث
        [
            InlineKeyboardButton("ℹ️ مساعدة", callback_data="user_action:help"),
            InlineKeyboardButton("🔄 تحديث", callback_data="user_action:refresh"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ القائمة المصغرة للمستخدم (Inline)
def user_compact_inline_kb():
    """قائمة مختصرة للاستخدام السريع"""
    keyboard = [
        [
            InlineKeyboardButton("⚡ تقاريري اليوم", callback_data="user_action:my_today"),
            InlineKeyboardButton("📊 إحصائياتي", callback_data="user_action:my_stats")
        ],
        [
            InlineKeyboardButton("📋 القائمة الكاملة", callback_data="user_action:full_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ قائمة بالأقسام (Categories)
def user_categories_menu():
    """قائمة منظمة بالفئات"""
    keyboard = [
        [InlineKeyboardButton("📝 إدارة التقارير", callback_data="category:reports")],
        [InlineKeyboardButton("📊 الإحصائيات والتحليلات", callback_data="category:analytics")],
        [InlineKeyboardButton("⚙️ الإعدادات والمساعدة", callback_data="category:settings")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ قائمة فرعية: إدارة التقارير
def reports_submenu():
    """قائمة فرعية لإدارة التقارير"""
    keyboard = [
        [InlineKeyboardButton("➕ إضافة تقرير جديد", callback_data="user_action:add_report")],
        [InlineKeyboardButton("✏️ تعديل تقارير اليوم", callback_data="user_action:edit")],
        [InlineKeyboardButton("📜 سجل تقاريري", callback_data="user_action:history")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="user_action:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ قائمة فرعية: الإحصائيات
def analytics_submenu():
    """قائمة فرعية للإحصائيات"""
    keyboard = [
        [InlineKeyboardButton("📊 إحصائياتي الشاملة", callback_data="user_action:my_stats")],
        [InlineKeyboardButton("📅 تقارير اليوم", callback_data="user_action:my_today")],
        [InlineKeyboardButton("📈 تقارير الأسبوع", callback_data="user_action:my_week")],
        [InlineKeyboardButton("📆 تقارير الشهر", callback_data="user_action:my_month")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="user_action:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ قائمة فرعية: الإعدادات
def settings_submenu():
    """قائمة فرعية للإعدادات"""
    keyboard = [
        [InlineKeyboardButton("📅 جدول اليوم", callback_data="user_action:schedule")],
        [InlineKeyboardButton("ℹ️ مساعدة", callback_data="user_action:help")],
        [InlineKeyboardButton("🔄 تحديث الصفحة", callback_data="user_action:refresh")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="user_action:back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ قائمة إدارة مجموعة التقارير
def reports_group_management_kb():
    """قائمة إدارة مجموعة التقارير"""
    keyboard = [
        [InlineKeyboardButton("📋 إعداد المجموعة", callback_data="group:setup")],
        [InlineKeyboardButton("🔗 إرسال دعوات", callback_data="group:invite")],
        [InlineKeyboardButton("📊 حالة المجموعة", callback_data="group:status")],
        [InlineKeyboardButton("⚙️ إعدادات البث", callback_data="group:settings")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin:back")]
    ]
    return InlineKeyboardMarkup(keyboard)
