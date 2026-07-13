@echo off
chcp 65001 >nul
echo ========================================
echo 📊 فحص logs البوت على السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 🔍 جاري جلب آخر 100 سطر من logs...
echo.

ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 100 --no-pager"

echo.
echo ========================================
echo 🔍 فحص حالة البوت...
echo ========================================
echo.

ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl status medical-bot --no-pager"

echo.
echo ========================================
pause
