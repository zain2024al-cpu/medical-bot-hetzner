# ARCHITECTURE RULES
## قواعد البنية والتطوير — ملزمة لكل تعديل

---

## 1. قواعد البنية العامة

### 1.1 ملكية المنطق (Ownership)
- كل منطق له مالك واحد فقط — ملف واحد يملك قرار التنفيذ.
- إذا نفس المنطق موجود في مكانين، أحدهما خطأ ويجب حذفه.
- لا يوجد "نسخة احتياطية" من الكود داخل الكود الحي.

### 1.2 مسؤولية الوحدة (Single Responsibility)
- كل ملف له وظيفة واحدة محددة: إما handler، أو renderer، أو service، أو navigation.
- `flows/shared.py` يملك: حفظ التقرير، بث التقرير، عرض الملخص النهائي، اختيار المترجم.
- `doctor_handlers.py` يملك: عرض قائمة الأطباء، استقبال الاختيار.
- `hospital_handlers.py` يملك: عرض قائمة المستشفيات، استقبال الاختيار.
- `department_handlers.py` يملك: عرض قائمة الأقسام، استقبال الاختيار.
- `patient_handlers.py` يملك: عرض قائمة المرضى، استقبال الاختيار.

### 1.3 لا handlers مكررة
- لا يوجد handler لنفس callback في ملفين مختلفين.
- إذا flow جديد يحتاج نفس السلوك، يستدعي الدالة الموجودة — لا ينسخها.

### 1.4 لا كود قديم معطّل
- لا توجد دوال `#` معلقة (commented-out) في الكود الحي.
- لا يوجد `LEGACY`, `OLD_`, `BACKUP_`, `_v1`, `_v2` داخل الملفات النشطة.
- إذا الكود القديم آمن للحذف، يُحذف فوراً — لا يُبقى.

### 1.5 Extraction Rule
- لا تعطّل ثم تضيف — استبدل أو فوّض فقط.
- تسلسل الإصلاح: Extract → Delegate → Remove (بالترتيب).
- Compatibility stubs مسموحة فقط أثناء المرحلة الانتقالية، وتُحذف عند الانتهاء.

---

## 2. قواعد Navigation

### 2.1 المرجع الوحيد للتنقل
- `context.user_data['history']` هو المصدر الوحيد لحالة التنقل.
- الملف المالك: `navigation.py` — الدوال: `nav_push`, `nav_pop`, `nav_peek`, `nav_clear`.
- لا أحد يكتب مباشرة على `context.user_data['history']` خارج `navigation.py`.

### 2.2 التنقل للأمام
- كل انتقال forward يستدعي `nav_push(context, current_state)` قبل الانتقال.
- لا يوجد hardcoded "الخطوة السابقة" في أي flow handler.

### 2.3 التنقل للخلف
- زر الرجوع يستدعي `nav_pop(context)` للحصول على الخطوة السابقة.
- لا يوجد custom back logic داخل أي flow — كل الرجوع عبر `navigation_helpers.py`.
- الملف المالك لمنطق الرجوع: `navigation_helpers.py` → `handle_smart_back_navigation`.

### 2.4 Pagination
- callbacks الصفحات (page_next, page_prev) لا تضغط على navigation stack.
- Pagination هو عرض فقط، لا يغير حالة التنقل.

### 2.5 ممنوع
- ممنوع استخدام `SmartNavigationManager.get_previous_step()` كبديل لـ `nav_pop`.
- ممنوع حساب الخطوة السابقة يدوياً بالـ `FLOW_MAPS` داخل handler.
- ممنوع تخزين "previous_state" يدوياً في `report_tmp`.

---

## 3. قواعد Handlers

### 3.1 كل flow في ملف مستقل
- كل نوع تقرير جديد → ملف جديد داخل `flows/`.
- لا تضاف flows جديدة داخل `flows/shared.py` — shared.py للمشترك فقط.
- المشترك بين جميع flows: اختيار المترجم، الملخص النهائي، الحفظ، البث.

### 3.2 لا inline keyboards داخل handlers
- الـ handler يعالج الإدخال فقط — لا يبني keyboards.
- بناء الكيبورد: ملفات `renderers/` أو `ui_primitives.py`.
- استثناء وحيد: keyboards بسيطة جداً (زرين) في نفس الملف مسموح مؤقتاً.

### 3.3 منطق DB في services فقط
- لا `session.query()` داخل handler مباشرة إلا عند الضرورة القصوى.
- خدمات البيانات: `services/hospitals_service.py`, `services/translators_service.py`, `services/doctors_service.py`.
- استثناء: `save_report_to_database` في `flows/shared.py` — بسبب تعقيده وعدم قابلية تقسيمه حالياً.

### 3.4 Imports
- لا circular imports — إذا A يستورد B، فـ B لا يستورد A.
- Lazy imports (`from x import y` داخل دالة) مسموحة لكسر circular imports فقط.
- `common_imports.py` هو نقطة الدخول للـ models — لا imports مباشرة من `db.models` في الـ flows.

---

## 4. قواعد الإضافة والتعديل

### 4.1 قبل أي تعديل
1. حدد من يملك هذا المنطق (Ownership Map أدناه).
2. تحقق أن المنطق غير موجود في مكان آخر.
3. إذا موجود في مكانين، ابدأ بتوحيده أولاً قبل الإضافة.

### 4.2 إضافة flow جديد
1. أنشئ `flows/new_flow_name.py`.
2. أضف states في `states.py`.
3. سجّل في `conversation_handler.py`.
4. لا تلمس `flows/shared.py` إلا إذا أضفت شيئاً مشتركاً حقاً.

### 4.3 تعديل flow موجود
1. التعديل في ملف الـ flow فقط.
2. إذا التعديل يؤثر على المشترك (مترجم، ملخص، حفظ) → عدّل `flows/shared.py`.
3. لا تنسخ كوداً من shared إلى flow — استدعِ الدالة.

### 4.4 حذف كود
- تحقق أولاً: `grep -r "function_name" .` — هل يُستدعى من مكان آخر؟
- إذا لا → احذف مباشرة.
- إذا نعم → حوّل المستدعين أولاً ثم احذف.
- لا تعلّق الكود — إما حي أو محذوف.

---

## 5. Ownership Map

| الوظيفة | المالك | الملف |
|---------|--------|-------|
| Navigation stack | `navigation.py` | `nav_push / nav_pop / nav_peek` |
| Back navigation logic | `navigation_helpers.py` | `handle_smart_back_navigation` |
| اختيار المريض | `patient_handlers.py` | `show_patient_selection` |
| اختيار المستشفى | `hospital_handlers.py` | `show_hospital_selection` |
| اختيار القسم | `department_handlers.py` | `show_department_selection` |
| اختيار الطبيب | `doctor_handlers.py` | `render_doctor_selection` |
| اختيار المترجم | `flows/shared.py` | `show_translator_selection` |
| الملخص النهائي | `flows/shared.py` | `show_final_summary` |
| تأكيد النشر | `flows/shared.py` | `handle_final_confirm` |
| حفظ التقرير في DB | `flows/shared.py` | `save_report_to_database` |
| بث التقرير | `services/broadcast_service.py` | `broadcast_new_report` |
| بيانات المستشفيات | `services/hospitals_service.py` | — |
| بيانات المترجمين | `services/translators_service.py` | — |
| بيانات الأطباء (DB) | `doctor_handlers.py` → `db/models.py:Doctor` | — |
| بيانات الأطباء (JSON) | `services/doctors_smart_search.py` | `data/doctors_organized.json` |
| ConversationHandler assembly | `conversation_handler.py` | `register(app)` |
| State constants | `states.py` | — |
| Flow maps | `services/smart_navigation_manager.py` | `FLOW_MAPS` |
| Edit before publish | `edit_handlers/before_publish/router.py` | per-flow edit files |
| Edit after publish | `bot/handlers/user/user_reports_edit.py` | standalone |

---

## 6. ما هو ممنوع دائماً

- ممنوع إنشاء ملف `*_backup.py` أو `*_old.py` أو `*_v2.py` في المشروع.
- ممنوع نسخ دالة من ملف لآخر — استدعاء فقط.
- ممنوع إضافة logic بديل موازٍ (parallel logic) لمنطق قائم.
- ممنوع استخدام `try/except` لإخفاء أخطاء import — إذا فشل import، هذا bug يُصلح.
- ممنوع `globals()` أو `getattr(module, name)` لاستدعاء handlers — imports صريحة فقط.
- ممنوع `os.path.exists()` للتحقق من وجود ملف Python في runtime.
- ممنوع إنشاء ConversationHandler ثانٍ لنفس المستخدم — handler واحد فقط.
