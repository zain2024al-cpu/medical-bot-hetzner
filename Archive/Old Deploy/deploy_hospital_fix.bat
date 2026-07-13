@echo off
chcp 65001 >nul
echo.
echo ========================================
echo نشر إصلاح مشكلة حفظ المستشفيات
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot

echo 📤 رفع الملف المصلح...
echo.

echo رفع bot/handlers/admin/admin_hospitals_management.py...
scp -o StrictHostKeyChecking=no "bot\handlers\admin\admin_hospitals_management.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/

if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع الملف
    pause
    exit /b 1
)

echo.
echo ✅ تم رفع الملف بنجاح!
echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار 5 ثواني...
timeout /t 5 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 15"

echo.
echo ========================================
echo ✅ تم النشر بنجاح!
echo ========================================
echo.
echo 📋 ملاحظة: جرب إضافة مستشفى جديد من الأدمن
echo    وتحقق من أنه لا يختفي بعد إعادة التشغيل
echo.
pause
