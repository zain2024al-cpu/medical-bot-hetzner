@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🔧 إصلاح ملف الخدمة على السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot

echo 📤 رفع ملف الخدمة المصحح...
scp -o StrictHostKeyChecking=no medical-bot.service %BOT_USER%@%SERVER_IP%:/tmp/medical-bot.service

echo.
echo 🔄 نسخ ملف الخدمة للمكان الصحيح...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp /tmp/medical-bot.service /etc/systemd/system/medical-bot.service"

echo.
echo 🔄 إعادة تحميل systemd...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl daemon-reload"

echo.
echo 🔄 إعادة تشغيل البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 5 ثواني...
timeout /t 5 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 20"

echo.
echo 📊 فحص logs (آخر 15 سطر)...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 15 --no-pager"

echo.
echo ========================================
echo ✅ تم الإصلاح!
echo ========================================
pause






