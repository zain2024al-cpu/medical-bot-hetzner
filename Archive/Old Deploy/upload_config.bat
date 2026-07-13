@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 📤 رفع ملف config.env إلى السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set REMOTE_PATH=/home/botuser/medical-bot

if not exist "config.env" (
    echo ❌ ملف config.env غير موجود محلياً!
    echo يرجى التأكد من وجود الملف في المجلد الحالي
    pause
    exit /b 1
)

echo 📤 رفع config.env...
scp -o StrictHostKeyChecking=no config.env %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/config.env

if errorlevel 0 (
    echo.
    echo ✅ تم رفع config.env بنجاح
    echo.
    echo 🔄 إعادة تشغيل البوت...
    ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo bot123456 | sudo -S systemctl restart medical-bot"
    
    echo.
    echo ⏳ انتظار 5 ثواني...
    timeout /t 5 /nobreak >nul
    
    echo.
    echo 🧪 فحص حالة البوت...
    ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo bot123456 | sudo -S systemctl status medical-bot --no-pager | head -n 15"
    
    echo.
    echo 📊 فحص logs (آخر 10 سطر)...
    ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo bot123456 | sudo -S journalctl -u medical-bot -n 10 --no-pager"
) else (
    echo ❌ فشل رفع config.env
)

echo.
pause

