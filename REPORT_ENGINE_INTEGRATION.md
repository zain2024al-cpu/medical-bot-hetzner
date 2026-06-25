# ================================================
# REPORT_ENGINE_INTEGRATION.md
# 🔌 كيفية دمج النظام الجديد في التطبيق
# ================================================

## 📋 خطوات التكامل

### 1. استيراد Logging

قم بإضافة هذا السطر في **أعلى app.py**:

```python
from shared.logging_config import setup_logging
```

### 2. تسجيل معالج التقارير الجديد

في **app.py** أو **main dispatcher setup**، أضف:

```python
from bot.handlers.admin.admin_reports_new import register_new_reports_handlers

# ... بعد إنشاء application و dispatcher ...

# تسجيل معالجات التقارير الجديدة
register_new_reports_handlers(application)
```

### 3. إضافة أزرار القائمة الرئيسية

إذا كان لديك قائمة رئيسية للمشرفين، أضف زراً جديداً:

```python
keyboard = [
    [InlineKeyboardButton("🖨️ التقارير الجديدة", callback_data="admin:reports_new")],
    # ... الأزرار الأخرى ...
]

# أو أضف command:
/reports_new - التقارير الجديدة
```

### 4. التحقق من الاستيرادات

تأكد من وجود جميع المتطلبات:

```bash
pip install reportlab
pip install matplotlib
pip install arabic_reshaper
pip install python-bidi
pip install sqlalchemy
```

---

## 🧪 اختبار النظام

### Test 1: التقرير الشامل

```python
from services.reporting_engine import ReportEngine
from services.reporting_engine.filters import (
    CompositeFilter, DateRangeFilter
)
from shared.report_constants import ReportType, DateRangePreset, ExportFormat
from services.export_handlers.export_factory import ExportFactory

# 1. إنشاء الفلاتر
filters = CompositeFilter()
filters.add("date_range", DateRangeFilter(preset=DateRangePreset.LAST_MONTH))

# 2. بناء التقرير
engine = ReportEngine()
report_data = engine.build_report(
    report_type=ReportType.GLOBAL,
    filters=filters,
    title="تقرير شامل - اختبار",
)

# 3. التصدير
pdf_buffer = ExportFactory.export(
    report_data=report_data,
    format=ExportFormat.PDF,
)

# 4. حفظ الملف للتحقق
if pdf_buffer:
    with open("test_global_report.pdf", "wb") as f:
        f.write(pdf_buffer.getvalue())
    print("✅ تم إنشاء التقرير بنجاح")
else:
    print("❌ فشل إنشاء التقرير")
```

### Test 2: تقرير المريض

```python
# نفس الخطوات لكن مع:
report_data = engine.build_report(
    report_type=ReportType.PATIENT,
    filters=filters,
    patient_id=1,
    title="تقرير المريض - اختبار",
)
```

---

## 📊 الملفات الجديدة المُنشأة

```
✅ shared/report_constants.py
✅ shared/logging_config.py

✅ services/reporting_engine/__init__.py
✅ services/reporting_engine/report_data.py
✅ services/reporting_engine/report_engine.py
✅ services/reporting_engine/report_data_collector.py
✅ services/reporting_engine/report_aggregator.py
✅ services/reporting_engine/report_stats_calculator.py

✅ services/reporting_engine/filters/__init__.py
✅ services/reporting_engine/filters/base_filter.py
✅ services/reporting_engine/filters/date_range_filter.py
✅ services/reporting_engine/filters/hospital_filter.py
✅ services/reporting_engine/filters/department_filter.py
✅ services/reporting_engine/filters/doctor_filter.py
✅ services/reporting_engine/filters/translator_filter.py
✅ services/reporting_engine/filters/patient_filter.py
✅ services/reporting_engine/filters/medical_action_filter.py
✅ services/reporting_engine/filters/composite_filter.py

✅ services/pdf_generation/__init__.py
✅ services/pdf_generation/pdf_builder.py
✅ services/pdf_generation/pdf_styles.py
✅ services/pdf_generation/pdf_tables.py
✅ services/pdf_generation/pdf_charts.py
✅ services/pdf_generation/pdf_renderer_arabic.py

✅ services/export_handlers/__init__.py
✅ services/export_handlers/export_factory.py

✅ db/repositories/statistics_repository.py

✅ bot/handlers/admin/admin_reports_new.py

✅ REPORT_ENGINE_DOCUMENTATION.md
✅ REPORT_ENGINE_INTEGRATION.md
```

---

## 🔍 التحقق من الأخطاء

إذا واجهت أخطاء:

### خطأ: ModuleNotFoundError

```
❌ No module named 'reportlab'
```

**الحل:**
```bash
pip install reportlab --upgrade
```

### خطأ: الخطوط العربية غير تعمل

```
⚠️ مكتبات العربية غير متوفرة
```

**الحل:**
```bash
pip install arabic_reshaper python-bidi
```

### خطأ: لا بيانات في التقرير

```
⚠️ لا توجد بيانات للتقرير
```

**الحل:**
- تحقق من الفلاتر المطبقة
- تأكد من وجود بيانات في قاعدة البيانات
- راجع `logs/reports_YYYYMMDD.log` للتفاصيل

---

## 🚀 النظام الجديد vs القديم

| الميزة | القديم | الجديد |
|--------|--------|--------|
| عدد الأزرار | 10+ | 2 |
| أنواع التقارير | محددة | موسعة |
| إعادة الاستخدام | منخفضة | عالية جداً |
| الفلاتر | متعددة ومختلفة | موحدة |
| دعم RTL | جزئي | كامل |
| Logging | محدود | شامل |
| إضافة تقارير جديدة | تعديل المحرك | نفس المحرك |

---

## 📋 خطة الحذف التدريجي

### المرحلة 1 (حالياً): التنفيذ ✅
- الملفات القديمة محفوظة
- النظام الجديد يعمل جنباً إلى جنب

### المرحلة 2 (بعد الاختبار): التحويل
- نقل المستخدمين تدريجياً
- الأزرار القديمة مخفية (اختيارية)

### المرحلة 3 (بعد التأكد): الحذف
- حذف الملفات القديمة
- حذف الأزرار القديمة

---

## ✅ Checklist قبل الإطلاق

- [ ] تثبيت جميع المتطلبات
- [ ] استيراد logging_config في app.py
- [ ] تسجيل معالجات التقارير الجديدة
- [ ] اختبار التقرير الشامل
- [ ] اختبار تقرير المريض
- [ ] التحقق من ملفات PDF
- [ ] اختبار مع البيانات الفعلية
- [ ] مراجعة logs للأخطاء
- [ ] اختبار على جهاز الإنتاج

---

## 📞 التواصل والدعم

في حالة أي مشاكل:

1. افتح `logs/reports_YYYYMMDD.log`
2. ابحث عن رسالة خطأ (❌)
3. اتبع الحل المقترح في هذا الملف
4. تواصل إذا استمرت المشكلة

---

**تم الإنشاء:** 2026-06-25  
**الإصدار:** 1.0  
**الحالة:** جاهز للاستخدام ✅
