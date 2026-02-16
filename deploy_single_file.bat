@echo off
chcp 65001 >nul
echo.
echo ========================================
echo 📤 رفع ملف واحد إلى السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456
set REMOTE_PATH=/home/botuser/medical-bot

if "%~1"=="" (
    echo ❌ يرجى تحديد مسار الملف
    echo.
    echo الاستخدام:
    echo    deploy_single_file.bat "bot\broadcast_control.py"
    echo.
    pause
    exit /b 1
)

set FILE_PATH=%~1
set LOCAL_PATH=%~dp0

echo 📄 رفع الملف: %FILE_PATH%
echo.

if not exist "%LOCAL_PATH%%FILE_PATH%" (
    echo ❌ الملف غير موجود: %LOCAL_PATH%%FILE_PATH%
    pause
    exit /b 1
)

echo 🔄 محاولة الرفع...
scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%%FILE_PATH%" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/%FILE_PATH%

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم رفع الملف بنجاح!
) else (
    echo ❌ فشل رفع الملف
    echo.
    echo 🔄 محاولة مرة أخرى...
    timeout /t 2 /nobreak >nul
    scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "%LOCAL_PATH%%FILE_PATH%" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/%FILE_PATH%
    
    if %ERRORLEVEL% EQU 0 (
        echo ✅ تم رفع الملف بنجاح في المحاولة الثانية!
    ) else (
        echo ❌ فشل رفع الملف بعد محاولتين
        echo.
        echo 💡 حاول رفعه يدوياً:
        echo    scp "%LOCAL_PATH%%FILE_PATH%" %BOT_USER%@%SERVER_IP%:%REMOTE_PATH%/%FILE_PATH%
    )
)

echo.
pause




