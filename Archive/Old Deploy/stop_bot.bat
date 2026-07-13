@echo off
echo ========================================
echo إيقاف جميع نسخ البوت
echo ========================================
echo.

echo البحث عن عمليات Python...
tasklist | findstr python

echo.
echo إيقاف جميع عمليات Python...
taskkill /F /IM python.exe 2>nul

if %errorlevel% == 0 (
    echo ✅ تم إيقاف جميع عمليات Python
) else (
    echo ℹ️ لا توجد عمليات Python قيد التشغيل
)

echo.
echo ========================================
pause
