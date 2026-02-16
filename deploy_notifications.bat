@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🎉 رفع إشعارات الميزات الجديدة
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📤 رفع الملف المحدث...
echo.

echo ⚠️  سيتم رفع: user_reports_add_new_system.py
echo    كلمة المرور: %BOT_PASSWORD%
echo.
pause

echo.
echo 📁 رفع الملف...
scp "%LOCAL_PATH%bot\handlers\user\user_reports_add_new_system.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/user/

if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع الملف
    pause
    exit /b 1
)

echo ✅ تم رفع الملف بنجاح
echo.

echo 🔐 تصحيح الصلاحيات...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown botuser:botuser %REMOTE_PATH%/bot/handlers/user/user_reports_add_new_system.py"
echo ✅ تم تصحيح الصلاحيات

echo.
echo 🧹 حذف Cache...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S find %REMOTE_PATH%/bot/handlers/user -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
echo ✅ تم حذف Cache

echo.
echo ========================================
echo 🔄 إعادة تشغيل البوت
echo ========================================
echo.

echo 🛑 إيقاف البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl stop medical-bot"
timeout /t 3 /nobreak >nul

echo.
echo 🚀 تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl start medical-bot"

echo.
echo ⏳ انتظار 10 ثوانٍ...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo 🧪 فحص حالة البوت
echo ========================================
echo.

echo 📊 1. فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo 📊 2. فحص آخر logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 20 --no-pager | tail -15"

echo.
echo ========================================
echo ✅ التحديث مكتمل!
echo ========================================
echo.
echo 🎉 الإشعارات الجديدة:
echo    ✅ إشعار عند بدء إضافة تقرير
echo    ✅ إشعار في قائمة المرضى (البحث)
echo    ✅ إشعار في قائمة الأقسام (قسم إشعاعي)
echo    ✅ إشعار في قائمة الإجراءات (جلسة إشعاعي)
echo.
echo 📱 اختبر البوت الآن!
echo.
pause
