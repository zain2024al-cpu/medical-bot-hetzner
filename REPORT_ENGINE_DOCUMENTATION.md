# ================================================
# REPORT_ENGINE_DOCUMENTATION.md
# 📊 توثيق محرك التقارير الجديد
# ================================================

## 📋 نظرة عامة

تم بناء **محرك تقارير موحد واحترافي** يدعم جميع أنواع التقارير من خلال نفس المحرك والمكونات.

### المرحلة الأولى:
- ✅ تقرير شامل (Global Report)
- ✅ تقرير مريض (Patient Report)

### المراحل القادمة (بدون تعديل المحرك):
- 🚀 تقرير مستشفى (Hospital Report)
- 🚀 تقرير مترجم (Translator Report)
- 🚀 تقرير رعاية صحية (Healthcare Report)
- 🚀 تقرير إداري (Executive Report)

---

## 🏗️ معمارية النظام

### 1. Filters System (نظام الفلاتر الموحد)

```
services/reporting_engine/filters/
├── base_filter.py              # الفلتر الأساسي (Abstract)
├── date_range_filter.py        # فلتر الفترة الزمنية
├── hospital_filter.py          # فلتر المستشفى
├── department_filter.py        # فلتر القسم
├── doctor_filter.py            # فلتر الطبيب
├── translator_filter.py        # فلتر المترجم
├── patient_filter.py           # فلتر المريض
├── medical_action_filter.py    # فلتر الإجراء
└── composite_filter.py         # دمج الفلاتر
```

**الاستخدام:**
```python
from services.reporting_engine.filters import (
    CompositeFilter, DateRangeFilter, HospitalFilter
)
from shared.report_constants import DateRangePreset

# إنشاء مجموعة فلاتر
filters = CompositeFilter()

# إضافة فلتر الفترة
date_filter = DateRangeFilter(preset=DateRangePreset.LAST_MONTH)
filters.add("date_range", date_filter)

# إضافة فلتر المستشفى
hospital_filter = HospitalFilter(hospital_ids=[1, 2, 3])
filters.add("hospitals", hospital_filter)

# الفلاتر الفعالة فقط ستُطبق
```

---

### 2. Report Engine (محرك التقارير)

```
services/reporting_engine/
├── report_engine.py              # المحرك الرئيسي
├── report_data.py                # بنية بيانات مرنة
├── report_data_collector.py      # جمع البيانات
├── report_aggregator.py          # تجميع البيانات
└── report_stats_calculator.py    # حساب الإحصائيات
```

**الاستخدام:**
```python
from services.reporting_engine import ReportEngine
from shared.report_constants import ReportType

engine = ReportEngine()

# بناء تقرير
report_data = engine.build_report(
    report_type=ReportType.GLOBAL,
    filters=filters,
    title="تقرير شامل",
    subtitle="الفترة: شهر واحد"
)

# ReportData مرن ويحتوي على:
# - Metadata (البيانات الوصفية)
# - Key Metrics (المؤشرات الرئيسية)
# - Statistics (الإحصائيات)
# - Tables (الجداول)
# - Charts (الرسوم البيانية)
# - Timeline (التسلسل الزمني)
# - Details (التفاصيل)
# - Recommendations (التوصيات)
# - Notes (ملاحظات)
# - Conclusion (الخاتمة)
```

---

### 3. PDF Generation (توليد PDF احترافي)

```
services/pdf_generation/
├── pdf_builder.py               # محرك بناء PDF
├── pdf_styles.py                # الأنماط والألوان
├── pdf_tables.py                # رسم الجداول
├── pdf_charts.py                # رسم الرسوم البيانية
└── pdf_renderer_arabic.py       # معالج العربية
```

**الاستخدام:**
```python
from services.pdf_generation import PDFBuilder

builder = PDFBuilder()
pdf_buffer = builder.build_from_report_data(report_data)

# النتيجة: BytesIO ready للإرسال إلى Telegram
```

---

### 4. Export Factory (مصنع التصدير)

معمارية Plugin تسمح بإضافة صيغ جديدة بسهولة:

```
services/export_handlers/
└── export_factory.py
    ├── PDFExporter        # مدعوم ✅
    ├── ExcelExporter      # قيد التطوير 🚀
    └── CSVExporter        # قيد التطوير 🚀
```

**الاستخدام:**
```python
from services.export_handlers.export_factory import ExportFactory
from shared.report_constants import ExportFormat

# تصدير إلى PDF
pdf_buffer = ExportFactory.export(
    report_data=report_data,
    format=ExportFormat.PDF,
    filename="my_report.pdf"
)

# في المستقبل: تصدير إلى Excel أو CSV دون تعديل المحرك
```

---

## 📊 بنية ReportData المرنة

```python
@dataclass
class ReportData:
    # البيانات الأساسية
    report_type: ReportType              # نوع التقرير
    title: str                           # عنوان
    subtitle: str                        # عنوان فرعي
    created_at: datetime                 # تاريخ الإنشاء
    
    # الأقسام (جميعها اختيارية)
    cover_page: Optional[Dict]           # صفحة الغلاف
    executive_summary: Optional[str]     # ملخص تنفيذي
    key_metrics: List[MetricItem]        # مؤشرات رئيسية
    statistics: Dict                     # إحصائيات
    tables: List[TableData]              # جداول
    charts: List[ChartData]              # رسوم بيانية
    timeline: List[TimelineItem]         # تسلسل زمني
    detailed_rows: List[DetailRow]       # تفاصيل
    recommendations: List[str]           # توصيات
    notes: List[str]                     # ملاحظات
    conclusion: str                      # خاتمة
```

---

## 🔄 مراحل الإنشاء (مع Logging)

```
1️⃣ BUILD FILTERS
   ├─ تحديد الفلاتر المطلوبة
   ├─ التحقق من صحتها
   └─ 📋 تسجيل الفلاتر المطبقة

2️⃣ FETCH DATA
   ├─ جمع البيانات من قاعدة البيانات
   ├─ تطبيق الفلاتر
   └─ 📋 تسجيل عدد السجلات المسترجعة

3️⃣ BUILD STATISTICS
   ├─ تجميع البيانات
   ├─ حساب الإحصائيات
   └─ 📋 تسجيل الإحصائيات المحسوبة

4️⃣ BUILD CHARTS
   ├─ تجهيز بيانات الرسوم البيانية
   ├─ إنشاء صور PNG
   └─ 📋 تسجيل عدد الرسوم البيانية

5️⃣ BUILD PDF
   ├─ إنشاء هيكل PDF
   ├─ إضافة الأقسام
   ├─ معالجة العربية (RTL)
   └─ 📋 تسجيل حجم الملف

6️⃣ EXPORT
   ├─ تحويل إلى BytesIO
   ├─ جاهز للإرسال
   └─ 📋 تسجيل النهاية
```

---

## 📋 نموذج الاستخدام الكامل

```python
# 1. استيراد المكتبات
from services.reporting_engine import ReportEngine
from services.reporting_engine.filters import (
    CompositeFilter, DateRangeFilter, PatientFilter
)
from services.export_handlers.export_factory import ExportFactory
from shared.report_constants import ReportType, DateRangePreset, ExportFormat

# 2. إنشاء الفلاتر
filters = CompositeFilter()
filters.add("date_range", DateRangeFilter(preset=DateRangePreset.LAST_MONTH))
filters.add("patient", PatientFilter(patient_id=123))

# 3. بناء التقرير
engine = ReportEngine()
report_data = engine.build_report(
    report_type=ReportType.PATIENT,
    filters=filters,
    title="تقرير المريض",
    patient_id=123
)

# 4. التصدير (حالياً PDF فقط)
pdf_buffer = ExportFactory.export(
    report_data=report_data,
    format=ExportFormat.PDF,
    filename="patient_report.pdf"
)

# 5. الإرسال عبر Telegram
await chat.send_document(
    document=pdf_buffer,
    filename="patient_report.pdf",
    caption="✅ تقرير المريض جاهز"
)
```

---

## 🔌 إضافة نوع تقرير جديد

لإضافة نوع تقرير جديد (مثل تقرير مستشفى) **بدون تعديل المحرك**:

### الخطوة 1: إضافة Template جديدة

```python
# templates/hospital_template.py

class HospitalReportTemplate:
    @staticmethod
    def prepare_report_data(aggregated, stats, kwargs):
        """تحضير بيانات تقرير مستشفى"""
        # إضافة منطق خاص بالمستشفى
        return report_data
```

### الخطوة 2: إنشاء Handler جديد

```python
# bot/handlers/admin/admin_hospital_reports.py

async def start_hospital_report(update, context):
    # منطق اختيار المستشفى
    pass

# ربطه بـ /hospital_report command
```

### الخطوة 3: استخدام نفس المحرك

```python
engine = ReportEngine()
report_data = engine.build_report(
    report_type=ReportType.HOSPITAL,  # النوع الجديد
    filters=filters,
    hospital_id=hospital_id
)
```

---

## 📝 ملف Logging الشامل

```
logs/reports_YYYYMMDD.log

Sample:
---
2026-06-25 14:30:00 - services.reporting_engine - INFO - 🚀 بدء بناء التقرير: global
2026-06-25 14:30:00 - services.reporting_engine - INFO - 📊 المرحلة 1: جمع البيانات
2026-06-25 14:30:01 - services.reporting_engine - INFO - ✅ تم جلب 150 تقرير
2026-06-25 14:30:01 - services.reporting_engine - INFO - 📈 المرحلة 2: تجميع البيانات
2026-06-25 14:30:02 - services.reporting_engine - INFO - 📉 المرحلة 3: حساب الإحصائيات
2026-06-25 14:30:02 - services.pdf_generation - INFO - 🔨 بدء إنشاء PDF للتقرير: global
2026-06-25 14:30:05 - services.pdf_generation - INFO - ✅ تم إنشاء PDF بنجاح (1250.50 KB)
---
```

---

## ✅ Checklist للمرحلة الأولى

- ✅ Filters System موحد
- ✅ Report Engine عام
- ✅ ReportData مرن
- ✅ PDF Builder احترافي
- ✅ Export Factory (قابل للتوسع)
- ✅ Statistics Repository
- ✅ Telegram Handler (2 زرار)
- ✅ Logging شامل
- ✅ دعم RTL كامل
- ✅ البيانات القديمة محفوظة

---

## 🚀 الخطوات التالية

1. اختبار النظام الجديد مع البيانات الفعلية
2. التأكد من عمل جميع الفلاتر
3. اختبار PDF في الطباعة
4. إضافة تقارير المستشفيات (نفس المحرك)
5. إضافة تقارير المترجمين (نفس المحرك)
6. إضافة Excel و CSV Exporters
7. حذف النظام القديم بعد التأكد

---

## 📞 الدعم والمشاكل

للإبلاغ عن مشاكل أو طلب ميزات جديدة:

1. تحقق من ملف `logs/reports_YYYYMMDD.log`
2. ابحث عن رسالة خطأ (❌)
3. تواصل مع فريق التطوير

---

**تم إنشاؤه بواسطة:** Report Engine v1.0  
**التاريخ:** 2026-06-25  
**الحالة:** جاهز للاستخدام ✅
