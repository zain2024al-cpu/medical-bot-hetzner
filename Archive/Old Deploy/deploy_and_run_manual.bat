@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 رفع الملفات وتشغيل البوت يدوياً
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📤 رفع الملفات المحدثة...
echo.

echo 📁 رفع مجلد bot/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📁 رفع مجلد config/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%config" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📁 رفع مجلد services/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%services" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📁 رفع مجلد data/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%data" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📄 رفع الملفات الأساسية...
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%app.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%requirements.txt" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%medical-bot.service" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if exist "%LOCAL_PATH%health.py" (
    scp -o StrictHostKeyChecking=no "%LOCAL_PATH%health.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
)

echo.
echo 📤 رفع سكريبت التشغيل اليدوي...
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%run_bot_manual.sh" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo ✅ تم رفع جميع الملفات بنجاح!
echo.

echo ========================================
echo 🔧 إعداد السيرفر وتشغيل البوت يدوياً
echo ========================================
echo.

echo 🔄 إيقاف الخدمة وإعداد السكريبت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl stop medical-bot && chmod +x %REMOTE_PATH%/run_bot_manual.sh"

echo.
echo ========================================
echo 🚀 تشغيل البوت يدوياً
echo ========================================
echo.
echo ⚠️  سيتم تشغيل البوت في نافذة SSH منفصلة
echo    اضغط Ctrl+C لإيقاف البوت
echo.
echo 📋 للاتصال بالسيرفر وتشغيل البوت يدوياً:
echo.
echo    ssh %BOT_USER%@%SERVER_IP%
echo    cd %REMOTE_PATH%
echo    bash run_bot_manual.sh
echo.
echo أو مباشرة:
echo    cd %REMOTE_PATH%
echo    source venv/bin/activate
echo    python app.py
echo.
echo ========================================
echo.

pause




