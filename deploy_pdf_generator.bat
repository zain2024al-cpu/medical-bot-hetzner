@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 📊 نشر تحديث PDF Generator
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📤 رفع ملف pdf_generator_enhanced.py المحدث...
echo.

scp -o StrictHostKeyChecking=no "%LOCAL_PATH%services\pdf_generator_enhanced.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/services/
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
echo ✅ تم إصلاح مشكلة dictionary في PDF Generator
echo.
echo 📝 التحسينات:
echo    • إضافة 'count' لجميع الجداول
echo    • إضافة 'percentage' للأطباء
echo    • توحيد أسماء الحقول مع template
echo.
echo 🎯 الآن جرب:
echo    1. نظام تحليل البيانات
echo    2. صدّر كـ PDF
echo    3. يجب أن يعمل بدون أخطاء
echo.
echo 🚀 البوت جاهز!
echo ========================================
echo.

pause
