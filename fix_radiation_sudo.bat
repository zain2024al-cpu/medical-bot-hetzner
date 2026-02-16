@echo off
chcp 65001 >nul
echo ========================================
echo 🚀 رفع radiation_therapy.py بطريقة بديلة
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📁 رفع إلى مجلد مؤقت...
scp "bot\handlers\user\user_reports_add_new_system\flows\radiation_therapy.py" %BOT_USER%@%SERVER_IP%:/tmp/

echo.
echo 📁 نقل الملف بصلاحيات sudo...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp /tmp/radiation_therapy.py /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/"

echo.
echo 📁 تغيير المالك...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown botuser:botuser /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/radiation_therapy.py"

echo.
echo 📁 تغيير الصلاحيات...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chmod 644 /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/radiation_therapy.py"

echo.
echo ✅ تم رفع الملف بنجاح
echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 10 ثواني...
timeout /t 10 /nobreak >nul

echo.
echo 🧪 فحص الأخطاء...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 30 --no-pager | grep radiation"

echo.
echo 📊 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
pause
