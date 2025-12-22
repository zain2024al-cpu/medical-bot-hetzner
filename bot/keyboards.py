# ================================================
# bot/keyboards.py
# 🔹 لوحات الأزرار للمستخدم + الأدمن
# ================================================

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton


# ✅ لوحة الأدمن الرئيسية - منظمة بشكل احترافي
def admin_main_kb():
    keyboard = [
        # الصف الأول: الإضافة والطباعة
        ["➕ إضافة حالة أولية", "🖨️ طباعة التقارير"],
        # الصف الثاني: الإدارة والتقييم
        ["👥 إدارة المستخدمين", "📊 تقييم المترجمين"],
        # الصف الثالث: إدارة الأدمنين والتحليلات
        ["👑 إدارة الأدمنين", "📊 تحليل البيانات"],
        # الصف الرابع: الجدول والتحديث
        ["📅 إدارة الجدول", "🔄 تحديث الصفحة"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)




# ✅ لوحة المستخدم الرئيسية - منظمة بشكل احترافي
def user_main_kb():
    keyboard = [
        # الصف الأول: الإضافة (الأكثر استخداماً)
        ["📝 إضافة تقرير جديد"],
        # الصف الثاني: الجدول وابدأ
        ["📅 جدول اليوم", "🚀 ابدأ"],
        # الصف الثالث: التعديل والتقرير الأولي
        ["✏️ تعديل التقارير", "📋 التقرير الأولي للمرضى"]
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
        # الصف الأول: الإجراءات السريعة
        [
            InlineKeyboardButton("⚡ إضافة سريع", callback_data="user_action:quick_add"),
            InlineKeyboardButton("⚡ تقاريري اليوم", callback_data="user_action:my_today")
        ],
        # الصف الثاني: العمليات الأساسية
        [
            InlineKeyboardButton("📝 إضافة تقرير", callback_data="user_action:add_report"),
            InlineKeyboardButton("✏️ تعديل", callback_data="user_action:edit")
        ],
        # الصف الثالث: الجدول والإحصائيات
        [
            InlineKeyboardButton("📅 جدول اليوم", callback_data="user_action:schedule"),
            InlineKeyboardButton("📊 إحصائياتي", callback_data="user_action:my_stats")
        ],
        # الصف الرابع: السجل والمساعدة
        [
            InlineKeyboardButton("📜 السجل", callback_data="user_action:history"),
            InlineKeyboardButton("ℹ️ مساعدة", callback_data="user_action:help")
        ],
        # الصف الخامس: التقرير الأولي للمرضى
        [
            InlineKeyboardButton("📋 التقرير الأولي للمرضى", callback_data="user_action:initial_case")
        ],
        # الصف الخامس: التحديث
        [
            InlineKeyboardButton("🔄 تحديث", callback_data="user_action:refresh")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ✅ القائمة المصغرة للمستخدم (Inline)
def user_compact_inline_kb():
    """قائمة مختصرة للاستخدام السريع"""
    keyboard = [
        [
            InlineKeyboardButton("⚡ إضافة سريع", callback_data="user_action:quick_add"),
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
