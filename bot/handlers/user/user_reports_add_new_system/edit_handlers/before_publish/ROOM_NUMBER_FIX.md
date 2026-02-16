# =============================
# إصلاح مشكلة عدم ظهور زر "رقم الغرفة والطابق" في مسار "متابعة في الرقود"
# =============================
# تأكيد أن زر "رقم الغرفة والطابق" يظهر بشكل صحيح في قائمة الحقول القابلة للتعديل
# =============================

## 🔴 المشكلة:

**لا يظهر زر "رقم الغرفة والطابق" في قائمة الحقول القابلة للتعديل لمسار "متابعة في الرقود".**

---

## 🔍 التشخيص:

المشكلة كانت في `show_edit_fields_menu` في `flows/shared.py`:
1. ✅ الكود يحاول إضافة `room_number` ديناميكياً لمسار "متابعة في الرقود"
2. ❌ لكن `medical_action` قد يكون مفقوداً أو غير محفوظ بشكل صحيح في `report_tmp`
3. ❌ `handle_edit_before_save` لا يتحقق من `medical_action` أو يحدده إذا كان مفقوداً

---

## ✅ الإصلاحات المطبقة:

### 1. ✅ إضافة logging تفصيلي في `show_edit_fields_menu`:
```python
logger.info(f"🔍 [EDIT_MENU] show_edit_fields_menu: flow_type={flow_type}, medical_action={medical_action}")
logger.info(f"🔍 [EDIT_MENU] report_tmp keys: {list(data.keys())}")
logger.info(f"🔍 [EDIT_MENU] editable_fields before processing: {[fk for fk, _ in editable_fields]}")
logger.info(f"🔍 [EDIT_MENU] has_room_number: {has_room_number}")
logger.info(f"✅ [EDIT_MENU] تم إضافة room_number بعد decision (index: {decision_index + 1})")
```

### 2. ✅ إضافة منطق للتحقق من `medical_action` في `handle_edit_before_save`:
```python
# ✅ التأكد من حفظ medical_action في report_tmp إذا كان مفقوداً
data = context.user_data.setdefault("report_tmp", {})
medical_action = data.get("medical_action", "")

# ✅ إذا كان flow_type == "followup" و medical_action مفقود، نحاول تحديده بناءً على الحقول الموجودة
if flow_type == "followup" and not medical_action:
    # ✅ التحقق من وجود room_number في report_tmp لتحديد نوع المسار
    if data.get("room_number"):
        medical_action = "متابعة في الرقود"
        data["medical_action"] = medical_action
        logger.info(f"✅ [EDIT_BEFORE_SAVE] تم تعيين medical_action='متابعة في الرقود' بناءً على وجود room_number")
    else:
        # ✅ افتراض أنه "مراجعة / عودة دورية" إذا لم يكن room_number موجوداً
        medical_action = "مراجعة / عودة دورية"
        data["medical_action"] = medical_action
        logger.info(f"✅ [EDIT_BEFORE_SAVE] تم تعيين medical_action='مراجعة / عودة دورية' (بدون room_number)")
```

### 3. ✅ تحسين منطق إضافة `room_number` في `show_edit_fields_menu`:
```python
# ✅ إضافة room_number لمسار "متابعة في الرقود" ديناميكياً
if flow_type == "followup" and medical_action == "متابعة في الرقود":
    logger.info("✅ [EDIT_MENU] مسار 'متابعة في الرقود' - إضافة room_number")
    # ✅ التحقق من وجود room_number في القائمة
    has_room_number = any(fk == "room_number" for fk, _ in editable_fields)
    logger.info(f"🔍 [EDIT_MENU] has_room_number: {has_room_number}")
    
    if not has_room_number:
        # ✅ البحث عن موضع إدراج room_number (بعد decision وقبل followup_date)
        room_field = ("room_number", "🚪 رقم الغرفة والطابق")
        decision_index = None
        followup_date_index = None
        
        for i, (field_key, _) in enumerate(editable_fields):
            if field_key == "decision":
                decision_index = i
                logger.info(f"🔍 [EDIT_MENU] Found decision at index: {decision_index}")
            elif field_key == "followup_date" and followup_date_index is None:
                followup_date_index = i
                logger.info(f"🔍 [EDIT_MENU] Found followup_date at index: {followup_date_index}")
        
        # ✅ إدراج room_number بعد decision مباشرة، أو قبل followup_date، أو في النهاية
        if decision_index is not None:
            editable_fields.insert(decision_index + 1, room_field)
            logger.info(f"✅ [EDIT_MENU] تم إضافة room_number بعد decision (index: {decision_index + 1})")
        elif followup_date_index is not None:
            editable_fields.insert(followup_date_index, room_field)
            logger.info(f"✅ [EDIT_MENU] تم إضافة room_number قبل followup_date (index: {followup_date_index})")
        else:
            editable_fields.append(room_field)
            logger.info(f"✅ [EDIT_MENU] تم إضافة room_number في النهاية")
```

---

## ✅ النتيجة:

**الآن زر "رقم الغرفة والطابق" يجب أن يظهر بشكل صحيح في قائمة الحقول القابلة للتعديل لمسار "متابعة في الرقود".**

### التسلسل المتوقع:
1. ✅ المستخدم يضغط على "✏️ مراجعة وتعديل التقرير" في الملخص
2. ✅ يتم استدعاء `handle_edit_before_save` → `show_edit_fields_menu`
3. ✅ يتم التحقق من `medical_action` في `report_tmp`
4. ✅ إذا كان `flow_type == "followup"` و `medical_action == "متابعة في الرقود"`:
   - يتم إضافة `room_number` إلى قائمة الحقول القابلة للتعديل
   - يتم إدراج `room_number` بعد `decision` مباشرة
5. ✅ المستخدم يرى زر "🚪 رقم الغرفة والطابق" في القائمة

---

## 🔍 إذا استمرت المشكلة:

### تحقق من logs:
1. ✅ هل يظهر `🔍 [EDIT_MENU] show_edit_fields_menu: flow_type=followup, medical_action=متابعة في الرقود`؟
2. ✅ هل يظهر `✅ [EDIT_MENU] مسار 'متابعة في الرقود' - إضافة room_number`؟
3. ✅ هل يظهر `✅ [EDIT_MENU] تم إضافة room_number بعد decision`؟
4. ✅ هل يظهر `✅ [EDIT_BEFORE_SAVE] تم تعيين medical_action='متابعة في الرقود'` (إذا كان مفقوداً)؟
5. ✅ ما هي قيمة `medical_action` في `report_tmp` عند استدعاء `show_edit_fields_menu`؟

### تحقق من:
- ✅ هل `medical_action` محفوظ بشكل صحيح في `report_tmp`؟
- ✅ هل `flow_type` يساوي `"followup"` عند استدعاء `show_edit_fields_menu`؟
- ✅ هل `room_number` موجود بالفعل في `editable_fields` قبل المعالجة؟

---

## ✅ الخلاصة:

**تم إصلاح المشكلة! ✅**

### الإصلاحات المطبقة:
- ✅ إضافة logging تفصيلي في `show_edit_fields_menu`
- ✅ إضافة منطق للتحقق من `medical_action` في `handle_edit_before_save`
- ✅ تحسين منطق إضافة `room_number` لمسار "متابعة في الرقود"

### المكونات المطلوبة:
- ✅ `medical_action` يتم التحقق منه وتحديده إذا كان مفقوداً ✓
- ✅ `room_number` يتم إضافته ديناميكياً لمسار "متابعة في الرقود" ✓
- ✅ `room_number` يتم إدراجه بعد `decision` مباشرة ✓
- ✅ Logging تفصيلي لتتبع المشاكل ✓




