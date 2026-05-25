# ================================================
# bot/handlers_registry.py
# 🔹 تسجيل جميع الهاندلرز (Handlers) بشكل منظم
# ================================================

def register_all_handlers(app):
    """
    تسجيل جميع الهاندلرز في التطبيق
    """

    # ── Platform bootstrap (must be first) ───────────────────────────────────
    # Registers all modules with the core registry so the interrupt interceptor
    # and routing system have the full module+button map at startup.
    from core.modules_bootstrap import bootstrap_all
    bootstrap_all()

    # ── Upload message capture (group -1, before ConversationHandlers) ────────
    from shared.uploads import collector as uploads
    uploads.register_handler(app)

    # 🔄 مقاطعة التدفق التلقائية (group=-2، قبل جميع ConversationHandlers)
    from bot.handlers.shared.flow_interrupt import register as register_flow_interrupt
    register_flow_interrupt(app)

    # 🔄 تسجيل handlers المشتركة (للجميع) - يجب أن تكون أولاً
    from bot.handlers.shared.shared_refresh import register as register_shared_refresh
    from bot.handlers.shared.shared_schedule import register as register_shared_schedule
    register_shared_refresh(app)
    register_shared_schedule(app)
    
    # 🔸 تسجيل handlers الأدمن المتخصصة (يجب تسجيل ConversationHandlers قبل admin_start)
    from bot.handlers.admin.admin_schedule_management import register as register_schedule_management
    from bot.handlers.admin.admin_evaluation import register as register_evaluation
    from bot.handlers.admin.admin_admins import register as register_admin_admins
    from bot.handlers.admin.admin_module_access import register as register_module_access
    register_schedule_management(app)
    register_evaluation(app)  # ✅ تسجيل ConversationHandler قبل admin_start
    register_admin_admins(app)  # ✅ إدارة الأدمنين - قبل admin_start لالتقاط admin:manage_admins
    register_module_access(app)  # ✅ إدارة الوصول للوحدات (amod:*)
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

    # ✅ إدارة المستخدمين للأدمن (يجب أن تكون مسجلة حتى تعمل callbacks الخاصة بها)
    register_users_management(app)
    
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

    # 📎 المرفقات الطبية
    from bot.handlers.user.user_medical_attachments import register as register_medical_attachments
    register_medical_attachments(app)

    # 📋 ملخص الحالة
    from bot.handlers.user.user_case_summary import register as register_case_summary
    register_case_summary(app)
    # register_schedule_view(app)  # تم تعطيله - استخدم shared_schedule بدلاً منه
    
    # ── Healthcare module (group 0: menu + notes text; group 1: wca/hc callbacks)
    # Registered AFTER all ConversationHandlers so the notes MessageHandler
    # is a lower-priority fallback within group 0.
    from modules.healthcare.routing import register_all as register_healthcare
    register_healthcare(app)

    # ── General Services module (groups 10-15: text/photo/callback handlers)
    from modules.general_services.routing import register_all as register_general_services
    register_general_services(app)

    # ── Shared selector/upload callback handlers (group 1) ────────────────────
    # Must be registered after ConversationHandlers and healthcare so group 1
    # gets a clean slot for msel:* / sel_pat:* / upl:* callbacks.
    from shared.selectors.patient_selector import selector as patient_selector
    from shared.multiselect import engine as multiselect
    patient_selector.register_handler(app)
    multiselect.register_handler(app)
    # Note: uploads.register_handler() already called above (group -1 msg + group 1 cb)

    # 🛡️ Universal Fallback - يجب أن يكون آخر شيء يتم تسجيله
    # يتعامل مع جميع الأزرار والرسائل غير المعالجة لمنع تعليق البوت
    from bot.handlers.shared.universal_fallback import register as register_universal_fallback
    register_universal_fallback(app)  # ✅ Fallback شامل (group=999)