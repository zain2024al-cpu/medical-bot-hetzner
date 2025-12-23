# Final Deployment Script - Correct Path
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$CORRECT_PATH = "/home/botuser/medical-bot/temp_upload"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Final Deployment to Hetzner" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Copy files directly via SCP (if needed) or use git
Write-Host "[1/4] Updating code..." -ForegroundColor Yellow

# Option: Use git if repo exists, otherwise we'll need to copy files
$updateCmd = "cd $CORRECT_PATH && if [ -d .git ]; then git fetch origin main && git reset --hard origin/main; else echo 'Not a git repo, skipping git update'; fi"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $updateCmd

# Step 2: Install dependencies in venv
Write-Host ""
Write-Host "[2/4] Updating dependencies in venv..." -ForegroundColor Yellow
$venvCmd = "cd $CORRECT_PATH && source venv/bin/activate && pip install -r requirements.txt --quiet --upgrade"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $venvCmd

# Step 3: Restart service
Write-Host ""
Write-Host "[3/4] Restarting bot service..." -ForegroundColor Yellow
$restartCmd = "systemctl restart medical-bot && sleep 3"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartCmd

# Step 4: Check status
Write-Host ""
Write-Host "[4/4] Checking service status..." -ForegroundColor Yellow
$statusCmd = "systemctl status medical-bot --no-pager | head -25"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $statusCmd

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: If code wasn't updated via git, you may need to:" -ForegroundColor Yellow
Write-Host "  1. Push to GitHub first (may need to allow secrets)" -ForegroundColor White
Write-Host "  2. Or manually copy files via SCP" -ForegroundColor White
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u medical-bot -f'" -ForegroundColor White


