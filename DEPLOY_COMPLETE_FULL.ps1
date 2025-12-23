# ================================================
# Complete Deployment Script for Hetzner
# النشر الكامل على Hetzner بعد رفع GitHub
# ================================================

$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner"
$GIT_REPO = "https://github.com/zain2024al-cpu/medical-bot-hetzner.git"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🚀 النشر الكامل على Hetzner" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if directory exists
Write-Host "[1/5] 🔍 التحقق من المجلد على السيرفر..." -ForegroundColor Yellow
$checkCmd = "test -d $REMOTE_PATH && echo 'EXISTS' || echo 'NOT_EXISTS'"
$result = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $checkCmd

if ($result -match "NOT_EXISTS") {
    Write-Host "⚠️ المجلد غير موجود. جاري الإنشاء والاستنساخ..." -ForegroundColor Yellow
    $setupCmd = "mkdir -p $REMOTE_PATH && cd $REMOTE_PATH && git clone $GIT_REPO . || (cd $REMOTE_PATH && git init && git remote add origin $GIT_REPO && git pull origin main)"
    ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $setupCmd
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ فشل في إنشاء المجلد والاستنساخ" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ تم إنشاء المجلد والاستنساخ" -ForegroundColor Green
} else {
    Write-Host "✅ المجلد موجود. جاري التحديث..." -ForegroundColor Green
}

# Step 2: Pull latest changes from GitHub
Write-Host ""
Write-Host "[2/5] 📥 جلب أحدث التحديثات من GitHub..." -ForegroundColor Yellow
$pullCmd = "cd $REMOTE_PATH && git fetch origin main && git reset --hard origin/main && echo '✅ تم جلب التحديثات'"
$pullResult = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $pullCmd
Write-Host $pullResult

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل في جلب التحديثات" -ForegroundColor Red
    exit 1
}

# Step 3: Install/update dependencies
Write-Host ""
Write-Host "[3/5] 📦 تحديث المتطلبات..." -ForegroundColor Yellow
$installCmd = "cd $REMOTE_PATH && if [ -d venv ]; then source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade; else python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade; fi && echo '✅ تم تحديث المتطلبات'"
$installResult = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $installCmd
Write-Host $installResult

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ تحذير: قد تكون هناك مشكلة في تثبيت المتطلبات" -ForegroundColor Yellow
}

# Step 4: Restart service
Write-Host ""
Write-Host "[4/5] 🔄 إعادة تشغيل خدمة البوت..." -ForegroundColor Yellow
$restartCmd = "systemctl daemon-reload && systemctl restart medical-bot && sleep 5 && echo '✅ تم إعادة التشغيل'"
$restartResult = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartCmd
Write-Host $restartResult

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل في إعادة تشغيل الخدمة" -ForegroundColor Red
    exit 1
}

# Step 5: Check service status
Write-Host ""
Write-Host "[5/5] 📊 التحقق من حالة الخدمة..." -ForegroundColor Yellow
$statusCmd = "systemctl status medical-bot --no-pager | head -25"
$statusResult = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $statusCmd
Write-Host $statusResult

# Check if service is running
$activeCmd = "systemctl is-active medical-bot"
$activeResult = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $activeCmd

if ($activeResult -match "active") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "✅ ✅ ✅ النشر مكتمل بنجاح! ✅ ✅ ✅" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📊 حالة الخدمة: ✅ تعمل" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 لمراقبة السجلات:" -ForegroundColor Cyan
    Write-Host "   ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u medical-bot -f'" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "⚠️ تحذير: الخدمة قد لا تعمل بشكل صحيح" -ForegroundColor Yellow
    Write-Host "يرجى التحقق من السجلات:" -ForegroundColor Yellow
    Write-Host "   ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u medical-bot -n 50'" -ForegroundColor White
    Write-Host ""
    exit 1
}

