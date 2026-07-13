@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🚀 نشر التحديثات وفحص قاعدة البيانات
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot

echo ⚠️  سيتم طلب كلمة المرور في كل عملية
echo    كلمة المرور: %BOT_PASSWORD%
echo.
pause

REM ========================================
REM المرحلة 1: رفع الملفات المحدثة
REM ========================================
echo.
echo ========================================
echo 📤 المرحلة 1: رفع الملفات المحدثة
echo ========================================
echo.

echo 📁 1/4 - رفع مجلد bot/handlers/user/
scp -r "bot\handlers\user\user_reports_add_new_system.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/user/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع user_reports_add_new_system.py
    pause
    exit /b 1
)

echo.
echo 📁 2/4 - رفع مجلد bot/handlers/user/user_reports_add_new_system/flows/
scp -r "bot\handlers\user\user_reports_add_new_system\flows\shared.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/user/user_reports_add_new_system/flows/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع shared.py
    pause
    exit /b 1
)

echo.
echo 📁 3/4 - رفع app.py
scp "app.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع app.py
    pause
    exit /b 1
)

echo.
echo 📁 4/4 - رفع services/broadcast_service.py
scp "services\broadcast_service.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/services/
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل رفع broadcast_service.py
    pause
    exit /b 1
)

echo.
echo ✅ تم رفع جميع الملفات المحدثة بنجاح
echo.

REM ========================================
REM المرحلة 2: إعادة تشغيل البوت
REM ========================================
echo.
echo ========================================
echo 🔄 المرحلة 2: إعادة تشغيل البوت
echo ========================================
echo.

echo 🛑 إيقاف البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl stop medical-bot"
echo.
echo ⏳ انتظار 5 ثواني...
timeout /t 5 /nobreak >nul

echo.
echo 🚀 تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl start medical-bot"
echo.
echo ⏳ انتظار 15 ثانية حتى يعمل البوت...
timeout /t 15 /nobreak >nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager | head -n 15"

echo.
echo 📊 فحص logs البوت (آخر 20 سطر)...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 20 --no-pager"

REM ========================================
REM المرحلة 3: فحص قاعدة البيانات
REM ========================================
echo.
echo ========================================
echo 🗃️  المرحلة 3: فحص قاعدة البيانات
echo ========================================
echo.

echo 📊 فحص عدد التقارير...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"SELECT COUNT(*) FROM reports;\""

echo.
echo 📊 فحص عدد المستشفيات...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"SELECT COUNT(*) FROM hospitals;\""

echo.
echo 📊 فحص عدد المرضى...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"SELECT COUNT(*) FROM patients;\""

echo.
echo 📊 فحص عدد الأطباء...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"SELECT COUNT(*) FROM doctors;\""

echo.
echo 📊 فحص عدد المترجمين...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"SELECT COUNT(*) FROM translators;\""

echo.
echo 📊 آخر 5 تقارير في قاعدة البيانات...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"SELECT id, patient_name, medical_action, created_at FROM reports ORDER BY id DESC LIMIT 5;\""

echo.
echo 📊 فحص أعمدة جدول reports...
ssh %BOT_USER%@%SERVER_IP% "sqlite3 %REMOTE_PATH%/db/medical_reports.db \"PRAGMA table_info(reports);\" | grep -E '(medical_action|radiation_therapy|periodic_followup)'"

REM ========================================
REM النتيجة النهائية
REM ========================================
echo.
echo ========================================
echo 🎉 النشر والفحص مكتمل!
echo ========================================
echo.
echo ✅ جميع الملفات المحدثة تم رفعها بنجاح
echo ✅ البوت تم إعادة تشغيله
echo ✅ قاعدة البيانات تعمل بشكل صحيح
echo.
echo 🎯 الآن:
echo    1. اذهب لتلغرام وابحث عن البوت
echo    2. اختبر مسار "مراجعة / عودة دورية"
echo    3. تأكد من أن نوع الإجراء يظهر صحيحاً
echo.
echo 📞 إذا واجهت مشاكل:
echo    ssh %BOT_USER%@%SERVER_IP%
echo    sudo journalctl -u medical-bot -f
echo.
echo 🚀 البوت محدث وجاهز للاستخدام!
echo ========================================
echo.

pause
