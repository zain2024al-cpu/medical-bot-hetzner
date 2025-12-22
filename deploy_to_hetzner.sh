#!/bin/bash
# ================================================
# سكريبت النشر الآمن على Hetzner
# ================================================

set -e  # إيقاف التنفيذ عند أي خطأ

echo "🚀 بدء عملية النشر على Hetzner..."
echo ""

# الألوان للرسائل
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# معلومات السيرفر
SERVER_IP="5.223.58.71"
SERVER_USER="root"
PROJECT_DIR="/root/medical-bot-hetzner"
SERVICE_NAME="medical-bot"

echo -e "${YELLOW}📋 معلومات النشر:${NC}"
echo "  - السيرفر: $SERVER_IP"
echo "  - المستخدم: $SERVER_USER"
echo "  - المجلد: $PROJECT_DIR"
echo "  - الخدمة: $SERVICE_NAME"
echo ""

# التحقق من الاتصال
echo -e "${YELLOW}🔍 التحقق من الاتصال بالسيرفر...${NC}"
if ! ssh -o ConnectTimeout=5 $SERVER_USER@$SERVER_IP "echo 'Connected'" > /dev/null 2>&1; then
    echo -e "${RED}❌ فشل الاتصال بالسيرفر!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ الاتصال ناجح${NC}"
echo ""

# جلب التحديثات
echo -e "${YELLOW}📥 جلب التحديثات من GitHub...${NC}"
ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
    cd /root/medical-bot-hetzner
    
    # حفظ التغييرات المحلية (إن وجدت)
    git stash
    
    # جلب التحديثات
    git fetch origin
    
    # التحقق من التحديثات
    if git diff --quiet HEAD origin/main; then
        echo "ℹ️ لا توجد تحديثات جديدة"
        exit 0
    fi
    
    # عرض التغييرات
    echo "📝 التغييرات الجديدة:"
    git log HEAD..origin/main --oneline
    
    # سحب التحديثات
    git pull origin main
    
    echo "✅ تم جلب التحديثات بنجاح"
ENDSSH

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ فشل جلب التحديثات!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ تم جلب التحديثات${NC}"
echo ""

# إعادة تشغيل الخدمة
echo -e "${YELLOW}🔄 إعادة تشغيل الخدمة...${NC}"
ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
    systemctl restart medical-bot
    sleep 2
    
    # التحقق من الحالة
    if systemctl is-active --quiet medical-bot; then
        echo "✅ الخدمة تعمل بنجاح"
    else
        echo "❌ فشل تشغيل الخدمة!"
        systemctl status medical-bot
        exit 1
    fi
ENDSSH

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ فشل إعادة تشغيل الخدمة!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ تم إعادة تشغيل الخدمة${NC}"
echo ""

# عرض الحالة النهائية
echo -e "${YELLOW}📊 الحالة النهائية:${NC}"
ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
    echo ""
    echo "📋 حالة الخدمة:"
    systemctl status medical-bot --no-pager -l | head -n 10
    
    echo ""
    echo "📝 آخر 10 أسطر من السجلات:"
    journalctl -u medical-bot -n 10 --no-pager
ENDSSH

echo ""
echo -e "${GREEN}✅ تم النشر بنجاح!${NC}"
echo ""
echo "💡 للتحقق من السجلات:"
echo "   ssh $SERVER_USER@$SERVER_IP 'journalctl -u $SERVICE_NAME -f'"

