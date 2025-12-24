# Deploy to Hetzner Script
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner"

Write-Host "Starting deployment to Hetzner..." -ForegroundColor Green

# Deploy command
$cmd = "cd $REMOTE_PATH && git fetch origin main && git reset --hard origin/main && systemctl restart medical-bot && sleep 2 && systemctl status medical-bot --no-pager | head -15"

Write-Host "Executing deployment..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Deployment failed!" -ForegroundColor Red
}



