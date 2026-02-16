# =============================
# Edit Handlers Architecture - هيكل معالجات التعديل
# =============================

## 📋 المبادئ والقوانين

### 1. **الفصل الكامل بين Flow Types**
- كل flow type له handlers منفصلة تماماً
- لا توجد دوال موحدة بين flow types
- كل ملف مستقل تماماً

### 2. **الفصل بين قبل وبعد النشر**
- `before_publish/` - handlers التعديل قبل النشر (في الملخص)
- `after_publish/` - handlers التعديل بعد النشر (في تقارير منشورة)

### 3. **كل حقل له handler منفصل**
- `handle_{flow_type}_edit_field_selection` - اختيار الحقل
- `handle_{flow_type}_edit_field_input` - إدخال القيمة الجديدة
- كل حقل له منطق خاص به داخل هذه handlers

### 4. **Router للتوجيه**
- `router.py` يوجه الطلبات إلى handler المناسب حسب `flow_type`
- Router بسيط - فقط توجيه، لا منطق أعمال

### 5. **معالجة الأخطاء محلية**
- كل handler يعالج أخطاءه فقط
- لا تأثير على handlers أخرى

## 📁 هيكل الملفات

```
edit_handlers/
├── __init__.py              # Exports رئيسية
├── ARCHITECTURE.md          # هذا الملف
│
├── before_publish/          # التعديل قبل النشر
│   ├── __init__.py
│   ├── router.py            # Router للتوجيه
│   ├── new_consult_edit.py  # ✅ استشارة جديدة
│   ├── followup_edit.py     # ✅ عودة دورية / متابعة في الرقود
│   ├── emergency_edit.py    # TODO: طوارئ
│   ├── surgery_consult_edit.py  # TODO: استشارة مع قرار عملية
│   ├── operation_edit.py    # TODO: عملية
│   ├── final_consult_edit.py    # TODO: استشارة أخيرة
│   ├── admission_edit.py    # TODO: ترقيد
│   ├── discharge_edit.py    # TODO: خروج
│   ├── radiology_edit.py    # TODO: أشعة
│   ├── app_reschedule_edit.py   # TODO: تأجيل موعد
│   └── rehab_edit.py        # TODO: علاج طبيعي
│
└── after_publish/           # التعديل بعد النشر
    ├── __init__.py
    ├── router.py            # Router للتوجيه
    ├── new_consult_edit.py  # TODO
    └── ...
```

## 🔄 Flow التعديل قبل النشر

### New Consult مثال:
1. المستخدم يضغط "✏️ مراجعة وتعديل التقرير"
2. `handle_edit_before_save` → `show_edit_fields_menu`
3. المستخدم يختار حقل (مثال: "tests")
4. `callback_data="edit_field:new_consult:tests"`
5. Router يوجه إلى `handle_new_consult_edit_field_selection`
6. Handler يعرض واجهة التعديل للحقل
7. المستخدم يرسل القيمة الجديدة
8. `handle_new_consult_edit_field_input` يحفظ القيمة
9. إعادة عرض الملخص

## ✅ الحقول لكل Flow Type

### New Consult (`new_consult_edit.py`):
- report_date, patient_name, hospital_name, department_name, doctor_name
- complaint, diagnosis, decision, **tests** (حقل منفصل)
- followup_date, followup_time, followup_reason

### Followup (`followup_edit.py`):
- report_date, patient_name, hospital_name, department_name, doctor_name
- complaint, diagnosis, decision
- **room_number** (فقط لـ "متابعة في الرقود")
- followup_date, followup_time, followup_reason

## 📝 ملاحظات التطوير

1. **إضافة flow type جديد:**
   - إنشاء ملف جديد في `before_publish/`
   - إضافة handlers: `handle_{flow_type}_edit_field_selection` و `handle_{flow_type}_edit_field_input`
   - تحديث `router.py` لإضافة التوجيه
   - تحديث `__init__.py` للـ exports

2. **إضافة حقل جديد:**
   - إضافة في `field_names` dictionary
   - إضافة منطق خاص في `handle_{flow_type}_edit_field_input` إذا لزم الأمر

3. **إصلاح خطأ في حقل معين:**
   - تعديل فقط في handler هذا الحقل
   - لا تعديل handlers أخرى أو دوال موحدة

## 🚫 ممنوعات

1. ❌ لا دوال موحدة بين flow types
2. ❌ لا دمج منطق flow types في دالة واحدة
3. ❌ لا تعديل handlers أخرى عند إصلاح خطأ في handler واحد
4. ❌ لا استخدام `handle_unified_edit_field_input` أو أي دالة موحدة

## ✅ المسموح

1. ✅ كل flow type له handlers منفصلة
2. ✅ كل حقل له منطق منفصل داخل handler
3. ✅ Router للتوجيه فقط (لا منطق أعمال)
4. ✅ معالجة أخطاء محلية في كل handler
5. ✅ ملفات كبيرة ومنظمة (لا ضغط)




