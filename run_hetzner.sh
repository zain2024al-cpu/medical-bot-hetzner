#!/bin/bash

# ================================================
# Run Bot on Hetzner VPS (Polling Mode)
# ================================================

echo ""
echo "================================================"
echo "تشغيل البوت على Hetzner VPS (وضع Polling)"
echo "================================================"
echo ""

# التحقق من وجود config.env
if [ ! -f "config.env" ]; then
    echo "❌ خطأ: ملف config.env غير موجود!"
    echo "يرجى إنشاء ملف config.env مع BOT_TOKEN"
    exit 1
fi

# التحقق من وجود البيئة الافتراضية
if [ ! -d "venv" ]; then
    echo "📦 إنشاء البيئة الافتراضية..."
    python3.12 -m venv venv
fi

# تفعيل البيئة الافتراضية
echo "🔧 تفعيل البيئة الافتراضية..."
source venv/bin/activate

# ترقية pip
echo "⬆️ ترقية pip..."
pip install --upgrade pip

# تثبيت المتطلبات
echo "📥 تثبيت المتطلبات..."
pip install -r requirements.txt

# ضبط المتغيرات للوضع أونلاين على Hetzner
export HETZNER_DEPLOYMENT="true"
export PORT="8080"
export WEBHOOK_URL=""

# ضبط مسار قاعدة البيانات على Hetzner
export DATABASE_PATH="/home/botuser/medical-bot/db/medical_reports.db"

# إنشاء مجلد قاعدة البيانات إذا لم يكن موجوداً
mkdir -p "$(dirname "$DATABASE_PATH")"

echo ""
echo "================================================"
echo "🚀 بدء البوت على Hetzner VPS (Polling)..."
echo "================================================"
echo ""
echo "البوت يعمل على Hetzner VPS في وضع Polling"
echo "اضغط Ctrl+C لإيقاف البوت"
echo ""

# تشغيل البوت
python app.py






