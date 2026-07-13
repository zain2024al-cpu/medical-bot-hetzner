@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🔧 إصلاح شامل ونشر البوت
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot

echo 🔍 التحقق من الملفات المطلوبة على السيرفر...
echo.

echo 1. التحقق من وجود config.env...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "test -f %REMOTE_PATH%/config.env && echo '✅ config.env موجود' || echo '❌ config.env غير موجود'"

echo.
echo 2. التحقق من وجود venv...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "test -d %REMOTE_PATH%/venv && echo '✅ venv موجود' || echo '❌ venv غير موجود'"

echo.
echo 3. التحقق من وجود app.py...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "test -f %REMOTE_PATH%/app.py && echo '✅ app.py موجود' || echo '❌ app.py غير موجود'"

echo.
echo 4. التحقق من Python في venv...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "test -f %REMOTE_PATH%/venv/bin/python && echo '✅ Python موجود' || echo '❌ Python غير موجود'"

echo.
echo ========================================
echo 📤 رفع ملف الخدمة المصحح...
echo ========================================
scp -o StrictHostKeyChecking=no medical-bot.service %BOT_USER%@%SERVER_IP%:/tmp/medical-bot.service

echo.
echo 🔄 نسخ ملف الخدمة وتحديث systemd...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp /tmp/medical-bot.service /etc/systemd/system/medical-bot.service && echo %BOT_PASSWORD% | sudo -S systemctl daemon-reload"

echo.
echo 🔄 إعادة تشغيل البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 5 ثواني...
timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo 🧪 فحص حالة البوت...
echo ========================================
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 25"

echo.
echo ========================================
echo 📊 فحص logs (آخر 20 سطر)...
echo ========================================
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 20 --no-pager"

echo.
echo ========================================
echo ✅ تم الإصلاح!
echo ========================================
echo.
echo إذا كان البوت لا يزال لا يعمل، تحقق من:
echo   1. وجود config.env مع BOT_TOKEN
echo   2. وجود venv ومكتبات Python المثبتة
echo   3. logs البوت للأخطاء
echo.
pause






