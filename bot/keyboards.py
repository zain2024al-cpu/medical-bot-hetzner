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
        ["📊 تحليل البيانات", "🛠️ إدارة النظام"],
        ["📊 التقييم", "🗑️ حذف التقارير"],
        ["🔄 تحديث الصفحة", broadcast_status]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)




# ✅ لوحة المستخدم الرئيسية الثابتة — احتياطية عند عدم وجود سجلات وصول
# This is the TRANSLATOR fallback keyboard only.
# Healthcare buttons are NOT included here: they appear via dynamic_user_kb()
# exclusively for users who have been granted the "healthcare" module.
def user_main_kb():
    keyboard = [
        ["📝 إضافة تقرير جديد"],
        ["✏️ تعديل التقارير", "🗑️ حذف التقارير"],
        ["📅 جدول اليوم", "🚀 ابدأ"],
        ["📋 ملخص الحالة", "📎 المرفقات الطبية"],
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def dynamic_user_kb(tg_user_id: int) -> ReplyKeyboardMarkup:
    """
    Build a per-user keyboard from the modules activated for this user.

    Module rows are assembled in registry registration order.  Falls back
    to user_main_kb() on any error so production is never disrupted.
    """
    try:
        from core.access.access_service import get_user_modules
        from core.routing.registry import registry

        modules = get_user_modules(tg_user_id)
        rows: list[list[str]] = []
        for module_key in modules:
            reg = registry.get(module_key)
            if reg and reg.keyboard_rows:
                for row in reg.keyboard_rows:
                    rows.append(list(row))

        if not rows:
            return user_main_kb()

        return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(
            f"dynamic_user_kb({tg_user_id}) error: {exc}", exc_info=True
        )
        return user_main_kb()


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
        [InlineKeyboardButton("📎 المرفقات الطبية", callback_data="user_action:medical_attachments")],
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


# ✅ لوحة الأدمن الرئيسية (Inline) — مستخدمة في admin_start.py
def admin_main_inline_kb():
    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="admin:refresh")],
        [InlineKeyboardButton("🏥 إدارة مجموعة التقارير", callback_data="admin:manage_group")],
        [InlineKeyboardButton("📊 تقرير تقييم الرعاية الصحية", callback_data="hceval:start")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_main_inline_kb_with_group():
    keyboard = [
        [InlineKeyboardButton("🔄 تحديث", callback_data="admin:refresh")],
        [InlineKeyboardButton("🏥 إدارة مجموعة التقارير", callback_data="admin:manage_group")],
        [InlineKeyboardButton("📊 تقرير تقييم الرعاية الصحية", callback_data="hceval:start")],
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
