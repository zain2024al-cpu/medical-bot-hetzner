# 🚀 دليل النشر المنظم - GitHub و Hetzner

## 📋 الخطوات المطلوبة

### 1️⃣ **التحضير قبل الرفع**

#### ✅ التحقق من الملفات الحساسة:
- [x] `config.env` محمي في `.gitignore` ✅
- [x] قاعدة البيانات محمية في `.gitignore` ✅
- [x] الملفات المؤقتة محمية ✅

#### ✅ الملفات الجديدة المضافة:
- `GROUP_SETUP.md` - دليل إعداد المجموعة
- `HOW_IT_WORKS.md` - شرح كيفية عمل النظام
- `bot/handlers/shared/group_handler.py` - معالج المجموعات
- `bot/handlers/user/user_initial_case.py` - التقرير الأولي
- `run_hetzner.sh` - سكريبت التشغيل على Hetzner

---

### 2️⃣ **رفع التحديثات على GitHub**

```bash
# 1. التحقق من الحالة
git status

# 2. إضافة الملفات الجديدة
git add GROUP_SETUP.md HOW_IT_WORKS.md
git add bot/handlers/shared/group_handler.py
git add bot/handlers/user/user_initial_case.py
git add run_hetzner.sh

# 3. إضافة التعديلات
git add -u  # يضيف جميع التعديلات والحذف

# 4. عمل commit
git commit -m "feat: إضافة دعم المجموعات وإخفاء الأزرار

- إضافة معالج المجموعات (group_handler.py)
- إخفاء الأزرار من المجموعة (فقط في الدردشة الخاصة)
- إضافة دعم إرسال التقارير للمجموعة تلقائياً
- إضافة التقرير الأولي للمرضى
- تحسين البحث عن المرضى والمترجمين
- إضافة ملفات توثيق (GROUP_SETUP.md, HOW_IT_WORKS.md)
- تنظيف الملفات القديمة غير المستخدمة"

# 5. رفع إلى GitHub
git push origin main
```

---

### 3️⃣ **النشر على Hetzner**

#### الطريقة 1: النشر التلقائي (مُوصى به)

```bash
# على السيرفر (Hetzner)
cd /root/medical-bot-hetzner
git pull origin main
systemctl restart medical-bot
systemctl status medical-bot
```

#### الطريقة 2: النشر اليدوي

```bash
# 1. الاتصال بالسيرفر
ssh root@5.223.58.71

# 2. الانتقال إلى مجلد المشروع
cd /root/medical-bot-hetzner

# 3. جلب التحديثات
git fetch origin
git pull origin main

# 4. التأكد من عدم وجود تعارضات
git status

# 5. إعادة تشغيل البوت
systemctl restart medical-bot

# 6. التحقق من الحالة
systemctl status medical-bot
journalctl -u medical-bot -f  # لمتابعة السجلات
```

---

### 4️⃣ **التحقق من النشر**

#### على السيرفر:
```bash
# التحقق من حالة الخدمة
systemctl status medical-bot

# متابعة السجلات
journalctl -u medical-bot -n 50 --no-pager

# التحقق من أن البوت يعمل
ps aux | grep python
```

#### في Telegram:
1. ✅ اختبار `/start` في الدردشة الخاصة (يجب أن تظهر الأزرار)
2. ✅ اختبار `/start` في المجموعة (يجب ألا تظهر أزرار)
3. ✅ إضافة تقرير جديد (يجب أن يظهر في المجموعة تلقائياً)
4. ✅ التحقق من أن البحث عن المرضى يعمل

---

### 5️⃣ **حل المشاكل**

#### إذا فشل git pull:
```bash
# حفظ التغييرات المحلية
git stash

# جلب التحديثات
git pull origin main

# استعادة التغييرات
git stash pop
```

#### إذا فشل إعادة التشغيل:
```bash
# إيقاف البوت
systemctl stop medical-bot

# التحقق من الأخطاء
journalctl -u medical-bot -n 100

# إعادة التشغيل
systemctl start medical-bot
```

#### إذا كان هناك تعارضات:
```bash
# إعادة تعيين التغييرات المحلية (احذر!)
git reset --hard origin/main

# ثم إعادة التشغيل
systemctl restart medical-bot
```

---

## ⚠️ **ملاحظات مهمة**

1. **لا ترفع `config.env`** - محمي في `.gitignore`
2. **لا ترفع قاعدة البيانات** - محمية في `.gitignore`
3. **احفظ نسخة احتياطية** قبل النشر
4. **اختبر على السيرفر** قبل الإعلان عن التحديثات

---

## 📝 **سجل التحديثات**

### الإصدار الحالي: v2.1.0
- ✅ إضافة دعم المجموعات
- ✅ إخفاء الأزرار من المجموعة
- ✅ إرسال التقارير للمجموعة تلقائياً
- ✅ تحسين البحث عن المرضى
- ✅ إضافة التقرير الأولي للمرضى

---

## 🔗 **روابط مفيدة**

- GitHub: https://github.com/zain2024al-cpu/medical-bot-hetzner
- Hetzner Console: https://console.hetzner.com
- Server IP: 5.223.58.71





