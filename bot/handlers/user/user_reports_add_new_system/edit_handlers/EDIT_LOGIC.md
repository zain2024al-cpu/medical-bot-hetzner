# منطق عمل التعديل قبل النشر وبعد النشر

## 📋 نظرة عامة

تم تعديل النظام لعرض **فقط الحقول المدخلة فعلياً** عند التعديل، سواء قبل النشر أو بعد النشر.

---

## 🔄 التعديل قبل النشر (Pre-Publish Edit)

### الملفات المعنية:
- `bot/handlers/user/user_reports_add_new_system/flows/shared.py` → `show_edit_fields_menu()`
- `bot/handlers/user/user_reports_add_new_system/flows/shared.py` → `_has_field_value()`

### منطق العمل:

#### 1. عند الضغط على "تعديل التقرير" قبل النشر:
```
User clicks "تعديل التقرير" button
    ↓
handle_edit_before_save() is called
    ↓
show_edit_fields_menu() is called
    ↓
get_editable_fields_by_flow_type(flow_type) returns ALL possible fields
    ↓
Dynamic processing (add/remove room_number based on medical_action)
    ↓
Filter fields using _has_field_value(data, field_key)
    ↓
Display ONLY fields with actual values
```

#### 2. دالة `_has_field_value(data, field_key)`:
- **الوظيفة**: التحقق من وجود قيمة فعلية للحقل في `report_tmp`
- **المنطق**:
  1. البحث في الحقول المشتقة أولاً (مثل `complaint_text` مقابل `complaint`)
  2. التحقق من الحقل نفسه
  3. إرجاع `True` فقط إذا كانت القيمة:
     - ليست `None`
     - ليست فارغة `""`
     - ليست `"غير محدد"` أو `"لا يوجد"` أو `"None"` أو `"null"`

#### 3. الحقول المشتقة المدعومة:
```python
field_aliases = {
    "complaint": ["complaint", "complaint_text"],
    "decision": ["decision", "doctor_decision"],
    "tests": ["tests", "notes"],
    "operation_details": ["operation_details", "notes"],
    "delivery_date": ["delivery_date", "radiology_delivery_date"],
    "room_number": ["room_number", "room_floor"],
    "device_name": ["device_name", "device_details"],
    "app_reschedule_return_date": ["app_reschedule_return_date", "followup_date"],
    # ... إلخ
}
```

#### 4. معالجة خاصة:
- **`room_number`**: يُضاف ديناميكياً لمسار "متابعة في الرقود" فقط
- **`room_number`**: يُزال من مسار "مراجعة / عودة دورية"

---

## 🔄 التعديل بعد النشر (Post-Publish Edit)

### الملفات المعنية:
- `bot/handlers/user/user_reports_edit.py` → `handle_report_selection()`
- `bot/handlers/user/user_reports_edit.py` → `show_field_selection()`
- `bot/handlers/user/user_reports_edit.py` → `_has_field_value_in_report()`

### منطق العمل:

#### 1. عند اختيار تقرير للتعديل:
```
User selects a report from list
    ↓
handle_report_selection() is called
    ↓
Load report from database
    ↓
Update context.user_data['current_report_data'] with ALL report fields
    ↓
get_editable_fields_by_action_type(medical_action) returns ALL possible fields
    ↓
Filter fields using _has_field_value_in_report(report, current_data, field_name)
    ↓
Display ONLY fields with actual values
```

#### 2. دالة `_has_field_value_in_report(report, current_report_data, field_name)`:
- **الوظيفة**: التحقق من وجود قيمة فعلية للحقل في التقرير المنشور
- **المنطق**:
  1. التحقق من `current_report_data` أولاً (البيانات المحملة)
  2. البحث في الحقول المشتقة
  3. التحقق من `report` مباشرة (fallback)
  4. إرجاع `True` فقط إذا كانت القيمة:
     - ليست `None`
     - ليست فارغة `""`
     - ليست `"غير محدد"` أو `"لا يوجد"` أو `"None"` أو `"null"` أو `"⚠️ فارغ"`
     - ليست `date` فارغ

---

## 📊 جدول مقارنة: التعديل قبل النشر vs بعد النشر

| الجانب | التعديل قبل النشر | التعديل بعد النشر |
|--------|------------------|-------------------|
| **مصدر البيانات** | `context.user_data['report_tmp']` | `Report` object from database + `context.user_data['current_report_data']` |
| **دالة الفلترة** | `_has_field_value(data, field_key)` | `_has_field_value_in_report(report, current_data, field_name)` |
| **دالة الحقول** | `get_editable_fields_by_flow_type(flow_type)` | `get_editable_fields_by_action_type(medical_action)` |
| **معالجة خاصة** | إضافة/إزالة `room_number` ديناميكياً | لا يوجد |
| **الحقول الأساسية** | عرضها (report_date, patient_name, etc.) | عرضها (report_date, patient_name, etc.) |

---

## 🎯 منطق كل مسار (Flow Type)

### 1. **new_consult** (استشارة جديدة)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `complaint`, `diagnosis`, `decision`, `tests`
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً
- `tests` يمكن أن يكون في `notes` أيضاً

### 2. **followup** (متابعة)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `complaint`, `diagnosis`, `decision`
- `room_number` (فقط لـ "متابعة في الرقود")
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- إذا `medical_action == "متابعة في الرقود"` → إضافة `room_number`
- إذا `medical_action == "مراجعة / عودة دورية"` → إزالة `room_number`
- عرض فقط الحقول المدخلة فعلياً

### 3. **emergency** (طوارئ)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `complaint`, `diagnosis`, `decision`, `status`, `admission_type`
- `room_number` (اختياري)
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً
- `status` و `admission_type` اختياريان

### 4. **surgery_consult** (استشارة مع قرار عملية)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `diagnosis`, `decision`, `operation_name_en`, `success_rate`, `benefit_rate`, `tests`
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً
- `operation_name_en`, `success_rate`, `benefit_rate` اختياريان

### 5. **operation** (عملية)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `operation_details`, `operation_name_en`, `notes`
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً

### 6. **final_consult** (استشارة أخيرة)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `diagnosis`, `decision`, `recommendations`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً

### 7. **admission** (ترقيد)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `admission_reason`, `room_number`, `notes`
- `followup_date`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً

### 8. **discharge** (خروج من المستشفى)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `discharge_type`, `admission_summary`, `operation_details`, `operation_name_en`
- `followup_date`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً

### 9. **radiology** (أشعة وفحوصات)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `radiology_type`, `delivery_date` (أو `radiology_delivery_date`)

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً
- `delivery_date` و `radiology_delivery_date` متساويان

### 10. **rehab_physical** (علاج طبيعي)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `therapy_details`
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً

### 11. **rehab_device** (أجهزة تعويضية)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `device_name` (أو `device_details`)
- `followup_date`, `followup_time`, `followup_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً
- `device_name` و `device_details` متساويان

### 12. **appointment_reschedule** (تأجيل موعد)
**الحقول المتوقعة:**
- `report_date`, `patient_name`, `hospital_name`, `department_name`, `doctor_name`
- `app_reschedule_reason`, `app_reschedule_return_date`, `app_reschedule_return_reason`

**القواعد:**
- عرض فقط الحقول المدخلة فعلياً
- `app_reschedule_return_date` يمكن أن يكون في `followup_date` أيضاً

---

## ✅ التحقق من الحقول (Field Validation)

### القيم المرفوضة (ستُعتبر الحقول فارغة):
- `None`
- `""` (سلسلة فارغة)
- `"غير محدد"`
- `"لا يوجد"`
- `"None"` (نص)
- `"null"` (نص)
- `"⚠️ فارغ"` (بعد النشر فقط)

### القيم المقبولة:
- أي نص غير فارغ (حتى لو كان حرف واحد)
- أي رقم
- أي تاريخ (`date` أو `datetime`)
- `"0"` (يعتبر قيمة)

---

## 🔍 أمثلة عملية

### مثال 1: استشارة جديدة - تم إدخال complaint و decision فقط
```
الحقول المدخلة: complaint="شكوى المريض", decision="قرار الطبيب"
الحقول المعروضة في قائمة التعديل:
  ✅ complaint (💬 شكوى المريض)
  ✅ decision (📝 قرار الطبيب)
الحقول غير المعروضة:
  ❌ diagnosis (لم يتم إدخاله)
  ❌ tests (لم يتم إدخاله)
  ❌ followup_date (لم يتم إدخاله)
```

### مثال 2: متابعة في الرقود - تم إدخال complaint و decision و room_number
```
الحقول المدخلة: complaint="شكوى", decision="قرار", room_number="205-2"
الحقول المعروضة في قائمة التعديل:
  ✅ complaint (💬 شكوى المريض)
  ✅ decision (📝 قرار الطبيب)
  ✅ room_number (🚪 رقم الغرفة والطابق)
الحقول غير المعروضة:
  ❌ diagnosis (لم يتم إدخاله)
  ❌ followup_date (لم يتم إدخاله)
```

### مثال 3: عودة دورية - تم إدخال complaint و decision و followup_date
```
الحقول المدخلة: complaint="شكوى", decision="قرار", followup_date="2026-01-15"
الحقول المعروضة في قائمة التعديل:
  ✅ complaint (💬 شكوى المريض)
  ✅ decision (📝 قرار الطبيب)
  ✅ followup_date (📅 موعد العودة)
الحقول غير المعروضة:
  ❌ diagnosis (لم يتم إدخاله)
  ❌ room_number (غير موجود في هذا المسار)
```

---

## 🛠️ التعديلات المطلوبة

### ✅ تم تنفيذها:
1. ✅ إضافة دالة `_has_field_value()` للتعديل قبل النشر
2. ✅ إضافة دالة `_has_field_value_in_report()` للتعديل بعد النشر
3. ✅ تعديل `show_edit_fields_menu()` لعرض فقط الحقول المدخلة
4. ✅ تعديل `handle_report_selection()` لعرض فقط الحقول المدخلة
5. ✅ تعديل `show_field_selection()` لعرض فقط الحقول المدخلة
6. ✅ إضافة دعم الحقول المشتقة (aliases)
7. ✅ معالجة خاصة لـ `room_number` في مسار followup

### ⚠️ ملاحظات مهمة:
- الحقول الأساسية (report_date, patient_name, etc.) يتم عرضها دائماً لأنها موجودة دائماً في التقرير
- الحقول الاختيارية (followup_date, tests, etc.) يتم عرضها فقط إذا كانت لها قيمة فعلية
- الحقول المشتقة (complaint/complaint_text, decision/doctor_decision) يتم التحقق منها في كلا الاسمين




