@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 📥 تحميل قاعدة البيانات والبيانات من السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot
set LOCAL_PATH=%~dp0

echo 📥 تحميل ملف قاعدة البيانات...
echo.

REM تحميل قاعدة البيانات
echo 📦 تحميل db/medical_reports.db...
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/db/medical_reports.db "%LOCAL_PATH%db\medical_reports.db"

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم تحميل قاعدة البيانات بنجاح
) else (
    echo ❌ فشل تحميل قاعدة البيانات
)

echo.
echo 📥 تحميل ملفات البيانات...
echo.

REM تحميل ملفات البيانات
echo 📦 تحميل data/doctors_unified.json...
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/data/doctors_unified.json "%LOCAL_PATH%data\doctors_unified.json"

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم تحميل doctors_unified.json بنجاح
) else (
    echo ⚠️ فشل تحميل doctors_unified.json (قد لا يكون موجوداً)
)

echo.
echo ========================================
echo ✅ تم تحميل الملفات من السيرفر
echo ========================================
echo.
echo 📋 الملفات المحملة:
echo    - db/medical_reports.db (قاعدة البيانات)
echo    - data/doctors_unified.json (بيانات المستشفيات والأطباء)
echo.
echo ⚠️ ملاحظة: البيانات الجديدة (المستشفيات والمرضى) موجودة في قاعدة البيانات
echo.

pause




