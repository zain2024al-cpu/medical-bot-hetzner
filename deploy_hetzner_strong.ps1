# ================================================
# deploy_hetzner_strong.ps1
# 🚀 سكريبت قوي للنشر على Hetzner
# ================================================

Write-Host "🚀 بدء النشر القوي على Hetzner..." -ForegroundColor Green
Write-Host ""

# معلومات الخادم
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner"

# التحقق من الاتصال
Write-Host "📡 التحقق من الاتصال بالخادم..." -ForegroundColor Yellow
try {
    $connection = Test-Connection -ComputerName $HETZNER_IP -Count 1 -Quiet
    if (-not $connection) {
        Write-Host "❌ فشل الاتصال بالخادم!" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ الاتصال بالخادم ناجح" -ForegroundColor Green
} catch {
    Write-Host "❌ خطأ في الاتصال: $_" -ForegroundColor Red
    exit 1
}

# التحقق من Git
Write-Host ""
Write-Host "📦 التحقق من Git..." -ForegroundColor Yellow
$gitStatus = git status --short 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ تحذير: قد تكون هناك مشاكل في Git" -ForegroundColor Yellow
}

# رفع التحديثات على GitHub (محاولة)
Write-Host ""
Write-Host "📤 محاولة رفع التحديثات على GitHub..." -ForegroundColor Yellow
try {
    # محاولة push (قد يفشل بسبب secrets protection)
    git push origin main 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ تم رفع التحديثات على GitHub" -ForegroundColor Green
    } else {
        Write-Host "⚠️ فشل رفع التحديثات على GitHub (قد يكون بسبب secrets protection)" -ForegroundColor Yellow
        Write-Host "   سيتم المتابعة مع النشر المباشر على Hetzner" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️ فشل رفع التحديثات على GitHub: $_" -ForegroundColor Yellow
    Write-Host "   سيتم المتابعة مع النشر المباشر على Hetzner" -ForegroundColor Yellow
}

# النشر على Hetzner
Write-Host ""
Write-Host "🚀 بدء النشر على Hetzner..." -ForegroundColor Green
Write-Host "   IP: $HETZNER_IP" -ForegroundColor Cyan
Write-Host "   Path: $REMOTE_PATH" -ForegroundColor Cyan

# الأمر الكامل للنشر
$deployCommand = @"
cd $REMOTE_PATH && \
echo '📥 جلب التحديثات من GitHub...' && \
git fetch origin main && \
git reset --hard origin/main && \
echo '✅ تم جلب التحديثات' && \
echo '' && \
echo '🔄 إعادة تشغيل البوت...' && \
systemctl restart medical-bot && \
sleep 3 && \
echo '✅ تم إعادة تشغيل البوت' && \
echo '' && \
echo '📊 حالة البوت:' && \
systemctl status medical-bot --no-pager -l | head -20 && \
echo '' && \
echo '✅ النشر مكتمل!'
"@

Write-Host ""
Write-Host "⚙️ تنفيذ الأوامر على الخادم..." -ForegroundColor Yellow
Write-Host ""

try {
    # تنفيذ الأمر عبر SSH
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 $HETZNER_USER@$HETZNER_IP $deployCommand
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ ✅ ✅ النشر مكتمل بنجاح! ✅ ✅ ✅" -ForegroundColor Green
        Write-Host ""
        Write-Host "📊 للتحقق من حالة البوت:" -ForegroundColor Cyan
        Write-Host "   ssh $HETZNER_USER@$HETZNER_IP 'systemctl status medical-bot'" -ForegroundColor White
        Write-Host ""
        Write-Host "📋 لعرض السجلات:" -ForegroundColor Cyan
        Write-Host "   ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u medical-bot -f'" -ForegroundColor White
    } else {
        Write-Host ""
        Write-Host "❌ فشل النشر. يرجى التحقق من الأخطاء أعلاه." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "❌ خطأ في النشر: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 نصائح:" -ForegroundColor Yellow
    Write-Host "   1. تأكد من أن SSH key مضاف للخادم" -ForegroundColor White
    Write-Host "   2. تأكد من أن المسار $REMOTE_PATH موجود" -ForegroundColor White
    Write-Host "   3. تأكد من أن البوت موجود في systemd" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "🎉 النشر مكتمل!" -ForegroundColor Green



