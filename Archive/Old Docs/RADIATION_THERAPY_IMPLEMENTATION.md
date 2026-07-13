# إضافة مسار الجلسة الإشعاعية - التوثيق

## ✅ ما تم إنجازه

### 1. إضافة القسم الجديد
- ✅ تم إضافة "العلاج الإشعاعي | The radiation Therapy" إلى `DIRECT_DEPARTMENTS` في `user_reports_add_helpers.py`

### 2. إضافة نوع الإجراء
- ✅ تم إضافة "جلسة إشعاعي" إلى `PREDEFINED_ACTIONS` في `user_reports_add_helpers.py`

### 3. إضافة States
- ✅ تم إضافة 7 states جديدة في `states.py` و `user_reports_add_new_system.py`:
  - `RADIATION_THERAPY_TYPE` - نوع الإشعاعي
  - `RADIATION_THERAPY_SESSION_NUMBER` - رقم الجلسة
  - `RADIATION_THERAPY_REMAINING` - الجلسات المتبقية
  - `RADIATION_THERAPY_RETURN_DATE` - تاريخ العودة والوقت
  - `RADIATION_THERAPY_RETURN_REASON` - سبب العودة
  - `RADIATION_THERAPY_TRANSLATOR` - اسم المترجم
  - `RADIATION_THERAPY_CONFIRM` - تأكيد

### 4. إنشاء Flow جديد
- ✅ تم إنشاء `flows/radiation_therapy.py` مع جميع الـ handlers المطلوبة

### 5. إضافة Routing
- ✅ تم إضافة routing في `action_type_handlers.py`
- ✅ تم إضافة `start_radiation_therapy_flow` إلى `stub_flows.py`

## 📋 الحقول المطلوبة

1. **نوع الإشعاعي** - نص حر (مثال: External Beam Radiation, Brachytherapy, IMRT)
2. **رقم الجلسة** - نص (مثال: "5" أو "5 من 30")
3. **الجلسات المتبقية** - رقم أو نص
4. **تاريخ العودة والوقت** - صيغة: YYYY-MM-DD HH:MM
5. **سبب العودة** - نص حر (أو ملاحظات نهائية إذا اكتملت الجلسات)
6. **اسم المترجم** - اختيار من القائمة أو إدخال يدوي

## 🎯 معالجة اكتمال الجلسات

عندما تكون الجلسات المتبقية = 0:
- ✅ يتم عرض رسالة تهنئة: "🎉 تهانينا! تم إكمال جميع الجلسات الإشعاعية"
- ✅ يطلب تاريخ اكتمال العلاج والوقت
- ✅ يطلب ملاحظات نهائية (اختياري) بدلاً من "سبب العودة"
- ✅ يتم حفظ `radiation_therapy_completed = True` في البيانات

## ⚠️ ما يحتاج إكمال

### 1. إضافة Handlers في الملف الرئيسي
يجب إضافة handlers في `user_reports_add_new_system.py`:

```python
# في قسم الـ handlers
async def handle_radiation_therapy_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from .flows.radiation_therapy import handle_radiation_therapy_type as handler
    return await handler(update, context)

async def handle_radiation_therapy_session_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from .flows.radiation_therapy import handle_radiation_therapy_session_number as handler
    return await handler(update, context)

async def handle_radiation_therapy_remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from .flows.radiation_therapy import handle_radiation_therapy_remaining as handler
    return await handler(update, context)

async def handle_radiation_therapy_return_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from .flows.radiation_therapy import handle_radiation_therapy_return_date as handler
    return await handler(update, context)

async def handle_radiation_therapy_return_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from .flows.radiation_therapy import handle_radiation_therapy_return_reason as handler
    return await handler(update, context)
```

### 2. إضافة إلى ConversationHandler
يجب إضافة states إلى `ConversationHandler` في `user_reports_add_new_system.py`:

```python
states={
    # ... states أخرى
    RADIATION_THERAPY_TYPE: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiation_therapy_type)
    ],
    RADIATION_THERAPY_SESSION_NUMBER: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiation_therapy_session_number)
    ],
    RADIATION_THERAPY_REMAINING: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiation_therapy_remaining)
    ],
    RADIATION_THERAPY_RETURN_DATE: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiation_therapy_return_date)
    ],
    RADIATION_THERAPY_RETURN_REASON: [
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_radiation_therapy_return_reason)
    ],
    # RADIATION_THERAPY_TRANSLATOR و RADIATION_THERAPY_CONFIRM
    # يتم التعامل معهما في shared handlers
}
```

### 3. تحديث save_report_to_database
يجب تحديث `save_report_to_database` في `flows/shared.py` لدعم `radiation_therapy`:

```python
elif flow_type == "radiation_therapy":
    radiation_type = data.get("radiation_therapy_type", "")
    session_number = data.get("radiation_therapy_session_number", "")
    remaining = data.get("radiation_therapy_remaining", "")
    completed = data.get("radiation_therapy_completed", False)
    final_notes = data.get("radiation_therapy_final_notes", "")
    
    complaint_text = ""
    decision_text = f"نوع الإشعاعي: {radiation_type}\n\n"
    decision_text += f"رقم الجلسة: {session_number}\n\n"
    decision_text += f"الجلسات المتبقية: {remaining}\n\n"
    
    if completed:
        decision_text += f"✅ تم إكمال جميع الجلسات\n\n"
        if final_notes:
            decision_text += f"ملاحظات نهائية: {final_notes}"
    else:
        return_date = data.get("radiation_therapy_return_date")
        return_reason = data.get("radiation_therapy_return_reason", "")
        if return_date:
            decision_text += f"تاريخ العودة: {return_date}\n\n"
        if return_reason:
            decision_text += f"سبب العودة: {return_reason}"
```

### 4. إضافة Back Navigation
يجب إضافة back navigation في `user_reports_add_new_system.py`:

```python
back_navigation_map = {
    # ... maps أخرى
    'RADIATION_THERAPY_TYPE': STATE_SELECT_ACTION_TYPE,
    'RADIATION_THERAPY_SESSION_NUMBER': 'RADIATION_THERAPY_TYPE',
    'RADIATION_THERAPY_REMAINING': 'RADIATION_THERAPY_SESSION_NUMBER',
    'RADIATION_THERAPY_RETURN_DATE': 'RADIATION_THERAPY_REMAINING',
    'RADIATION_THERAPY_RETURN_REASON': 'RADIATION_THERAPY_RETURN_DATE',
    'RADIATION_THERAPY_TRANSLATOR': 'RADIATION_THERAPY_RETURN_REASON',
    'RADIATION_THERAPY_CONFIRM': 'RADIATION_THERAPY_TRANSLATOR',
}
```

### 5. تهيئة States في radiation_therapy.py
يجب استدعاء `init_states()` في بداية الملف الرئيسي:

```python
from .flows.radiation_therapy import init_states
init_states({
    'RADIATION_THERAPY_TYPE': RADIATION_THERAPY_TYPE,
    'RADIATION_THERAPY_SESSION_NUMBER': RADIATION_THERAPY_SESSION_NUMBER,
    'RADIATION_THERAPY_REMAINING': RADIATION_THERAPY_REMAINING,
    'RADIATION_THERAPY_RETURN_DATE': RADIATION_THERAPY_RETURN_DATE,
    'RADIATION_THERAPY_RETURN_REASON': RADIATION_THERAPY_RETURN_REASON,
    'RADIATION_THERAPY_TRANSLATOR': RADIATION_THERAPY_TRANSLATOR,
    'RADIATION_THERAPY_CONFIRM': RADIATION_THERAPY_CONFIRM,
})
```

## 📝 اقتراح الفورم عند اكتمال الجلسات

عند اكتمال جميع الجلسات (الجلسات المتبقية = 0):

### الفورم المقترح:
```
🎉 **اكتمال العلاج الإشعاعي**

✅ تم إكمال جميع الجلسات بنجاح

📋 **ملخص العلاج:**
- نوع الإشعاعي: [نوع الإشعاعي]
- إجمالي الجلسات: [الرقم الكلي]
- تاريخ اكتمال العلاج: [التاريخ والوقت]

📝 **ملاحظات نهائية:**
[الملاحظات المدخلة]

👤 **المترجم:** [اسم المترجم]
📅 **تاريخ التقرير:** [تاريخ التقرير]
```

### الحقول المحفوظة:
- `radiation_therapy_type` - نوع الإشعاعي
- `radiation_therapy_session_number` - رقم الجلسة الأخيرة
- `radiation_therapy_remaining` - 0
- `radiation_therapy_completed` - True
- `radiation_therapy_final_notes` - الملاحظات النهائية
- `followup_date` - تاريخ اكتمال العلاج
- `followup_reason` - "اكتمال العلاج الإشعاعي. ملاحظات: [الملاحظات]"

## 🚀 الخطوات التالية

1. إضافة handlers في الملف الرئيسي
2. إضافة states إلى ConversationHandler
3. تحديث save_report_to_database
4. إضافة back navigation
5. تهيئة states في radiation_therapy.py
6. اختبار المسار الكامل
7. نشر التحديثات

## ✅ الملفات المعدلة

- `bot/handlers/user/user_reports_add_helpers.py` - إضافة القسم ونوع الإجراء
- `bot/handlers/user/user_reports_add_new_system/states.py` - إضافة states
- `bot/handlers/user/user_reports_add_new_system.py` - إضافة states
- `bot/handlers/user/user_reports_add_new_system/flows/radiation_therapy.py` - ملف جديد
- `bot/handlers/user/user_reports_add_new_system/action_type_handlers.py` - إضافة routing
- `bot/handlers/user/user_reports_add_new_system/flows/stub_flows.py` - إضافة stub
