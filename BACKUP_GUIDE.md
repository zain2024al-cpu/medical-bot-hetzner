# دليل النسخ الاحتياطي — بوت التقارير الطبية

هذا الملف يشرح كل طبقات النسخ الاحتياطي المفعَّلة حالياً، مكان كل نسخة، وطريقة الاسترجاع عند الحاجة.

## نظرة عامة — 4 طبقات حماية

| # | الطبقة | التكرار | المحتوى | المكان |
|---|--------|---------|---------|--------|
| 1 | نسخ محلي سريع | كل ساعة | قاعدة البيانات فقط | `~/backups/` على السيرفر نفسه |
| 2 | نسخ محلي يومي | يومياً 3 صباحاً | قاعدة البيانات فقط (مع WAL checkpoint) | `~/medical-bot-hetzner/db/backups/` |
| 3 | نسخ بالبريد يومي | يومياً (مع مهمة الصيانة الداخلية للبوت) | قاعدة البيانات فقط (مضغوطة) | بريدك الإلكتروني |
| 4 | نسخ بالبريد أسبوعي | أسبوعياً | **ملفات الإعدادات السرية فقط**: `.env` + `config.env` | بريدك الإلكتروني |

**لماذا 4 طبقات؟**
- الطبقات 1-2 (محلية): استرجاع سريع لحالات الحذف/التلف البسيط، لكنها على نفس القرص — لا تحمي من كارثة كاملة بالسيرفر.
- الطبقة 3 (بريد يومي): نسخة **خارج السيرفر** لقاعدة البيانات فقط — تحمي البيانات الطبية والمالية يومياً.
- الطبقة 4 (بريد أسبوعي): نسخة **خارج السيرفر** لملفات الإعدادات السرية (`BOT_TOKEN`, `ADMIN_IDS`, إلخ) اللي **لا توجد في GitHub أصلاً** (لأسباب أمنية) ولا في أي نسخة أخرى. لو ضاع السيرفر بالكامل، هذه هي الطريقة الوحيدة لاسترجاع ملفات الإعدادات بدون إعادة كتابتها يدوياً من الذاكرة.

⚠️ **ملاحظة مهمة**: جُرِّب في البداية إرسال **كود المشروع كاملاً** أسبوعياً بالبريد، لكن Gmail يحظر أي مرفق مضغوط يحتوي ملفات كود/سكربتات (`.py`, `.sh`) تلقائياً كـ"محتوى خطر محتمل" — حتى لو كان المرسِل والمستقبِل نفس الحساب. لذلك اقتصر النطاق على ملفات الإعدادات فقط (لا كود بداخلها، فلا تُحظَر). **الكود نفسه محفوظ بالكامل وبتاريخه على GitHub — وهو مصدر أفضل أصلاً من أي نسخة بريد.**

---

## الطبقة 1: النسخ المحلي السريع (كل ساعة)

- **من يشغّله**: مهمة داخلية بكود البوت نفسه (`services/scheduler.py` → `_sqlite_quick_backup_job`)
- **الملف**: `~/backups/backup_$DATE.db` (سكربت `/home/botuser/scripts/backup.sh` عبر cron أيضاً، كل ساعة)
- **ميزة إضافية**: لو لاحظ سكربت `scripts/backup.sh` أن قاعدة البيانات فارغة أو مفقودة، يسترجعها تلقائياً من `backup_safe.db` أو آخر نسخة متاحة.
- **الاحتفاظ**: آخر 50 نسخة فقط (الأقدم تُحذف تلقائياً).

## الطبقة 2: النسخ المحلي اليومي (3 صباحاً)

- **السكربت**: `/home/botuser/backup_database.sh` (عبر cron، يومياً الساعة 3 صباحاً)
- **الملف**: `~/medical-bot-hetzner/db/backups/backup_daily_TIMESTAMP.db`
- **ميزة إضافية**: يعمل `WAL checkpoint` قبل النسخ لضمان نسخة متّسقة تماماً.
- **الاحتفاظ**: آخر 30 يوماً فقط.
- **اللوغ**: `/home/botuser/backup.log`

## الطبقة 3: النسخ بالبريد اليومي (قاعدة البيانات فقط)

- **من يشغّله**: مهمة داخلية بكود البوت (`services/scheduler.py` → `_sqlite_daily_backup_job` → `services/backup_email.py::send_backup_via_email`)
- **المحتوى**: نسخة مضغوطة (`.gz`) من قاعدة البيانات فقط، تُرسَل تلقائياً لبريدك بعد كل نسخة محلية يومية ناجحة.
- **لا يحتاج cron منفصل** — يعمل تلقائياً طالما البوت شغّال.

## الطبقة 4: النسخ بالبريد الأسبوعي (ملفات الإعدادات السرية)

- **السكربت**: `/home/botuser/full_project_backup.sh` (عبر cron، أسبوعياً — الأحد 4 صباحاً)
- **المحتوى**: أرشيف `tar.gz` صغير يشمل **فقط**:
  - **`.env` و`config.env`** — ملفات الإعدادات السرية (التوكن، معرفات الأدمن، معرفات المجموعات) — **غير موجودة في أي مكان آخر خارج السيرفر**
  - (الكود *لا* يُضمَّن — محفوظ بالكامل على GitHub أصلاً، وتضمينه يتسبب بحظر Gmail للمرفق)
- **الاحتفاظ**: آخر 8 نسخ أسبوعية (~شهرين) في `~/full_backups/`، تُرسَل أيضاً بالبريد لكل نسخة.
- **اللوغ**: `/home/botuser/full_backup.log`

---

## متطلبات التشغيل (`.env`)

```
BACKUP_EMAIL_FROM=بريدك@gmail.com
BACKUP_EMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx   # App Password من Google (وليس كلمة المرور العادية)
BACKUP_EMAIL_TO=بريد_الوجهة@gmail.com        # اختياري — افتراضياً نفس FROM
```

للحصول على App Password: فعّل "التحقق بخطوتين" على حسابك، ثم من https://myaccount.google.com/apppasswords أنشئ رمزاً جديداً.

---

## كيف تسترجع نسخة عند الحاجة؟

### استرجاع قاعدة البيانات فقط (من نسخة محلية أو بريد)
```bash
# أوقف البوت أولاً
pm2 stop medbot

# لو النسخة من البريد: فك الضغط أولاً
gunzip daily_YYYYMMDD_HHMMSS.db.gz

# انسخ النسخة فوق القاعدة الحالية (بعد أخذ نسخة احتياطية من الحالية أولاً للأمان)
cp ~/medical-bot-hetzner/db/medical_reports.db ~/medical_reports_before_restore.db
cp daily_YYYYMMDD_HHMMSS.db ~/medical-bot-hetzner/db/medical_reports.db

pm2 start medbot
```

### استرجاع المشروع كاملاً (سيناريو كارثة/سيرفر جديد بالكامل)
```bash
# 1) استنسخ الكود من GitHub (المصدر الأساسي دائماً)
git clone https://github.com/zain2024al-cpu/medical-bot-hetzner.git ~/medical-bot-hetzner
cd ~/medical-bot-hetzner

# 2) استرجع ملفات الإعدادات السرية من الأرشيف الأسبوعي المُستلَم بالبريد
tar -xzf config_secrets_YYYYMMDD_HHMMSS.tar.gz -C ~/medical-bot-hetzner/

# 3) استرجع قاعدة البيانات من أحدث نسخة (بريد يومي أو محلية)
gunzip -c daily_YYYYMMDD_HHMMSS.db.gz > ~/medical-bot-hetzner/db/medical_reports.db

# 4) أكمل التجهيز المعتاد
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
pm2 start app.py --interpreter ./venv/bin/python --name medbot
```

---

## التحقق من عمل النسخ (اختبار يدوي فوري)

```bash
cd ~/medical-bot-hetzner
source venv/bin/activate

# اختبار النسخ اليومي بالبريد (قاعدة البيانات فقط)
python3 -c "
import config.settings
from services.render_backup import create_local_backup
from services.backup_email import send_backup_via_email
path = create_local_backup('daily')
print('backup path:', path)
print('email sent:', send_backup_via_email(path))
"

# اختبار سكربت المشروع الأسبوعي كاملاً
bash /home/botuser/full_project_backup.sh
tail -20 /home/botuser/full_backup.log
```

⚠️ **ملاحظة مهمة**: أوامر الاختبار اليدوي لازم تستورد `config.settings` أولاً (كما بالمثال أعلاه) — هذا ما يحمّل فعلياً ملفات `.env`/`config.env`. تجاهل هذه الخطوة يجعل بيانات البريد تظهر "غير مضبوطة" حتى لو كانت صحيحة، لأن التحميل لا يحدث تلقائياً خارج التشغيل الطبيعي للبوت.
