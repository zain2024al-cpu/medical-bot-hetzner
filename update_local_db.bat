@echo off
chcp 65001 >nul
cls
echo.
echo ═══════════════════════════════════════════════════════════════════════
echo  📥 تحديث قاعدة البيانات المحلية من السيرفر
echo ═══════════════════════════════════════════════════════════════════════
echo.
echo  هذا السكريبت سيقوم بـ:
echo  1. تنزيل قاعدة البيانات من السيرفر
echo  2. إنشاء نسخة احتياطية مؤرخة
echo  3. تحديث القاعدة المحلية
echo.
pause

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo  📥 المرحلة 1: تنزيل من السيرفر
echo ═══════════════════════════════════════════════════════════════════════
echo.

scp botuser@5.223.58.71:/home/botuser/medical-bot/db/medical_reports.db db/medical_reports_online.db

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم تنزيل قاعدة البيانات بنجاح
) else (
    echo ❌ فشل التنزيل
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo  💾 المرحلة 2: إنشاء نسخة احتياطية
echo ═══════════════════════════════════════════════════════════════════════
echo.

if not exist "db\backups" mkdir "db\backups"

for /f "tokens=1-4 delims=/ " %%a in ('date /t') do set mydate=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set mytime=%%a-%%b
set datetime=%mydate%_%mytime::=-%

copy "db\medical_reports_online.db" "db\backups\medical_reports_%datetime%.db"

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم إنشاء نسخة احتياطية: medical_reports_%datetime%.db
) else (
    echo ❌ فشل إنشاء النسخة الاحتياطية
)

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo  🔄 المرحلة 3: تحديث القاعدة المحلية
echo ═══════════════════════════════════════════════════════════════════════
echo.

copy /Y "db\medical_reports_online.db" "db\medical_reports.db"

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم تحديث قاعدة البيانات المحلية
) else (
    echo ❌ فشل التحديث
    pause
    exit /b 1
)

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo  🧪 المرحلة 4: فحص القاعدة المحدثة
echo ═══════════════════════════════════════════════════════════════════════
echo.

set PYTHONIOENCODING=utf-8
python check_local_db.py

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo  ✅ اكتمل التحديث بنجاح!
echo ═══════════════════════════════════════════════════════════════════════
echo.
pause
