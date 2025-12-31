# =============================
# flows/app_reschedule.py
# مسار تأجيل موعد - APPOINTMENT RESCHEDULE FLOW
# =============================

import logging
from ._import_helper import load_original_module

logger = logging.getLogger(__name__)

# استيراد من الملف الأصلي مؤقتاً حتى يتم نقل جميع الدوال
_module = load_original_module()

if _module:
    # قد يكون الاسم مختلفاً في الملف الأصلي
    start_appointment_reschedule_flow = getattr(_module, 'start_appointment_reschedule_flow', None)
    if start_appointment_reschedule_flow is None:
        start_appointment_reschedule_flow = getattr(_module, 'start_reschedule_flow', None)
    handle_app_reschedule_reason = getattr(_module, 'handle_app_reschedule_reason', None)
    handle_app_reschedule_return_date_text = getattr(_module, 'handle_app_reschedule_return_date_text', None)
    handle_app_reschedule_return_reason = getattr(_module, 'handle_app_reschedule_return_reason', None)
else:
    # Fallback stubs
    async def start_appointment_reschedule_flow(message, context):
        logger.error("start_appointment_reschedule_flow not available")
        return None
    
    handle_app_reschedule_reason = handle_app_reschedule_return_date_text = \
    handle_app_reschedule_return_reason = start_appointment_reschedule_flow

__all__ = [
    'start_appointment_reschedule_flow',
    'handle_app_reschedule_reason',
    'handle_app_reschedule_return_date_text',
    'handle_app_reschedule_return_reason',
]

