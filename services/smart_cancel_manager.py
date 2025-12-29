# ================================================
# services/smart_cancel_manager.py
# 🔹 مدير الإلغاء الذكي
# ================================================

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SmartCancelManager:
    """
    مدير ذكي لمعالجة عمليات الإلغاء المختلفة
    """

    @staticmethod
    def get_cancel_context(context) -> str:
        """
        تحديد سياق الإلغاء بناءً على البيانات الحالية
        """
        user_data = context.user_data

        # إذا كان في وضع تعديل مؤقت
        if user_data.get('editing_draft'):
            return 'draft_edit'

        # إذا كان في وضع تعديل تقرير موجود
        if 'current_report_data' in user_data and user_data['current_report_data']:
            return 'report_edit'

        # إذا كان هناك بيانات تقرير مؤقتة (إنشاء تقرير جديد)
        if 'report_tmp' in user_data and user_data['report_tmp']:
            return 'report_creation'

        # إذا كان في وضع بحث
        from services.smart_navigation_manager import SmartNavigationManager
        search_context = SmartNavigationManager.get_search_context()
        if search_context and search_context.get('current_search_type'):
            return 'search'

        # إلغاء عام
        return 'general'

    @staticmethod
    async def handle_contextual_cancel(update, context, cancel_context: str):
        """
        التعامل مع الإلغاء حسب السياق
        """
        if cancel_context == 'draft_edit':
            from bot.handlers.user.user_reports_add_new_system import cancel_draft_edit
            await cancel_draft_edit(update, context)

        elif cancel_context == 'report_edit':
            from bot.handlers.user.user_reports_add_new_system import cancel_report_edit
            await cancel_report_edit(update, context)

        elif cancel_context == 'report_creation':
            from bot.handlers.user.user_reports_add_new_system import cancel_report_creation
            await cancel_report_creation(update, context)

        elif cancel_context == 'search':
            from bot.handlers.user.user_reports_add_new_system import cancel_search
            await cancel_search(update, context)

        else:
            from bot.handlers.user.user_reports_add_new_system import cancel_general
            await cancel_general(update, context)

    @staticmethod
    def get_cancel_message(cancel_context: str) -> str:
        """
        الحصول على رسالة الإلغاء المناسبة للسياق
        """
        messages = {
            'draft_edit': "❌ تم إلغاء التعديل المؤقت\n\nلم يتم حفظ أي تغييرات\nيمكنك إعادة التعديل أو الحفظ الآن",
            'report_edit': "❌ تم إلغاء تعديل التقرير\n\nلم يتم حفظ أي تغييرات على التقرير الأصلي\nالعودة لقائمة التقارير...",
            'report_creation': "❌ تم إلغاء إنشاء التقرير\n\n⚠️ سيتم حذف جميع البيانات التي أدخلتها\nتأكد من حفظ أي معلومات مهمة قبل المتابعة",
            'search': "❌ تم إلغاء البحث\n\nالعدول للخطوة السابقة...",
            'general': "❌ تم إلغاء العملية بالكامل\n\n⚠️ سيتم حذف جميع البيانات والإعدادات الحالية\nيمكنك البدء من جديد في أي وقت"
        }

        return messages.get(cancel_context, messages['general'])

    @staticmethod
    def should_show_warning(cancel_context: str) -> bool:
        """
        تحديد ما إذا كان يجب عرض تحذير قبل الإلغاء
        """
        warning_contexts = ['report_creation', 'general']
        return cancel_context in warning_contexts

    @staticmethod
    def test_cancel_contexts():
        """
        اختبار تحديد السياقات المختلفة
        """
        print("🧪 اختبار تحديد سياقات الإلغاء:")

        # محاكاة context مختلفة
        test_contexts = [
            ({'editing_draft': True}, 'draft_edit'),
            ({'current_report_data': {'id': 1}}, 'report_edit'),
            ({'report_tmp': {'patient_name': 'test'}}, 'report_creation'),
            ({}, 'general')
        ]

        for user_data, expected in test_contexts:
            # محاكاة context
            class MockContext:
                def __init__(self, user_data):
                    self.user_data = user_data

            context = MockContext(user_data)
            result = SmartCancelManager.get_cancel_context(context)

            status = '✅' if result == expected else '❌'
            print(f"   {status} {user_data} → {result} (متوقع: {expected})")

        # اختبار الرسائل
        print("\n📝 اختبار رسائل الإلغاء:")
        for context_type in ['draft_edit', 'report_edit', 'report_creation', 'search', 'general']:
            message = SmartCancelManager.get_cancel_message(context_type)
            warning = SmartCancelManager.should_show_warning(context_type)
            print(f"   • {context_type}: {'تحذير' if warning else 'عادي'} - {len(message)} حرف")

        return True



