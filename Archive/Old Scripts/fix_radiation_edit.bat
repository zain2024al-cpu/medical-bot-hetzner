@echo off
chcp 65001 >nul
echo 📤 رفع radiation_therapy_edit.py...

scp "bot\handlers\user\user_reports_add_new_system\edit_handlers\before_publish\radiation_therapy_edit.py" botuser@5.223.58.71:/tmp/radiation_therapy_edit.py

if %ERRORLEVEL% EQU 0 (
    echo ✅ تم رفع الملف إلى /tmp
    
    echo 🔧 نقل الملف مع sudo...
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S mv /tmp/radiation_therapy_edit.py /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/edit_handlers/before_publish/"
    
    echo 🔐 تصحيح الصلاحيات...
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S chown botuser:botuser /home/botuser/medical-bot/bot/handlers/user/user_reports_add_new_system/edit_handlers/before_publish/radiation_therapy_edit.py"
    
    echo 🔄 إعادة تشغيل البوت...
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S systemctl restart medical-bot"
    
    timeout /t 8 /nobreak >nul
    
    echo 📊 فحص الحالة...
    ssh botuser@5.223.58.71 "echo bot123456 | sudo -S systemctl is-active medical-bot"
    
    echo ✅ تم بنجاح!
) else (
    echo ❌ فشل رفع الملف
)

pause
