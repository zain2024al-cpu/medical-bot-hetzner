# ================================================
# سكريبت رفع الملفات المحدثة وإعادة التشغيل
# ================================================

$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "botuser"
$REMOTE_PATH = "/home/botuser/medical-bot"
$LOCAL_PATH = "."

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 رفع الملفات المحدثة وإعادة التشغيل" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من وجود الملفات
if (-not (Test-Path "app.py")) {
    Write-Host "❌ خطأ: لم يتم العثور على app.py" -ForegroundColor Red
    Write-Host "تأكد من أنك في المجلد الصحيح (botuser@)" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/5] 📤 رفع الملفات المحدثة..." -ForegroundColor Yellow
Write-Host ""

# رفع الملفات الأساسية
$filesToUpload = @(
    "app.py",
    "config",
    "bot",
    "db",
    "services",
    "requirements.txt",
    "data"
)

foreach ($item in $filesToUpload) {
    if (Test-Path $item) {
        Write-Host "  📁 رفع $item..." -ForegroundColor Gray
        scp -r -o StrictHostKeyChecking=no "$LOCAL_PATH\$item" ${HETZNER_USER}@${HETZNER_IP}:${REMOTE_PATH}/ 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✅ تم رفع $item" -ForegroundColor Green
        } else {
            Write-Host "    ⚠️ تحذير: قد يكون هناك مشكلة في رفع $item" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ⚠️ $item غير موجود، سيتم تخطيه" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "[2/5] 📦 تثبيت/تحديث المتطلبات..." -ForegroundColor Yellow
$installCmd = "cd $REMOTE_PATH && source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $installCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ تم تثبيت المتطلبات" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ تحذير: قد تكون هناك مشكلة في تثبيت المتطلبات" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/5] 🔄 إعادة تشغيل الخدمة..." -ForegroundColor Yellow
$restartCmd = "sudo systemctl restart medical-bot"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ تم إرسال أمر إعادة التشغيل" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ تحذير: قد تكون هناك مشكلة في إعادة التشغيل" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[4/5] ⏳ انتظار 3 ثوانٍ..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

Write-Host ""
Write-Host "[5/5] 📊 التحقق من حالة الخدمة..." -ForegroundColor Yellow
$statusCmd = "sudo systemctl status medical-bot --no-pager | head -20"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $statusCmd

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ تم الانتهاء من النشر!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 لعرض السجلات:" -ForegroundColor Yellow
Write-Host "  ssh $HETZNER_USER@$HETZNER_IP 'sudo journalctl -u medical-bot -f'" -ForegroundColor White
Write-Host ""


