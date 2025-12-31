# =============================
# stub_flows.py
# Stub functions للمسارات - يستورد من الملفات الجديدة في flows/ (التي بدورها تستورد من الملف الأصلي)
# =============================

import logging

logger = logging.getLogger(__name__)

# استيراد من الملفات الجديدة في flows/ (التي بدورها تستورد من الملف الأصلي)
# هذا يوفر طبقة تجريدية تسمح بنقل المحتوى تدريجياً
try:
    from .new_consult import start_new_consultation_flow
    from .followup import start_followup_flow, start_periodic_followup_flow
    from .emergency import start_emergency_flow
    from .admission import start_admission_flow
    from .operation import start_operation_flow
    from .surgery_consult import start_surgery_consult_flow
    from .final_consult import start_final_consult_flow
    from .discharge import start_discharge_flow
    from .rehab import start_rehab_flow
    from .radiology import start_radiology_flow
    from .app_reschedule import start_appointment_reschedule_flow as start_reschedule_flow
    
    logger.debug("✅ Successfully imported all flow functions from flows/ modules")
except ImportError as e:
    logger.error(f"❌ Error importing flow functions from flows/ modules: {e}")
    
    # Fallback: استيراد من الملفات الفردية (التي تستخدم importlib)
    # لا حاجة لاستيراد مباشر من الملف الأصلي هنا لأن الملفات الفردية تفعل ذلك
    logger.warning("⚠️ Using fallback: flow files will load from original file via importlib")
    
    try:
        # الملفات الفردية ستحمل من الملف الأصلي تلقائياً
        # لكن إذا فشل ذلك، نستخدم stubs
        pass
    except Exception as fallback_error:
        logger.error(f"❌ Error importing from original file: {fallback_error}")
        async def stub_flow(message, context):
            logger.error("Flow functions not available - using stub")
            return None
        start_new_consultation_flow = start_followup_flow = start_periodic_followup_flow = \
        start_emergency_flow = start_admission_flow = start_operation_flow = \
        start_surgery_consult_flow = start_final_consult_flow = start_discharge_flow = \
        start_rehab_flow = start_radiology_flow = start_reschedule_flow = stub_flow

__all__ = [
    'start_new_consultation_flow',
    'start_followup_flow',
    'start_periodic_followup_flow',
    'start_emergency_flow',
    'start_admission_flow',
    'start_operation_flow',
    'start_surgery_consult_flow',
    'start_final_consult_flow',
    'start_discharge_flow',
    'start_rehab_flow',
    'start_radiology_flow',
    'start_reschedule_flow',
]
