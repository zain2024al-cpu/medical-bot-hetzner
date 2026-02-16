@echo off
chcp 65001 >nul
echo ========================================
echo 🔍 فحص logs البوت مع تصفية
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 🔍 جاري جلب آخر 200 سطر من logs وفحص الأخطاء...
echo.

ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 200 --no-pager | grep -E '(ERROR|WARNING|start_report|إضافة تقرير|approved|not approved|user_id)'"

echo.
echo ========================================
pause
