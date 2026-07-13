@echo off
chcp 65001 > nul
echo ===============================================
echo 📊 نشر نظام تقييم المترجمين المحدث
echo ===============================================
echo.

echo [1/2] رفع ملف admin_evaluation.py...
scp -o StrictHostKeyChecking=no bot/handlers/admin/admin_evaluation.py botuser@5.223.58.71:/home/botuser/medical-bot/bot/handlers/admin/
if %ERRORLEVEL% neq 0 (
    echo ❌ فشل رفع الملف
    pause
    exit /b 1
)
echo ✅ تم رفع الملف بنجاح
echo.

echo [2/2] إعادة تشغيل البوت...
ssh -o StrictHostKeyChecking=no botuser@5.223.58.71 "cd /home/botuser/medical-bot && supervisorctl restart medical_bot"
if %ERRORLEVEL% neq 0 (
    echo ⚠️ تحذير: قد تحتاج لإعادة تشغيل البوت يدوياً
) else (
    echo ✅ تم إعادة تشغيل البوت بنجاح
)
echo.

echo ===============================================
echo ✅ اكتمل النشر بنجاح!
echo ===============================================
pause
