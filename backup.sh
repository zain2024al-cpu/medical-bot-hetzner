#!/bin/bash

# ================================================
# 💾 سكريبت النسخ الاحتياطي للبوت الطبي
# ================================================

set -e  # إيقاف عند أي خطأ

# ألوان للإخراج
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# إعدادات النسخ الاحتياطي
BACKUP_DIR="/home/botuser/backups"
PROJECT_DIR="/home/botuser/medical-bot"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
LOG_FILE="$BACKUP_DIR/backup_$TIMESTAMP.log"

# إنشاء مجلد النسخ إذا لم يكن موجوداً
mkdir -p "$BACKUP_DIR"

# دالة لتسجيل السجلات
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🚀 بدء عملية النسخ الاحتياطي..."

# التحقق من وجود قاعدة البيانات
if [[ -f "$PROJECT_DIR/db/medical_reports.db" ]]; then
    DB_SIZE=$(du -h "$PROJECT_DIR/db/medical_reports.db" | cut -f1)
    log "📊 حجم قاعدة البيانات: $DB_SIZE"
else
    log "⚠️ قاعدة البيانات غير موجودة في المسار المتوقع"
fi

# إنشاء النسخة الاحتياطية
log "📦 إنشاء النسخة الاحتياطية..."
if tar -czf "$BACKUP_FILE" \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.log' \
    --exclude='.git' \
    --exclude='backups' \
    --exclude='node_modules' \
    --exclude='.env' \
    --exclude='config.env' \
    -C /home/botuser medical-bot 2>/dev/null; then

    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "✅ تم إنشاء النسخة الاحتياطية: $BACKUP_FILE"
    log "📊 حجم النسخة الاحتياطية: $BACKUP_SIZE"
else
    log "❌ فشل في إنشاء النسخة الاحتياطية"
    exit 1
fi

# التحقق من سلامة النسخة الاحتياطية
log "🔍 التحقق من سلامة النسخة الاحتياطية..."
if tar -tzf "$BACKUP_FILE" &>/dev/null; then
    log "✅ النسخة الاحتياطية سليمة"
else
    log "❌ النسخة الاحتياطية تالفة!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# حساب عدد الملفات في النسخة الاحتياطية
FILE_COUNT=$(tar -tzf "$BACKUP_FILE" | wc -l)
log "📁 عدد الملفات في النسخة الاحتياطية: $FILE_COUNT"

# حذف النسخ الاحتياطية القديمة (احتفظ بآخر 7 أيام)
log "🗑️ حذف النسخ الاحتياطية القديمة..."
DELETED_COUNT=$(find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +7 -delete -print 2>/dev/null | wc -l)
if [[ $DELETED_COUNT -gt 0 ]]; then
    log "🗑️ تم حذف $DELETED_COUNT نسخة احتياطية قديمة"
fi

# عرض إحصائيات النسخ الاحتياطي
log "📊 إحصائيات النسخ الاحتياطي:"
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "backup_*.tar.gz" | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "   - عدد النسخ الاحتياطية المحفوظة: $BACKUP_COUNT"
log "   - إجمالي حجم مجلد النسخ: $TOTAL_SIZE"

# التحقق من المساحة المتاحة
DISK_USAGE=$(df -h "$BACKUP_DIR" | tail -1 | awk '{print $5}')
log "💾 استخدام المساحة: $DISK_USAGE"

# إشعار إذا كانت المساحة منخفضة
DISK_USAGE_PERCENT=$(df "$BACKUP_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ $DISK_USAGE_PERCENT -gt 90 ]]; then
    log "⚠️ تحذير: مساحة القرص منخفضة جداً ($DISK_USAGE)"
elif [[ $DISK_USAGE_PERCENT -gt 80 ]]; then
    log "⚠️ تنبيه: مساحة القرص منخفضة ($DISK_USAGE)"
fi

# حفظ معلومات إضافية في ملف منفصل
INFO_FILE="$BACKUP_DIR/backup_info_$TIMESTAMP.txt"
cat > "$INFO_FILE" << EOF
معلومات النسخ الاحتياطي - $TIMESTAMP
=====================================
تاريخ الإنشاء: $(date)
المسار: $BACKUP_FILE
الحجم: $BACKUP_SIZE
عدد الملفات: $FILE_COUNT
استخدام المساحة: $DISK_USAGE
عدد النسخ المحفوظة: $BACKUP_COUNT
إجمالي حجم النسخ: $TOTAL_SIZE
EOF

log "📝 تم حفظ معلومات إضافية في: $INFO_FILE"
log "✅ اكتملت عملية النسخ الاحتياطي بنجاح!"

# إرسال إشعار عبر Telegram (اختياري)
if [[ -n "$TELEGRAM_BOT_TOKEN" && -n "$TELEGRAM_ADMIN_ID" ]]; then
    MESSAGE="✅ تم إنشاء نسخة احتياطية جديدة
📊 الحجم: $BACKUP_SIZE
📁 عدد الملفات: $FILE_COUNT
📅 التاريخ: $TIMESTAMP"

    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d chat_id="$TELEGRAM_ADMIN_ID" \
        -d text="$MESSAGE" >/dev/null 2>&1 && log "📱 تم إرسال إشعار Telegram"
fi

echo ""
echo "==============================================="
echo -e "${GREEN}✅ اكتملت عملية النسخ الاحتياطي بنجاح!${NC}"
echo "📁 الملف: $BACKUP_FILE"
echo "📊 الحجم: $BACKUP_SIZE"
echo "==============================================="
