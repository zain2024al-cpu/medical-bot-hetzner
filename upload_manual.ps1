# Upload Updated Files to Server
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "botuser"
$REMOTE_PATH = "/home/botuser/medical-bot"
$LOCAL_PATH = "."

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Uploading Updated Files to Server" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path "app.py")) {
    Write-Host "Error: app.py not found" -ForegroundColor Red
    Write-Host "Make sure you are in the botuser@ folder" -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] Uploading files..." -ForegroundColor Yellow
Write-Host ""

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
        Write-Host "  Uploading $item..." -ForegroundColor Gray
        scp -r -o StrictHostKeyChecking=no "$LOCAL_PATH\$item" ${HETZNER_USER}@${HETZNER_IP}:${REMOTE_PATH}/ 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    OK: $item uploaded" -ForegroundColor Green
        } else {
            Write-Host "    Warning: Issue uploading $item" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  Warning: $item not found, skipping" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "[2/4] Installing/updating requirements..." -ForegroundColor Yellow
$installCmd = "cd $REMOTE_PATH && source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $installCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK: Requirements installed" -ForegroundColor Green
} else {
    Write-Host "  Warning: Issue installing requirements" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/4] Stopping auto service (if running)..." -ForegroundColor Yellow
$stopCmd = "sudo systemctl stop medical-bot 2>/dev/null || true"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $stopCmd
Write-Host "  OK: Auto service stopped" -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] Upload complete!" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Manual Run Instructions:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Connect to server:" -ForegroundColor White
Write-Host "   ssh $HETZNER_USER@$HETZNER_IP" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Go to bot folder:" -ForegroundColor White
Write-Host "   cd $REMOTE_PATH" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Activate virtual environment:" -ForegroundColor White
Write-Host "   source venv/bin/activate" -ForegroundColor Cyan
Write-Host ""
Write-Host "4. Run bot manually:" -ForegroundColor White
Write-Host "   python app.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Or use script:" -ForegroundColor Gray
Write-Host "   bash run_hetzner.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "5. To stop bot: Press Ctrl+C" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Additional Tips:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "View logs (if running as service):" -ForegroundColor White
Write-Host "   sudo journalctl -u medical-bot -f" -ForegroundColor Cyan
Write-Host ""
Write-Host "Restart bot as service (later):" -ForegroundColor White
Write-Host "   sudo systemctl start medical-bot" -ForegroundColor Cyan
Write-Host "   sudo systemctl status medical-bot" -ForegroundColor Cyan
Write-Host ""
Write-Host "View bot logs directly:" -ForegroundColor White
Write-Host "   tail -f logs/bot.log" -ForegroundColor Cyan
Write-Host ""





