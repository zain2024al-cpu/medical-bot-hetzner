# ================================================
# services/smart_navigation_manager.py
# 🔹 مدير التنقل الذكي بين الخطوات
# ================================================

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SmartNavigationManager:
    """
    مدير ذكي للتنقل بين خطوات إنشاء التقارير
    """

    # خرائط التدفق لكل نوع تقرير
    FLOW_MAPS = {
        'new_consult': {
            'select_action': 'R_ACTION_TYPE',
            'R_ACTION_TYPE': 'select_patient',
            'select_patient': 'select_hospital',
            'select_hospital': 'select_department',
            'select_department': 'select_doctor',
            'select_doctor': 'select_translator',
            'select_translator': 'enter_complaint',
            'enter_complaint': 'enter_diagnosis',
            'enter_diagnosis': 'enter_medications',
            'enter_medications': 'enter_notes',
            'enter_notes': 'confirm_report'
        },
        'emergency': {
            'select_action': 'R_ACTION_TYPE',
            'R_ACTION_TYPE': 'select_patient',
            'select_patient': 'select_hospital',
            'select_hospital': 'select_department',
            'select_department': 'select_doctor',
            'select_doctor': 'select_translator',
            'select_translator': 'emergency_status',
            'emergency_status': 'emergency_admission',
            'emergency_admission': 'enter_complaint',
            'enter_complaint': 'enter_diagnosis',
            'enter_diagnosis': 'enter_medications',
            'enter_medications': 'enter_notes',
            'enter_notes': 'confirm_report'
        },
        'followup': {
            'select_action': 'R_ACTION_TYPE',
            'R_ACTION_TYPE': 'select_patient',
            'select_patient': 'select_hospital',
            'select_hospital': 'select_department',
            'select_department': 'select_doctor',
            'select_doctor': 'select_translator',
            'select_translator': 'followup_date',
            'followup_date': 'enter_complaint',
            'enter_complaint': 'enter_diagnosis',
            'enter_diagnosis': 'enter_medications',
            'enter_medications': 'enter_notes',
            'enter_notes': 'confirm_report'
        }
    }

    @staticmethod
    def get_previous_step(flow_type: str, current_step: str, context=None) -> Optional[str]:
        """
        الحصول على الخطوة السابقة في التدفق
        """
        if flow_type not in SmartNavigationManager.FLOW_MAPS:
            logger.warning(f"Unknown flow type: {flow_type}")
            return None

        flow_map = SmartNavigationManager.FLOW_MAPS[flow_type]

        # البحث عن الخطوة الحالية في القيم
        for step_name, step_value in flow_map.items():
            if step_value == current_step:
                return step_name

        logger.warning(f"Current step '{current_step}' not found in flow '{flow_type}'")
        return None

    @staticmethod
    def get_next_step(flow_type: str, current_step: str) -> Optional[str]:
        """
        الحصول على الخطوة التالية في التدفق
        """
        if flow_type not in SmartNavigationManager.FLOW_MAPS:
            logger.warning(f"Unknown flow type: {flow_type}")
            return None

        flow_map = SmartNavigationManager.FLOW_MAPS[flow_type]

        if current_step in flow_map:
            return flow_map[current_step]

        logger.warning(f"Current step '{current_step}' not found in flow '{flow_type}'")
        return None

    @staticmethod
    def get_search_context() -> Dict[str, Any]:
        """
        الحصول على سياق البحث الحالي
        """
        # هذه دالة مؤقتة - سيتم تطويرها لاحقاً
        return {}

    @staticmethod
    def set_search_context(search_type, query=None):
        pass

    @staticmethod
    def clear_search_context():
        pass

    @staticmethod
    def validate_flow_transition(flow_type: str, from_step: str, to_step: str) -> bool:
        """
        التحقق من صحة الانتقال بين الخطوات
        """
        expected_next = SmartNavigationManager.get_next_step(flow_type, from_step)
        return expected_next == to_step

    @staticmethod
    def get_flow_progress(flow_type: str, current_step: str) -> tuple[int, int]:
        """
        الحصول على تقدم التدفق (الخطوة الحالية، إجمالي الخطوات)
        """
        if flow_type not in SmartNavigationManager.FLOW_MAPS:
            return 0, 0

        flow_map = SmartNavigationManager.FLOW_MAPS[flow_type]

        # حساب عدد الخطوات الإجمالية
        total_steps = len(flow_map)

        # حساب الخطوة الحالية
        current_step_index = 0
        for i, (step_name, step_value) in enumerate(flow_map.items(), 1):
            if step_value == current_step:
                current_step_index = i
                break

        return current_step_index, total_steps

    @staticmethod
    def get_step_description(flow_type: str, step: str) -> str:
        """
        الحصول على وصف الخطوة باللغة العربية
        """
        step_descriptions = {
            'select_action': 'اختيار نوع الإجراء',
            'R_ACTION_TYPE': 'اختيار نوع الإجراء',
            'select_patient': 'اختيار اسم المريض',
            'select_hospital': 'اختيار المستشفى',
            'select_department': 'اختيار القسم',
            'select_doctor': 'اختيار اسم الطبيب',
            'select_translator': 'اختيار المترجم',
            'enter_complaint': 'إدخال الشكوى',
            'enter_diagnosis': 'إدخال التشخيص',
            'enter_medications': 'إدخال الأدوية',
            'enter_notes': 'إدخال الملاحظات',
            'emergency_status': 'حالة الطوارئ',
            'emergency_admission': 'قرار الدخول',
            'followup_date': 'موعد المتابعة',
            'confirm_report': 'تأكيد التقرير'
        }

        return step_descriptions.get(step, step)

    @staticmethod
    def test_flow_maps():
        """
        اختبار صحة خرائط التدفق
        """
        print("🧪 اختبار خرائط التدفق:")

        test_cases = [
            ('new_consult', 'select_patient', 'select_hospital'),
            ('emergency', 'select_patient', 'select_hospital'),
            ('followup', 'select_patient', 'select_hospital'),
            ('new_consult', 'select_hospital', 'select_department'),
            ('new_consult', 'select_department', 'select_doctor'),
            ('new_consult', 'select_doctor', 'select_translator'),
        ]

        for flow_type, from_step, expected_to_step in test_cases:
            actual_to_step = SmartNavigationManager.get_next_step(flow_type, from_step)
            status = "✅" if actual_to_step == expected_to_step else "❌"
            print(f"  {status} {flow_type}: {from_step} → {actual_to_step} (متوقع: {expected_to_step})")

        # اختبار التقدم
        progress_tests = [
            ('new_consult', 'select_patient', (2, 12)),
            ('emergency', 'select_hospital', (3, 13)),
        ]

        print("\n📊 اختبار التقدم:")
        for flow_type, step, expected_progress in progress_tests:
            actual_progress = SmartNavigationManager.get_flow_progress(flow_type, step)
            status = "✅" if actual_progress == expected_progress else "❌"
            print(f"  {status} {flow_type} - {step}: {actual_progress} (متوقع: {expected_progress})")

        return True


smart_nav_manager = SmartNavigationManager()
