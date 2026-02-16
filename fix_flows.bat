@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 رفع مجلد flows كاملاً
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📁 رفع مجلد flows/ كاملاً...
scp -r "bot\handlers\user\user_reports_add_new_system\flows" %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/

echo.
echo ✅ تم رفع المجلد
echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 15 ثانية...
timeout /t 15 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 20"

echo.
echo 📊 فحص logs (آخر 40 سطر)...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 40 --no-pager | grep -E '(ERROR|WARNING|Advanced|Basic|running)'"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
pause
