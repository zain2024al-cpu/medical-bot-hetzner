@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 رفع الملفات يدوياً إلى السيرفر (محسّن)
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set TEMP_PATH=/tmp/deploy_temp
set LOCAL_PATH=%~dp0

echo 📤 رفع الملفات المحدثة...
echo.
echo ⚠️  سيتم طلب كلمة المرور: %BOT_PASSWORD%
echo.

echo 🔧 إنشاء مجلد مؤقت على السيرفر...
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "mkdir -p %TEMP_PATH%"

echo.
echo 📁 رفع مجلد bot/ إلى المجلد المؤقت...
scp -r -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📁 رفع مجلد config/ إلى المجلد المؤقت...
scp -r -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%config" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📁 رفع مجلد services/ إلى المجلد المؤقت...
scp -r -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%services" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📁 رفع مجلد data/ إلى المجلد المؤقت...
scp -r -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%data" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/

echo.
echo 📄 رفع الملفات الأساسية إلى المجلد المؤقت...
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%app.py" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%requirements.txt" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%medical-bot.service" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
if exist "%LOCAL_PATH%health.py" (
    scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%health.py" %BOT_USER%@%SERVER_IP%:%TEMP_PATH%/
)

echo.
echo 🔄 نسخ الملفات من المجلد المؤقت إلى مجلد البوت...
echo ⚠️ حماية قاعدة البيانات: حفظ نسخة احتياطية قبل النسخ...
REM ✅ حفظ نسخة احتياطية من قاعدة البيانات قبل النسخ
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp %REMOTE_PATH%/db/medical_reports.db %REMOTE_PATH%/db/medical_reports.db.backup_$(date +%%Y%%m%%d_%%H%%M%%S) 2>/dev/null || true"
echo 🔄 نسخ الملفات (بدون استبدال قاعدة البيانات)...
REM ✅ نسخ الملفات مع استثناء قاعدة البيانات
REM نسخ bot, config, services
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp -r %TEMP_PATH%/bot %REMOTE_PATH%/ && echo %BOT_PASSWORD% | sudo -S cp -r %TEMP_PATH%/config %REMOTE_PATH%/ && echo %BOT_PASSWORD% | sudo -S cp -r %TEMP_PATH%/services %REMOTE_PATH%/"
REM ✅ نسخ data folder بشكل انتقائي (لا نستبدل قاعدة البيانات الموجودة)
REM نسخ فقط ملفات JSON/TXT من data folder، وليس قاعدة البيانات
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "if [ -d %TEMP_PATH%/data ]; then echo %BOT_PASSWORD% | sudo -S mkdir -p %REMOTE_PATH%/data && echo %BOT_PASSWORD% | sudo -S cp %TEMP_PATH%/data/*.json %REMOTE_PATH%/data/ 2>/dev/null || true && echo %BOT_PASSWORD% | sudo -S cp %TEMP_PATH%/data/*.txt %REMOTE_PATH%/data/ 2>/dev/null || true; fi"
REM نسخ الملفات الأساسية
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S cp %TEMP_PATH%/app.py %REMOTE_PATH%/ 2>/dev/null || true && echo %BOT_PASSWORD% | sudo -S cp %TEMP_PATH%/requirements.txt %REMOTE_PATH%/ 2>/dev/null || true && echo %BOT_PASSWORD% | sudo -S cp %TEMP_PATH%/medical-bot.service %REMOTE_PATH%/ 2>/dev/null || true"
REM تعيين الصلاحيات
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown -R botuser:botuser %REMOTE_PATH%"
REM تنظيف المجلد المؤقت
ssh -o StrictHostKeyChecking=no %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S rm -rf %TEMP_PATH%"
echo ✅ تم حماية قاعدة البيانات من الاستبدال

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

