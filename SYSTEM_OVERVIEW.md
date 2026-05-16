# SYSTEM OVERVIEW
## خريطة عقل البوت — المرجع الكامل للبنية

---

## 1. كيف يعمل البوت — الصورة الكاملة

```
User sends message / presses button
        │
        ▼
Application (python-telegram-bot)
        │
        ├── ConversationHandler (user_reports_add_new_system)
        │       │
        │       ├── States → flow handlers → summary → publish
        │       └── Back button → nav_pop → previous renderer
        │
        ├── InlineQueryHandler (patient search)
        │       └── user_patient_search_inline.py
        │
        ├── Admin handlers (admin_*.py)
        │
        └── universal_fallback.py (catches unregistered callbacks)
```

---

## 2. تدفق إنشاء تقرير جديد

```
/start أو زر "تقرير جديد"
        │
        ▼
action_type_handlers.py → اختيار نوع الإجراء (new_consult / emergency / followup / ...)
        │
        ▼
patient_handlers.py → اختيار / بحث المريض
        │
        ▼
hospital_handlers.py → اختيار المستشفى
        │
        ▼
department_handlers.py → اختيار القسم
        │
        ▼
doctor_handlers.py → اختيار / بحث الطبيب
        │
        ▼
flows/shared.py → show_translator_selection() → اختيار المترجم
        │
        ▼
flows/<flow_name>.py → خطوات خاصة بكل نوع
        │
        ▼
flows/shared.py → show_final_summary() → عرض الملخص + أزرار
        │
        ├── زر "تعديل" → edit_handlers/before_publish/router.py
        ├── زر "مراجعة" → show_review_screen()
        └── زر "نشر" → handle_final_confirm() → save_report_to_database()
                                │
                                ▼
                        services/broadcast_service.py → broadcast_new_report()
                        → يرسل للقنوات ويُنهي ConversationHandler
```

---

## 3. أنواع الـ Flows

| flow_type | الاسم بالعربي | الملف |
|-----------|---------------|-------|
| `new_consult` | استشارة جديدة | `flows/new_consult.py` |
| `followup` | متابعة في الرقود | `flows/followup.py` |
| `periodic_followup` | مراجعة / عودة دورية | `flows/followup.py` (sub-flow) |
| `inpatient_followup` | متابعة في الرقود | `flows/followup.py` (sub-flow) |
| `emergency` | طوارئ | `flows/emergency.py` |
| `admission` | ترقيد | `flows/admission.py` |
| `operation` | عملية | `flows/operation.py` |
| `surgery_consult` | استشارة مع قرار عملية | `flows/surgery_consult.py` |
| `final_consult` | استشارة أخيرة | `flows/final_consult.py` |
| `discharge` | خروج من المستشفى | `flows/discharge.py` |
| `rehab_physical` | علاج طبيعي | `flows/rehab.py` |
| `rehab_device` / `device` | أجهزة تعويضية | `flows/rehab.py` |
| `radiology` | أشعة وفحوصات | `flows/radiology.py` |
| `appointment_reschedule` | تأجيل موعد | `flows/app_reschedule.py` |
| `radiation_therapy` | جلسة إشعاعي | `flows/radiation_therapy.py` |

---

## 4. كيف يعمل نظام الرجوع (Back Navigation)

### المبدأ
كل انتقال للأمام يضغط الحالة الحالية على Stack. الرجوع يسحب من Stack.

### التسلسل
```
nav_push(context, STATE_X)  ← عند كل انتقال للأمام
        │
user presses "رجوع"
        │
        ▼
handle_smart_back_navigation()  ← navigation_helpers.py
        │
        ▼
nav_pop(context)  ← navigation.py
        │
        ▼
previous_state → renderer المناسب
```

### Stack Key
```python
context.user_data['history']  # list of state constants
```

### الملفات
- `navigation.py` — `nav_push`, `nav_pop`, `nav_peek`, `nav_clear`, `nav_get_history`
- `navigation_helpers.py` — `handle_smart_back_navigation` (يقرأ Stack ويستدعي الـ renderer الصحيح)

### ممنوع
- حساب الخطوة السابقة يدوياً.
- استخدام `FLOW_MAPS` للتنقل للخلف.
- كتابة `context.user_data['history']` مباشرة خارج `navigation.py`.

---

## 5. هيكل الحزمة الكاملة

```
bot/handlers/user/user_reports_add_new_system/
│
├── __init__.py                    ← Package entry — exports register()
├── conversation_handler.py        ← ConversationHandler assembly — owned by nobody else
├── states.py                      ← State constants (STATE_SELECT_PATIENT, ...)
├── common_imports.py              ← DB models import point
│
├── action_type_handlers.py        ← اختيار نوع الإجراء (أول خطوة)
├── patient_handlers.py            ← المريض
├── hospital_handlers.py           ← المستشفى
├── department_handlers.py         ← القسم
├── doctor_handlers.py             ← الطبيب (DB + JSON)
│
├── navigation.py                  ← Stack implementation (nav_push/pop/peek)
├── navigation_helpers.py          ← Back navigation logic
├── smart_state_renderer.py        ← Re-render screens after back
├── execute_smart_state_action.py  ← State machine executor
│
├── date_time_handlers.py          ← Calendar + Time picker handlers
├── selector_context.py            ← Saves selected values to report_tmp
├── managers.py                    ← PatientDataManager, DoctorDataManager
├── utils.py                       ← Helper utilities
├── ui_primitives.py               ← Reusable keyboard builders
│
├── flows/
│   ├── shared.py                  ← مشترك: مترجم، ملخص، نشر، حفظ، بث
│   ├── new_consult.py
│   ├── followup.py                ← يشمل periodic + inpatient
│   ├── emergency.py
│   ├── admission.py
│   ├── operation.py
│   ├── surgery_consult.py
│   ├── final_consult.py
│   ├── discharge.py
│   ├── rehab.py                   ← physical + device
│   ├── radiology.py
│   ├── app_reschedule.py
│   ├── radiation_therapy.py
│   └── stub_flows.py              ← Stubs للـ flows غير المكتملة
│
├── edit_handlers/
│   ├── before_publish/
│   │   ├── router.py              ← يوجه لـ edit handler المناسب حسب flow_type
│   │   ├── new_consult_edit.py
│   │   ├── followup_edit.py
│   │   ├── emergency_edit.py
│   │   └── ... (ملف لكل flow)
│   └── draft/
│       └── handlers.py
│
└── inline_query.py                ← Inline search داخل الحزمة

bot/handlers/user/user_reports_edit.py   ← تعديل بعد النشر (مستقل تماماً)

services/
├── broadcast_service.py           ← إرسال التقارير للقنوات
├── hospitals_service.py           ← بيانات المستشفيات
├── translators_service.py         ← بيانات المترجمين
├── doctors_service.py             ← بيانات الأطباء (helper)
├── doctors_smart_search.py        ← بحث ذكي في JSON
├── smart_navigation_manager.py    ← FLOW_MAPS + SmartNavigationManager singleton
├── broadcast_service.py           ← بث التقارير
└── ...
```

---

## 6. Ownership Map الكاملة

| الوظيفة | المالك الوحيد | الملف |
|---------|---------------|-------|
| Navigation stack write | `navigation.py` | `nav_push / nav_pop` |
| Back navigation decision | `navigation_helpers.py` | `handle_smart_back_navigation` |
| Screen re-render after back | `smart_state_renderer.py` | `SmartStateRenderer` |
| اختيار المريض | `patient_handlers.py` | `show_patient_selection` |
| اختيار المستشفى | `hospital_handlers.py` | `show_hospital_selection` |
| اختيار القسم | `department_handlers.py` | `show_department_selection` |
| اختيار الطبيب | `doctor_handlers.py` | `render_doctor_selection` |
| اختيار المترجم | `flows/shared.py` | `show_translator_selection` |
| الملخص النهائي | `flows/shared.py` | `show_final_summary` |
| تأكيد النشر | `flows/shared.py` | `handle_final_confirm` |
| حفظ التقرير في DB | `flows/shared.py` | `save_report_to_database` |
| بث التقرير | `services/broadcast_service.py` | `broadcast_new_report` |
| تعديل قبل النشر — routing | `edit_handlers/before_publish/router.py` | — |
| تعديل بعد النشر | `user_reports_edit.py` | standalone ConversationHandler |
| State constants | `states.py` | — |
| ConversationHandler assembly | `conversation_handler.py` | `register(app)` |
| Flow step maps | `services/smart_navigation_manager.py` | `FLOW_MAPS` |
| بيانات المستشفيات | `services/hospitals_service.py` | — |
| بيانات المترجمين | `services/translators_service.py` | — |
| بيانات الأطباء (DB) | `doctor_handlers.py` ← `db/models.py:Doctor` | composite key lookup |
| بيانات الأطباء (JSON) | `services/doctors_smart_search.py` | `data/doctors_organized.json` |
| Admin hospital management | `admin_hospitals_management.py` | — |
| Admin translator management | `admin_translators_management.py` | — |

---

## 7. قواعد البيانات — الجداول الرئيسية

| الجدول | الاستخدام |
|--------|-----------|
| `Report` | التقارير المنشورة |
| `Patient` | المرضى (يُنشأ تلقائياً عند أول تقرير) |
| `Hospital` | المستشفيات |
| `Department` | الأقسام |
| `Doctor` | الأطباء (composite key: name + hospital_id + department_id) |
| `TranslatorDirectory` | المترجمون (الجدول الرسمي — linked بـ translator_id) |

---

## 8. تدفق البيانات — report_tmp

كل بيانات التقرير تُحفظ مؤقتاً في:
```python
context.user_data['report_tmp']  # dict
```

المفاتيح الرئيسية:
```
patient_name, hospital_name, department_name, doctor_name
translator_id, translator_name
complaint, diagnosis, decision
followup_date, followup_time, followup_reason
current_flow  ← flow_type الفعلي
medical_action ← النص العربي للإجراء
```

يُمسح بالكامل بعد `save_report_to_database` بنجاح.

---

## 9. مصادر بيانات الأطباء

```
عرض قائمة الأطباء
        │
        ├── 1. SQLite (Doctor table) — composite key: name + hospital_id + dept_id
        │         ↓ أولوية قصوى
        └── 2. data/doctors_organized.json (عبر doctors_smart_search.py)
                  ↓ يُضاف ما لم يظهر من DB

دمج بدون تكرار → القائمة النهائية للمستخدم
```

---

## 10. نقاط الدخول للـ Handlers

```python
# handlers_registry.py يسجّل بالترتيب:
1. InlineQueryHandler ← patient search (webhook only)
2. user_reports_add_new_system.register(app) ← ConversationHandler
3. user_reports_edit.register(app) ← Edit ConversationHandler
4. admin_*.register(app) ← Admin handlers
5. universal_fallback ← يمسك ما لم يُعالج
```
