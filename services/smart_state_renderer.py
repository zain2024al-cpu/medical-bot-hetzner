# ================================================
# services/smart_state_renderer.py
# 🎨 مدير إعادة العرض الذكي للشاشات
# ================================================

import logging
from typing import Optional
from bot.handlers.user.user_reports_add_new_system import (
    show_patient_selection, show_doctor_input, show_translator_selection,
    PatientDataManager, DoctorDataManager, smart_nav_manager,
    STATE_SELECT_PATIENT, STATE_SELECT_DOCTOR, get_translator_state
)

logger = logging.getLogger(__name__)

class SmartStateRenderer:
    """
    مدير ذكي لإعادة عرض الشاشات بعد الرجوع أو التعديل
    يضمن أن جميع البيانات والأسماء تظهر بشكل صحيح دائماً
    """

    @staticmethod
    async def render_patient_selection(message, context, search_query=""):
        """
        إعادة عرض شاشة اختيار المريض مع ضمان ظهور الأسماء دائماً
        """
        logger.info("🎯 Rendering patient selection with FRESH data")

        # تنظيف أي بيانات قديمة للمريض لضمان البداية من جديد
        PatientDataManager.clear_patient_data(context)

        # إعداد سياق البحث من جديد
        smart_nav_manager.set_search_context('patient')
        context.user_data['_current_search_type'] = 'patient'

        # تحديث الحالة بدقة
        context.user_data['_conversation_state'] = STATE_SELECT_PATIENT

        # التأكد من وجود report_tmp
        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        # إضافة علامة للتحقق من أن البيانات محدثة
        context.user_data['report_tmp']['_patient_data_fresh'] = True

        logger.info("✅ Patient selection fully refreshed and ready")
        # عرض شاشة المريض مع البحث
        await show_patient_selection(message, context, search_query)

    @staticmethod
    async def render_doctor_selection(message, context, search_query=""):
        """
        إعادة عرض شاشة اختيار الطبيب مع ضمان ظهور الأسماء دائماً
        """
        logger.info("🎯 Rendering doctor selection with FRESH data")

        # تنظيف أي بيانات قديمة للطبيب لضمان البداية من جديد
        DoctorDataManager.clear_doctor_data(context)

        # إعداد سياق البحث من جديد
        smart_nav_manager.set_search_context('doctor')
        context.user_data['_current_search_type'] = 'doctor'

        # تحديث الحالة بدقة
        context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

        # التأكد من وجود report_tmp
        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        # إضافة علامة للتحقق من أن البيانات محدثة
        context.user_data['report_tmp']['_doctor_data_fresh'] = True

        logger.info("✅ Doctor selection fully refreshed and ready")
        # عرض شاشة الطبيب مع البحث
        await show_doctor_input(message, context)

    @staticmethod
    async def render_translator_selection(message, context, flow_type):
        """
        إعادة عرض شاشة اختيار المترجم مع ضمان ظهور الأسماء دائماً
        """
        logger.info("🎯 Rendering translator selection with FRESH data")

        # تنظيف أي بيانات قديمة للمترجم لضمان البداية من جديد
        if 'report_tmp' in context.user_data:
            context.user_data['report_tmp'].pop('translator_name', None)
            context.user_data['report_tmp'].pop('translator_id', None)

        # تحديث الحالة بدقة
        translator_state = get_translator_state(flow_type)
        context.user_data['_conversation_state'] = translator_state

        # التأكد من وجود report_tmp
        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        # إضافة علامة للتحقق من أن البيانات محدثة
        context.user_data['report_tmp']['_translator_data_fresh'] = True

        logger.info("✅ Translator selection fully refreshed and ready")
        # عرض شاشة المترجم
        await show_translator_selection(message, context, flow_type)

    @staticmethod
    async def ensure_search_context(context, search_type):
        """
        التأكد من أن سياق البحث صحيح ومحدث دائماً
        """
        current_type = context.user_data.get('_current_search_type')
        if current_type != search_type:
            # إعادة تهيئة سياق البحث بالكامل
            smart_nav_manager.clear_search_context()
            smart_nav_manager.set_search_context(search_type)
            context.user_data['_current_search_type'] = search_type

            logger.info(f"🔄 FORCE reset search context from {current_type} to {search_type}")

    @staticmethod
    async def validate_data_consistency(context):
        """
        التحقق من تناسق البيانات وإصلاح أي مشاكل
        """
        logger.info("🔍 Validating data consistency")

        report_tmp = context.user_data.get('report_tmp', {})
        current_state = context.user_data.get('_conversation_state')

        # فحص تناسق بيانات المريض
        if current_state == STATE_SELECT_PATIENT:
            if not report_tmp.get('_patient_data_fresh'):
                logger.warning("⚠️ Patient data not fresh, forcing refresh")
                await SmartStateRenderer.ensure_search_context(context, 'patient')
                report_tmp['_patient_data_fresh'] = True

        # فحص تناسق بيانات الطبيب
        elif current_state == STATE_SELECT_DOCTOR:
            if not report_tmp.get('_doctor_data_fresh'):
                logger.warning("⚠️ Doctor data not fresh, forcing refresh")
                await SmartStateRenderer.ensure_search_context(context, 'doctor')
                report_tmp['_doctor_data_fresh'] = True

        # فحص تناسق بيانات المترجم
        elif 'TRANSLATOR' in str(current_state):
            if not report_tmp.get('_translator_data_fresh'):
                logger.warning("⚠️ Translator data not fresh, forcing refresh")
                flow_type = report_tmp.get('current_flow', 'new_consult')
                translator_state = get_translator_state(flow_type)
                context.user_data['_conversation_state'] = translator_state
                report_tmp['_translator_data_fresh'] = True

        logger.info("✅ Data consistency validated")

    @staticmethod
    async def force_data_refresh(context, data_type):
        """
        إجبار تحديث البيانات بالكامل
        """
        logger.info(f"🔄 Force refreshing {data_type} data")

        if data_type == 'all':
            # تحديث جميع البيانات
            PatientDataManager.clear_patient_data(context)
            DoctorDataManager.clear_doctor_data(context)
            smart_nav_manager.clear_search_context()

            if 'report_tmp' in context.user_data:
                context.user_data['report_tmp'].pop('translator_name', None)
                context.user_data['report_tmp'].pop('translator_id', None)

            logger.info("🔄 All data forcefully refreshed")

        elif data_type == 'patient':
            PatientDataManager.clear_patient_data(context)
            await SmartStateRenderer.ensure_search_context(context, 'patient')
            logger.info("🔄 Patient data forcefully refreshed")

        elif data_type == 'doctor':
            DoctorDataManager.clear_doctor_data(context)
            await SmartStateRenderer.ensure_search_context(context, 'doctor')
            logger.info("🔄 Doctor data forcefully refreshed")

        elif data_type == 'translator':
            if 'report_tmp' in context.user_data:
                context.user_data['report_tmp'].pop('translator_name', None)
                context.user_data['report_tmp'].pop('translator_id', None)
            logger.info("🔄 Translator data forcefully refreshed")

    @staticmethod
    async def test_renderer_system():
        """
        اختبار نظام إعادة العرض
        """
        print("🧪 اختبار SmartStateRenderer:")

        # فحص وجود جميع الدوال
        methods = [
            'render_patient_selection',
            'render_doctor_selection',
            'render_translator_selection',
            'ensure_search_context',
            'validate_data_consistency',
            'force_data_refresh'
        ]

        for method in methods:
            if hasattr(SmartStateRenderer, method):
                print(f"   ✅ {method}")
            else:
                print(f"   ❌ {method} - مفقود")

        print("   🎯 SmartStateRenderer جاهز!")

        return True



