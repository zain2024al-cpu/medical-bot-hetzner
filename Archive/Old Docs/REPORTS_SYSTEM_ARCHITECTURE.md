# نظام التقارير الاحترافي الجديد
## Professional Reporting System Architecture

**التاريخ:** 2026-06-26  
**الهدف:** تحل محل 10 أزرار قديمة بـ نظام موحد واضح يدعم نوعين فقط من التقارير  
**الحالة:** ✅ مكتمل وجاهز للاختبار

---

## 📊 نظرة عامة

### المشكلة القديمة
- 10 أزرار طباعة مختلفة في `admin_printing.py` (2691 سطر)
- مسارات متداخلة ومعقدة
- عدم وضوح في الـ UX
- لا توجد PDFs احترافية

### الحل الجديد
**زر واحد:** "🖨️ طباعة التقارير"  
**نوعان فقط:**
1. 📊 **تقرير شامل** — جميع المرضى في فترة زمنية
2. 👤 **تقرير مريض** — مريض واحد مع تصفية متقدمة

---

## 🏗️ البنية المعمارية

```
🖨️ طباعة التقارير (Keyboard Button)
         ↓
admin_reports_menu.py (entry point)
    ↓                         ↓
📊 اختر النوع                👤 تقرير مريض
    ↓                         ↓
admin_comprehensive_report   admin_patient_report
    ↓                         ↓
build_comprehensive_pdf    build_patient_pdf
    ↓                         ↓
    [PDF]                    [PDF]
```

---

## 📁 الملفات الجديدة / المحدثة

### 1️⃣ **bot/handlers/admin/admin_reports_menu.py** (نقطة الدخول الرئيسية)

**المسؤولية:** عرض قائمة اختيار النوع وتوجيه إلى المسار المناسب

**الحالات:**
- `MENU_CHOOSE_TYPE` — اختيار النوع

**الـ Callbacks:**
- `report_menu:comp` → تقرير شامل
- `report_menu:patient` → تقرير مريض
- `report_menu:cancel` → إلغاء

**الـ Entry:**
```python
register_reports_menu(app)  # في handlers_registry.py
```

---

### 2️⃣ **bot/handlers/admin/admin_comprehensive_report.py** (التقرير الشامل)

**المسؤولية:** اختيار الفترة الزمنية وتوليد PDF يغطي جميع المرضى

**الحالات:**
- `CR_PERIOD` — اختيار الفترة الزمنية

**الفترات المتاحة:**
- 🕐 اليوم
- 📅 هذا الأسبوع
- 📅 هذا الشهر
- 📅 آخر 3 أشهر
- 📅 السنة كاملة

**الـ Callbacks:**
- `cr:today`, `cr:week`, `cr:month`, `cr:3m`, `cr:year` → توليد PDF
- `cr:back` → رجوع للقائمة الرئيسية
- `cr:cancel` → إلغاء

**الـ Output:**
```
Comprehensive_START_END.pdf
📊 التقرير الشامل
📅 الفترة: ...
📋 XXX حالة | XXX مريض | XXX مستشفى
```

---

### 3️⃣ **bot/handlers/admin/admin_patient_report.py** (تقرير المريض الواحد)

**المسؤولية:** بناء تقرير احترافي لمريض واحد مع تصفية متقدمة

**الحالات:**
- `PR_SEARCH` — البحث عن المريض
- `PR_PICK` — اختيار المريض من النتائج
- `PR_DEPTS` — اختيار الأقسام
- `PR_ACTIONS` — اختيار الإجراءات
- `PR_PERIOD` — اختيار الفترة الزمنية

**مسار الاستخدام:**
```
1. اكتب اسم المريض
2. اختر من النتائج
3. اختر: كل الأقسام أو محدد
4. اختر: كل الإجراءات أو محدد
5. اختر الفترة: كل التقارير / آخر شهر / آخر 3 أشهر
6. PDF احترافي
```

**الـ Callbacks:**
- `pr:pick:ID` → اختيار مريض
- `pr:depts:all/select` → اختيار أقسام
- `pr:actions:all/select` → اختيار إجراءات
- `pr:period:ID:RANGE` → اختيار فترة وتوليد PDF
- `pr:back_*` → التنقل للخلف
- `pr:cancel` → إلغاء

**الـ Output:**
```
Patient_ID_RANGE.pdf
👤 تقرير المريض
📝 اسم المريض
📅 الفترة: ...
📋 XXX تقرير
```

---

### 4️⃣ **services/comprehensive_report_pdf.py** (PDF Builder للشامل)

**الـ API:**
```python
pdf_buf = build_comprehensive_pdf(reports, stats, period_label)
```

**الأقسام:**
- غلاف احترافي
- ملخص الإحصائيات (إجمالي، مرضى، مستشفيات، أقسام، إجراءات)
- جدول المستشفيات
- جدول الأقسام
- جدول الإجراءات
- رسم بياني توزيع الإجراءات
- رسم بياني التوزيع الزمني

**الميزات:**
- ✅ دعم كامل للعربية RTL
- ✅ Fallback أنظمة للخطوط
- ✅ رسوم بيانية Matplotlib
- ✅ Pagination تلقائي
- ✅ Header/Footer على كل صفحة

---

### 5️⃣ **services/patient_report_pdf.py** (PDF Builder للمريض)

**الـ API:**
```python
pdf_buf = build_patient_pdf(patient, reports, dept_filter, period_label)
```

**الأقسام:**
- غلاف احترافي (بيانات المريض)
- ملخص إحصائي
- جدول المستشفيات
- جدول الأقسام
- جدول الإجراءات
- جدول التقارير التفصيلي
- رسوم بيانية

**الميزات:**
- ✅ دعم كامل للعربية RTL
- ✅ معلومات المريض والملف
- ✅ تصفية حسب الأقسام المختارة
- ✅ رسوم بيانية توضيحية

---

### 6️⃣ **services/reports_repository.py** (وسيط قاعدة البيانات)

**الدوال الرئيسية:**

```python
# البحث والفحص
async def get_patients_by_name(query_text) → list[dict]
async def get_reports(start, end, patient_id=None, depts=None, actions=None) → list[dict]
def get_all_departments() → list[str]
def get_all_actions() → list[str]

# التجميع
aggregate_by_hospital(reports) → dict[str, int]
aggregate_by_department(reports) → dict[str, int]
aggregate_by_action(reports) → dict[str, int]
aggregate_by_date(reports) → dict[date, int]
aggregate_by_translator(reports) → dict[str, int]

# الإحصائيات
compute_stats(reports) → dict
```

**الميزات:**
- ✅ Async/sync pattern with asyncio.to_thread()
- ✅ Error handling مع logging
- ✅ Fallback من Patient → Report.patient_name

---

## 🔗 التكامل مع النظام

### في `bot/handlers_registry.py`:
```python
from bot.handlers.admin.admin_reports_menu import register as register_reports_menu
from bot.handlers.admin.admin_comprehensive_report import register as register_comprehensive_report
from bot.handlers.admin.admin_patient_report import register as register_patient_report

register_reports_menu(app)              # Entry point
register_comprehensive_report(app)      # cr:* callbacks
register_patient_report(app)            # pr:* conversation
```

### في `bot/handlers/shared/universal_fallback.py`:
```python
KNOWN_CALLBACKS = [
    ...
    r"^report_menu:",      # Main menu
    r"^pr:",               # Patient report
    r"^cr:",               # Comprehensive report
]
```

### في `bot/keyboards.py`:
```python
def admin_main_kb():
    keyboard = [
        ["➕ إضافة حالة أولية", "🖨️ طباعة التقارير"],  # ← نفس الزر
        ...
    ]
```
الزر يذهب إلى `admin_reports_menu.start_reports_menu()`

---

## 🔄 مسار العمل الكامل

### مسار التقرير الشامل:
```
User: يضغط "🖨️ طباعة التقارير"
    ↓
admin_reports_menu.start_reports_menu()
    ↓ "اختر نوع التقرير"
    [📊 تقرير شامل] [👤 تقرير مريض]
    ↓ User يختار 📊
admin_comprehensive_report.show_period_menu()
    ↓ "اختر الفترة"
    [اليوم] [أسبوع] [شهر] [3 شهور] [سنة]
    ↓ User يختار (مثلاً) "شهر"
admin_comprehensive_report.handle_period()
    ↓
services.reports_repository.get_reports(start, end)
    ↓
services.comprehensive_report_pdf.build_comprehensive_pdf()
    ↓
context.bot.send_document(pdf_buf)
    ↓ User يستقبل PDF احترافي
```

### مسار تقرير المريض:
```
User: يضغط "🖨️ طباعة التقارير"
    ↓
admin_reports_menu.start_reports_menu()
    ↓ "اختر نوع التقرير"
    [📊 تقرير شامل] [👤 تقرير مريض]
    ↓ User يختار 👤
admin_patient_report.show_patient_search()
    ↓ "اكتب اسم المريض"
User: يكتب الاسم
    ↓
admin_patient_report.handle_patient_search()
    ↓ قائمة النتائج
    [مريض 1] [مريض 2] ...
    ↓ User يختار مريض
admin_patient_report.handle_patient_picked()
    ↓ "اختر الأقسام"
    [كل الأقسام] [اختيار محدد]
    ↓ User يختار
admin_patient_report.handle_depts_picked()
    ↓ "اختر الإجراءات"
    [كل الإجراءات] [اختيار محدد]
    ↓ User يختار
admin_patient_report.handle_actions_picked()
    ↓ "اختر الفترة"
    [كل التقارير] [آخر شهر] [آخر 3 أشهر]
    ↓ User يختار
admin_patient_report.handle_period_picked()
    ↓
services.reports_repository.get_reports(patient_id, depts, actions, start, end)
    ↓
services.patient_report_pdf.build_patient_pdf()
    ↓
context.bot.send_document(pdf_buf)
    ↓ User يستقبل PDF احترافي
```

---

## 🎨 ميزات الـ PDF

### الخطوط:
```
Windows: tahoma.ttf → arial.ttf → NotoNaskhArabic-Regular.ttf
Linux:   /usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf
Fallback: Helvetica
```

### الألوان (حسب احترافية):
```python
primary:    #1565C0 (أزرق داكن)
accent:     #0288D1 (أزرق فاتح)
success:    #2E7D32 (أخضر)
light_bg:   #F0F4F8 (خلفية فاتحة)
card_bg:    #FAFCFF (كارت خلفية)
grid:       #D0D9E8 (خطوط الجدول)
text_dark:  #1A237E (نص داكن)
text_gray:  #546E7A (نص رمادي)
```

### الجداول:
- Header باللون الأزرق مع نص أبيض
- صفوف متناوبة (أبيض وخلفية فاتحة)
- Borders دقيقة
- Padding احترافي

### الرسوم البيانية:
- Matplotlib horizontal bar charts
- Line charts للتوزيع الزمني
- ألوان متطابقة مع theme
- RTL-safe labels

---

## 🧪 اختبار

```bash
# تصريف الأخطاء:
python -m py_compile \
  bot/handlers/admin/admin_reports_menu.py \
  bot/handlers/admin/admin_comprehensive_report.py \
  bot/handlers/admin/admin_patient_report.py \
  services/comprehensive_report_pdf.py \
  services/patient_report_pdf.py \
  services/reports_repository.py

# اختبار الاستيرادات:
python -c "from bot.handlers.admin import admin_reports_menu, admin_comprehensive_report, admin_patient_report"
python -c "from services import comprehensive_report_pdf, patient_report_pdf, reports_repository"
```

---

## 📋 القائمة المتبقية

- [ ] حذف `admin_printing.py` (2691 سطر)
- [ ] حذف أي استيرادات قديمة من `admin_printing`
- [ ] اختبار كامل في بيئة التطوير
- [ ] اختبار الـ PDFs مع أنواع أرقام مختلفة
- [ ] تحسينات اختيارية: multiselect UI للأقسام والإجراءات

---

## 🎯 الملخص

✅ **نظام تقارير احترافي موحد**
- زر واحد بدلاً من 10
- مساران واضحان فقط
- PDFs احترافية بدعم كامل للعربية
- بنية معمارية نظيفة وقابلة للصيانة
- معايير عالية من الأداء والأمان
