# =============================
# Edit Before Publish Handlers
# =============================
# هذا المجلد يحتوي على handlers التعديل قبل النشر
# كل flow type له ملف منفصل تماماً
# =============================

from .new_consult_edit import (
    handle_new_consult_edit_field_selection,
    handle_new_consult_edit_field_input,
)

from .followup_edit import (
    handle_followup_edit_field_selection,
    handle_followup_edit_field_input,
)

from .periodic_followup_edit import (
    handle_periodic_followup_edit_field_selection,
    handle_periodic_followup_edit_field_input,
)

from .inpatient_followup_edit import (
    handle_inpatient_followup_edit_field_selection,
    handle_inpatient_followup_edit_field_input,
)

from .emergency_edit import (
    handle_emergency_edit_field_selection,
    handle_emergency_edit_field_input,
)

from .surgery_consult_edit import (
    handle_surgery_consult_edit_field_selection,
    handle_surgery_consult_edit_field_input,
)

from .operation_edit import (
    handle_operation_edit_field_selection,
    handle_operation_edit_field_input,
)

from .final_consult_edit import (
    handle_final_consult_edit_field_selection,
    handle_final_consult_edit_field_input,
)

from .admission_edit import (
    handle_admission_edit_field_selection,
    handle_admission_edit_field_input,
)

from .discharge_edit import (
    handle_discharge_edit_field_selection,
    handle_discharge_edit_field_input,
)

from .radiology_edit import (
    handle_radiology_edit_field_selection,
    handle_radiology_edit_field_input,
)

from .appointment_reschedule_edit import (
    handle_appointment_reschedule_edit_field_selection,
    handle_appointment_reschedule_edit_field_input,
)

from .rehab_physical_edit import (
    handle_rehab_physical_edit_field_selection,
    handle_rehab_physical_edit_field_input,
)

from .rehab_device_edit import (
    handle_rehab_device_edit_field_selection,
    handle_rehab_device_edit_field_input,
)

from .radiation_therapy_edit import (
    handle_radiation_therapy_edit_field_selection,
    handle_radiation_therapy_edit_field_input,
)

__all__ = [
    # New Consult
    'handle_new_consult_edit_field_selection',
    'handle_new_consult_edit_field_input',
    
    # Followup
    'handle_followup_edit_field_selection',
    'handle_followup_edit_field_input',
    
    # Periodic Followup
    'handle_periodic_followup_edit_field_selection',
    'handle_periodic_followup_edit_field_input',
    
    # Inpatient Followup
    'handle_inpatient_followup_edit_field_selection',
    'handle_inpatient_followup_edit_field_input',
    
    # Emergency
    'handle_emergency_edit_field_selection',
    'handle_emergency_edit_field_input',
    
    # Surgery Consult
    'handle_surgery_consult_edit_field_selection',
    'handle_surgery_consult_edit_field_input',
    
    # Operation
    'handle_operation_edit_field_selection',
    'handle_operation_edit_field_input',
    
    # Final Consult
    'handle_final_consult_edit_field_selection',
    'handle_final_consult_edit_field_input',
    
    # Admission
    'handle_admission_edit_field_selection',
    'handle_admission_edit_field_input',
    
    # Discharge
    'handle_discharge_edit_field_selection',
    'handle_discharge_edit_field_input',
    
    # Radiology
    'handle_radiology_edit_field_selection',
    'handle_radiology_edit_field_input',
    
    # Appointment Reschedule
    'handle_appointment_reschedule_edit_field_selection',
    'handle_appointment_reschedule_edit_field_input',
    
    # Rehab Physical
    'handle_rehab_physical_edit_field_selection',
    'handle_rehab_physical_edit_field_input',
    
    # Rehab Device
    'handle_rehab_device_edit_field_selection',
    'handle_rehab_device_edit_field_input',
    
    # Radiation Therapy
    'handle_radiation_therapy_edit_field_selection',
    'handle_radiation_therapy_edit_field_input',
]

