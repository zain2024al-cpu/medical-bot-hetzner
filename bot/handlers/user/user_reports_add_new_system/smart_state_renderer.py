# =============================
# smart_state_renderer.py
# مدير إعادة العرض الذكي للشاشات - مستخرج من الـ monolith
# =============================

import logging

from .states import STATE_SELECT_PATIENT, STATE_SELECT_DOCTOR
from .managers import PatientDataManager, DoctorDataManager

logger = logging.getLogger(__name__)


def _get_smart_nav_manager():
    from services.smart_navigation_manager import smart_nav_manager
    return smart_nav_manager


class SmartStateRenderer:
    """
    مدير ذكي لإعادة عرض الشاشات بعد الرجوع أو التعديل
    يضمن أن جميع البيانات والأسماء تظهر بشكل صحيح دائماً
    """

    @staticmethod
    async def render_patient_selection(message, context, search_query="", query=None,
                                       restore=False, update=None):
        """
        إعادة عرض شاشة اختيار المريض مع ضمان ظهور الأسماء دائماً.
        restore=True: يستعيد السياق المحفوظ.
        """
        from .patient_handlers import show_patient_selection
        logger.info("🎯 Rendering patient selection with FRESH data")

        PatientDataManager.clear_patient_data(context)
        _get_smart_nav_manager().set_search_context('patient')
        context.user_data['_current_search_type'] = 'patient'
        context.user_data['_conversation_state'] = STATE_SELECT_PATIENT

        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}
        context.user_data['report_tmp']['_patient_data_fresh'] = True

        logger.info("✅ Patient selection fully refreshed and ready")
        await show_patient_selection(message, context, search_query,
                                     query=query, restore=restore, update=update)

    @staticmethod
    async def render_doctor_selection(message, context, search_query="", query=None):
        """Forward to modular doctor selector authority."""
        from .doctor_handlers import show_doctor_input
        context.user_data.setdefault('report_tmp', {})['_doctor_data_fresh'] = True
        context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR
        context.user_data['_current_search_type'] = 'doctor'
        await show_doctor_input(message, context, query=query)

    @staticmethod
    async def render_translator_selection(message, context, flow_type):
        """
        إعادة عرض شاشة اختيار المترجم مع ضمان ظهور الأسماء دائماً
        """
        from .flows.shared import show_translator_selection, get_translator_state
        logger.info("🎯 Rendering translator selection with FRESH data")

        if 'report_tmp' in context.user_data:
            context.user_data['report_tmp'].pop('translator_name', None)
            context.user_data['report_tmp'].pop('translator_id', None)

        translator_state = get_translator_state(flow_type)
        context.user_data['_conversation_state'] = translator_state

        if 'report_tmp' not in context.user_data:
            context.user_data['report_tmp'] = {}

        context.user_data['report_tmp']['_translator_data_fresh'] = True

        logger.info("✅ Translator selection fully refreshed and ready")
        await show_translator_selection(message, context, flow_type)

    @staticmethod
    async def ensure_search_context(context, search_type):
        """
        التأكد من أن سياق البحث صحيح ومحدث دائماً
        """
        current_type = context.user_data.get('_current_search_type')
        if current_type != search_type:
            _get_smart_nav_manager().clear_search_context()
            _get_smart_nav_manager().set_search_context(search_type)
            context.user_data['_current_search_type'] = search_type
            logger.info(f"🔄 FORCE reset search context from {current_type} to {search_type}")

    @staticmethod
    async def validate_data_consistency(context):
        """
        التحقق من تناسق البيانات وإصلاح أي مشاكل
        """
        from .flows.shared import get_translator_state
        report_tmp = context.user_data.get('report_tmp', {})
        current_state = context.user_data.get('_conversation_state')

        if current_state == STATE_SELECT_PATIENT:
            if not report_tmp.get('_patient_data_fresh'):
                logger.warning("⚠️ Patient data not fresh, forcing refresh")
                await SmartStateRenderer.ensure_search_context(context, 'patient')
                report_tmp['_patient_data_fresh'] = True

        elif current_state == STATE_SELECT_DOCTOR:
            if not report_tmp.get('_doctor_data_fresh'):
                logger.warning("⚠️ Doctor data not fresh, forcing refresh")
                await SmartStateRenderer.ensure_search_context(context, 'doctor')
                report_tmp['_doctor_data_fresh'] = True

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
        if data_type == 'all':
            PatientDataManager.clear_patient_data(context)
            DoctorDataManager.clear_doctor_data(context)
            _get_smart_nav_manager().clear_search_context()

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


__all__ = ['SmartStateRenderer']
