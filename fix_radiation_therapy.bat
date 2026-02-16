@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 رفع ملف radiation_therapy.py
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot

echo 📁 إنشاء مجلد flows إذا لم يكن موجوداً...
ssh %BOT_USER%@%SERVER_IP% "mkdir -p %REMOTE_PATH%/bot/handlers/user/user_reports_add_new_system/flows"

echo.
echo 📁 رفع radiation_therapy.py...
scp "bot\handlers\user\user_reports_add_new_system\flows\radiation_therapy.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/user/user_reports_add_new_system/flows/

echo.
echo 📁 رفع __init__.py للمجلد flows...
scp "bot\handlers\user\user_reports_add_new_system\flows\__init__.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/user/user_reports_add_new_system/flows/

echo.
echo 📁 التأكد من الصلاحيات...
ssh %BOT_USER%@%SERVER_IP% "chmod -R 755 %REMOTE_PATH%/bot/handlers/user/user_reports_add_new_system/flows/"

echo.
echo ✅ تم رفع الملفات
echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 10 ثواني...
timeout /t 10 /nobreak >nul

echo.
echo 🧪 فحص الأخطاء...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 20 --no-pager | grep -E '(radiation|ERROR|Advanced)'"

echo.
echo 📊 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 15"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
pause
