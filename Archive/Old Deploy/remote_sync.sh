#!/bin/bash
# سكريبت لنسخ الملفات من مجلد مؤقت إلى مجلد البوت

REMOTE_PATH="/home/botuser/medical-bot"
TEMP_PATH="/home/botuser/temp_deploy"

echo "========================================"
echo "🔄 مزامنة الملفات المحدثة"
echo "========================================"
echo ""

# إنشاء المجلد المؤقت إذا لم يكن موجوداً
mkdir -p "$TEMP_PATH"

# نسخ الملفات من المجلد المؤقت
if [ -d "$TEMP_PATH" ]; then
    echo "📁 نسخ المجلدات..."
    
    # نسخ bot
    if [ -d "$TEMP_PATH/bot" ]; then
        echo "   → bot/"
        cp -r "$TEMP_PATH/bot"/* "$REMOTE_PATH/bot/" 2>/dev/null
    fi
    
    # نسخ config
    if [ -d "$TEMP_PATH/config" ]; then
        echo "   → config/"
        cp -r "$TEMP_PATH/config"/* "$REMOTE_PATH/config/" 2>/dev/null
    fi
    
    # نسخ services
    if [ -d "$TEMP_PATH/services" ]; then
        echo "   → services/"
        cp -r "$TEMP_PATH/services"/* "$REMOTE_PATH/services/" 2>/dev/null
    fi
    
    # نسخ data
    if [ -d "$TEMP_PATH/data" ]; then
        echo "   → data/"
        cp -r "$TEMP_PATH/data"/* "$REMOTE_PATH/data/" 2>/dev/null
    fi
    
    # نسخ الملفات الأساسية
    echo "📄 نسخ الملفات الأساسية..."
    for file in app.py requirements.txt medical-bot.service health.py; do
        if [ -f "$TEMP_PATH/$file" ]; then
            echo "   → $file"
            cp "$TEMP_PATH/$file" "$REMOTE_PATH/"
        fi
    done
    
    # تنظيف المجلد المؤقت
    echo ""
    echo "🧹 تنظيف الملفات المؤقتة..."
    rm -rf "$TEMP_PATH"
    
    echo ""
    echo "✅ تم نسخ جميع الملفات بنجاح"
else
    echo "❌ المجلد المؤقت غير موجود: $TEMP_PATH"
    exit 1
fi

echo ""
echo "========================================"

