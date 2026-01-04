# خطة تقسيم الملف الأصلي بالكامل

## الهدف
استغناء كامل عن الملف الأصلي `user_reports_add_new_system.py` أو تقليله إلى الحد الأدنى

## الوضع الحالي
- الملف الأصلي يحتوي على ~9900 سطر
- النسخة المقسمة تعتمد على الملف الأصلي في:
  1. `conversation_handler.py` - يستدعي `_original_module.register(app)`
  2. جميع ملفات flows - تستورد handlers من الملف الأصلي
  3. `flows/shared.py` - يستورد `save_report_to_database` و `handle_edit_before_save`
  4. `department_handlers.py` - يستورد `start_radiology_flow`

## المهام المطلوبة

### المرحلة 1: نقل الدوال المشتركة ✅
- [x] نقل `save_report_to_database` إلى `flows/shared.py` (كامل)
- [x] نقل `handle_edit_before_save` إلى `flows/shared.py` (كامل)
- [ ] نقل `load_translator_names` إلى `flows/shared.py`
- [ ] نقل `ensure_default_translators` إلى `flows/shared.py`
- [ ] نقل `debug_state_monitor` إلى `decorators.py` أو `utils.py`

### المرحلة 2: نقل Inline Query Handlers
- [ ] نقل `patient_inline_query_handler` إلى `inline_query.py`
- [ ] نقل `doctor_inline_query_handler` إلى `inline_query.py`
- [ ] نقل `handle_chosen_inline_result` إلى `inline_query.py`

### المرحلة 3: نقل جميع handlers المسارات
لكل مسار (11 مسار):
- [ ] نقل جميع handlers من الملف الأصلي إلى ملف flow المقابل
- [ ] مثال: `handle_new_consult_complaint`, `handle_new_consult_decision`, etc. → `flows/new_consult.py`

**المسارات:**
1. **new_consult** - استشارة جديدة
   - `handle_new_consult_complaint`
   - `handle_new_consult_decision`
   - `handle_new_consult_tests`
   - `handle_new_consult_followup_*` (date, time, reason)
   - `handle_new_consult_followup_calendar_*`

2. **followup** - مراجعة
   - `handle_followup_complaint`
   - `handle_followup_diagnosis`
   - `handle_followup_decision`
   - `handle_followup_room_floor`
   - `handle_followup_reason`

3. **emergency** - طوارئ
   - `handle_emergency_complaint`
   - `handle_emergency_diagnosis`
   - `handle_emergency_decision`
   - `handle_emergency_status_*`
   - `handle_emergency_admission_type_*`
   - `handle_emergency_room_number`
   - `handle_emergency_date_time_text`
   - `handle_emergency_reason`

4. **admission** - ترقيد
   - `handle_admission_reason`
   - `handle_admission_room`
   - `handle_admission_notes`
   - `handle_admission_followup_*`

5. **surgery_consult** - استشارة مع قرار عملية
   - `handle_surgery_consult_diagnosis`
   - `handle_surgery_consult_decision`
   - `handle_surgery_consult_name_en`
   - `handle_surgery_consult_success_rate`
   - `handle_surgery_consult_benefit_rate`
   - `handle_surgery_consult_tests`
   - `handle_surgery_consult_followup_*`

6. **operation** - عملية
   - `handle_operation_details_ar`
   - `handle_operation_name_en`
   - `handle_operation_notes`
   - `handle_operation_followup_*`

7. **final_consult** - استشارة أخيرة
   - `handle_final_consult_diagnosis`
   - `handle_final_consult_decision`
   - `handle_final_consult_recommendations`

8. **discharge** - خروج من المستشفى
   - `handle_discharge_type`
   - `handle_discharge_admission_summary`
   - `handle_discharge_operation_*`
   - `handle_discharge_followup_*`

9. **rehab** - علاج طبيعي / أجهزة تعويضية
   - `handle_rehab_type`
   - `handle_physical_therapy_*`
   - `handle_device_*`

10. **radiology** - أشعة وفحوصات
    - `handle_radiology_type`
    - `handle_radiology_delivery_date`
    - (يتم استدعاؤه من `department_handlers.py`)

11. **app_reschedule** - تأجيل موعد
    - `handle_app_reschedule_reason`
    - `handle_app_reschedule_return_*`

### المرحلة 4: بناء ConversationHandler كاملاً
- [ ] بناء `ConversationHandler` في `conversation_handler.py` بدون الاعتماد على الملف الأصلي
- [ ] نقل جميع states handlers من الملف الأصلي
- [ ] ربط جميع handlers المسارات من ملفات flows

### المرحلة 5: نقل دوال التعديل والحفظ
- [ ] نقل `handle_edit_draft_report`
- [ ] نقل `handle_finish_edit_draft`
- [ ] نقل `handle_back_to_summary`
- [ ] نقل `handle_edit_draft_field`
- [ ] نقل `handle_back_to_edit_fields`
- [ ] نقل `handle_save_callback`
- [ ] نقل `handle_final_confirm` (إذا لم تكن موجودة في flows/shared.py)

### المرحلة 6: تحديث الاستيرادات
- [ ] تحديث جميع ملفات flows لإزالة `load_original_module`
- [ ] تحديث `conversation_handler.py` لإزالة `_load_original_module`
- [ ] تحديث `department_handlers.py` لإزالة استيراد `start_radiology_flow`
- [ ] تحديث `flows/shared.py` لإزالة استيراد من الملف الأصلي

### المرحلة 7: الاختبار والتنظيف
- [ ] اختبار جميع المسارات
- [ ] اختبار Inline Query
- [ ] اختبار التعديل والحفظ
- [ ] حذف أو تقليل الملف الأصلي

## الملفات المستهدفة

### ملفات جديدة مطلوبة:
- `decorators.py` - للـ decorators المشتركة (debug_state_monitor)

### ملفات للتحديث:
- `conversation_handler.py` - بناء ConversationHandler كامل
- `flows/shared.py` - إضافة جميع الدوال المشتركة
- `flows/new_consult.py` - إضافة جميع handlers
- `flows/followup.py` - إضافة جميع handlers
- `flows/emergency.py` - إضافة جميع handlers
- `flows/admission.py` - إضافة جميع handlers
- `flows/surgery_consult.py` - إضافة جميع handlers
- `flows/operation.py` - إضافة جميع handlers
- `flows/final_consult.py` - إضافة جميع handlers
- `flows/discharge.py` - إضافة جميع handlers
- `flows/rehab.py` - إضافة جميع handlers
- `flows/radiology.py` - إضافة جميع handlers
- `flows/app_reschedule.py` - إضافة جميع handlers
- `inline_query.py` - إضافة inline query handlers

## الترتيب المقترح للتنفيذ

1. **المرحلة 1** - نقل الدوال المشتركة (أسهل)
2. **المرحلة 2** - نقل Inline Query Handlers
3. **المرحلة 3** - نقل handlers المسارات (الأكبر)
4. **المرحلة 4** - بناء ConversationHandler
5. **المرحلة 5** - نقل دوال التعديل
6. **المرحلة 6** - تحديث الاستيرادات
7. **المرحلة 7** - الاختبار والتنظيف

## ملاحظات
- يجب الحفاظ على نفس الوظائف والسلوك
- يجب اختبار كل مرحلة قبل الانتقال للتالية
- يمكن الاحتفاظ بالملف الأصلي كـ backup حتى التأكد من عمل كل شيء






