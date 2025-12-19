# ================================================
# Stop Bot Locally
# ================================================

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Stopping the Bot Locally" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Search for Python processes running app.py
Write-Host "🔍 Searching for running bot processes..." -ForegroundColor Yellow

$processes = Get-CimInstance Win32_Process | Where-Object { 
    ($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and 
    $_.CommandLine -like "*app.py*"
}

if ($processes) {
    Write-Host "✅ Found running bot processes:" -ForegroundColor Green
    Write-Host ""
    
    foreach ($proc in $processes) {
        Write-Host "   🔸 Process ID: $($proc.ProcessId)" -ForegroundColor Cyan
        Write-Host "   📝 Command: $($proc.CommandLine)" -ForegroundColor Gray
        Write-Host ""
    }
    
    Write-Host "⏹️  Stopping processes..." -ForegroundColor Yellow
    
    foreach ($proc in $processes) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "   ✅ Process $($proc.ProcessId) stopped." -ForegroundColor Green
        } catch {
            Write-Host "   ❌ Failed to stop process $($proc.ProcessId): $_" -ForegroundColor Red
        }
    }
    
    Write-Host ""
    Write-Host "✅ Bot stopped successfully!" -ForegroundColor Green
} else {
    Write-Host "ℹ️  No bot processes currently running." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "💡 If the bot is running in a Terminal window, press Ctrl+C to stop it." -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
