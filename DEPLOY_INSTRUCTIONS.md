# 📋 تعليمات النشر السريع

## 🚀 النشر إلى GitHub ثم Hetzner

### الطريقة 1: استخدام السكريبت التلقائي (موصى به)

1. افتح PowerShell في مجلد `botuser@`
2. شغّل السكريبت:
   ```powershell
   .\DEPLOY_NOW.ps1
   ```

### الطريقة 2: النشر اليدوي

#### الخطوة 1: إضافة الملفات المحدثة
```powershell
cd botuser@
git add bot/handlers/user/user_reports_add_new_system.py
```

#### الخطوة 2: إنشاء Commit
```powershell
git commit -m "Fix: إصلاح مشكلة البحث عن الأطباء والمترجمين وإصلاح تعديل التقرير قبل الحفظ

- إصلاح unified_inline_query_handler للتحقق من search_type أولاً
- إضافة handle_edit_field_selection إلى جميع CONFIRM states
- إصلاح زر الرجوع في شاشة التعديل
- تحسين معالجة edit_field callbacks"
```

#### الخطوة 3: رفع إلى GitHub
```powershell
git push origin main
```

#### الخطوة 4: النشر على Hetzner
```powershell
ssh root@5.223.58.71 "cd /root/medical-bot-hetzner && git stash && git fetch origin main && git pull origin main && systemctl restart medical-bot"
```

#### الخطوة 5: التحقق من الحالة
```powershell
ssh root@5.223.58.71 "systemctl status medical-bot --no-pager -l | head -n 10"
```

## 📝 الملفات المحدثة

- `bot/handlers/user/user_reports_add_new_system.py` - إصلاحات البحث والتعديل

## ⚠️ ملاحظات مهمة

1. تأكد من أنك متصل بالإنترنت
2. تأكد من وجود صلاحيات الوصول إلى GitHub و Hetzner
3. في حالة فشل أي خطوة، تحقق من السجلات:
   ```powershell
   ssh root@5.223.58.71 "journalctl -u medical-bot -f"
   ```

## 🔍 التحقق من النشر

بعد النشر، تحقق من:
1. ✅ الخدمة تعمل: `systemctl is-active medical-bot`
2. ✅ لا توجد أخطاء في السجلات
3. ✅ البوت يستجيب للأوامر بشكل صحيح





