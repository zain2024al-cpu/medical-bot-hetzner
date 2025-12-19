# 🚀 دليل إعدادات قاعدة البيانات للاستضافة الإلكترونية

## 📋 نظرة عامة

هذا الملف يشرح كيفية استخدام ملف `db/online_hosting_config.py` لإعداد قاعدة البيانات للاستضافة الإلكترونية على منصات مثل:
- Google Cloud Run
- Google App Engine
- Railway
- Render
- أي منصة استضافة أخرى

---

## 🔧 الملفات المطلوبة

### 1. ملف الإعدادات
```
db/online_hosting_config.py
```
يحتوي على جميع إعدادات قاعدة البيانات المخصصة للاستضافة الإلكترونية.

---

## ⚙️ الإعدادات المتاحة

### إعدادات المسار

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|-------------------|
| `DATABASE_PATH` | مسار قاعدة البيانات داخل الـ Container | `/app/db/medical_reports.db` |
| `BACKUP_DIR` | مجلد النسخ الاحتياطية المحلية | `/app/db/backups` |

### إعدادات Google Cloud Storage

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|-------------------|
| `GCP_PROJECT_ID` | معرف مشروع Google Cloud | `lunar-standard-477302-a6` |
| `GCS_BUCKET_NAME` | اسم Bucket في Cloud Storage | `{PROJECT_ID}-sqlite-backups` |
| `GCS_PERSISTENT_PATH` | مسار النسخة المستمرة في GCS | `persistent/medical_reports.db` |
| `GCS_BACKUP_PATH` | مسار النسخ الاحتياطية في GCS | `backups` |
| `GCS_LOCATION` | المنطقة الجغرافية | `asia-south1` |

### إعدادات النسخ الاحتياطي التلقائي

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|-------------------|
| `AUTO_BACKUP_ENABLED` | تفعيل النسخ الاحتياطي التلقائي | `true` |
| `AUTO_BACKUP_INTERVAL` | فترة النسخ الاحتياطي (بالدقائق) | `10` |
| `MAX_BACKUP_COPIES` | عدد النسخ المحفوظة | `30` |

### إعدادات SQLite

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|-------------------|
| `SQLITE_TIMEOUT` | مهلة الاتصال (بالثواني) | `30` |
| `SQLITE_POOL_SIZE` | حجم تجمع الاتصالات | `20` |
| `SQLITE_MAX_OVERFLOW` | الحد الأقصى للاتصالات الإضافية | `10` |
| `ENABLE_WAL_MODE` | تفعيل WAL Mode | `true` |
| `SQLITE_CACHE_SIZE` | حجم الذاكرة المؤقتة | `-64000` (64MB) |

### إعدادات الاستعادة والحفظ

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|-------------------|
| `AUTO_RESTORE_ON_STARTUP` | استعادة تلقائية عند البدء | `true` |
| `AUTO_SAVE_ON_SHUTDOWN` | حفظ تلقائي عند الإغلاق | `true` |

---

## 📝 كيفية الاستخدام

### 1. في ملف `env.yaml` (لـ Google Cloud)

```yaml
# إعدادات قاعدة البيانات للاستضافة
DATABASE_PATH: "/app/db/medical_reports.db"
GCP_PROJECT_ID: "lunar-standard-477302-a6"
GCS_BUCKET_NAME: "lunar-standard-477302-a6-sqlite-backups"
AUTO_BACKUP_ENABLED: "true"
AUTO_BACKUP_INTERVAL: "10"
AUTO_RESTORE_ON_STARTUP: "true"
AUTO_SAVE_ON_SHUTDOWN: "true"
```

### 2. في ملف `config.env` (للاستضافة المحلية)

```env
# إعدادات قاعدة البيانات للاستضافة
DATABASE_PATH=/app/db/medical_reports.db
GCP_PROJECT_ID=lunar-standard-477302-a6
GCS_BUCKET_NAME=lunar-standard-477302-a6-sqlite-backups
AUTO_BACKUP_ENABLED=true
AUTO_BACKUP_INTERVAL=10
AUTO_RESTORE_ON_STARTUP=true
AUTO_SAVE_ON_SHUTDOWN=true
```

### 3. في الكود (Python)

```python
from db.online_hosting_config import OnlineHostingConfig, init_online_hosting_config

# تهيئة الإعدادات عند بدء التطبيق
init_online_hosting_config()

# استخدام الإعدادات
database_path = OnlineHostingConfig.DATABASE_PATH
bucket_name = OnlineHostingConfig.GCS_BUCKET_NAME

# الحصول على جميع الإعدادات
config = OnlineHostingConfig.get_config_dict()

# طباعة الإعدادات (للتشخيص)
OnlineHostingConfig.print_config()
```

---

## 🔄 التكامل مع `db/session.py`

يمكن تحديث `db/session.py` لاستخدام الإعدادات من `online_hosting_config.py`:

```python
from db.online_hosting_config import OnlineHostingConfig

# استخدام المسار من الإعدادات
DATABASE_PATH = OnlineHostingConfig.DATABASE_PATH
DATABASE_URL = OnlineHostingConfig.get_database_url()

# استخدام إعدادات SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": OnlineHostingConfig.SQLITE_TIMEOUT,
        "isolation_level": None
    },
    pool_pre_ping=True,
    pool_recycle=OnlineHostingConfig.SQLITE_POOL_RECYCLE,
    pool_size=OnlineHostingConfig.SQLITE_POOL_SIZE,
    max_overflow=OnlineHostingConfig.SQLITE_MAX_OVERFLOW
)
```

---

## 🚀 خطوات النشر للاستضافة الإلكترونية

### 1. إعداد متغيرات البيئة

في منصة الاستضافة (Google Cloud Run / App Engine):

```bash
# متغيرات مطلوبة
DATABASE_PATH=/app/db/medical_reports.db

# متغيرات اختيارية (للنسخ الاحتياطي)
GCP_PROJECT_ID=lunar-standard-477302-a6
GCS_BUCKET_NAME=lunar-standard-477302-a6-sqlite-backups
AUTO_BACKUP_ENABLED=true
AUTO_BACKUP_INTERVAL=10
AUTO_RESTORE_ON_STARTUP=true
AUTO_SAVE_ON_SHUTDOWN=true
```

### 2. تحديث `app.py` لاستخدام الإعدادات

```python
from db.online_hosting_config import init_online_hosting_config

async def main():
    # تهيئة إعدادات الاستضافة
    init_online_hosting_config()
    
    # باقي الكود...
```

### 3. التأكد من وجود مجلد قاعدة البيانات

في `Dockerfile` أو `app.yaml`:

```dockerfile
# إنشاء مجلد قاعدة البيانات
RUN mkdir -p /app/db /app/db/backups
```

---

## 🔍 التحقق من الإعدادات

### طباعة الإعدادات الحالية

```python
from db.online_hosting_config import OnlineHostingConfig

# طباعة جميع الإعدادات
OnlineHostingConfig.print_config()

# التحقق من صحة الإعدادات
is_valid = OnlineHostingConfig.validate_config()
```

### الحصول على معلومات الإعدادات

```python
# الحصول على قاموس بجميع الإعدادات
config = OnlineHostingConfig.get_config_dict()

# الحصول على رابط قاعدة البيانات
db_url = OnlineHostingConfig.get_database_url()
```

---

## ⚠️ ملاحظات مهمة

### 1. المسارات
- للاستضافة الإلكترونية: استخدم مسارات مطلقة مثل `/app/db/medical_reports.db`
- للاستضافة المحلية: يمكن استخدام مسارات نسبية مثل `db/medical_reports.db`

### 2. النسخ الاحتياطي
- النسخ الاحتياطي التلقائي يتطلب إعداد Google Cloud Storage
- تأكد من وجود الصلاحيات المطلوبة للوصول إلى Cloud Storage

### 3. الأداء
- WAL Mode محسّن للأداء في البيئات متعددة الخيوط
- حجم الذاكرة المؤقتة قابل للتعديل حسب موارد الخادم

### 4. الأمان
- لا تضع معلومات حساسة في ملفات الإعدادات
- استخدم متغيرات البيئة للقيم الحساسة

---

## 🆘 استكشاف الأخطاء

### المشكلة: قاعدة البيانات لا تُحمّل من Cloud Storage

**الحل:**
1. تحقق من وجود `GCP_PROJECT_ID` و `GCS_BUCKET_NAME`
2. تأكد من وجود الصلاحيات المطلوبة
3. تحقق من أن `AUTO_RESTORE_ON_STARTUP=true`

### المشكلة: النسخ الاحتياطي لا يعمل

**الحل:**
1. تحقق من `AUTO_BACKUP_ENABLED=true`
2. تأكد من إعداد Google Cloud Storage بشكل صحيح
3. تحقق من السجلات (logs) للأخطاء

### المشكلة: قاعدة البيانات لا تُحفظ عند الإغلاق

**الحل:**
1. تأكد من `AUTO_SAVE_ON_SHUTDOWN=true`
2. أضف معالج إغلاق في `app.py`:

```python
import atexit
from db.persistent_storage import save_database_to_cloud

# حفظ قاعدة البيانات عند الإغلاق
atexit.register(save_database_to_cloud)
```

---

## 📚 مراجع إضافية

- [DATABASE_PERSISTENCE_GUIDE.md](./DATABASE_PERSISTENCE_GUIDE.md) - دليل استمرارية البيانات
- [db/persistent_storage.py](./db/persistent_storage.py) - مدير التخزين المستمر
- [db/session.py](./db/session.py) - مدير جلسات قاعدة البيانات

---

## ✅ الخلاصة

ملف `db/online_hosting_config.py` يوفر:
- ✅ إعدادات مركزية لقاعدة البيانات
- ✅ دعم النسخ الاحتياطي التلقائي
- ✅ تكامل مع Google Cloud Storage
- ✅ إعدادات محسّنة للأداء
- ✅ سهولة التخصيص والتعديل

استخدم هذا الملف لضمان عمل قاعدة البيانات بشكل صحيح في بيئة الاستضافة الإلكترونية! 🎉

