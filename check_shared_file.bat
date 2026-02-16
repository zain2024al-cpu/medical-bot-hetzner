@echo off
chcp 65001 >nul
echo ========================================
echo 🔍 فحص ملف shared.py على السيرفر
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser

echo 📊 حجم الملف وتاريخ التعديل:
ssh %BOT_USER%@%SERVER_IP% "ls -lh /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/shared.py"

echo.
echo 📊 فحص وجود radiation_therapy_type في الملف:
ssh %BOT_USER%@%SERVER_IP% "grep -c 'radiation_therapy_type' /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/shared.py"

echo.
echo 📊 عرض السطور التي تحتوي على radiation:
ssh %BOT_USER%@%SERVER_IP% "grep -n 'radiation_therapy_type=' /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/shared.py | head -5"

echo.
echo ========================================
pause
