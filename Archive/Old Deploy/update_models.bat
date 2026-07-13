@echo off
chcp 65001 >nul
echo ========================================
echo 🔧 رفع ملف models.py المحدث
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📁 رفع إلى مجلد مؤقت...
scp "db\models.py" %BOT_USER%@%SERVER_IP%:/tmp/

echo.
echo 📁 نقل الملف...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp /tmp/models.py /home/botuser/medical-bot/db/"

echo.
echo 📁 تغيير المالك...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown botuser:botuser /home/botuser/medical-bot/db/models.py"

echo.
echo 📁 فحص المحتوى...
ssh %BOT_USER%@%SERVER_IP% "grep -c 'radiation_therapy' /home/botuser/medical-bot/db/models.py"

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
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 15"

echo.
echo 📊 فحص آخر logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 20 --no-pager | tail -10"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
echo.
echo جرب الآن إضافة تقرير جلسة إشعاعي!
echo.
pause
