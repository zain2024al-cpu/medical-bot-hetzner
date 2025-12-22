# ================================================
# bot/handlers_registry.py
# 🔹 تسجيل جميع الهاندلرز (Handlers) بشكل منظم
# ================================================

def register_all_handlers(app):
    """
    تسجيل جميع الهاندلرز في التطبيق
    """
    
    # 🔄 تسجيل handlers المشتركة (للجميع) - يجب أن تكون أولاً
    from bot.handlers.shared.shared_refresh import register as register_shared_refresh
    from bot.handlers.shared.shared_schedule import register as register_shared_schedule
    from bot.handlers.shared.group_handler import register as register_group_handler
    register_shared_refresh(app)
    register_shared_schedule(app)
    register_group_handler(app)  # ✅ معالجة الرسائل في المجموعات
    
    # 🔸 تسجيل واجهة الأدمن
    from bot.handlers.admin.admin_start import register as register_admin_start
    register_admin_start(app)  # ✅ واجهة الأدمن (أمر /admin والموافقات)
    
    # 🔹 تسجيل واجهة المستخدم (الرسالة الترحيبية + القائمة الرئيسية)
    from bot.handlers.user.user_start import register as register_user_start
    register_user_start(app)
    
    # 🔸 تسجيل handlers الأدمن المتخصصة
    from bot.handlers.admin import (
        admin_initial_case,
        admin_reports,
        admin_ai,
        admin_notes,
        # admin_schedule,  # تم تعطيله - استخدم shared_schedule
        # admin_users,  # تم تعطيله - استخدم admin_users_management بدلاً منه
    )
    from bot.handlers.admin.admin_schedule_management import register as register_schedule_management
    from bot.handlers.admin.admin_evaluation import register as register_evaluation
    from bot.handlers.admin.admin_users_management import register as register_users_management
    from bot.handlers.admin.admin_admins import register as register_admin_admins
    # from bot.handlers.admin.admin_printing import register as register_admin_printing  # تم تعطيله - تداخل
    from bot.handlers.admin.admin_daily_patients import register as register_daily_patients
    from bot.handlers.admin.admin_data_analysis import register as register_data_analysis
    # تم حذف admin_patient_management
    
    admin_initial_case.register(app)
    admin_reports.register(app)  # ✅ نظام الطباعة المحدث (مع خيار القسم)
    admin_ai.register(app)
    admin_notes.register(app)
    # admin_users.register(app)  # تم تعطيله - استخدم admin_users_management بدلاً منه
    register_schedule_management(app)
    register_evaluation(app)
    register_users_management(app)  # ✅ النظام الجديد الكامل
    register_admin_admins(app)  # ✅ إدارة الأدمنين
    # register_admin_printing(app)  # ❌ تم تعطيله - تداخل مع admin_reports (نفس الزر)
    register_daily_patients(app)  # ✅ إدارة أسماء المرضى اليومية
    register_data_analysis(app)  # ✅ نظام تحليل البيانات الشامل
    # تم حذف register_patient_management - نظام بسيط

    # 🔹 تسجيل handlers المستخدم المتخصصة
    from bot.handlers.user import (
        # user_reports_add,  # تم تعطيله - استخدم user_reports_add_new_system
        user_reports_edit,
        user_reports_history,
        user_search_basic,
        user_help,
    )
    # from bot.handlers.user.user_schedule_view import register as register_schedule_view  # تم تعطيله
    
    # 🆕 النظام الجديد - المرحلة 1 (استشارة جديدة، مراجعة، طوارئ، ترقيد)
    from bot.handlers.user import user_reports_add_new_system
    user_reports_add_new_system.register(app)
    
    # 📋 التقرير الأولي للمرضى
    from bot.handlers.user.user_initial_case import register as register_initial_case
    register_initial_case(app)
    
    # 🎨 النظام الجديد - Inline Menu + Command Shortcuts (معطّل - المستخدم يفضل الأزرار الثابتة)
    # from bot.handlers.user.user_inline_menu import register as register_inline_menu
    # from bot.handlers.user.user_shortcuts import register as register_shortcuts
    # register_inline_menu(app)  # ❌ معطّل
    # register_shortcuts(app)    # ❌ معطّل
    
    # user_reports_add.register(app)  # ❌ تم تعطيل النظام القديم
    user_reports_edit.register(app)
    user_reports_history.register(app)
    user_search_basic.register(app)
    user_help.register(app)
    # register_schedule_view(app)  # تم تعطيله - استخدم shared_schedule بدلاً منه