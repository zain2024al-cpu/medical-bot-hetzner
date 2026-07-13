# اختبار سيناريوهات النظام الجديد

## السيناريو 1: تقرير شامل (اليوم)

```
1. Admin يضغط "🖨️ طباعة التقارير"
   ↓ ConversationHandler entry_point يستدعي start_reports_menu()
   ↓ الحالة: MENU_CHOOSE_TYPE

2. يظهر: "اختر نوع التقرير"
   [📊 تقرير شامل] [👤 تقرير مريض] [❌ إلغاء]

3. Admin يضغط "📊 تقرير شامل"
   ↓ pattern: report_menu:comp
   ↓ handle_type_selection() يستدعي show_period_menu()
   ↓ الحالة: CR_PERIOD

4. يظهر: "اختر الفترة"
   [🕐 اليوم] [📅 أسبوع] ... [⬅️ رجوع] [❌ إلغاء]

5. Admin يضغط "🕐 اليوم"
   ↓ pattern: cr:today
   ↓ handle_period() ينفذ:
      a. _resolve_period() → (today, today, label)
      b. get_reports(today, today) من services.reports_repository
      c. build_comprehensive_pdf(reports, stats, label)
      d. send_document(pdf_buf)

6. ✅ يستقبل PDF احترافي مع جداول ورسوم بيانية
```

**النقاط الحرجة:**
- entry_point message button: "🖨️ طباعة التقارير" → start_reports_menu ✓
- callback pattern: `report_menu:` → universal_fallback ✓
- callback pattern: `cr:` → universal_fallback ✓
- PDF generation: build_comprehensive_pdf تستورد reports_repository ✓

---

## السيناريو 2: تقرير مريض (كل التقارير)

```
1. Admin يضغط "🖨️ طباعة التقارير"
   ↓ start_reports_menu()
   ↓ MENU_CHOOSE_TYPE

2. Admin يضغط "👤 تقرير مريض"
   ↓ pattern: report_menu:patient
   ↓ handle_type_selection() يستدعي show_patient_search()
   ↓ الحالة: PR_SEARCH

3. يظهر: "اكتب اسم المريض"

4. Admin يكتب: "أحمد"
   ↓ handle_patient_search() ينفذ:
      a. get_patients_by_name("أحمد") من reports_repository
      b. يعرض قائمة نتائج البحث

5. Admin يختار مريض من النتائج
   ↓ pattern: pr:pick:ID
   ↓ handle_patient_picked() ينفذ:
      a. تخزين patient_id في context
      b. يعرض قائمة الأقسام
   ↓ الحالة: PR_DEPTS

6. Admin يضغط "✅ كل الأقسام"
   ↓ pattern: pr:depts:all
   ↓ handle_depts_picked() ينفذ:
      a. تخزين depts = None (كل الأقسام)
      b. يعرض قائمة الإجراءات
   ↓ الحالة: PR_ACTIONS

7. Admin يضغط "✅ كل الإجراءات"
   ↓ pattern: pr:actions:all
   ↓ handle_actions_picked() ينفذ:
      a. تخزين actions = None (كل الإجراءات)
      b. يعرض قائمة الفترات
   ↓ الحالة: PR_PERIOD

8. Admin يضغط "📋 كل التقارير"
   ↓ pattern: pr:period:ID:all
   ↓ handle_period_picked() ينفذ:
      a. get_reports(date.min, today, patient_id=ID, depts=None, actions=None)
      b. build_patient_pdf(patient, reports, depts=None, period_label)
      c. send_document(pdf_buf)

9. ✅ يستقبل PDF احترافي لمريض واحد
```

**النقاط الحرجة:**
- callback pattern: `pr:` → universal_fallback ✓
- حالات متعددة: PR_SEARCH → PR_PICK → PR_DEPTS → PR_ACTIONS → PR_PERIOD ✓
- PDF generation: build_patient_pdf تستورد reports_repository ✓

---

## فحوصات ضمان الجودة

### 1. فحص البناء (Build Check)
```bash
python -m py_compile bot/handlers/admin/admin_reports_menu.py
python -m py_compile bot/handlers/admin/admin_comprehensive_report.py
python -m py_compile bot/handlers/admin/admin_patient_report.py
python -m py_compile services/comprehensive_report_pdf.py
python -m py_compile services/patient_report_pdf.py
python -m py_compile services/reports_repository.py
```
✅ جميع الملفات تمرر

### 2. فحص الاستيرادات (Import Check)
```python
from bot.handlers.admin.admin_reports_menu import register
from bot.handlers.admin.admin_comprehensive_report import register
from bot.handlers.admin.admin_patient_report import register
from services.comprehensive_report_pdf import build_comprehensive_pdf
from services.patient_report_pdf import build_patient_pdf
from services.reports_repository import get_reports
```
✅ جميع الاستيرادات تعمل

### 3. فحص الدوال (Function Check)
✅ جميع الدوال المطلوبة موجودة
- admin_reports_menu: start_reports_menu, handle_type_selection, register
- admin_comprehensive: show_period_menu, handle_period, register
- admin_patient: show_patient_search, handle_patient_search, handle_patient_picked, handle_depts_picked, handle_actions_picked, handle_period_picked, register
- comprehensive_pdf: build_comprehensive_pdf
- patient_pdf: build_patient_pdf
- reports_repository: get_reports, get_patients_by_name, aggregate_*

### 4. فحص التسجيل (Registration Check)
✅ handlers_registry.py يسجل:
- register_reports_menu(app)
- register_comprehensive_report(app)
- register_patient_report(app)

### 5. فحص الـ Callbacks (Patterns Check)
✅ universal_fallback.py يحتوي على:
- r"^report_menu:"
- r"^cr:"
- r"^pr:"

### 6. فحص عدم التضارب (Conflict Check)
✅ لا يوجد:
- تضارب في callback patterns
- استيرادات دائرية
- دوال مفقودة
- أزرار مكررة

---

## الاستنتاج

✅ **النظام جاهز للإطلاق**

جميع الفحوصات أظهرت أن النظام:
1. خالي من أخطاء البناء
2. جميع الاستيرادات صحيحة
3. جميع الدوال موجودة ومعرفة
4. التسجيل صحيح في handlers_registry
5. الـ Callbacks صحيح في universal_fallback
6. لا يوجد تضارب أو مشاكل تكامل

**يمكن رفع التحديثات بأمان** 🚀
