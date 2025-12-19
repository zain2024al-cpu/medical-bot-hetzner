# ================================================
# Run Bot Locally (Polling Mode)
# ================================================

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Running Bot Locally (Polling Mode)" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if config.env exists
if (-not (Test-Path "config.env")) {
    Write-Host "ERROR: config.env file not found!" -ForegroundColor Red
    Write-Host "Please create config.env file with BOT_TOKEN" -ForegroundColor Yellow
    exit 1
}

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "Starting bot in polling mode..." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "The bot will run in POLLING mode (local development)" -ForegroundColor Yellow
Write-Host "No SERVICE_URL environment variable = Polling mode" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the bot" -ForegroundColor Yellow
Write-Host ""

# Clear SERVICE_URL to force polling mode
$env:SERVICE_URL = ""
$env:PORT = ""

# Run the bot
python app.py
