@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 رفع جميع الملفات المحدثة - نشر كامل
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo ⚠️  سيتم رفع جميع الملفات المحدثة
echo    كلمة المرور: %BOT_PASSWORD%
echo.
pause

echo.
echo ========================================
echo 📤 المرحلة 1: رفع المجلدات الرئيسية
echo ========================================
echo.

echo 📁 1/6 - رفع مجلد bot/ كامل...
scp -r "%LOCAL_PATH%bot" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
echo ✅ تم رفع bot/

echo.
echo 📁 2/6 - رفع مجلد db/...
scp -r "%LOCAL_PATH%db\models.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/db/
scp -r "%LOCAL_PATH%db\session.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/db/
echo ✅ تم رفع db/

echo.
echo 📁 3/6 - رفع مجلد services/...
scp -r "%LOCAL_PATH%services" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
echo ✅ تم رفع services/

echo.
echo 📁 4/6 - رفع مجلد config/...
scp -r "%LOCAL_PATH%config" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
echo ✅ تم رفع config/

echo.
echo 📁 5/6 - رفع مجلد data/...
scp -r "%LOCAL_PATH%data" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
echo ✅ تم رفع data/

echo.
echo 📁 6/6 - رفع الملفات الأساسية...
scp "%LOCAL_PATH%app.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
scp "%LOCAL_PATH%requirements.txt" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
echo ✅ تم رفع الملفات الأساسية

echo.
echo ========================================
echo 🔧 المرحلة 2: تصحيح الصلاحيات
echo ========================================
echo.

echo 🔐 تصحيح ملكية الملفات...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown -R botuser:botuser %REMOTE_PATH%/bot"
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown -R botuser:botuser %REMOTE_PATH%/services"
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown -R botuser:botuser %REMOTE_PATH%/config"
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown -R botuser:botuser %REMOTE_PATH%/data"
echo ✅ تم تصحيح الصلاحيات

echo.
echo ========================================
echo 🧹 المرحلة 3: تنظيف Cache
echo ========================================
echo.

echo 🗑️ حذف جميع ملفات __pycache__...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S find %REMOTE_PATH% -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
echo ✅ تم حذف Cache

echo.
echo ========================================
echo 🔄 المرحلة 4: إعادة تشغيل البوت
echo ========================================
echo.

echo 🛑 إيقاف البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl stop medical-bot"
timeout /t 3 /nobreak >nul

echo.
echo 🚀 تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl start medical-bot"

echo.
echo ⏳ انتظار 15 ثانية...
timeout /t 15 /nobreak >nul

echo.
echo ========================================
echo 🧪 المرحلة 5: فحص النظام
echo ========================================
echo.

echo 📊 1. فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo 📊 2. فحص آخر logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 25 --no-pager | tail -15"

echo.
echo 📊 3. فحص حالة مفصلة...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 20"

echo.
echo ========================================
echo 🎉 النشر الكامل مكتمل!
echo ========================================
echo.
echo ✅ جميع الملفات تم رفعها بنجاح
echo ✅ البوت تم إعادة تشغيله
echo ✅ Cache تم تنظيفه
echo.
echo 🎯 الميزات المحدثة:
echo    - ✅ دالة البحث عن مريض
echo    - ✅ جلسة إشعاعي
echo    - ✅ مراجعة / عودة دورية
echo    - ✅ جميع المسارات الأخرى
echo.
echo 📱 اختبر البوت الآن: @med_reports_bot
echo.
pause
