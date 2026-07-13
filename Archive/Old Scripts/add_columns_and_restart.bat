@echo off
chcp 65001 >nul
echo ========================================
echo 🔧 إضافة أعمدة radiation_therapy
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📁 رفع السكريبت...
scp "add_radiation_columns_server.py" %BOT_USER%@%SERVER_IP%:/tmp/

echo.
echo 🚀 تشغيل السكريبت...
ssh %BOT_USER%@%SERVER_IP% "python3 /tmp/add_radiation_columns_server.py"

echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 10 ثواني...
timeout /t 10 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 15"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
echo.
echo الآن يمكنك تجربة إضافة تقرير جلسة إشعاعي!
echo.
pause
