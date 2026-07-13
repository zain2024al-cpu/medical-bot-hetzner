@echo off
chcp 65001 >nul
echo ============================================
echo رفع جميع التحديثات إلى السيرفر
echo ============================================
echo.

REM نسخ الملفات من real_bot_final إلى مجلد Git أولاً
set "GIT_DIR=C:\Users\nalgu\OneDrive\Desktop\omar\medical_reports_bot_backup_20251207_034941\medical_reports_bot_backup_20251207_034941"
set "SOURCE_DIR=C:\Users\nalgu\OneDrive\Desktop\omar\real_bot_final"

echo 📋 نسخ الملفات المحدثة...
echo.

copy /Y "%SOURCE_DIR%\db\models.py" "%GIT_DIR%\db\models.py" >nul
copy /Y "%SOURCE_DIR%\config\settings.py" "%GIT_DIR%\config\settings.py" >nul
copy /Y "%SOURCE_DIR%\services\broadcast_service.py" "%GIT_DIR%\services\broadcast_service.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers\user\user_reports_add_new_system\flows\shared.py" "%GIT_DIR%\bot\handlers\user\user_reports_add_new_system\flows\shared.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers\user\user_reports_delete.py" "%GIT_DIR%\bot\handlers\user\user_reports_delete.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers\user\user_reports_edit.py" "%GIT_DIR%\bot\handlers\user\user_reports_edit.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers\user\user_reports_add_new_system.py" "%GIT_DIR%\bot\handlers\user\user_reports_add_new_system.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers\user\user_reports_add_new_system\patient_handlers.py" "%GIT_DIR%\bot\handlers\user\user_reports_add_new_system\patient_handlers.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers\user\user_patient_search_inline.py" "%GIT_DIR%\bot\handlers\user\user_patient_search_inline.py" >nul
copy /Y "%SOURCE_DIR%\bot\handlers_registry.py" "%GIT_DIR%\bot\handlers_registry.py" >nul
copy /Y "%SOURCE_DIR%\bot\keyboards.py" "%GIT_DIR%\bot\keyboards.py" >nul
copy /Y "%SOURCE_DIR%\add_missing_columns.py" "%GIT_DIR%\add_missing_columns.py" >nul

echo ✅ تم نسخ جميع الملفات
echo.

echo 📤 رفع الملفات على السيرفر...
echo.

REM رفع الملفات إلى السيرفر
scp "%SOURCE_DIR%\db\models.py" botuser@5.223.58.71:/home/botuser/temp_models.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/db && echo bot123456 | sudo -S cp /home/botuser/temp_models.py /home/botuser/medical-bot/db/models.py && rm /home/botuser/temp_models.py"

scp "%SOURCE_DIR%\config\settings.py" botuser@5.223.58.71:/home/botuser/temp_settings.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/config && echo bot123456 | sudo -S cp /home/botuser/temp_settings.py /home/botuser/medical-bot/config/settings.py && rm /home/botuser/temp_settings.py"

scp "%SOURCE_DIR%\services\broadcast_service.py" botuser@5.223.58.71:/home/botuser/temp_broadcast.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/services && echo bot123456 | sudo -S cp /home/botuser/temp_broadcast.py /home/botuser/medical-bot/services/broadcast_service.py && rm /home/botuser/temp_broadcast.py"

scp "%SOURCE_DIR%\bot\handlers\user\user_reports_add_new_system\flows\shared.py" botuser@5.223.58.71:/home/botuser/temp_shared.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows && echo bot123456 | sudo -S cp /home/botuser/temp_shared.py /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/flows/shared.py && rm /home/botuser/temp_shared.py"

scp "%SOURCE_DIR%\bot\handlers\user\user_reports_delete.py" botuser@5.223.58.71:/home/botuser/temp_delete.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot/handlers/user && echo bot123456 | sudo -S cp /home/botuser/temp_delete.py /home/botuser/medical-bot/bot/handlers/user/user_reports_delete.py && rm /home/botuser/temp_delete.py"

scp "%SOURCE_DIR%\bot\handlers\user\user_reports_edit.py" botuser@5.223.58.71:/home/botuser/temp_edit.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot/handlers/user && echo bot123456 | sudo -S cp /home/botuser/temp_edit.py /home/botuser/medical-bot/bot/handlers/user/user_reports_edit.py && rm /home/botuser/temp_edit.py"

scp "%SOURCE_DIR%\bot\handlers\user\user_reports_add_new_system.py" botuser@5.223.58.71:/home/botuser/temp_add_new.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot/handlers/user && echo bot123456 | sudo -S cp /home/botuser/temp_add_new.py /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system.py && rm /home/botuser/temp_add_new.py"

scp "%SOURCE_DIR%\bot\handlers\user\user_reports_add_new_system\patient_handlers.py" botuser@5.223.58.71:/home/botuser/temp_patient_handlers.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system && echo bot123456 | sudo -S cp /home/botuser/temp_patient_handlers.py /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/patient_handlers.py && rm /home/botuser/temp_patient_handlers.py"

scp "%SOURCE_DIR%\bot\handlers\user\user_patient_search_inline.py" botuser@5.223.58.71:/home/botuser/temp_search_inline.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot/handlers/user && echo bot123456 | sudo -S cp /home/botuser/temp_search_inline.py /home/botuser/medical-bot/bot/handlers/user/user_patient_search_inline.py && rm /home/botuser/temp_search_inline.py"

scp "%SOURCE_DIR%\bot\handlers_registry.py" botuser@5.223.58.71:/home/botuser/temp_registry.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot && echo bot123456 | sudo -S cp /home/botuser/temp_registry.py /home/botuser/medical-bot/bot/handlers_registry.py && rm /home/botuser/temp_registry.py"

scp "%SOURCE_DIR%\bot\keyboards.py" botuser@5.223.58.71:/home/botuser/temp_keyboards.py
ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/bot && echo bot123456 | sudo -S cp /home/botuser/temp_keyboards.py /home/botuser/medical-bot/bot/keyboards.py && rm /home/botuser/temp_keyboards.py"

scp "%SOURCE_DIR%\add_missing_columns.py" botuser@5.223.58.71:/home/botuser/add_missing_columns.py

echo.
echo ============================================
echo 🔄 إضافة الأعمدة المفقودة في قاعدة البيانات...
echo ============================================
echo.

ssh botuser@5.223.58.71 "cd /home/botuser/medical-bot && python3 add_missing_columns.py"

echo.
echo ============================================
echo 🔄 إعادة تشغيل البوت...
echo ============================================
echo.

ssh botuser@5.223.58.71 "echo bot123456 | sudo -S systemctl restart medical-bot"
if %errorlevel%==0 (echo ✅ تم إعادة تشغيل البوت) else (echo ❌ فشل إعادة تشغيل البوت)

echo.
echo ============================================
echo ✅ اكتمل التحديث والنشر بنجاح!
echo ============================================
echo.
pause




