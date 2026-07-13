@echo off
chcp 65001 >nul
echo ========================================
echo 🧪 فحص نهائي شامل للبوت
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser
set BOT_PASSWORD=bot123456

echo 📊 1. فحص أن البوت يعمل...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S systemctl is-active medical-bot"

echo.
echo 📊 2. فحص آخر 30 سطر من logs...
ssh %BOT_USER%@%SERVER_IP% "echo %BOT_PASSWORD% | sudo -S journalctl -u medical-bot -n 30 --no-pager | tail -20"

echo.
echo 📊 3. فحص وجود الملفات المهمة...
echo    - user_reports_add_new_system.py
ssh %BOT_USER%@%SERVER_IP% "ls -lh /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system.py 2>/dev/null && echo '   ✅ موجود' || echo '   ❌ مفقود'"

echo    - shared.py
ssh %BOT_USER%@%SERVER_IP% "ls -lh /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/shared.py 2>/dev/null && echo '   ✅ موجود' || echo '   ❌ مفقود'"

echo    - radiation_therapy.py
ssh %BOT_USER%@%SERVER_IP% "ls -lh /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/radiation_therapy.py 2>/dev/null && echo '   ✅ موجود' || echo '   ❌ مفقود'"

echo.
echo ========================================
echo 🎉 الفحص مكتمل!
echo ========================================
pause
