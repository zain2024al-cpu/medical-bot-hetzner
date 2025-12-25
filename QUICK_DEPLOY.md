# ⚡ النشر السريع - خطوات مختصرة

## 🚀 رفع على GitHub

```powershell
# في PowerShell (Windows)
.\deploy.ps1
```

أو يدوياً:

```bash
# 1. إضافة الملفات
git add .

# 2. Commit
git commit -m "feat: إضافة دعم المجموعات وإخفاء الأزرار"

# 3. Push
git push origin main
```

---

## 🌐 النشر على Hetzner

### الطريقة السريعة:
```bash
ssh root@5.223.58.71 'cd /root/medical-bot-hetzner && git pull origin main && systemctl restart medical-bot'
```

### الطريقة الآمنة:
```bash
# 1. الاتصال
ssh root@5.223.58.71

# 2. الانتقال للمجلد
cd /root/medical-bot-hetzner

# 3. جلب التحديثات
git pull origin main

# 4. إعادة التشغيل
systemctl restart medical-bot

# 5. التحقق
systemctl status medical-bot
```

---

## ✅ التحقق من النشر

```bash
# على السيرفر
journalctl -u medical-bot -f
```

---

## 📝 ملاحظات

- ✅ `config.env` محمي (لا يُرفع)
- ✅ قاعدة البيانات محمية (لا تُرفع)
- ✅ جميع الملفات الحساسة محمية





