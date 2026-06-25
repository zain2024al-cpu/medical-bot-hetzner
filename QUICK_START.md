# ================================================
# QUICK_START.md
# 🚀 دليل البدء السريع
# ================================================

## ⚡ ابدأ في 5 دقائق

### 1. التثبيت

```bash
pip install reportlab matplotlib arabic_reshaper python-bidi sqlalchemy
```

### 2. استيراد Logging

في **app.py**:

```python
from shared.logging_config import setup_logging

# سيتم إعداد Logging تلقائياً
```

### 3. تسجيل المعالج

في نفس **app.py**:

```python
from bot.handlers.admin.admin_reports_new import register_new_reports_handlers

# بعد إنشاء application
register_new_reports_handlers(application)
```

### 4. أضف الأمر للقائمة

```python
/reports_new - التقارير الجديدة
```

### ✅ تم! النظام جاهز

---

## 🧪 اختبر سريعاً

```python
from services.reporting_engine import ReportEngine
from services.reporting_engine.filters import (
    CompositeFilter, DateRangeFilter
)
from shared.report_constants import ReportType, DateRangePreset, ExportFormat
from services.export_handlers.export_factory import ExportFactory

# 1. الفلاتر
filters = CompositeFilter()
filters.add("date_range", DateRangeFilter(preset=DateRangePreset.LAST_MONTH))

# 2. بناء التقرير
engine = ReportEngine()
report_data = engine.build_report(
    report_type=ReportType.GLOBAL,
    filters=filters,
    title="تقرير شامل",
)

# 3. تصدير
pdf_buffer = ExportFactory.export(
    report_data=report_data,
    format=ExportFormat.PDF,
)

# 4. حفظ
with open("test_report.pdf", "wb") as f:
    f.write(pdf_buffer.getvalue())

print("✅ تم!")
```

---

## 📚 الملفات المهمة

| الملف | الدور |
|------|-------|
| `REPORT_ENGINE_DOCUMENTATION.md` | توثيق كامل |
| `REPORT_ENGINE_INTEGRATION.md` | كيفية الدمج |
| `REPORT_ENGINE_COMPLETE_SUMMARY.md` | ملخص شامل |
| `logs/reports_YYYYMMDD.log` | سجل الأخطاء |

---

## 🎯 المسارات المتاحة

### تقرير شامل
```
📊 تقرير شامل
  ↓ اختيار الفترة
    → آخر شهر
    → آخر 3 أشهر
    → هذه السنة
    → كل الفترات
  ↓ PDF جاهز
```

### تقرير مريض
```
👤 تقرير مريض
  ↓ البحث عن المريض
  ↓ اختيار الأقسام
  ↓ اختيار الإجراءات
  ↓ اختيار الفترة
  ↓ PDF جاهز
```

---

## ❌ في حالة الأخطاء

### خطأ: ModuleNotFoundError
```bash
pip install reportlab matplotlib
```

### خطأ: لا بيانات
- تحقق من قاعدة البيانات
- راجع `logs/reports_YYYYMMDD.log`

### خطأ: الخطوط العربية
```bash
pip install arabic_reshaper python-bidi
```

---

## 📞 هل تحتاج مساعدة؟

1. ✅ اقرأ الملفات المرفقة
2. ✅ افتح السجل للأخطاء
3. ✅ جرب الأمثلة المعطاة
4. ✅ تواصل إذا استمرت المشكلة

---

**تم!** 🎉 النظام جاهز للاستخدام
