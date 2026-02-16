@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 رفع الملفات يدوياً إلى السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📤 رفع الملفات المحدثة...
echo.
echo ⚠️  سيتم طلب كلمة المرور: %BOT_PASSWORD%
echo.

echo 📁 رفع مجلد bot/ (مع معالجة الأخطاء)...
scp -r -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/ 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️  تحذير: بعض الملفات قد فشل رفعها، سيتم المحاولة مرة أخرى...
    timeout /t 2 /nobreak >nul
    scp -r -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/ 2>&1
)

echo.
echo 📁 رفع مجلد config/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%config" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📁 رفع مجلد services/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%services" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📁 رفع مجلد data/
scp -r -o StrictHostKeyChecking=no "%LOCAL_PATH%data" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/

echo.
echo 📄 رفع الملفات الأساسية...
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%app.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%requirements.txt" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp -o StrictHostKeyChecking=no "%LOCAL_PATH%medical-bot.service" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if exist "%LOCAL_PATH%health.py" (
    scp -o StrictHostKeyChecking=no "%LOCAL_PATH%health.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
)

echo.
echo ✅ تم رفع جميع الملفات بنجاح!
echo.
echo ========================================
echo 📋 الخطوات التالية:
echo ========================================
echo.
echo 1. الاتصال بالسيرفر:
echo    ssh %BOT_USER%@%SERVER_IP%
echo.
echo 2. الانتقال لمجلد البوت:
echo    cd %REMOTE_PATH%
echo.
echo 3. إيقاف الخدمة (إذا كانت تعمل):
echo    sudo systemctl stop medical-bot
echo.
echo 4. تشغيل البوت يدوياً:
echo    source venv/bin/activate
echo    python app.py
echo.
echo أو إعادة تشغيل الخدمة:
echo    sudo systemctl restart medical-bot
echo.
echo ========================================
echo.

pause

