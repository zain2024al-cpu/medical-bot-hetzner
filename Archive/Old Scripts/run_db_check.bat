@echo off
chcp 65001 >nul
echo ========================================
echo 🔍 فحص أعمدة قاعدة البيانات
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser

echo 📁 رفع السكريبت...
scp "check_db_columns.py" %BOT_USER%@%SERVER_IP%:/tmp/

echo.
echo 🚀 تشغيل الفحص...
ssh %BOT_USER%@%SERVER_IP% "python3 /tmp/check_db_columns.py"

echo.
echo ========================================
pause
