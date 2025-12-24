# Complete Deployment Script for Hetzner
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner"
$GIT_REPO = "https://github.com/zain2024al-cpu/medical-bot-hetzner.git"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Complete Deployment to Hetzner" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if directory exists
Write-Host "[1/5] Checking remote directory..." -ForegroundColor Yellow
$checkCmd = "test -d $REMOTE_PATH && echo 'EXISTS' || echo 'NOT_EXISTS'"
$result = ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $checkCmd

if ($result -match "NOT_EXISTS") {
    Write-Host "Directory not found. Creating and cloning..." -ForegroundColor Yellow
    $setupCmd = "mkdir -p $REMOTE_PATH && cd $REMOTE_PATH && git clone $GIT_REPO . || (cd $REMOTE_PATH && git init && git remote add origin $GIT_REPO && git pull origin main)"
    ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $setupCmd
} else {
    Write-Host "Directory exists. Updating..." -ForegroundColor Green
}

# Step 2: Pull latest changes
Write-Host ""
Write-Host "[2/5] Pulling latest changes..." -ForegroundColor Yellow
$pullCmd = "cd $REMOTE_PATH && git fetch origin main && git reset --hard origin/main"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $pullCmd

# Step 3: Install dependencies
Write-Host ""
Write-Host "[3/5] Installing/updating dependencies..." -ForegroundColor Yellow
$installCmd = "cd $REMOTE_PATH && python3 -m pip install -r requirements.txt --quiet --upgrade"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $installCmd

# Step 4: Restart service
Write-Host ""
Write-Host "[4/5] Restarting bot service..." -ForegroundColor Yellow
$restartCmd = "systemctl restart medical-bot && sleep 3"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartCmd

# Step 5: Check status
Write-Host ""
Write-Host "[5/5] Checking service status..." -ForegroundColor Yellow
$statusCmd = "systemctl status medical-bot --no-pager | head -20"
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $statusCmd

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u medical-bot -f'" -ForegroundColor White



