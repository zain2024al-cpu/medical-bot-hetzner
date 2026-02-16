@echo off
chcp 65001 >nul
echo ========================================
echo 🧹 حذف Python cache وإعادة التشغيل
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 🗑️ حذف __pycache__ من مجلد db...
ssh %BOT_USER%@%SERVER_IP% "rm -rf /home/botuser/medical-bot/db/__pycache__"

echo.
echo 🗑️ حذف جميع ملفات .pyc...
ssh %BOT_USER%@%SERVER_IP% "find /home/botuser/medical-bot/db -name '*.pyc' -delete"

echo.
echo 🗑️ حذف __pycache__ من جميع المجلدات...
ssh %BOT_USER%@%SERVER_IP% "find /home/botuser/medical-bot -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"

echo.
echo ✅ تم حذف Cache
echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 15 ثانية...
timeout /t 15 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo 📊 آخر logs:
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 15 --no-pager | tail -8"

echo.
echo ========================================
echo 🎉 مكتمل!
echo ========================================
echo.
echo الآن جرب إضافة تقرير جلسة إشعاعي!
echo إذا استمر الخطأ، أرسل لي نص الخطأ الكامل.
echo.
pause
