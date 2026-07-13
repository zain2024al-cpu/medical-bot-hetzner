# 🚀 دليل إعداد البوت الطبي على Hetzner VPS

## 📋 نظرة عامة

هذا الدليل يوضح كيفية إعداد البوت الطبي على Hetzner VPS مع نظام نشر تلقائي.

### 🎯 ما سنقوم به:

1. ✅ إعداد VPS على Hetzner
2. ✅ تثبيت Python والبيئة المطلوبة
3. ✅ إعداد البوت مع systemd
4. ✅ إعداد النشر التلقائي عبر GitHub Actions
5. ✅ إعداد النسخ الاحتياطي التلقائي
6. ✅ إعداد المراقبة والتنبيهات

---

## 🛠️ الخطوة 1: إعداد VPS على Hetzner

### أ. اختيار السيرفر المناسب:

**موصى به للبوت الطبي:**
- **نوع:** CX11 (€2.89/شهر)
- **مواصفات:** 1 vCPU, 2GB RAM, 20GB SSD
- **نظام التشغيل:** Ubuntu 22.04 LTS

### ب. إعداد السيرفر الأساسي:

1. **سجل دخول إلى Hetzner Console**
2. **اضغط "Add Server"**
3. **اختر:**
   - Location: Singapore (ممتاز للشرق الأوسط!) أو Germany (Falkenstein) أو Finland (Helsinki)
   - Images: Ubuntu 22.04
   - Type: CX11 (€2.89/month) أو CX31 (2vCPU/4GB/80GB) للأداء الأفضل
   - SSH Keys: أضف مفتاح SSH الخاص بك
   - Name: `medical-bot-server`

### ج. أضف SSH Key (مهم للأمان):

```bash
# على جهازك المحلي، أنشئ مفتاح SSH إذا لم يكن موجوداً:
ssh-keygen -t ed25519 -C "your-email@example.com"

# انسخ المفتاح العام:
cat ~/.ssh/id_ed25519.pub
```

**مفتاحك الحالي (ed25519):**
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGlgiUUiVzKpmO2UYFQBQLw4pzIo3zKm/OYGZWGeKhAr nalgu@omar
```

#### خطوات إضافة المفتاح في Hetzner Console:

1. **اذهب إلى "Security" > "SSH Keys"**
2. **اضغط "Add SSH Key"**
3. **Name:** `medical-bot-ssh-key`
4. **Public Key:** الصق المفتاح أعلاه
5. **اضغط "Add SSH Key"**

✅ **مفتاحك جاهز للاستخدام!**

---

## ⚙️ الخطوة 2: الإعداد الأولي للسيرفر

### أ. الاتصال بالسيرفر:

```bash
# استبدل IP_ADDRESS بعنوان IP السيرفر
ssh root@IP_ADDRESS
```

### ب. تحديث النظام:

```bash
apt update && apt upgrade -y
apt install -y curl wget git htop vim ufw fail2ban
```

### ج. إعداد جدار الحماية:

```bash
# تفعيل UFW
ufw allow OpenSSH
ufw --force enable

# تحقق من حالة الجدار الناري
ufw status
```

### د. إنشاء مستخدم جديد (بدلاً من root):

```bash
# إنشاء مستخدم جديد
adduser botuser

# إعطاء صلاحيات sudo
usermod -aG sudo botuser

# نسخ SSH keys للمستخدم الجديد
rsync --archive --chown=botuser:botuser ~/.ssh /home/botuser

# الآن استخدم المستخدم الجديد
su - botuser
```

---

## 🐍 الخطوة 3: تثبيت Python والبيئة

### أ. تثبيت Python 3.12:

```bash
# تثبيت Python 3.12
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev

# التحقق من التثبيت
python3.12 --version
```

### ب. تثبيت المكتبات المطلوبة للبوت:

```bash
# تثبيت pip وأدوات البناء
sudo apt install -y python3-pip build-essential

# تثبيت مكتبات النظام المطلوبة
sudo apt install -y libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev shared-mime-info

# تثبيت wkhtmltopdf للـ PDF (إذا كنت تستخدمه)
sudo apt install -y wkhtmltopdf
```

---

## 📁 الخطوة 4: إعداد مجلد المشروع

### أ. إنشاء مجلد المشروع:

```bash
# إنشاء مجلد المشروع
mkdir -p ~/medical-bot
cd ~/medical-bot

# استنساخ المشروع من GitHub
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git .
```

### ب. إعداد البيئة الافتراضية:

```bash
# إنشاء البيئة الافتراضية
python3.12 -m venv venv

# تفعيل البيئة الافتراضية
source venv/bin/activate

# تثبيت المتطلبات
pip install -r requirements.txt
```

---

## 🔐 الخطوة 5: إعداد متغيرات البيئة

### أ. إنشاء ملف .env:

```bash
# إنشاء ملف المتغيرات البيئية
nano .env
```

**أضف المحتوى التالي:**

```env
# Telegram Bot Token (من BotFather)
BOT_TOKEN=8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo

# قائمة المشرفين
ADMIN_IDS=123456789,987654321

# المنطقة الزمنية
TIMEZONE=Asia/Riyadh

# OpenAI API (إذا كنت تستخدم)
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4

# قاعدة البيانات
DATABASE_URL=sqlite:///db/medical_reports.db

# Webhook (اختياري)
WEBHOOK_URL=https://your-domain.com
PORT=8080
```

### ب. إعداد الأمان لملف .env:

```bash
# جعل الملف محمي
chmod 600 .env
```

---

## 🚀 الخطوة 6: إعداد systemd للبوت

### أ. إنشاء ملف الخدمة:

```bash
# إنشاء ملف systemd
sudo nano /etc/systemd/system/medical-bot.service
```

**أضف المحتوى التالي:**

```ini
[Unit]
Description=Medical Reports Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/medical-bot
Environment=PATH=/home/botuser/medical-bot/venv/bin
ExecStart=/home/botuser/medical-bot/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### ب. تفعيل وتشغيل الخدمة:

```bash
# إعادة تحميل systemd
sudo systemctl daemon-reload

# تفعيل الخدمة للتشغيل التلقائي
sudo systemctl enable medical-bot

# تشغيل الخدمة
sudo systemctl start medical-bot

# التحقق من حالة الخدمة
sudo systemctl status medical-bot
```

---

## 🔄 الخطوة 7: إعداد النشر التلقائي

### أ. إعداد GitHub Actions:

**أنشئ الملف: `.github/workflows/deploy-hetzner.yml`**

```yaml
name: Deploy to Hetzner

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Setup SSH
      uses: webfactory/ssh-agent@v0.9.0
      with:
        ssh-private-key: ${{ secrets.SSH_PRIVATE_KEY }}

    - name: Deploy to Hetzner
      run: |
        ssh -o StrictHostKeyChecking=no botuser@${{ secrets.HETZNER_HOST }} << 'EOF'
          cd ~/medical-bot
          git pull origin main
          source venv/bin/activate
          pip install -r requirements.txt
          sudo systemctl restart medical-bot
          echo "✅ Deployment completed successfully!"
        EOF
```

### ب. إضافة الأسرار في GitHub:

1. **اذهب إلى Repository Settings > Secrets and variables > Actions**
2. **أضف الأسرار التالية:**

```bash
SSH_PRIVATE_KEY=محتوى مفتاح SSH الخاص
HETZNER_HOST=عنوان IP السيرفر
```

---

## 💾 الخطوة 8: إعداد النسخ الاحتياطي

### أ. إنشاء سكريبت النسخ الاحتياطي:

```bash
# إنشاء مجلد النسخ الاحتياطي
mkdir -p ~/backups

# إنشاء سكريبت النسخ الاحتياطي
nano ~/backup.sh
```

**أضف المحتوى:**

```bash
#!/bin/bash

# إعدادات النسخ الاحتياطي
BACKUP_DIR="/home/botuser/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"

# إنشاء مجلد النسخ إذا لم يكن موجوداً
mkdir -p $BACKUP_DIR

# إنشاء النسخة الاحتياطية
tar -czf $BACKUP_FILE \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='backups' \
    -C /home/botuser medical-bot

# حذف النسخ الاحتياطية القديمة (احتفظ بآخر 7 أيام)
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete

echo "✅ Backup created: $BACKUP_FILE"
```

### ب. جعل السكريبت قابل للتنفيذ وجدولته:

```bash
# جعل السكريبت قابل للتنفيذ
chmod +x ~/backup.sh

# إضافة مهمة مجدولة للنسخ اليومي
crontab -e

# أضف هذا السطر للنسخ اليومي في الساعة 2 صباحاً:
0 2 * * * /home/botuser/backup.sh
```

---

## 📊 الخطوة 9: إعداد المراقبة

### أ. تثبيت htop ومراقبة السجلات:

```bash
# تثبيت أدوات المراقبة
sudo apt install -y htop iotop ncdu

# مراقبة السجلات
sudo journalctl -u medical-bot -f

# مراقبة استخدام الموارد
htop
```

### ب. إعداد تنبيهات البريد الإلكتروني (اختياري):

```bash
# تثبيت mailutils
sudo apt install -y mailutils

# إعداد البريد (يحتاج تكوين postfix)
sudo apt install -y postfix
```

---

## 🧪 الخطوة 10: الاختبار والتشخيص

### أ. اختبار البوت:

```bash
# التحقق من أن البوت يعمل
sudo systemctl status medical-bot

# عرض سجلات البوت
sudo journalctl -u medical-bot -n 50

# إعادة تشغيل البوت
sudo systemctl restart medical-bot
```

### ب. اختبار النشر التلقائي:

```bash
# من جهازك المحلي، اجعل تغيير بسيط
echo "# Test deployment" >> README.md
git add .
git commit -m "Test deployment"
git push origin main

# راقب النشر على GitHub Actions
```

---

## 📋 قائمة المراجعة النهائية

### ✅ التحقق من الإعداد:

- [ ] VPS مُشغل ومتصل
- [ ] Python 3.12 مثبت
- [ ] البيئة الافتراضية مُعدة
- [ ] البوت يعمل مع systemd
- [ ] النشر التلقائي مُعد
- [ ] النسخ الاحتياطي مُجدول
- [ ] الجدار الناري مُفعل
- [ ] SSH Key مُعد للأمان

### 🔧 أوامر مفيدة:

```bash
# مراقبة البوت
sudo systemctl status medical-bot

# إعادة تشغيل البوت
sudo systemctl restart medical-bot

# عرض السجلات
sudo journalctl -u medical-bot -f

# النسخ الاحتياطي اليدوي
~/backup.sh

# مراقبة الموارد
htop
```

---

## 🆘 استكشاف الأخطاء

### مشكلة: البوت لا يبدأ
```bash
# تحقق من السجلات
sudo journalctl -u medical-bot -n 50

# تشغيل البوت يدوياً للاختبار
cd ~/medical-bot
source venv/bin/activate
python app.py
```

### مشكلة: النشر التلقائي فشل
```bash
# تحقق من GitHub Actions logs
# تأكد من أن SSH key صحيح
# تأكد من أن المسار صحيح على السيرفر
```

### مشكلة: نفاد المساحة
```bash
# تحقق من استخدام المساحة
df -h

# تنظيف packages
sudo apt autoremove -y
sudo apt autoclean
```

---

## 💰 التكاليف الشهرية

- **Hetzner VPS:** €2.89
- **Domain (اختياري):** €10-15
- **Backup Storage (اختياري):** €1-5

**المجموع: €3.89/شهر** (أرخص من معظم المنصات!)

---

## 🎉 الخلاصة

الآن لديك بوت طبي يعمل على Hetzner VPS مع:
- ✅ نشر تلقائي عند كل push
- ✅ نسخ احتياطي يومي
- ✅ مراقبة مستمرة
- ✅ أمان محسن
- ✅ تكلفة منخفضة

**استمتع باستضافة البوت على Hetzner!** 🚀

---

## 📚 الملفات ذات الصلة

- `hetzner-setup.sh` - سكريبت الإعداد التلقائي
- `.github/workflows/deploy-hetzner.yml` - ملف النشر التلقائي
- `backup.sh` - سكريبت النسخ الاحتياطي
- `medical-bot.service` - ملف systemd
