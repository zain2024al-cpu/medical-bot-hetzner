# =============================
# Implementation Guide - دليل التنفيذ
# =============================

## 🎯 الهدف
إعادة هيكلة كاملة لنظام التعديل وفق القوانين التالية:

### القوانين الأساسية:
1. ✅ **فصل كامل**: كل flow type له handlers منفصلة تماماً
2. ✅ **لا دوال موحدة**: كل handler مستقل تماماً
3. ✅ **كل حقل منفصل**: منطق خاص لكل حقل داخل handler
4. ✅ **معالجة أخطاء محلية**: كل handler يعالج أخطاءه فقط
5. ✅ **ملفات منظمة**: ملفات كبيرة ومنظمة - لا ضغط

## 📁 الهيكل الحالي (قبل التغيير)

```
user_reports_add_new_system.py (ملف كبير جداً)
├── handle_unified_edit_field_input() ❌ دالة موحدة
├── handle_edit_field_selection() ❌ دالة موحدة
└── ...

flows/shared.py
├── show_edit_fields_menu() ❌ دالة موحدة
└── handle_edit_before_save() ❌ دالة موحدة
```

## 📁 الهيكل الجديد (بعد التغيير)

```
edit_handlers/
├── before_publish/              # التعديل قبل النشر
│   ├── router.py               # Router للتوجيه فقط
│   ├── new_consult_edit.py     # ✅ استشارة جديدة (منفصل)
│   ├── followup_edit.py        # ✅ عودة دورية / متابعة (منفصل)
│   ├── emergency_edit.py       # TODO: طوارئ (منفصل)
│   └── ...
│
└── after_publish/               # التعديل بعد النشر
    ├── router.py               # Router للتوجيه فقط
    ├── new_consult_edit.py     # TODO: استشارة جديدة (منفصل)
    └── ...
```

## 🔄 Flow التعديل قبل النشر

### مثال: تعديل حقل "tests" في استشارة جديدة

1. **المستخدم يضغط "✏️ مراجعة وتعديل التقرير"**
   - `handle_final_confirm` → `action="edit"`
   - `handle_edit_before_save` → `show_edit_fields_menu`

2. **عرض قائمة الحقول**
   - `show_edit_fields_menu` يعرض الحقول
   - زر: `callback_data="edit_field:new_consult:tests"`

3. **المستخدم يختار حقل "tests"**
   - Router يتلقى: `edit_field:new_consult:tests`
   - Router يوجه إلى: `handle_new_consult_edit_field_selection`

4. **Handler يعرض واجهة التعديل**
   - `handle_new_consult_edit_field_selection` يعرض:
     - القيمة الحالية
     - طلب القيمة الجديدة

5. **المستخدم يرسل القيمة الجديدة**
   - Router يتلقى: message text
   - Router يوجه إلى: `handle_new_consult_edit_field_input`

6. **Handler يحفظ القيمة**
   - `handle_new_consult_edit_field_input` يحفظ في `report_tmp["tests"]`
   - منطق خاص لحقل `tests` (لا يضيفه لـ `medications`)
   - إعادة عرض الملخص

## ✅ Handlers المنفصلة لكل Flow Type

### New Consult (`new_consult_edit.py`):
```python
# ✅ Field Selection Handler
async def handle_new_consult_edit_field_selection(update, context):
    """معالجة اختيار حقل للتعديل - استشارة جديدة"""
    # منطق خاص لـ new_consult فقط
    # كل حقل له منطق منفصل

# ✅ Field Input Handler
async def handle_new_consult_edit_field_input(update, context):
    """معالجة إدخال القيمة الجديدة - استشارة جديدة"""
    # منطق خاص لـ new_consult فقط
    # كل حقل له معالجة منفصلة:
    if field_key == "tests":
        # ✅ منطق خاص لـ tests
        data["tests"] = text
        # لا نضيف لـ medications هنا
    elif field_key == "complaint":
        # ✅ منطق خاص لـ complaint
        data["complaint"] = text
        data["complaint_text"] = text
    elif field_key == "decision":
        # ✅ منطق خاص لـ decision
        data["decision"] = text
        data["doctor_decision"] = text
    # ... إلخ
```

### Followup (`followup_edit.py`):
```python
# ✅ Field Selection Handler
async def handle_followup_edit_field_selection(update, context):
    """معالجة اختيار حقل للتعديل - followup"""
    # منطق خاص لـ followup فقط
    # ✅ التحقق من room_number - فقط لـ "متابعة في الرقود"
    if field_key == "room_number":
        if medical_action != "متابعة في الرقود":
            # خطأ - الحقل غير متاح
            return

# ✅ Field Input Handler
async def handle_followup_edit_field_input(update, context):
    """معالجة إدخال القيمة الجديدة - followup"""
    # منطق خاص لـ followup فقط
    if field_key == "room_number":
        if medical_action == "متابعة في الرقود":
            # ✅ منطق خاص لـ room_number في متابعة في الرقود
            data["room_number"] = text
        else:
            # خطأ - الحقل غير متاح
            return
    # ... إلخ
```

## 🔀 Router

### Router بسيط - فقط توجيه:
```python
async def route_edit_field_selection(update, context):
    """Router لتوجيه اختيار الحقل"""
    flow_type = extract_flow_type_from_callback(update.callback_query.data)
    
    if flow_type == "new_consult":
        return await handle_new_consult_edit_field_selection(update, context)
    elif flow_type == "followup":
        return await handle_followup_edit_field_selection(update, context)
    # ... إلخ

async def route_edit_field_input(update, context):
    """Router لتوجيه إدخال القيمة"""
    flow_type = context.user_data.get("edit_flow_type")
    
    if flow_type == "new_consult":
        return await handle_new_consult_edit_field_input(update, context)
    elif flow_type == "followup":
        return await handle_followup_edit_field_input(update, context)
    # ... إلخ
```

## 📝 ملاحظات التطوير

### 1. إضافة Flow Type جديد:
```
1. إنشاء ملف جديد: edit_handlers/before_publish/{flow_type}_edit.py
2. إضافة handlers:
   - handle_{flow_type}_edit_field_selection
   - handle_{flow_type}_edit_field_input
3. تحديث router.py لإضافة التوجيه
4. تحديث __init__.py للـ exports
5. تحديث conversation handler state
```

### 2. إضافة حقل جديد:
```
1. إضافة في field_names dictionary
2. إضافة منطق خاص في handle_{flow_type}_edit_field_input
3. لا تعديل handlers أخرى
```

### 3. إصلاح خطأ في حقل معين:
```
1. تعديل فقط في handler هذا الحقل
2. لا تعديل handlers أخرى
3. لا تعديل router
4. لا تعديل ملفات أخرى
```

## 🚫 ممنوعات

1. ❌ **لا دوال موحدة** بين flow types
2. ❌ **لا دمج منطق** flow types في دالة واحدة
3. ❌ **لا تعديل handlers أخرى** عند إصلاح خطأ
4. ❌ **لا استخدام `handle_unified_edit_field_input`** أو أي دالة موحدة
5. ❌ **لا ضغط الكود** في ملف واحد

## ✅ المسموح

1. ✅ **كل flow type له handlers منفصلة**
2. ✅ **كل حقل له منطق منفصل** داخل handler
3. ✅ **Router للتوجيه فقط** (لا منطق أعمال)
4. ✅ **معالجة أخطاء محلية** في كل handler
5. ✅ **ملفات كبيرة ومنظمة** (لا ضغط)

## 📊 الحالة الحالية

### ✅ مكتمل:
- [x] هيكل الملفات الأساسي
- [x] handlers لـ `new_consult` و `followup`
- [x] router للتوجيه
- [x] توثيق الهيكل

### 🔄 قيد العمل:
- [ ] تكامل router مع conversation handler
- [ ] إصلاح imports
- [ ] اختبار handlers الجديدة

### ⏳ قادم:
- [ ] إضافة handlers لباقي flow types
- [ ] handlers التعديل بعد النشر
- [ ] إزالة `handle_unified_edit_field_input` تدريجياً




