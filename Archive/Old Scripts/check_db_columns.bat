@echo off
chcp 65001 >nul
echo ========================================
echo 🔍 فحص أعمدة قاعدة البيانات على السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📊 فحص أعمدة جدول reports:
ssh %BOT_USER%@%SERVER_IP% "sqlite3 /home/botuser/medical-bot/db/medical_reports.db \"PRAGMA table_info(reports);\" | grep radiation"

echo.
echo ========================================
pause
