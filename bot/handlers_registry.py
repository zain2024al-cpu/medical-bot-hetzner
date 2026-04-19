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
    register_shared_refresh(app)
    register_shared_schedule(app)
    
    # 🔸 تسجيل handlers الأدمن المتخصصة (يجب تسجيل ConversationHandlers قبل admin_start)
    from bot.handlers.admin.admin_schedule_management import register as register_schedule_management
    from bot.handlers.admin.admin_evaluation import register as register_evaluation
    from bot.handlers.admin.admin_admins import register as register_admin_admins
    register_schedule_management(app)
    register_evaluation(app)  # ✅ تسجيل ConversationHandler قبل admin_start
    register_admin_admins(app)  # ✅ إدارة الأدمنين - قبل admin_start لالتقاط admin:manage_admins
    from bot.handlers.admin.admin_reports_recovery import register as register_reports_recovery
    register_reports_recovery(app)  # ✅ استعادة تقارير من .db / .json قبل admin_start
    from bot.handlers.user.user_paste_full_report import register as register_paste_full_report
    register_paste_full_report(app)  # ✅ لصق تقرير جاهز (أدمن فقط) قبل admin_start

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
    )
    from bot.handlers.admin.admin_users_management import register as register_users_management
    from bot.handlers.admin.admin_printing import register as register_admin_printing  # ✅ معالج الطباعة
    
    # ✅ تسجيل نظام الطباعة الاحترافي (يحتوي الآن على الفلترة المتقدمة مدمجة)
    register_admin_printing(app)  # ✅ نظام الطباعة الاحترافي الموحد
    
    admin_initial_case.register(app)
    # admin_reports.register(app)  # ❌ تم الدمج في admin_printing
    
    # تسجيل أمر /print_patient من admin_reports بشكل منفصل
    from bot.handlers.admin.admin_reports import handle_print_patient_command
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("print_patient", handle_print_patient_command))

    # ✅ هذه الدوال كانت تُستدعى بدون استيرادها (سبب NameError على السيرفر)
    from bot.handlers.admin.admin_daily_patients import register as register_daily_patients
    from bot.handlers.admin.admin_data_analysis import register as register_data_analysis
    from bot.handlers.admin.admin_hospitals_management import register as register_hospitals_management
    from bot.handlers.admin.admin_translators_management import register as register_translators_management
    from bot.handlers.admin.admin_delete_reports import register as register_admin_delete_reports
    from bot.handlers.admin.admin_backup_commands import register as register_admin_backup_commands

    register_daily_patients(app)  # ✅ إدارة أسماء المرضى اليومية
    register_data_analysis(app)  # ✅ نظام تحليل البيانات الشامل
    register_hospitals_management(app)  # ✅ إدارة المستشفيات
    register_translators_management(app)  # ✅ إدارة المترجمين
    register_admin_delete_reports(app)  # ✅ حذف التقارير للأدمن
    register_admin_backup_commands(app)  # ✅ أوامر /backup و /logs للأدمن
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
    
    # 🔍 نظام البحث عن المرضى باستخدام Inline Query (منفصل ومستقل)
    # ✅ تسجيله قبل user_reports_add_new_system لضمان أولوية أعلى
    from bot.handlers.user.user_patient_search_inline import register as register_patient_search_inline
    register_patient_search_inline(app)
    
    # 🆕 النظام الجديد - المرحلة 1 (استشارة جديدة، مراجعة، طوارئ، ترقيد)
    from bot.handlers.user import user_reports_add_new_system
    user_reports_add_new_system.register(app)
    
    # 🗑️ نظام حذف التقارير
    from bot.handlers.user.user_reports_delete import register as register_user_reports_delete
    register_user_reports_delete(app)
    
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
    
    # 🛡️ Universal Fallback - يجب أن يكون آخر شيء يتم تسجيله
    # يتعامل مع جميع الأزرار والرسائل غير المعالجة لمنع تعليق البوت
    from bot.handlers.shared.universal_fallback import register as register_universal_fallback
    register_universal_fallback(app)  # ✅ Fallback شامل (group=999)