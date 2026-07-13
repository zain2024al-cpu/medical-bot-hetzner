@echo off
chcp 65001 >nul
echo ========================================
echo 🔍 فحص ملفات flows على السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📂 الملفات في مجلد flows:
ssh %BOT_USER%@%SERVER_IP% "ls -lh /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/"

echo.
echo 📊 فحص آخر logs:
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 25 --no-pager | tail -15"

echo.
echo ========================================
pause
