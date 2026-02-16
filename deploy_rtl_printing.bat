@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 📄 نشر تحديث RTL للطباعة
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📤 رفع ملف admin_printing.py المحدث...
echo.

scp -o StrictHostKeyChecking=no "%LOCAL_PATH%bot\handlers\admin\admin_printing.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع الملف
    pause
    exit /b 1
)

echo.
echo ✅ تم رفع الملف بنجاح
echo.

echo 🔄 إعادة تشغيل البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl restart medical-bot"

echo.
echo ⏳ انتظار تشغيل البوت (10 ثواني)...
timeout /t 10 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "systemctl status medical-bot --no-pager | head -n 10"

echo.
echo ========================================
echo 🎉 النشر مكتمل!
echo ========================================
echo.
echo ✅ تم تحسين RTL للطباعة
echo.
echo 📝 التحسينات:
echo    • جميع النصوص من اليمين لليسار
echo    • الجداول محاذاة يمين
echo    • البطاقات والإحصائيات محاذاة يمين
echo    • الحدود على اليمين بدلاً من اليسار
echo    • تحسين عرض PDF
echo.
echo 🎯 الآن جرب:
echo    1. افتح البوت في تلغرام
echo    2. اطبع أي تقرير
echo    3. يجب أن يكون التنسيق من اليمين لليسار
echo.
echo 🚀 البوت جاهز!
echo ========================================
echo.

pause
