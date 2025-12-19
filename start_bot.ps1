# ================================================
# تشغيل البوت بسرعة
# ================================================

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "تشغيل البوت..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من وجود config.env
if (-not (Test-Path "config.env")) {
    Write-Host "خطأ: ملف config.env غير موجود!" -ForegroundColor Red
    Write-Host "يرجى إنشاء ملف config.env مع BOT_TOKEN" -ForegroundColor Yellow
    exit 1
}

# تفعيل البيئة الافتراضية
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "تفعيل البيئة الافتراضية..." -ForegroundColor Yellow
    & .\venv\Scripts\Activate.ps1
} else {
    Write-Host "تحذير: البيئة الافتراضية غير موجودة" -ForegroundColor Yellow
    Write-Host "سيتم استخدام Python النظام" -ForegroundColor Yellow
}

# ضبط المتغيرات للوضع المحلي (Polling)
$env:SERVICE_URL = ""
$env:PORT = ""

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "بدء البوت في وضع Polling..." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "البوت يعمل في الوضع المحلي (Polling)" -ForegroundColor Yellow
Write-Host "اضغط Ctrl+C لإيقاف البوت" -ForegroundColor Yellow
Write-Host ""

# تشغيل البوت
python app.py





