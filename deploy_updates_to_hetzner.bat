@echo off
echo.
echo ========================================
echo 🚀 نشر التحديثات الجديدة للبوت على Hetzner
echo ========================================
echo.

set SERVER_IP=5.223.58.71
set BOT_USER=botuser

echo 📋 خطوات النشر:
echo 1. رفع الملفات المحدثة
echo 2. إعادة تشغيل البوت
echo 3. فحص العمل
echo.

echo 🔍 فحص الاتصال بالسيرفر...
ssh -o ConnectTimeout=10 %BOT_USER%@%SERVER_IP% "echo '✅ الاتصال ناجح'" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ فشل الاتصال بالسيرفر
    echo تأكد من أن السيرفر يعمل وأن SSH مفتوح
    pause
    exit /b 1
)

echo.
echo 📤 رفع الملفات المحدثة...
echo رفع services/smart_navigation_manager.py...
scp services/smart_navigation_manager.py %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/services/
echo رفع services/smart_cancel_manager.py...
scp services/smart_cancel_manager.py %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/services/
echo رفع services/smart_state_renderer.py...
scp services/smart_state_renderer.py %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/services/

echo رفع الدلائل الجديدة...
scp PRACTICAL_TESTING_GUIDE.md %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/
scp SMART_CANCEL_SYSTEM_GUIDE.md %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/
scp SMART_NAVIGATION_SYSTEM_GUIDE.md %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/
scp DEPLOYMENT_UPDATE_GUIDE.md %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/

echo رفع الملفات المحدثة...
scp bot/handlers/user/user_reports_add_new_system.py %BOT_USER%@%SERVER_IP%:/home/botuser/medical-bot/bot/handlers/user/

echo.
echo 🔄 إعادة تشغيل البوت...
ssh %BOT_USER%@%SERVER_IP% "cd /home/botuser/medical-bot && source venv/bin/activate && pkill -f 'python app.py' && sleep 2 && nohup python app.py > bot.log 2>&1 &"

echo.
echo ⏳ انتظار تشغيل البوت (10 ثواني)...
timeout /t 10 /nobreak > nul

echo.
echo 🧪 فحص حالة البوت...
ssh %BOT_USER%@%SERVER_IP% "ps aux | grep python | grep -v grep"

echo.
echo 📊 فحص logs البوت...
ssh %BOT_USER%@%SERVER_IP% "tail -n 10 /home/botuser/medical-bot/bot.log"

echo.
echo ========================================
echo 🎉 النشر مكتمل!
echo ========================================
echo.
echo ✅ التحديثات المرفوعة:
echo    - SmartNavigationManager
echo    - SmartCancelManager
echo    - SmartStateRenderer
echo    - handle_smart_back_navigation
echo    - الدلائل الجديدة
echo.
echo 🎯 الآن:
echo    1. اذهب لتلغرام وابحث عن البوت
echo    2. اختبر الأزرار الجديدة
echo    3. تأكد من ظهور الأسماء دائماً
echo    4. اختبر الرجوع الذكي
echo.
echo 📞 إذا واجهت مشاكل:
echo    - تحقق من logs: tail -f bot.log
echo    - أخبرني بالتفاصيل للإصلاح
echo.
echo 🚀 البوت محدث وجاهز للاستخدام!
echo ========================================

pause



