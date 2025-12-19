# ⚡ دليل سريع للنشر على Render

## 🚀 خطوات سريعة

### 1. رفع الكود إلى GitHub

```powershell
# في PowerShell
.\deploy_render.ps1
```

أو يدوياً:
```bash
git add .
git commit -m "نشر على Render"
git push origin main
```

### 2. إنشاء Service على Render

1. اذهب إلى [dashboard.render.com](https://dashboard.render.com)
2. اضغط **"New +"** → **"Web Service"**
3. اختر المستودع من GitHub
4. الإعدادات:
   - **Name:** `medical-reports-bot`
   - **Runtime:** `Docker`
   - **Dockerfile Path:** `./Dockerfile`
   - **Plan:** `Starter` (مجاني) أو `Standard` (مدفوع)

### 3. إضافة متغيرات البيئة

في Render Dashboard → Environment:
```
BOT_TOKEN=8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo
ADMIN_IDS=2116274898
TIMEZONE=Asia/Riyadh
DATABASE_PATH=/app/db/medical_reports.db
PORT=8080
AUTO_RESTORE_ON_STARTUP=true
AUTO_SAVE_ON_SHUTDOWN=true
```

### 4. إعداد Webhook

بعد النشر، ستحصل على URL مثل:
```
https://medical-reports-bot.onrender.com
```

أرسل هذا الأمر:
```bash
curl -X POST "https://api.telegram.org/bot8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo/setWebhook?url=https://medical-reports-bot.onrender.com/8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo"
```

### 5. رفع قاعدة البيانات (اختياري)

**الطريقة 1: عبر Render Disk**
1. أنشئ Disk في Render
2. Mount Path: `/app/db`
3. ارفع `medical_reports.db` إلى Disk

**الطريقة 2: عبر Git (مؤقت)**
```bash
cp db/medical_reports.db db/medical_reports_initial.db
git add db/medical_reports_initial.db
git commit -m "إضافة قاعدة البيانات"
git push origin main

# بعد النشر، احذف الملف:
git rm db/medical_reports_initial.db
git commit -m "إزالة قاعدة البيانات"
git push origin main
```

---

## ✅ التحقق

1. تحقق من Logs في Render Dashboard
2. ابحث عن:
   ```
   ✅ تم تحميل X اسم مريض من قاعدة البيانات
   ✅ Database loaded: X KB
   ```
3. اختبر البوت في Telegram

---

## 🔄 تحديث البيانات

### تحديث الكود:
```bash
git add .
git commit -m "تحديث"
git push origin main
# Render سيُحدّث تلقائياً
```

### تحديث قاعدة البيانات:
1. ارفع قاعدة البيانات إلى Render Disk
2. أعد تشغيل الـ Service من Dashboard

---

## 📚 للمزيد

راجع `RENDER_DEPLOYMENT_GUIDE.md` للتفاصيل الكاملة.

