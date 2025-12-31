#!/bin/bash

# ================================================
# 🚀 سكريبت إعداد البوت الطبي على Hetzner VPS
# ================================================

set -e  # إيقاف السكريبت عند أي خطأ

# ألوان للإخراج
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# دالة لطباعة الرسائل الملونة
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ================================================
# التحقق من أننا نعمل كـ root
# ================================================
if [[ $EUID -ne 0 ]]; then
   print_error "هذا السكريبت يجب تشغيله كـ root"
   exit 1
fi

print_status "🚀 بدء إعداد البوت الطبي على Hetzner VPS..."
echo "==============================================="

# ================================================
# تحديث النظام
# ================================================
print_status "📦 تحديث النظام..."
apt update && apt upgrade -y
print_success "تم تحديث النظام"

# ================================================
# تثبيت المكتبات الأساسية
# ================================================
print_status "🛠️ تثبيت المكتبات الأساسية..."
apt install -y curl wget git htop vim ufw fail2ban software-properties-common build-essential
print_success "تم تثبيت المكتبات الأساسية"

# ================================================
# إعداد جدار الحماية
# ================================================
print_status "🔥 إعداد جدار الحماية..."
ufw allow OpenSSH
ufw --force enable
print_success "تم تفعيل جدار الحماية"

# ================================================
# تثبيت Python 3.12
# ================================================
print_status "🐍 تثبيت Python 3.12..."
add-apt-repository ppa:deadsnakes/ppa -y
apt update
apt install -y python3.12 python3.12-venv python3.12-dev python3-pip
print_success "تم تثبيت Python 3.12"

# ================================================
# تثبيت مكتبات النظام المطلوبة للبوت
# ================================================
print_status "📚 تثبيت مكتبات النظام المطلوبة..."
apt install -y libcairo2-dev libpango1.0-dev libgdk-pixbuf2.0-dev libffi-dev shared-mime-info
apt install -y wkhtmltopdf  # للـ PDF generation
print_success "تم تثبيت مكتبات النظام"

# ================================================
# إنشاء مستخدم جديد للبوت
# ================================================
print_status "👤 إنشاء مستخدم البوت..."
USER_EXISTS=$(getent passwd botuser || echo "")
if [[ -z "$USER_EXISTS" ]]; then
    useradd -m -s /bin/bash botuser
    usermod -aG sudo botuser
    print_success "تم إنشاء المستخدم botuser"
else
    print_warning "المستخدم botuser موجود مسبقاً"
fi

# ================================================
# إعداد SSH للمستخدم الجديد
# ================================================
print_status "🔑 إعداد SSH للمستخدم..."
if [[ ! -d "/home/botuser/.ssh" ]]; then
    mkdir -p /home/botuser/.ssh
    cp /root/.ssh/authorized_keys /home/botuser/.ssh/ 2>/dev/null || true
    chown -R botuser:botuser /home/botuser/.ssh
    chmod 700 /home/botuser/.ssh
    chmod 600 /home/botuser/.ssh/authorized_keys 2>/dev/null || true
    print_success "تم إعداد SSH للمستخدم"
else
    print_warning "SSH موجود مسبقاً للمستخدم"
fi

# ================================================
# إنشاء مجلد المشروع
# ================================================
print_status "📁 إنشاء مجلد المشروع..."
mkdir -p /home/botuser/medical-bot
mkdir -p /home/botuser/backups
chown -R botuser:botuser /home/botuser/medical-bot
chown -R botuser:botuser /home/botuser/backups
print_success "تم إنشاء مجلدات المشروع"

# ================================================
# إنشاء ملف systemd للبوت
# ================================================
print_status "⚙️ إنشاء خدمة systemd للبوت..."
cat > /etc/systemd/system/medical-bot.service << 'EOF'
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
EOF
print_success "تم إنشاء خدمة systemd"

# ================================================
# إنشاء سكريبت النسخ الاحتياطي
# ================================================
print_status "💾 إنشاء سكريبت النسخ الاحتياطي..."
cat > /home/botuser/backup.sh << 'EOF'
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
    --exclude='.git' \
    -C /home/botuser medical-bot 2>/dev/null || true

# حذف النسخ الاحتياطية القديمة (احتفظ بآخر 7 أيام)
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete 2>/dev/null || true

echo "✅ Backup created: $BACKUP_FILE"
echo "📊 Backup size: $(du -h $BACKUP_FILE | cut -f1) 2>/dev/null || echo 'N/A'"
EOF

chmod +x /home/botuser/backup.sh
chown botuser:botuser /home/botuser/backup.sh
print_success "تم إنشاء سكريبت النسخ الاحتياطي"

# ================================================
# إعداد النسخ الاحتياطي التلقائي
# ================================================
print_status "⏰ إعداد النسخ الاحتياطي التلقائي..."
CRON_JOB="0 2 * * * /home/botuser/backup.sh"
(crontab -u botuser -l 2>/dev/null; echo "$CRON_JOB") | crontab -u botuser -
print_success "تم جدولة النسخ الاحتياطي اليومي الساعة 2 صباحاً"

# ================================================
# إعداد fail2ban للحماية من الهجمات
# ================================================
print_status "🛡️ إعداد fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban
print_success "تم تفعيل fail2ban"

# ================================================
# تنظيف النظام
# ================================================
print_status "🧹 تنظيف النظام..."
apt autoremove -y
apt autoclean
print_success "تم تنظيف النظام"

# ================================================
# إعادة تحميل systemd
# ================================================
print_status "🔄 إعادة تحميل systemd..."
systemctl daemon-reload
print_success "تم إعادة تحميل systemd"

# ================================================
# التحقق من التثبيت
# ================================================
print_status "🔍 التحقق من التثبيت..."

# التحقق من Python
if command -v python3.12 &> /dev/null; then
    PYTHON_VERSION=$(python3.12 --version)
    print_success "Python: $PYTHON_VERSION"
else
    print_error "Python غير مثبت بشكل صحيح"
fi

# التحقق من Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    print_success "Git: $GIT_VERSION"
else
    print_error "Git غير مثبت بشكل صحيح"
fi

# التحقق من UFW
if command -v ufw &> /dev/null; then
    UFW_STATUS=$(ufw status | grep "Status:" | cut -d' ' -f2)
    print_success "UFW: $UFW_STATUS"
else
    print_error "UFW غير مثبت بشكل صحيح"
fi

# التحقق من وجود المستخدم
if id "botuser" &>/dev/null; then
    print_success "المستخدم botuser: موجود"
else
    print_error "المستخدم botuser غير موجود"
fi

# التحقق من systemd service
if [[ -f "/etc/systemd/system/medical-bot.service" ]]; then
    print_success "systemd service: موجود"
else
    print_error "systemd service غير موجود"
fi

# التحقق من سكريبت النسخ الاحتياطي
if [[ -x "/home/botuser/backup.sh" ]]; then
    print_success "سكريبت النسخ الاحتياطي: جاهز"
else
    print_error "سكريبت النسخ الاحتياطي غير جاهز"
fi

echo ""
echo "==============================================="
print_success "🎉 اكتمل إعداد السيرفر الأساسي!"
echo ""
print_warning "📋 الخطوات التالية:"
echo "   1. انسخ المشروع إلى السيرفر"
echo "   2. أعد تسمية config.env.example إلى .env وأدخل البيانات"
echo "   3. شغل البوت: sudo systemctl start medical-bot"
echo "   4. أعد تسمية .env إلى config.env للأمان"
echo ""
print_warning "🔑 معلومات مهمة:"
echo "   - المستخدم: botuser"
echo "   - مجلد المشروع: /home/botuser/medical-bot"
echo "   - خدمة systemd: medical-bot"
echo "   - النسخ الاحتياطي: ~/backup.sh (يومياً الساعة 2 صباحاً)"
echo ""
print_success "🚀 استمتع ببوتك على Hetzner!"
echo "==============================================="

