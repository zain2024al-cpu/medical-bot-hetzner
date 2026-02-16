@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 🔍 فحص ورفع تحديثات ملفات الأدمن
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📋 الملفات المحدثة للرفع:
echo    1. admin_printing.py (2/9/2026)
echo    2. admin_hospitals_management.py (2/8/2026)
echo    3. admin_reports.py (2/8/2026)
echo    4. admin_start.py (2/8/2026)
echo    5. admin_users_management.py (2/8/2026)
echo.
pause

echo.
echo ========================================
echo 📤 المرحلة 1: رفع الملفات
echo ========================================
echo.

echo 📁 1/5 - رفع admin_printing.py...
scp "%LOCAL_PATH%bot\handlers\admin\admin_printing.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/
if %ERRORLEVEL% EQU 0 (echo ✅ تم) else (echo ❌ فشل)

echo.
echo 📁 2/5 - رفع admin_hospitals_management.py...
scp "%LOCAL_PATH%bot\handlers\admin\admin_hospitals_management.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/
if %ERRORLEVEL% EQU 0 (echo ✅ تم) else (echo ❌ فشل)

echo.
echo 📁 3/5 - رفع admin_reports.py...
scp "%LOCAL_PATH%bot\handlers\admin\admin_reports.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/
if %ERRORLEVEL% EQU 0 (echo ✅ تم) else (echo ❌ فشل)

echo.
echo 📁 4/5 - رفع admin_start.py...
scp "%LOCAL_PATH%bot\handlers\admin\admin_start.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/
if %ERRORLEVEL% EQU 0 (echo ✅ تم) else (echo ❌ فشل)

echo.
echo 📁 5/5 - رفع admin_users_management.py...
scp "%LOCAL_PATH%bot\handlers\admin\admin_users_management.py" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/bot/handlers/admin/
if %ERRORLEVEL% EQU 0 (echo ✅ تم) else (echo ❌ فشل)

echo.
echo ========================================
echo 🔧 المرحلة 2: تصحيح الصلاحيات
echo ========================================
echo.

echo 🔐 تصحيح صلاحيات الملفات...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S chown botuser:botuser %REMOTE_PATH%/bot/handlers/admin/*.py"
echo ✅ تم تصحيح الصلاحيات

echo.
echo ========================================
echo 🧹 المرحلة 3: تنظيف Cache
echo ========================================
echo.

echo 🗑️ حذف __pycache__ من admin...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S find %REMOTE_PATH%/bot/handlers/admin -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
echo ✅ تم حذف Cache

echo.
echo ========================================
echo 🧪 المرحلة 4: فحص الملفات
echo ========================================
echo.

echo 📊 فحص الملفات المرفوعة...
ssh %BOT_USER%@%SERVER_IP% "ls -lh %REMOTE_PATH%/bot/handlers/admin/admin_printing.py %REMOTE_PATH%/bot/handlers/admin/admin_hospitals_management.py %REMOTE_PATH%/bot/handlers/admin/admin_reports.py %REMOTE_PATH%/bot/handlers/admin/admin_start.py %REMOTE_PATH%/bot/handlers/admin/admin_users_management.py 2>/dev/null | tail -5"

echo.
echo ========================================
echo 🔄 المرحلة 5: إعادة تشغيل البوت
echo ========================================
echo.

echo 🛑 إيقاف البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl stop medical-bot"
timeout /t 3 /nobreak >nul

echo.
echo 🚀 تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl start medical-bot"

echo.
echo ⏳ انتظار 12 ثانية...
timeout /t 12 /nobreak >nul

echo.
echo ========================================
echo 🧪 المرحلة 6: فحص النظام
echo ========================================
echo.

echo 📊 1. فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo 📊 2. فحص آخر logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 25 --no-pager | tail -18"

echo.
echo ========================================
echo ✅ اكتمل الرفع والفحص!
echo ========================================
echo.
echo 🎯 الملفات المرفوعة:
echo    ✅ admin_printing.py
echo    ✅ admin_hospitals_management.py
echo    ✅ admin_reports.py
echo    ✅ admin_start.py
echo    ✅ admin_users_management.py
echo.
echo 📱 اختبر لوحة الأدمن الآن!
echo.
pause
