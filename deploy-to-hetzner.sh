#!/bin/bash

# ================================================
# 🚀 سكريبت النشر السريع للبوت على Hetzner
# ================================================

set -e

# ألوان للإخراج
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# متغيرات
REPO_URL="${REPO_URL:-}"
HETZNER_HOST="${HETZNER_HOST:-}"
SSH_KEY_PATH="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"

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

# التحقق من المتطلبات
check_requirements() {
    print_status "🔍 التحقق من المتطلبات..."

    # التحقق من SSH
    if [[ ! -f "$SSH_KEY_PATH" ]]; then
        print_error "مفتاح SSH غير موجود: $SSH_KEY_PATH"
        print_status "أنشئ مفتاح SSH: ssh-keygen -t ed25519 -C 'your-email@example.com'"
        exit 1
    fi

    # التحقق من git
    if ! command -v git >/dev/null 2>&1; then
        print_error "git غير مثبت"
        exit 1
    fi

    # التحقق من أننا في مجلد git
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        print_error "هذا ليس مجلد git"
        exit 1
    fi

    print_success "جميع المتطلبات متوفرة"
}

# إعداد SSH للسيرفر
setup_ssh() {
    print_status "🔑 إعداد SSH للسيرفر..."

    if [[ -z "$HETZNER_HOST" ]]; then
        read -p "أدخل عنوان IP السيرفر: " HETZNER_HOST
    fi

    # إضافة المفتاح العام إلى known_hosts
    ssh-keyscan -H "$HETZNER_HOST" >> ~/.ssh/known_hosts 2>/dev/null

    # اختبار الاتصال
    if ! ssh -o StrictHostKeyChecking=no -i "$SSH_KEY_PATH" "botuser@$HETZNER_HOST" "echo 'SSH connection successful'" 2>/dev/null; then
        print_error "فشل في الاتصال بالسيرفر"
        print_status "تأكد من:"
        print_status "  1. أن عنوان IP صحيح"
        print_status "  2. أن المفتاح العام مضاف للمستخدم botuser"
        print_status "  3. أن الجدار الناري يسمح بـ SSH"
        exit 1
    fi

    print_success "SSH مُعد بنجاح"
}

# رفع المشروع للسيرفر
deploy_project() {
    print_status "📤 رفع المشروع للسيرفر..."

    # الحصول على عنوان المستودع
    if [[ -z "$REPO_URL" ]]; then
        REPO_URL=$(git config --get remote.origin.url)
        if [[ -z "$REPO_URL" ]]; then
            print_error "لم يتم العثور على عنوان المستودع"
            print_status "أدخل عنوان المستودع يدوياً:"
            read -p "Repository URL: " REPO_URL
        fi
    fi

    ssh -i "$SSH_KEY_PATH" "botuser@$HETZNER_HOST" << EOF
        set -e

        echo "📁 التنقل إلى مجلد المشروع..."
        cd ~/medical-bot

        echo "📦 تحديث المشروع..."
        if [[ -d ".git" ]]; then
            git pull origin main --force
        else
            echo "إعادة استنساخ المشروع..."
            cd ..
            rm -rf medical-bot
            git clone $REPO_URL medical-bot
            cd medical-bot
        fi

        echo "🐍 إعداد البيئة الافتراضية..."
        if [[ ! -d "venv" ]]; then
            python3.12 -m venv venv
        fi

        source venv/bin/activate
        pip install -r requirements.txt

        echo "⚙️ إعادة تشغيل الخدمة..."
        sudo systemctl restart medical-bot

        echo "⏳ انتظار بدء الخدمة..."
        sleep 5

        echo "📊 فحص حالة الخدمة..."
        sudo systemctl status medical-bot --no-pager -l

        echo "✅ تم النشر بنجاح!"
EOF

    print_success "تم رفع المشروع بنجاح"
}

# فحص النشر
verify_deployment() {
    print_status "🔍 فحص النشر..."

    ssh -i "$SSH_KEY_PATH" "botuser@$HETZNER_HOST" << 'EOF'
        echo "📊 حالة الخدمة:"
        sudo systemctl status medical-bot --no-pager | head -10

        echo ""
        echo "📝 السجلات الأخيرة:"
        sudo journalctl -u medical-bot -n 5 --no-pager

        echo ""
        echo "💾 النسخ الاحتياطي الأخير:"
        ls -la ~/backups/ | tail -3

        echo ""
        echo "✅ فحص النشر مكتمل"
EOF

    print_success "تم فحص النشر بنجاح"
}

# الدالة الرئيسية
main() {
    echo "==============================================="
    print_status "🚀 بدء النشر على Hetzner VPS"
    echo "==============================================="

    check_requirements
    setup_ssh
    deploy_project
    verify_deployment

    echo ""
    echo "==============================================="
    print_success "🎉 اكتمل النشر بنجاح!"
    echo ""
    print_status "📋 معلومات مفيدة:"
    echo "   - السيرفر: $HETZNER_HOST"
    echo "   - المشروع: ~/medical-bot"
    echo "   - السجلات: sudo journalctl -u medical-bot -f"
    echo "   - إعادة التشغيل: sudo systemctl restart medical-bot"
    echo ""
    print_status "🛠️ أوامر مفيدة:"
    echo "   ssh -i $SSH_KEY_PATH botuser@$HETZNER_HOST"
    echo "   ~/backup.sh  # للنسخ الاحتياطي اليدوي"
    echo "   ~/monitor.sh # لفحص الحالة"
    echo "==============================================="
}

# تشغيل السكريبت
main "$@"

