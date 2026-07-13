@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 نشر البوت على Hetzner (طريقة بسيطة)
echo ========================================
echo.
echo ⚠️  سيتم طلب كلمة المرور عدة مرات
echo    كلمة المرور: bot123456
echo.
pause

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set TEMP_PATH=/home/botuser/temp_deploy
set LOCAL_PATH=%~dp0

echo.
echo 📤 رفع الملفات إلى مجلد مؤقت...
echo.
echo 🔧 إنشاء المجلد المؤقت على السيرفر...
ssh %BOT_USER%@%SERVER_IP% "mkdir -p %TEMP_PATH%"

echo.
echo 📁 رفع bot/
scp -r "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📁 رفع config/
scp -r "%LOCAL_PATH%config" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📁 رفع services/
scp -r "%LOCAL_PATH%services" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📁 رفع data/
scp -r "%LOCAL_PATH%data" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📄 رفع الملفات الأساسية...
scp "%LOCAL_PATH%app.py" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
scp "%LOCAL_PATH%requirements.txt" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
scp "%LOCAL_PATH%medical-bot.service" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
if exist "%LOCAL_PATH%health.py" scp "%LOCAL_PATH%health.py" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📤 رفع سكريبت المزامنة...
scp "%LOCAL_PATH%remote_sync.sh" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 🔄 تنفيذ المزامنة على السيرفر...
ssh %BOT_USER%@%SERVER_IP% "chmod +x %TEMP_PATH%/remote_sync.sh && bash %TEMP_PATH%/remote_sync.sh"

echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 10 ثواني...
timeout /t 10 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 20"

echo.
echo 📊 فحص logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 15 --no-pager"

echo.
echo ========================================
echo 🎉 النشر مكتمل!
echo ========================================
pause

