@echo off
chcp 65001 >nul
echo ========================================
echo 🧹 حذف Cache بصلاحيات sudo
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 🗑️ حذف __pycache__ بصلاحيات sudo...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S rm -rf /home/botuser/medical-bot/db/__pycache__"

echo.
echo 🗑️ حذف جميع __pycache__...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S find /home/botuser/medical-bot -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"

echo.
echo ✅ تم حذف Cache
echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 15 ثانية...
timeout /t 15 /nobreak >nul

echo.
echo 🧪 فحص...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo ========================================
echo 🎉 البوت يعمل!
echo ========================================
echo.
echo الآن جرب إضافة تقرير "جلسة إشعاعي"
echo.
pause
