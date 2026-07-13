@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 📥 جلب قاعدة البيانات من السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set REMOTE_DB_PATH=/home/botuser/medical-bot/db/medical_reports.db
set LOCAL_DB_PATH=db\medical_reports.db
set BACKUP_DIR=db\backups

echo.
echo ⚠️  سيتم طلب كلمة المرور
echo    كلمة المرور: bot123456
echo.
pause

echo.
echo 📥 جلب قاعدة البيانات من السيرفر...
echo.

REM إنشاء مجلد db إذا لم يكن موجوداً
if not exist "db" mkdir db

REM إنشاء مجلد backups إذا لم يكن موجوداً
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM إنشاء نسخة احتياطية من قاعدة البيانات الحالية (إن وجدت)
if exist "%LOCAL_DB_PATH%" (
    echo 💾 إنشاء نسخة احتياطية من قاعدة البيانات الحالية...
    set BACKUP_NAME=backup_before_download_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%
    set BACKUP_NAME=%BACKUP_NAME: =0%
    copy "%LOCAL_DB_PATH%" "%BACKUP_DIR%\%BACKUP_NAME%.db" >nul
    echo ✅ تم حفظ النسخة الاحتياطية: %BACKUP_DIR%\%BACKUP_NAME%.db
    echo.
)

REM جلب قاعدة البيانات من السيرفر
echo 📥 جلب قاعدة البيانات من السيرفر...
scp %BOT_USER%@%SERVER_IP%:%REMOTE_DB_PATH% "%LOCAL_DB_PATH%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ تم جلب قاعدة البيانات بنجاح!
    echo.
    echo 📊 معلومات قاعدة البيانات:
    dir "%LOCAL_DB_PATH%" | findstr /C:"medical_reports.db"
    echo.
    echo 🔍 التحقق من محتويات قاعدة البيانات...
    echo.
    python check_database_after_download.py
    echo.
    echo 🔄 الآن قاعدة البيانات المحلية محدثة مع السيرفر
) else (
    echo.
    echo ❌ فشل جلب قاعدة البيانات من السيرفر
    echo    تحقق من الاتصال بالسيرفر والمسارات
)

echo.
echo ========================================
pause

