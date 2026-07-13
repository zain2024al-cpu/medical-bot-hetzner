@echo off
chcp 65001 >nul
echo ============================================
echo تحديث النسخة الاحتياطية ورفع الملفات للسيرفر
echo ============================================
echo.

REM نسخ الملفات المحدثة إلى النسخة الاحتياطية
echo 📋 نسخ الملفات المحدثة إلى النسخة الاحتياطية...
echo.

copy /Y "db\models.py" "..\BOT_OMAR_2026_20260102_002648\db\models.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ db\models.py) else (echo ❌ فشل نسخ db\models.py)

copy /Y "services\broadcast_service.py" "..\BOT_OMAR_2026_20260102_002648\services\broadcast_service.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ services\broadcast_service.py) else (echo ❌ فشل نسخ services\broadcast_service.py)

copy /Y "bot\handlers\user\user_reports_add_new_system\flows\shared.py" "..\BOT_OMAR_2026_20260102_002648\bot\handlers\user\user_reports_add_new_system\flows\shared.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ shared.py) else (echo ❌ فشل نسخ shared.py)

copy /Y "bot\handlers\user\user_reports_delete.py" "..\BOT_OMAR_2026_20260102_002648\bot\handlers\user\user_reports_delete.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ user_reports_delete.py) else (echo ❌ فشل نسخ user_reports_delete.py)

copy /Y "bot\keyboards.py" "..\BOT_OMAR_2026_20260102_002648\bot\keyboards.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ keyboards.py) else (echo ❌ فشل نسخ keyboards.py)

copy /Y "bot\handlers_registry.py" "..\BOT_OMAR_2026_20260102_002648\bot\handlers_registry.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ handlers_registry.py) else (echo ❌ فشل نسخ handlers_registry.py)

copy /Y "bot\handlers\user\user_reports_edit.py" "..\BOT_OMAR_2026_20260102_002648\bot\handlers\user\user_reports_edit.py" >nul
if %errorlevel%==0 (echo ✅ تم نسخ user_reports_edit.py) else (echo ❌ فشل نسخ user_reports_edit.py)

echo.
echo ============================================
echo ✅ تم تحديث النسخة الاحتياطية بنجاح!
echo ============================================
echo.
echo 📤 رفع الملفات على السيرفر...
echo.

REM رفع الملفات على السيرفر (إلى مجلد مؤقت أولاً)
echo رفع db\models.py...
scp "db\models.py" botuser@5.223.58.71:/home/botuser/temp_models.py
if %errorlevel%==0 (
    echo ✅ تم رفع db\models.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/db && echo bot123456 | sudo -S cp /home/botuser/temp_models.py /home/botuser/medical-bot/temp_upload/db/models.py && rm /home/botuser/temp_models.py"
) else (echo ❌ فشل رفع db\models.py)

echo رفع services\broadcast_service.py...
scp "services\broadcast_service.py" botuser@5.223.58.71:/home/botuser/temp_broadcast.py
if %errorlevel%==0 (
    echo ✅ تم رفع services\broadcast_service.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/services && echo bot123456 | sudo -S cp /home/botuser/temp_broadcast.py /home/botuser/medical-bot/temp_upload/services/broadcast_service.py && rm /home/botuser/temp_broadcast.py"
) else (echo ❌ فشل رفع services\broadcast_service.py)

echo رفع bot\handlers\user\user_reports_add_new_system\flows\shared.py...
scp "bot\handlers\user\user_reports_add_new_system\flows\shared.py" botuser@5.223.58.71:/home/botuser/temp_shared.py
if %errorlevel%==0 (
    echo ✅ تم رفع shared.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/bot/handlers/user/user_reports_add_new_system/flows && echo bot123456 | sudo -S cp /home/botuser/temp_shared.py /home/botuser/medical-bot/temp_upload/bot/handlers/user/user_reports_add_new_system/flows/shared.py && rm /home/botuser/temp_shared.py"
) else (echo ❌ فشل رفع shared.py)

echo رفع bot\handlers\user\user_reports_delete.py...
scp "bot\handlers\user\user_reports_delete.py" botuser@5.223.58.71:/home/botuser/temp_delete.py
if %errorlevel%==0 (
    echo ✅ تم رفع user_reports_delete.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/bot/handlers/user && echo bot123456 | sudo -S cp /home/botuser/temp_delete.py /home/botuser/medical-bot/temp_upload/bot/handlers/user/user_reports_delete.py && rm /home/botuser/temp_delete.py"
) else (echo ❌ فشل رفع user_reports_delete.py)

echo رفع bot\keyboards.py...
scp "bot\keyboards.py" botuser@5.223.58.71:/home/botuser/temp_keyboards.py
if %errorlevel%==0 (
    echo ✅ تم رفع keyboards.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/bot && echo bot123456 | sudo -S cp /home/botuser/temp_keyboards.py /home/botuser/medical-bot/temp_upload/bot/keyboards.py && rm /home/botuser/temp_keyboards.py"
) else (echo ❌ فشل رفع keyboards.py)

echo رفع bot\handlers_registry.py...
scp "bot\handlers_registry.py" botuser@5.223.58.71:/home/botuser/temp_registry.py
if %errorlevel%==0 (
    echo ✅ تم رفع handlers_registry.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/bot && echo bot123456 | sudo -S cp /home/botuser/temp_registry.py /home/botuser/medical-bot/temp_upload/bot/handlers_registry.py && rm /home/botuser/temp_registry.py"
) else (echo ❌ فشل رفع handlers_registry.py)

echo رفع bot\handlers\user\user_reports_edit.py...
scp "bot\handlers\user\user_reports_edit.py" botuser@5.223.58.71:/home/botuser/temp_edit.py
if %errorlevel%==0 (
    echo ✅ تم رفع user_reports_edit.py
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mkdir -p /home/botuser/medical-bot/temp_upload/bot/handlers/user && echo bot123456 | sudo -S cp /home/botuser/temp_edit.py /home/botuser/medical-bot/temp_upload/bot/handlers/user/user_reports_edit.py && rm /home/botuser/temp_edit.py"
) else (echo ❌ فشل رفع user_reports_edit.py)

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

