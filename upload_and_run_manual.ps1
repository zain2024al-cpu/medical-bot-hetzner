# ================================================
# سكريبت رفع الملفات المحدثة وتشغيل البوت يدوياً
# ================================================

$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "botuser"
$REMOTE_PATH = "/home/botuser/medical-bot"
$LOCAL_PATH = "."

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 رفع الملفات المحدثة على السيرفر" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من وجود الملفات
if (-not (Test-Path "app.py")) {
    Write-Host "❌ خطأ: لم يتم العثور على app.py" -ForegroundColor Red
    Write-Host "تأكد من أنك في المجلد الصحيح (botuser@)" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] 📤 رفع الملفات المحدثة..." -ForegroundColor Yellow
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
        $result = scp -r -o StrictHostKeyChecking=no "$LOCAL_PATH\$item" ${HETZNER_USER}@${HETZNER_IP}:${REMOTE_PATH}/ 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    ✅ تم رفع $item" -ForegroundColor Green
        } else {
            Write-Host "    ⚠️ تحذير: قد يكون هناك مشكلة في رفع $item" -ForegroundColor Yellow
            Write-Host "    $result" -ForegroundColor Red
        }
    } else {
        Write-Host "  ⚠️ $item غير موجود، سيتم تخطيه" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "[2/4] 📦 تثبيت/تحديث المتطلبات..." -ForegroundColor Yellow
$installCmd = "cd $REMOTE_PATH && source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade"
$installResult = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $installCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ تم تثبيت المتطلبات" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ تحذير: قد تكون هناك مشكلة في تثبيت المتطلبات" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/4] 🛑 إيقاف الخدمة التلقائية (إن وجدت)..." -ForegroundColor Yellow
$stopCmd = "sudo systemctl stop medical-bot 2>/dev/null || true"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $stopCmd
Write-Host "  ✅ تم إيقاف الخدمة التلقائية" -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] ✅ اكتمل رفع الملفات!" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📋 تعليمات التشغيل اليدوي:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1️⃣  اتصل بالسيرفر:" -ForegroundColor White
Write-Host "   ssh $HETZNER_USER@$HETZNER_IP" -ForegroundColor Cyan
Write-Host ""
Write-Host "2️⃣  انتقل إلى مجلد البوت:" -ForegroundColor White
Write-Host "   cd $REMOTE_PATH" -ForegroundColor Cyan
Write-Host ""
Write-Host "3️⃣  فعّل البيئة الافتراضية:" -ForegroundColor White
Write-Host "   source venv/bin/activate" -ForegroundColor Cyan
Write-Host ""
Write-Host "4️⃣  شغّل البوت يدوياً:" -ForegroundColor White
Write-Host "   python app.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "   أو باستخدام السكريبت:" -ForegroundColor Gray
Write-Host "   bash run_hetzner.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "5️⃣  لإيقاف البوت: اضغط Ctrl+C" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "💡 نصائح إضافية:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 لعرض السجلات (إذا كان البوت يعمل كخدمة):" -ForegroundColor White
Write-Host "   sudo journalctl -u medical-bot -f" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔄 لإعادة تشغيل البوت كخدمة (لاحقاً):" -ForegroundColor White
Write-Host "   sudo systemctl start medical-bot" -ForegroundColor Cyan
Write-Host "   sudo systemctl status medical-bot" -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 لعرض سجلات البوت المباشرة:" -ForegroundColor White
Write-Host "   tail -f logs/bot.log" -ForegroundColor Cyan
Write-Host ""



