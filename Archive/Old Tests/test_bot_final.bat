@echo off
chcp 65001 >nul
echo ========================================
echo 🧪 اختبار البوت النهائي
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📊 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo 📊 آخر 50 سطر من logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 50 --no-pager | tail -30"

echo.
echo ========================================
echo ✅ البوت جاهز للاختبار!
echo ========================================
echo.
echo 🎯 الآن:
echo    1. افتح Telegram
echo    2. ابحث عن @med_reports_bot
echo    3. اضغط على "إضافة تقرير جديد"
echo    4. تأكد من أنه يعمل بشكل صحيح
echo.
pause
