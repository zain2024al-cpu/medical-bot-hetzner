@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 رفع ملف states.py المفقود
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📁 رفع states.py...
scp "bot\handlers\user\user_reports_add_new_system\states.py" %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/

echo.
echo ✅ تم رفع الملف
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
echo 📊 فحص logs (آخر 30 سطر)...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 30 --no-pager"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
pause
