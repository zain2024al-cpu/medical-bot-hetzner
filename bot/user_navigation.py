# ================================================
# bot/user_navigation.py
# 🎯 نظام التنقل الموحد لملفات المستخدم
# واجهة مبسطة لاستخدام نظام التنقل الذكي
# ================================================

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.shared_navigation import (
    SmartNavigationManager,
    NavigationRenderer,
    handle_smart_back,
    navigate_to_state,
    create_back_button,
    create_nav_buttons,
    add_back_button
)

logger = logging.getLogger(__name__)


# ================================================
# Namespaces للأنظمة المختلفة
# ================================================

class NavigationNamespace:
    """أسماء السياقات المختلفة للتنقل"""
    REPORTS = "reports"  # نظام إضافة التقارير
    INITIAL_CASE = "initial_case"  # نظام التقرير الأولي
    EDIT_REPORTS = "edit_reports"  # نظام تعديل التقارير
    SCHEDULE = "schedule"  # نظام الجدول
    DEFAULT = "default"  # النظام الافتراضي


# ================================================
# Renderer موحد لنظام التقارير
# ================================================

class ReportsNavigationRenderer(NavigationRenderer):
    """
    Renderer مخصص لنظام التقارير
    يتم تسجيل renderers من ملف user_reports_add_new_system.py
    """
    
    def __init__(self):
        super().__init__()
        self._setup_renderers()
    
    def _setup_renderers(self):
        """
        تسجيل renderers من ملف التقارير
        يتم استدعاؤها عند الحاجة لتجنب circular imports
        """
        pass  # سيتم ملؤها ديناميكياً
    
    def register_reports_renderers(self, renderers_dict: dict):
        """
        تسجيل renderers من ملف التقارير
        
        Args:
            renderers_dict: قاموس {state: (renderer_func, state_name)}
        """
        for state, (renderer_func, state_name) in renderers_dict.items():
            self.register_state(state, renderer_func, state_name)
        logger.info(f"✅ Registered {len(renderers_dict)} report renderers")


# ================================================
# دوال مساعدة للاستخدام السريع
# ================================================

def setup_reports_navigation(context: ContextTypes.DEFAULT_TYPE):
    """
    إعداد نظام التنقل لنظام التقارير
    """
    namespace = NavigationNamespace.REPORTS
    nav_manager = SmartNavigationManager.get_manager(context, namespace)
    logger.info(f"✅ Reports navigation setup complete (namespace: {namespace})")
    return nav_manager


def setup_initial_case_navigation(context: ContextTypes.DEFAULT_TYPE):
    """
    إعداد نظام التنقل لنظام التقرير الأولي
    """
    namespace = NavigationNamespace.INITIAL_CASE
    nav_manager = SmartNavigationManager.get_manager(context, namespace)
    logger.info(f"✅ Initial case navigation setup complete (namespace: {namespace})")
    return nav_manager


def go_to_state(
    context: ContextTypes.DEFAULT_TYPE,
    state: any,
    namespace: str = NavigationNamespace.REPORTS,
    state_data: dict = None
):
    """
    الانتقال إلى state جديد (دالة مختصرة)
    
    Args:
        context: Context object
        state: الـ state الجديد
        namespace: سياق التنقل
        state_data: بيانات إضافية
    """
    navigate_to_state(context, state, namespace, state_data)


def go_back(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    namespace: str = NavigationNamespace.REPORTS,
    renderer: NavigationRenderer = None,
    fallback_handler: callable = None
):
    """
    الرجوع للخطوة السابقة (دالة مختصرة)
    
    Args:
        update: Update object
        context: Context object
        namespace: سياق التنقل
        renderer: NavigationRenderer
        fallback_handler: دالة احتياطية
    """
    return handle_smart_back(update, context, namespace, renderer, fallback_handler)


def clear_navigation(context: ContextTypes.DEFAULT_TYPE, namespace: str = NavigationNamespace.REPORTS):
    """
    تنظيف تاريخ التنقل
    
    Args:
        context: Context object
        namespace: سياق التنقل
    """
    SmartNavigationManager.clear_manager(context, namespace)
    logger.info(f"✅ Cleared navigation for namespace: {namespace}")


def get_current_state(context: ContextTypes.DEFAULT_TYPE, namespace: str = NavigationNamespace.REPORTS):
    """
    الحصول على الـ state الحالي
    
    Args:
        context: Context object
        namespace: سياق التنقل
    
    Returns:
        الـ state الحالي أو None
    """
    nav_manager = SmartNavigationManager.get_manager(context, namespace)
    return nav_manager.peek_state()


def has_navigation_history(context: ContextTypes.DEFAULT_TYPE, namespace: str = NavigationNamespace.REPORTS) -> bool:
    """
    التحقق من وجود تاريخ تنقل
    
    Args:
        context: Context object
        namespace: سياق التنقل
    
    Returns:
        True إذا كان هناك تاريخ، False otherwise
    """
    nav_manager = SmartNavigationManager.get_manager(context, namespace)
    return nav_manager.has_history()


# ================================================
# دالة معالجة زر الرجوع الموحدة
# ================================================

async def handle_back_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    namespace: str = NavigationNamespace.REPORTS
):
    """
    معالج زر الرجوع الموحد
    يمكن استخدامه مباشرة في CallbackQueryHandler
    
    Usage:
        app.add_handler(CallbackQueryHandler(
            lambda u, c: handle_back_button(u, c, NavigationNamespace.REPORTS),
            pattern="^nav:back$"
        ))
    """
    return await handle_smart_back(update, context, namespace)


# ================================================
# دالة معالجة زر الإلغاء الموحدة
# ================================================

async def handle_cancel_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    namespace: str = NavigationNamespace.REPORTS
):
    """
    معالج زر الإلغاء الموحد
    ينظف جميع البيانات ويعيد للقائمة الرئيسية
    
    Usage:
        app.add_handler(CallbackQueryHandler(
            lambda u, c: handle_cancel_button(u, c, NavigationNamespace.REPORTS),
            pattern="^nav:cancel$"
        ))
    """
    query = update.callback_query
    
    if query:
        await query.answer()
    
    try:
        # تنظيف تاريخ التنقل
        clear_navigation(context, namespace)
        
        # تنظيف البيانات المؤقتة
        if "report_tmp" in context.user_data:
            context.user_data.pop("report_tmp", None)
        
        # تنظيف conversation state
        context.user_data.pop("_conversation_state", None)
        
        # تنظيف أي بيانات إضافية
        keys_to_remove = [
            "_current_search_type",
            "patient_search_mode",
            "hospitals_search_mode",
            "departments_search_mode",
            "doctor_manual_mode",
            "step_history"
        ]
        for key in keys_to_remove:
            context.user_data.pop(key, None)
        
        logger.info(f"✅ Cancelled operation and cleared navigation (namespace: {namespace})")
        
        if query:
            await query.edit_message_text(
                "❌ **تم إلغاء العملية**\n\n"
                "تم تنظيف جميع البيانات.\n"
                "يمكنك البدء من جديد.",
                parse_mode="Markdown"
            )
        elif update.message:
            await update.message.reply_text(
                "❌ **تم إلغاء العملية**\n\n"
                "تم تنظيف جميع البيانات.",
                parse_mode="Markdown"
            )
        
        return ConversationHandler.END
    
    except Exception as e:
        logger.error(f"❌ Error in handle_cancel_button: {e}", exc_info=True)
        return ConversationHandler.END





