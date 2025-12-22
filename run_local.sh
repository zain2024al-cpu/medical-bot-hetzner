#!/bin/bash

# ================================================
# Run Bot Locally (Polling Mode) - Linux/Mac
# ================================================

echo ""
echo "================================================"
echo "تشغيل البوت محلياً (وضع Polling)"
echo "================================================"
echo ""

# التحقق من وجود config.env
if [ ! -f "config.env" ]; then
    echo "❌ خطأ: ملف config.env غير موجود!"
    echo "يرجى إنشاء ملف config.env مع BOT_TOKEN"
    echo "يمكنك نسخ config.env.example إلى config.env"
    exit 1
fi

# التحقق من وجود البيئة الافتراضية
if [ ! -d "venv" ]; then
    echo "📦 إنشاء البيئة الافتراضية..."
    python3 -m venv venv
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

# ضبط المتغيرات للوضع المحلي
export HETZNER_DEPLOYMENT="false"
export PORT="0"
export WEBHOOK_URL=""

echo ""
echo "================================================"
echo "🚀 بدء البوت في الوضع المحلي (Polling)..."
echo "================================================"
echo ""
echo "البوت يعمل في الوضع المحلي (Polling)"
echo "اضغط Ctrl+C لإيقاف البوت"
echo ""

# تشغيل البوت
python app.py


