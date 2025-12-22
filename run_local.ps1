# ================================================
# Run Bot Locally (Polling Mode) - Windows
# ================================================

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "تشغيل البوت محلياً (وضع Polling)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من وجود config.env
if (-not (Test-Path "config.env")) {
    Write-Host "خطأ: ملف config.env غير موجود!" -ForegroundColor Red
    Write-Host "يرجى إنشاء ملف config.env مع BOT_TOKEN" -ForegroundColor Yellow
    Write-Host "يمكنك نسخ config.env.example إلى config.env" -ForegroundColor Yellow
    exit 1
}

# التحقق من وجود البيئة الافتراضية
if (-not (Test-Path "venv")) {
    Write-Host "إنشاء البيئة الافتراضية..." -ForegroundColor Yellow
    python -m venv venv
}

# تفعيل البيئة الافتراضية
Write-Host "تفعيل البيئة الافتراضية..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# ترقية pip
Write-Host "ترقية pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# تثبيت المتطلبات
Write-Host "تثبيت المتطلبات..." -ForegroundColor Yellow
pip install -r requirements.txt

# ضبط المتغيرات للوضع المحلي
$env:HETZNER_DEPLOYMENT = "false"
$env:PORT = "0"
$env:WEBHOOK_URL = ""

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "بدء البوت في الوضع المحلي (Polling)..." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "البوت يعمل في الوضع المحلي (Polling)" -ForegroundColor Yellow
Write-Host "اضغط Ctrl+C لإيقاف البوت" -ForegroundColor Yellow
Write-Host ""

# تشغيل البوت
python app.py
