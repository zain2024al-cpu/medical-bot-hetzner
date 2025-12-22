# 🤖 Medical Reports Bot - نظام إدارة التقارير الطبية

بوت تليجرام متقدم لإدارة التقارير الطبية والمتابعة مع الأطباء والمرضى مع دعم الاستضافة السحابية الكامل.

## ✨ الميزات الرئيسية

### 📊 إدارة البيانات
- 👥 **إدارة المرضى**: قاعدة بيانات مع 98 مريض جاهز + بحث محسّن
- 🏥 **إدارة الأطباء**: نظام بحث ذكي بالأسماء والتخصصات
- 📝 **تقارير طبية**: تقارير شاملة مع تفاصيل كاملة
- 📅 **جدولة المواعيد**: تتبع المواعيد والمتابعة
- 📋 **التقرير الأولي**: عرض التقارير الأولية للمرضى

### 👥 دعم المجموعات (جديد!)
- 📢 **إرسال تلقائي**: التقارير تُرسل تلقائياً للمجموعة بعد الحفظ
- 🔒 **أمان**: إضافة التقارير من الدردشة الخاصة فقط
- 🎯 **واجهة نظيفة**: الأزرار مخفية في المجموعة

### 🔧 التقنيات المتقدمة
- 🧠 **ذكاء اصطناعي**: تحليل البيانات وتوليد التقارير
- ☁️ **سحابية كاملة**: Google Cloud Storage للنسخ الاحتياطي
- 🔄 **نسخ احتياطي تلقائي**: كل 10 دقائق + يومي
- 📱 **واجهات متعددة**: Webhook و Polling

### 🚀 الاستضافة
- ⚡ **Hetzner VPS**: سكريبتات نشر كاملة
- 💻 **الوضع المحلي**: للتطوير والاختبار

## 📋 المتطلبات

### 🤖 بوت تليجرام
- حساب Telegram Bot من [@BotFather](https://t.me/BotFather)
- توكن البوت (موجود في `config.env`)

### ☁️ استضافة سحابية
- خادم Hetzner VPS (CX11: €2.89/شهر)

### 🛠️ متطلبات التطوير
- Python 3.12+

## 🚀 التشغيل المحلي (للتطوير)

### على Windows:
```powershell
# 1. انتقل إلى مجلد المشروع
cd botuser@

# 2. شغّل السكريبت
.\run_local.ps1
```

### على Linux/Mac:
```bash
# 1. انتقل إلى مجلد المشروع
cd botuser@

# 2. اجعل السكريبت قابل للتنفيذ
chmod +x run_local.sh

# 3. شغّل السكريبت
./run_local.sh
```

### إعداد ملف config.env:
```bash
cp config.env.example config.env
# عدل config.env بالقيم الصحيحة (BOT_TOKEN, ADMIN_IDS, etc.)
```

**ملاحظة:** السكريبتات تقوم تلقائياً بـ:
- إنشاء البيئة الافتراضية إذا لم تكن موجودة
- تثبيت المتطلبات
- ضبط متغيرات البيئة للوضع المحلي
- تشغيل البوت في وضع Polling

## 🌐 طرق النشر المتاحة

### 🖥️ **Hetzner VPS** ⭐ (الموصى به - الأسهل والأرخص)

#### الإعداد الأولي:
```bash
# على السيرفر، شغّل سكريبت الإعداد (مرة واحدة)
sudo bash hetzner-setup.sh
```

#### رفع المشروع:
```bash
# من جهازك المحلي
scp -r botuser@/* botuser@YOUR_SERVER_IP:/home/botuser/medical-bot/
```

#### إعداد ملف config.env على السيرفر:
```bash
# على السيرفر
cd /home/botuser/medical-bot
cp config.env.example config.env
nano config.env  # عدّل القيم
```

#### تشغيل البوت باستخدام systemd:
```bash
# إعداد الخدمة
sudo cp medical-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable medical-bot
sudo systemctl start medical-bot

# التحقق من الحالة
sudo systemctl status medical-bot
```

**المميزات:**
- ✅ تكلفة €2.89/شهر فقط
- ✅ أداء ممتاز للشرق الأوسط
- ✅ نسخ احتياطي تلقائي
- ✅ سهولة الصيانة
- ✅ يعمل في وضع Polling (أسهل وأكثر موثوقية)

**للمزيد من التفاصيل:** راجع [SETUP_GUIDE.md](SETUP_GUIDE.md)

### ☁️ **Google Cloud Run** (للأداء العالي)
```bash
# نشر تلقائي
.\deploy_complete.ps1
```

### 🚂 **Railway** (سهل الاستخدام)
```bash
# رفع ونشر تلقائي
.\push_with_database.ps1
```

### 🎨 **Render** (مجاني جزئياً)
```bash
# نشر مع webhook
.\deploy_render.ps1
```

## 📁 هيكل المشروع

```
medical-reports-bot/
├── app.py                 # نقطة البداية الرئيسية
├── bot/                   # منطق البوت
│   ├── handlers/         # معالجات الأوامر
│   ├── keyboards.py      # لوحات المفاتيح
│   └── user_interface.py # واجهة المستخدم
├── config/               # إعدادات التطبيق
├── db/                   # قاعدة البيانات والنماذج
├── services/             # الخدمات المساعدة
├── templates/            # قوالب HTML للتقارير
├── data/                 # البيانات الأساسية
├── .github/             # GitHub Actions للنشر التلقائي
├── hetzner-setup.sh     # سكريبت إعداد Hetzner VPS
├── deploy-complete.ps1  # نشر Google Cloud Run
├── medical-bot.service  # خدمة systemd
└── backup.sh           # النسخ الاحتياطي التلقائي
```

## 🎯 دليل البدء السريع

### 1. إعداد سيرفر Hetzner VPS
```bash
# إنشاء سيرفر جديد على Hetzner
# اختر: Ubuntu 22.04, CX11 (€2.89/شهر)
```

### 2. إعداد المشروع محلياً
```bash
# استنساخ المشروع
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd medical-reports-bot

# إعداد البيئة
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. رفع المشروع للسيرفر
```bash
# من جهازك المحلي
.\upload_to_hetzner.bat
```

### 4. إعداد البوت على السيرفر
```bash
# على السيرفر
cd /home/botuser/medical-bot
./setup_bot_on_server.sh
```

## 📞 الدعم والمساعدة

### استكشاف الأخطاء الشائعة

#### ❌ البوت لا يبدأ
```bash
# فحص السجلات
sudo journalctl -u medical-bot -n 20

# فحص الحالة
sudo systemctl status medical-bot
```

#### ❌ مشاكل قاعدة البيانات
```bash
# إعادة بناء قاعدة البيانات
cd /home/botuser/medical-bot
source venv/bin/activate
python -c "from db.session import init_database; init_database()"
```

#### ❌ مشاكل النشر
```bash
# فحص ملف البيئة
cat /home/botuser/medical-bot/.env

# إعادة تشغيل الخدمة
sudo systemctl restart medical-bot
```

## 📊 الميزات المتقدمة

- 🔄 **نسخ احتياطي تلقائي** كل 10 دقائق
- ☁️ **Google Cloud Storage** للتخزين السحابي
- 📊 **تحليلات متقدمة** مع الذكاء الاصطناعي
- 📱 **دعم Webhook** للاستجابة الفورية
- 🔒 **أمان محسن** مع تشفير البيانات

## 📝 الترخيص

هذا المشروع مرخص تحت رخصة MIT - راجع ملف [LICENSE](LICENSE) للتفاصيل.

---

## 🎉 استمتع باستخدام البوت!

🚀 **البوت جاهز للعمل 24/7 مع نسخ احتياطي تلقائي ومراقبة شاملة**

## 🚀 التشغيل المحلي

### المتطلبات
- Python 3.12+
- حساب Telegram Bot (@BotFather)

### خطوات التشغيل

1. **استنساخ المشروع**
```bash
git clone <repository-url>
cd medical-reports-bot
```

2. **إعداد البيئة الافتراضية**
```bash
python -m venv venv
venv\Scripts\activate  # على Windows
# أو source venv/bin/activate على Linux/Mac
```

3. **تثبيت المتطلبات**
```bash
pip install -r requirements.txt
```

4. **إعداد ملف التكوين**
```bash
cp config.env.example config.env
# عدل config.env بالقيم الصحيحة
```

5. **تشغيل البوت**
```bash
python app.py
```

## 🌐 النشر على الاستضافات السحابية

### 🚂 النشر على Railway

#### الخطوات:

1. **رفع المشروع إلى GitHub**
```bash
git add .
git commit -m "Add Railway deployment support"
git push origin main
```

2. **إنشاء مشروع جديد على Railway**
   - اذهب إلى [Railway.app](https://railway.app)
   - انقر "New Project"
   - اختر "Deploy from GitHub repo"

3. **إعداد متغيرات البيئة في Railway**
   - `BOT_TOKEN`: توكن البوت من @BotFather
   - `ADMIN_IDS`: معرفات الإداريين (مفصولة بفاصلة)
   - `TIMEZONE`: المنطقة الزمنية (مثل: Asia/Kolkata)
   - `OPENAI_API_KEY`: مفتاح OpenAI (اختياري)
   - `OPENAI_MODEL`: نموذج OpenAI (gpt-4o)

4. **إعداد قاعدة البيانات**
   - Railway سيقوم بإنشاء PostgreSQL تلقائياً
   - أو يمكنك إضافة خدمة PostgreSQL من "Add Plugin"

### 🎨 النشر على Render

#### الخطوات:

1. **ربط مع GitHub**
   - اذهب إلى [Render.com](https://render.com)
   - انقر "New +" → "Web Service"
   - اربط حساب GitHub

2. **إعداد الخدمة**
   - اختر المشروع من GitHub
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`

3. **إعداد متغيرات البيئة**
   - نفس المتغيرات المذكورة أعلاه
   - `RENDER_EXTERNAL_URL`: سيتم تعيينه تلقائياً

4. **إضافة قاعدة PostgreSQL**
   - انقر "New +" → "PostgreSQL"
   - اربطها بالخدمة الرئيسية

### ☁️ النشر على Heroku

#### الخطوات:

1. **إنشاء تطبيق Heroku**
```bash
heroku create your-app-name
```

2. **إعداد متغيرات البيئة**
```bash
heroku config:set BOT_TOKEN=your_bot_token
heroku config:set ADMIN_IDS=your_admin_ids
heroku config:set TIMEZONE=Asia/Kolkata
heroku config:set OPENAI_API_KEY=your_openai_key
```

3. **نشر التطبيق**
```bash
git push heroku main
```

## ⚙️ إعدادات البيئة

| المتغير | الوصف | مطلوب |
|---------|--------|--------|
| `BOT_TOKEN` | توكن البوت من Telegram | ✅ |
| `ADMIN_IDS` | معرفات الإداريين | ✅ |
| `TIMEZONE` | المنطقة الزمنية | ✅ |
| `OPENAI_API_KEY` | مفتاح OpenAI للذكاء الاصطناعي | ❌ |
| `DATABASE_URL` | رابط قاعدة البيانات | ❌ (يتم إنشاؤه تلقائياً) |

## 📁 هيكل المشروع

```
medical-reports-bot/
├── bot/                    # منطق البوت
│   ├── handlers/          # معالجات الرسائل
│   │   ├── user/         # معالجات المستخدمين
│   │   └── admin/        # معالجات الإداريين
│   ├── keyboards.py      # لوحات الأزرار
│   └── user_interface.py # واجهة المستخدم
├── db/                    # قاعدة البيانات
├── templates/             # قوالب HTML
├── services/              # خدمات إضافية
├── config.env            # إعدادات البيئة
├── requirements.txt      # متطلبات Python
└── app.py               # نقطة البداية
```

## 🔧 الأوامر المتاحة

- `/start` - بدء استخدام البوت
- `/help` - عرض المساعدة
- `/stats` - عرض الإحصائيات (للإداريين فقط)

## 📞 الدعم

للدعم الفني أو الاستفسارات، يرجى فتح issue في المشروع.

## 📄 الترخيص

هذا المشروع مرخص تحت رخصة MIT.
