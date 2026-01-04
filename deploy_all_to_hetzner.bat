@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 نشر جميع الملفات المحدثة للبوت على Hetzner
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📤 رفع جميع الملفات المحدثة...
echo.
echo ⚠️  ملاحظة: سيتم طلب كلمة المرور في كل عملية نقل
echo    كلمة المرور: %BOT_PASSWORD%
echo.

echo 📁 رفع مجلد bot/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع مجلد bot
    pause
    exit /b 1
)

echo.
echo 📁 رفع مجلد config/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%config" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع مجلد config
    pause
    exit /b 1
)

echo.
echo 📁 رفع مجلد services/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%services" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع مجلد services
    pause
    exit /b 1
)

echo.
echo 📁 رفع مجلد data/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%data" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع مجلد data
    pause
    exit /b 1
)

echo.
echo 📄 رفع الملفات الأساسية...
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%app.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%requirements.txt" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%medical-bot.service" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if exist "%LOCAL_PATH%health.py" (
    scp -o StrictHostKeyChecking=no "%LOCAL_PATH%health.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
)

echo.
echo ✅ تم رفع جميع الملفات
echo.

echo 🔄 إعادة تشغيل البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار تشغيل البوت (10 ثواني)...
timeout /t 10 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 20"

echo.
echo 📊 فحص logs البوت (آخر 15 سطر)...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 15 --no-pager"

echo.
echo ========================================
echo 🎉 النشر مكتمل!
echo ========================================
echo.
echo ✅ جميع الملفات المحدثة تم رفعها بنجاح
echo ✅ البوت تم إعادة تشغيله
echo.
echo 🎯 الآن:
echo    1. اذهب لتلغرام وابحث عن البوت
echo    2. اختبر جميع الوظائف الجديدة
echo    3. تأكد من عمل جميع الأزرار
echo.
echo 📞 إذا واجهت مشاكل:
echo    ssh %BOT_USER%@%SERVER_IP%
echo    sudo journalctl -u medical-bot -n 50
echo.
echo 🚀 البوت محدث وجاهز للاستخدام!
echo ========================================
echo.

pause






