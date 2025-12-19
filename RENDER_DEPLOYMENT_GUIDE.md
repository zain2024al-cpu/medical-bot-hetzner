# 🚀 دليل النشر على Render

## 📋 نظرة عامة

هذا الدليل يشرح كيفية نشر البوت الطبي على منصة Render لتحديث البيانات.

---

## ✅ المتطلبات

1. حساب على [Render.com](https://render.com)
2. حساب GitHub (لربط المستودع)
3. قاعدة البيانات المحلية جاهزة للرفع

---

## 📝 الخطوات

### 1. إعداد المستودع على GitHub

#### أ. رفع الكود إلى GitHub:

```bash
# التأكد من أنك في مجلد المشروع
cd medical_reports_bot

# إضافة جميع الملفات
git add .

# عمل commit
git commit -m "إعداد النشر على Render"

# رفع إلى GitHub
git push origin main
```

#### ب. التأكد من أن الملفات المهمة موجودة:
- ✅ `Dockerfile`
- ✅ `requirements.txt`
- ✅ `render.yaml`
- ✅ `app.py`
- ✅ جميع ملفات المشروع

---

### 2. رفع قاعدة البيانات إلى Render Disk

Render يوفر **Disk Storage** لحفظ قاعدة البيانات بشكل دائم.

#### أ. رفع قاعدة البيانات:

**الطريقة 1: عبر Render Dashboard**
1. اذهب إلى Render Dashboard
2. أنشئ **Disk** جديد
3. ارفع ملف `db/medical_reports.db` إلى الـ Disk

**الطريقة 2: عبر Git (مؤقت)**
```bash
# نسخ قاعدة البيانات إلى مجلد مؤقت
cp db/medical_reports.db db/medical_reports_initial.db

# إضافة إلى Git (مؤقت - فقط للرفع الأول)
git add db/medical_reports_initial.db
git commit -m "إضافة قاعدة البيانات الأولية"
git push origin main
```

**ملاحظة:** بعد الرفع، احذف `medical_reports_initial.db` من Git.

---

### 3. إنشاء Service على Render

#### أ. تسجيل الدخول إلى Render:
1. اذهب إلى [dashboard.render.com](https://dashboard.render.com)
2. سجل الدخول بحسابك

#### ب. إنشاء Web Service جديد:
1. اضغط على **"New +"**
2. اختر **"Web Service"**
3. اختر **"Build and deploy from a Git repository"**
4. اربط حساب GitHub الخاص بك
5. اختر المستودع `medical_reports_bot`

#### ج. إعدادات الخدمة:

**Basic Settings:**
- **Name:** `medical-reports-bot`
- **Region:** اختر أقرب منطقة (مثلاً: `Oregon`)
- **Branch:** `main`
- **Root Directory:** (اتركه فارغاً)
- **Runtime:** `Docker`
- **Dockerfile Path:** `./Dockerfile`

**Environment Variables:**
أضف المتغيرات التالية:

```
BOT_TOKEN=8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo
ADMIN_IDS=2116274898
TIMEZONE=Asia/Riyadh
AI_ENABLED=true
AI_MODEL_NAME=gpt-4
AI_MAX_TOKENS=2000
OPENAI_API_KEY=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
OPENAI_MODEL=gpt-4o
DATABASE_PATH=/app/db/medical_reports.db
PORT=8080
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
AUTO_RESTORE_ON_STARTUP=true
AUTO_SAVE_ON_SHUTDOWN=true
AUTO_BACKUP_ENABLED=true
AUTO_BACKUP_INTERVAL=10
```

**Plan:**
- **Starter:** مجاني (مع قيود)
- **Standard:** مدفوع (موصى به للإنتاج)

#### د. إعدادات متقدمة:

**Health Check:**
- **Health Check Path:** `/health` (اختياري)
- **Health Check Interval:** `60` ثانية

**Auto-Deploy:**
- ✅ **Auto-Deploy:** مفعّل (يُحدّث تلقائياً عند push)

---

### 4. إعداد Disk Storage (لحفظ قاعدة البيانات)

#### أ. إنشاء Disk:
1. في Render Dashboard، اضغط **"New +"**
2. اختر **"Disk"**
3. **Name:** `medical-reports-db`
4. **Size:** `1 GB` (أو أكثر حسب الحاجة)
5. **Mount Path:** `/app/db`

#### ب. ربط Disk بالـ Service:
1. اذهب إلى إعدادات الـ Service
2. في قسم **"Disks"**، اضغط **"Link Disk"**
3. اختر الـ Disk الذي أنشأته
4. **Mount Path:** `/app/db`

#### ج. رفع قاعدة البيانات إلى Disk:
```bash
# بعد ربط الـ Disk، يمكنك رفع قاعدة البيانات عبر:
# 1. Render Dashboard → Disk → Upload
# 2. أو عبر SSH (إذا كان متاحاً)
```

---

### 5. النشر

#### أ. النشر التلقائي:
- بعد ربط المستودع، Render سيبدأ البناء تلقائياً
- راقب الـ Logs للتأكد من نجاح البناء

#### ب. النشر اليدوي:
1. في Render Dashboard، اضغط على الـ Service
2. اضغط **"Manual Deploy"**
3. اختر **"Deploy latest commit"**

---

### 6. إعداد Webhook في Telegram

بعد النشر، ستحصل على URL مثل:
```
https://medical-reports-bot.onrender.com
```

#### أ. إعداد Webhook:
1. افتح Telegram
2. ابحث عن `@BotFather`
3. أرسل `/setwebhook`
4. أرسل:
```
https://medical-reports-bot.onrender.com/8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo
```

أو استخدم curl:
```bash
curl -X POST "https://api.telegram.org/bot8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo/setWebhook?url=https://medical-reports-bot.onrender.com/8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo"
```

---

## 🔄 تحديث البيانات

### الطريقة 1: تحديث قاعدة البيانات على Render Disk

#### أ. تحميل قاعدة البيانات المحلية:
```bash
# من جهازك المحلي
scp db/medical_reports.db user@render:/app/db/
```

#### ب. عبر Render Dashboard:
1. اذهب إلى Disk
2. اضغط **"Upload"**
3. ارفع ملف `medical_reports.db`
4. أعد تشغيل الـ Service

### الطريقة 2: إعادة النشر مع قاعدة البيانات

```bash
# 1. نسخ قاعدة البيانات
cp db/medical_reports.db db/medical_reports_initial.db

# 2. إضافة إلى Git (مؤقت)
git add db/medical_reports_initial.db
git commit -m "تحديث قاعدة البيانات"
git push origin main

# 3. Render سيعيد النشر تلقائياً

# 4. بعد النشر، احذف الملف من Git
git rm db/medical_reports_initial.db
git commit -m "إزالة قاعدة البيانات من Git"
git push origin main
```

---

## 🔍 التحقق من النشر

### 1. فحص Logs:
1. في Render Dashboard، اضغط على الـ Service
2. اضغط **"Logs"**
3. تحقق من:
   ```
   ✅ تم تحميل X اسم مريض من قاعدة البيانات
   ✅ تم تهيئة أسماء المرضى بنجاح
   ✅ Database loaded: X KB
   ```

### 2. اختبار البوت:
1. افتح Telegram
2. ابحث عن البوت
3. أرسل `/start`
4. جرب إضافة تقرير جديد
5. تحقق من أن أسماء المرضى تظهر ✅

---

## ⚠️ ملاحظات مهمة

### 1. قاعدة البيانات:
- ✅ استخدم Render Disk لحفظ قاعدة البيانات بشكل دائم
- ✅ تأكد من أن `DATABASE_PATH=/app/db/medical_reports.db`
- ✅ تأكد من أن `AUTO_RESTORE_ON_STARTUP=true`

### 2. متغيرات البيئة:
- ⚠️ لا تضع قيم حساسة في `render.yaml`
- ✅ استخدم Environment Variables في Render Dashboard
- ✅ احفظ `BOT_TOKEN` و `OPENAI_API_KEY` كـ secrets

### 3. الأداء:
- ⚠️ الخطة المجانية (Starter) قد تكون بطيئة
- ✅ الخطة المدفوعة (Standard) موصى بها للإنتاج
- ✅ راقب استخدام الموارد في Dashboard

### 4. النسخ الاحتياطي:
- ✅ Render Disk يحفظ البيانات تلقائياً
- ✅ يمكنك رفع نسخ احتياطية يدوياً
- ✅ استخدم `AUTO_BACKUP_ENABLED=true` للنسخ التلقائي

---

## 🆘 استكشاف الأخطاء

### المشكلة: البوت لا يعمل

**الحل:**
1. تحقق من Logs في Render Dashboard
2. تحقق من متغيرات البيئة
3. تحقق من أن Webhook مُعدّ بشكل صحيح

### المشكلة: قاعدة البيانات فارغة

**الحل:**
1. تحقق من أن Disk مربوط بشكل صحيح
2. ارفع قاعدة البيانات إلى Disk
3. أعد تشغيل الـ Service

### المشكلة: أسماء المرضى لا تظهر

**الحل:**
1. تحقق من Logs: `✅ تم تحميل X اسم مريض`
2. تحقق من أن قاعدة البيانات موجودة في Disk
3. أعد تشغيل الـ Service

---

## 📚 الملفات ذات الصلة

- `render.yaml` - إعدادات Render
- `Dockerfile` - إعدادات Docker
- `db/online_hosting_config.py` - إعدادات قاعدة البيانات
- `db/patient_names_loader.py` - تحميل أسماء المرضى
- `PATIENT_NAMES_DATABASE_FIX.md` - إصلاح أسماء المرضى

---

## ✅ الخلاصة

بعد اتباع هذه الخطوات:
1. ✅ البوت سيعمل على Render
2. ✅ قاعدة البيانات ستُحفظ بشكل دائم
3. ✅ أسماء المرضى ستظهر بشكل صحيح
4. ✅ البيانات ستُحدّث تلقائياً

**رابط البوت:** `https://medical-reports-bot.onrender.com`

🎉 تم النشر بنجاح!

