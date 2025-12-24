# Direct File Copy Deployment
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/home/botuser/medical-bot/temp_upload"
$LOCAL_PATH = "."

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Direct File Copy Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Files to copy (key files only)
$filesToCopy = @(
    "app.py",
    "bot",
    "config",
    "db",
    "services",
    "requirements.txt"
)

Write-Host "[1/3] Copying files to server..." -ForegroundColor Yellow
foreach ($file in $filesToCopy) {
    Write-Host "  Copying $file..." -ForegroundColor Gray
    scp -r -o StrictHostKeyChecking=no "$LOCAL_PATH\$file" ${HETZNER_USER}@${HETZNER_IP}:${REMOTE_PATH}/ 2>&1 | Out-Null
}

Write-Host ""
Write-Host "[2/3] Installing dependencies..." -ForegroundColor Yellow
$installCmd = "cd $REMOTE_PATH && source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $installCmd

Write-Host ""
Write-Host "[3/3] Restarting service..." -ForegroundColor Yellow
$restartCmd = "systemctl restart medical-bot && sleep 3 && systemctl status medical-bot --no-pager | head -20"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartCmd

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan



