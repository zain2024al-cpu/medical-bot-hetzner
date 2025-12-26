# 🔐 إعداد GitHub Secrets - دليل شامل

## ❌ المشكلة

إذا ظهر لك هذا الخطأ في GitHub Actions:
```
❌ Error: SSH_PRIVATE_KEY secret is not set
```

هذا يعني أن الـ secrets لم يتم إضافتها في GitHub بعد.

---

## ✅ الحل: إضافة Secrets في GitHub

### الخطوة 1: الذهاب إلى صفحة Secrets

1. اذهب إلى مستودع GitHub:
   ```
   https://github.com/zain2024al-cpu/medical-bot-hetzner
   ```

2. اضغط على **Settings** (الإعدادات)

3. من القائمة الجانبية، اضغط على **Secrets and variables** → **Actions**

4. اضغط على **New repository secret**

---

### الخطوة 2: إضافة SSH_PRIVATE_KEY

1. **Name (الاسم):** `SSH_PRIVATE_KEY`

2. **Secret (القيمة):** الصق المفتاح الخاص التالي:

```
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0AAAAGAAAABBwnOU0b/
aBmj4ZUImtC6qzAAAAGAAAAAEAAAAzAAAAC3NzaC1lZDI1NTE5AAAAIKBbK+kZTUqfXTe1
L/1madPuriTSr/SvJTDj6cFz1/WmAAAAoJcTQ/YIzyfiBljMTNjUixLJ/9w1a9HLJEjzDB
7AFdJw8v8D39sH9SOLVr5yMM8f6WeLWSzhCHVYmuCAgKJSQ2kc/8eEP6ukRDjyQ4mzd+Cp
XYorMlW7FQL/GgJpW0MP5n86f7tmwCF6Q14vhZqpwnsaWAYyK0zadTzETWrcz42FnXeYAU
3tKU/RjmaQgZ5yNF6+aaS7ObnaPwELVvk/dHI=
-----END OPENSSH PRIVATE KEY-----
```

⚠️ **مهم جداً:**
- يجب نسخ المفتاح **كاملاً** بما في ذلك `-----BEGIN` و `-----END`
- لا تضيف مسافات إضافية في البداية أو النهاية
- يجب أن يكون المفتاح في سطر واحد أو عدة أسطر كما هو أعلاه

3. اضغط على **Add secret**

---

### الخطوة 3: إضافة HETZNER_HOST

1. اضغط على **New repository secret** مرة أخرى

2. **Name (الاسم):** `HETZNER_HOST`

3. **Secret (القيمة):** `5.223.58.71`

4. اضغط على **Add secret**

---

### الخطوة 4: التحقق من الإعداد

بعد إضافة الـ secrets، يجب أن ترى:

- ✅ `SSH_PRIVATE_KEY` (يظهر كـ `••••••••`)
- ✅ `HETZNER_HOST` (يظهر كـ `5.223.58.71`)

---

## 🧪 اختبار الإعداد

### الطريقة 1: تشغيل Workflow يدوياً

1. اذهب إلى صفحة Actions:
   ```
   https://github.com/zain2024al-cpu/medical-bot-hetzner/actions
   ```

2. اضغط على **🚀 Deploy to Hetzner VPS**

3. اضغط على **Run workflow** → **Run workflow**

4. راقب التنفيذ - يجب أن ترى:
   - ✅ `🔐 Setting up SSH connection...`
   - ✅ `✅ SSH setup completed successfully`
   - ✅ `🚀 Starting deployment to Hetzner VPS...`
   - ✅ `✅ Deployment completed successfully!`

### الطريقة 2: Push جديد

بعد إضافة الـ secrets، أي push جديد إلى `main` سيُشغل الـ workflow تلقائياً.

---

## 🔍 استكشاف الأخطاء

### الخطأ: "SSH_PRIVATE_KEY secret is not set"

**السبب:** الـ secret غير موجود أو الاسم غير صحيح

**الحل:**
1. تأكد من أن الاسم هو `SSH_PRIVATE_KEY` (حساس لحالة الأحرف)
2. تأكد من أنك أضفته في **Secrets and variables** → **Actions**
3. تأكد من أنك في المستودع الصحيح

---

### الخطأ: "HETZNER_HOST secret is not set"

**السبب:** الـ secret غير موجود أو الاسم غير صحيح

**الحل:**
1. تأكد من أن الاسم هو `HETZNER_HOST` (حساس لحالة الأحرف)
2. تأكد من أن القيمة هي `5.223.58.71` (بدون مسافات)

---

### الخطأ: "Cannot connect to server"

**السبب:** مشكلة في SSH key أو السيرفر غير متاح

**الحل:**
1. تأكد من أن SSH key صحيح (يبدأ بـ `-----BEGIN` وينتهي بـ `-----END`)
2. تأكد من أن السيرفر متاح: `ping 5.223.58.71`
3. تأكد من أن المفتاح العام موجود على السيرفر

---

## 📝 ملاحظات مهمة

1. **الأمان:**
   - لا تشارك الـ secrets مع أي شخص
   - لا ترفع الـ secrets في الكود
   - GitHub يحمي الـ secrets ولا يمكن لأي شخص رؤيتها

2. **التحديث:**
   - إذا غيرت SSH key، يجب تحديث `SSH_PRIVATE_KEY` في GitHub
   - إذا غيرت IP السيرفر، يجب تحديث `HETZNER_HOST` في GitHub

3. **التحقق:**
   - بعد إضافة الـ secrets، انتظر دقيقة ثم شغل الـ workflow
   - أحياناً GitHub يحتاج وقت قصير لتحديث الـ secrets

---

## ✅ الخلاصة

بعد إضافة الـ secrets:
- ✅ `SSH_PRIVATE_KEY` → المفتاح الخاص الكامل
- ✅ `HETZNER_HOST` → `5.223.58.71`

الـ workflow سيعمل تلقائياً عند كل push إلى `main`!

