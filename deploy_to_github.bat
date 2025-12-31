@echo off
echo.
echo ========================================
echo 🚀 رفع التحديثات الجديدة لـ GitHub
echo ========================================
echo.

echo 📋 التحديثات المضافة:
echo ✅ SmartNavigationManager - تنقل ذكي بخطوة واحدة
echo ✅ SmartCancelManager - إلغاء ذكي حسب السياق
echo ✅ SmartStateRenderer - إعادة عرض الأسماء دائماً
echo ✅ handle_smart_back_navigation - رجوع محسن
echo ✅ PRACTICAL_TESTING_GUIDE.md - دليل الفحص العملي
echo ✅ SMART_CANCEL_SYSTEM_GUIDE.md - دليل نظام الإلغاء
echo ✅ SMART_NAVIGATION_SYSTEM_GUIDE.md - دليل نظام التنقل
echo ✅ DEPLOYMENT_UPDATE_GUIDE.md - دليل النشر
echo.

echo 🔄 إضافة جميع الملفات الجديدة...
git add .

echo.
echo 📝 إنشاء commit مع رسالة واضحة...
git commit -m "🚀 إضافة الأنظمة الذكية المحسنة للبوت

✅ Smart Navigation System - تنقل ذكي بخطوة واحدة
✅ Smart Cancel System - إلغاء ذكي حسب السياق
✅ Smart State Renderer - إعادة عرض الأسماء دائماً
✅ تحسينات البحث والعرض الفوري للمرضى والأطباء
✅ handle_smart_back_navigation - رجوع محسن
✅ دلائل شاملة للاستخدام والفحص

🧪 الاختبارات المطلوبة:
- ظهور أسماء المرضى (95) فوراً دائماً
- ظهور أسماء الأطباء (48) فوراً دائماً
- ظهور أسماء المترجمين (20) فوراً دائماً
- رجوع ذكي بخطوة واحدة فقط
- إلغاء ذكي حسب السياق

📚 الملفات المضافة:
- services/smart_navigation_manager.py
- services/smart_cancel_manager.py
- services/smart_state_renderer.py
- PRACTICAL_TESTING_GUIDE.md
- SMART_CANCEL_SYSTEM_GUIDE.md
- SMART_NAVIGATION_SYSTEM_GUIDE.md
- DEPLOYMENT_UPDATE_GUIDE.md"

echo.
echo 📤 رفع لـ GitHub...
git push origin main

echo.
echo ✅ تم الرفع بنجاح!
echo.
echo 🎯 الآن يمكن:
echo    1. النشر التلقائي إذا كان CI/CD مفعل
echo    2. رفع يدوي باستخدام deploy_updates_to_hetzner.bat
echo    3. اختبار البوت محلياً
echo.
echo 🔗 رابط المشروع على GitHub:
echo https://github.com/zain2024al-cpu/medical-bot-hetzner
echo.
echo 🎉 التحديثات جاهزة للنشر!
echo ========================================

pause

