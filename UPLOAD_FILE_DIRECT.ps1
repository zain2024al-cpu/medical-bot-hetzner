# ================================================
# رفع الملف مباشرة إلى Hetzner
# ================================================

$ErrorActionPreference = "Stop"

Write-Host "🚀 رفع الملف مباشرة إلى Hetzner..." -ForegroundColor Green
Write-Host ""

# معلومات Hetzner
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner/bot/handlers/user"
$SERVICE_NAME = "medical-bot"

# المسار المحلي للملف
$localFile = Join-Path $PSScriptRoot "bot\handlers\user\user_reports_add_new_system.py"

if (-not (Test-Path $localFile)) {
    Write-Host "❌ الملف غير موجود: $localFile" -ForegroundColor Red
    exit 1
}

Write-Host "📁 الملف المحلي: $localFile" -ForegroundColor Cyan
Write-Host "📁 المسار على السيرفر: $REMOTE_PATH/user_reports_add_new_system.py" -ForegroundColor Cyan
Write-Host ""

# رفع الملف
Write-Host "📤 جارٍ رفع الملف..." -ForegroundColor Yellow

# استخدام scp
$scpCommand = "scp -o StrictHostKeyChecking=no `"$localFile`" ${HETZNER_USER}@${HETZNER_IP}:${REMOTE_PATH}/user_reports_add_new_system.py"
Invoke-Expression $scpCommand

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل رفع الملف" -ForegroundColor Red
    Write-Host "   جارٍ المحاولة بطريقة بديلة..." -ForegroundColor Yellow
    
    # طريقة بديلة: استخدام base64
    $fileContent = Get-Content $localFile -Raw -Encoding UTF8
    $base64Content = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($fileContent))
    
    $uploadScript = @"
cd $REMOTE_PATH
echo '$base64Content' | base64 -d > user_reports_add_new_system.py
chmod 644 user_reports_add_new_system.py
echo '✅ تم رفع الملف'
"@
    
    ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $uploadScript
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ فشل رفع الملف بالطريقة البديلة أيضاً" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ تم رفع الملف بنجاح" -ForegroundColor Green
Write-Host ""

# إعادة تشغيل الخدمة
Write-Host "🔄 إعادة تشغيل الخدمة..." -ForegroundColor Yellow

$restartScript = @"
systemctl restart $SERVICE_NAME
sleep 5
if systemctl is-active --quiet $SERVICE_NAME; then
    echo '✅ الخدمة تعمل بنجاح'
    systemctl status $SERVICE_NAME --no-pager -l | head -n 15
else
    echo '❌ فشل تشغيل الخدمة!'
    systemctl status $SERVICE_NAME --no-pager -l | head -n 20
    exit 1
fi
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartScript

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل إعادة تشغيل الخدمة" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ تم النشر بنجاح!" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host ""



