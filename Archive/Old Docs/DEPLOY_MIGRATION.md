# تعليمات إضافة عمود radiation_therapy_recommendations

## المشكلة
العمود `radiation_therapy_recommendations` غير موجود في قاعدة البيانات على السيرفر، مما يسبب خطأ عند استخدام نظام التقييم.

## الحل

### الطريقة 1: استخدام السكربت (موصى به)

1. ارفع الملف `run_migration_radiation.py` إلى السيرفر:
```bash
scp run_migration_radiation.py botuser@5.223.58.71:/home/botuser/medical-bot/
```

2. اتصل بالسيرفر:
```bash
ssh botuser@5.223.58.71
```

3. انتقل إلى مجلد البوت:
```bash
cd /home/botuser/medical-bot
```

4. نفّذ السكربت:
```bash
python3 run_migration_radiation.py
```

### الطريقة 2: تنفيذ SQL مباشرة

اتصل بقاعدة البيانات على السيرفر:
```bash
ssh botuser@5.223.58.71
cd /home/botuser/medical-bot
sqlite3 db/medical_reports.db
```

ثم نفّذ:
```sql
ALTER TABLE reports ADD COLUMN radiation_therapy_recommendations TEXT;
```

للتحقق:
```sql
PRAGMA table_info(reports);
```

ثم اخرج:
```sql
.quit
```

### الطريقة 3: استخدام Python مباشرة على السيرفر

```bash
ssh botuser@5.223.58.71
cd /home/botuser/medical-bot
python3 -c "
import sqlite3
conn = sqlite3.connect('db/medical_reports.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(reports)')
columns = [col[1] for col in cursor.fetchall()]
if 'radiation_therapy_recommendations' not in columns:
    cursor.execute('ALTER TABLE reports ADD COLUMN radiation_therapy_recommendations TEXT')
    conn.commit()
    print('SUCCESS: Column added')
else:
    print('INFO: Column already exists')
conn.close()
"
```

## التحقق من النجاح

بعد تنفيذ أي من الطرق أعلاه، تحقق من أن العمود موجود:
```bash
sqlite3 db/medical_reports.db "PRAGMA table_info(reports);" | grep radiation_therapy_recommendations
```

إذا ظهر العمود، فالمشكلة تم حلها! ✅
