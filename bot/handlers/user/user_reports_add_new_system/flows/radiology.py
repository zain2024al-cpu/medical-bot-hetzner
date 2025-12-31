# =============================
# flows/radiology.py
# مسار أشعة وفحوصات - RADIOLOGY FLOW
# =============================

import logging
from ._import_helper import load_original_module

logger = logging.getLogger(__name__)

# استيراد من الملف الأصلي مؤقتاً حتى يتم نقل جميع الدوال
_module = load_original_module()

if _module:
    start_radiology_flow = getattr(_module, 'start_radiology_flow', None)
    handle_radiology_type = getattr(_module, 'handle_radiology_type', None)
    handle_radiology_delivery_date_text = getattr(_module, 'handle_radiology_delivery_date_text', None)
else:
    # Fallback stubs
    async def start_radiology_flow(message, context):
        logger.error("start_radiology_flow not available")
        return None
    
    handle_radiology_type = handle_radiology_delivery_date_text = start_radiology_flow

__all__ = [
    'start_radiology_flow',
    'handle_radiology_type',
    'handle_radiology_delivery_date_text',
]

