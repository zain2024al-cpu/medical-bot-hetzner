# ================================================
# سكريبت النشر المنظم - GitHub و Hetzner
# ================================================

Write-Host "🚀 بدء عملية النشر المنظم..." -ForegroundColor Cyan
Write-Host ""

# التحقق من أننا في مجلد Git
if (-not (Test-Path ".git")) {
    Write-Host "❌ خطأ: هذا ليس مجلد Git!" -ForegroundColor Red
    exit 1
}

# الألوان
$GREEN = "Green"
$YELLOW = "Yellow"
$RED = "Red"
$CYAN = "Cyan"

Write-Host "📋 الخطوة 1: التحقق من الملفات الحساسة..." -ForegroundColor $YELLOW

# التحقق من أن config.env غير موجود في Git
$configEnv = git ls-files config.env
if ($configEnv) {
    Write-Host "⚠️  تحذير: config.env موجود في Git!" -ForegroundColor $YELLOW
    Write-Host "   يجب إزالته من Git: git rm --cached config.env" -ForegroundColor $YELLOW
} else {
    Write-Host "✅ config.env محمي (غير موجود في Git)" -ForegroundColor $GREEN
}

Write-Host ""
Write-Host "📋 الخطوة 2: إضافة الملفات الجديدة..." -ForegroundColor $YELLOW

# إضافة الملفات الجديدة
$newFiles = @(
    "DEPLOYMENT_GUIDE.md",
    "GROUP_SETUP.md",
    "HOW_IT_WORKS.md",
    "bot/handlers/shared/group_handler.py",
    "bot/handlers/user/user_initial_case.py",
    "deploy_to_hetzner.sh",
    "run_hetzner.sh"
)

foreach ($file in $newFiles) {
    if (Test-Path $file) {
        git add $file
        Write-Host "  ✅ تمت إضافة: $file" -ForegroundColor $GREEN
    } else {
        Write-Host "  ⚠️  الملف غير موجود: $file" -ForegroundColor $YELLOW
    }
}

Write-Host ""
Write-Host "📋 الخطوة 3: إضافة التعديلات والحذف..." -ForegroundColor $YELLOW
git add -u
Write-Host "✅ تمت إضافة جميع التعديلات" -ForegroundColor $GREEN

Write-Host ""
Write-Host "📋 الخطوة 4: عرض التغييرات..." -ForegroundColor $YELLOW
git status --short

Write-Host ""
$confirm = Read-Host "هل تريد المتابعة مع commit و push? (y/n)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "❌ تم الإلغاء" -ForegroundColor $RED
    exit 0
}

Write-Host ""
Write-Host "📋 الخطوة 5: عمل commit..." -ForegroundColor $YELLOW

$commitMessage = @"
feat: إضافة دعم المجموعات وإخفاء الأزرار

- إضافة معالج المجموعات (group_handler.py)
- إخفاء الأزرار من المجموعة (فقط في الدردشة الخاصة)
- إضافة دعم إرسال التقارير للمجموعة تلقائياً
- إضافة التقرير الأولي للمرضى
- تحسين البحث عن المرضى والمترجمين
- إضافة ملفات توثيق (GROUP_SETUP.md, HOW_IT_WORKS.md)
- تنظيف الملفات القديمة غير المستخدمة
"@

git commit -m $commitMessage

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ تم عمل commit بنجاح" -ForegroundColor $GREEN
} else {
    Write-Host "❌ فشل عمل commit" -ForegroundColor $RED
    exit 1
}

Write-Host ""
Write-Host "📋 الخطوة 6: رفع إلى GitHub..." -ForegroundColor $YELLOW

$branch = git branch --show-current
Write-Host "  الفرع الحالي: $branch" -ForegroundColor $CYAN

$confirmPush = Read-Host "هل تريد رفع التغييرات إلى GitHub? (y/n)"
if ($confirmPush -eq "y" -or $confirmPush -eq "Y") {
    git push origin $branch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ تم الرفع إلى GitHub بنجاح" -ForegroundColor $GREEN
    } else {
        Write-Host "❌ فشل الرفع إلى GitHub" -ForegroundColor $RED
        exit 1
    }
} else {
    Write-Host "⏭️  تم تخطي الرفع إلى GitHub" -ForegroundColor $YELLOW
}

Write-Host ""
Write-Host "📋 الخطوة 7: النشر على Hetzner..." -ForegroundColor $YELLOW

$deployHetzner = Read-Host "هل تريد النشر على Hetzner الآن? (y/n)"
if ($deployHetzner -eq "y" -or $deployHetzner -eq "Y") {
    Write-Host ""
    Write-Host "🔗 الاتصال بالسيرفر ونشر التحديثات..." -ForegroundColor $CYAN
    Write-Host ""
    Write-Host "يمكنك استخدام الأمر التالي:" -ForegroundColor $YELLOW
    Write-Host "  ssh root@5.223.58.71 'cd /root/medical-bot-hetzner && git pull origin main && systemctl restart medical-bot'" -ForegroundColor $CYAN
    Write-Host ""
    Write-Host "أو استخدام السكريبت:" -ForegroundColor $YELLOW
    Write-Host "  bash deploy_to_hetzner.sh" -ForegroundColor $CYAN
} else {
    Write-Host "⏭️  تم تخطي النشر على Hetzner" -ForegroundColor $YELLOW
}

Write-Host ""
Write-Host "✅ تم إكمال العملية بنجاح!" -ForegroundColor $GREEN
Write-Host ""
Write-Host "📝 ملخص:" -ForegroundColor $CYAN
Write-Host "  - تم عمل commit للتحديثات" -ForegroundColor $GREEN
Write-Host "  - تم الرفع إلى GitHub (إن تم تأكيده)" -ForegroundColor $GREEN
Write-Host "  - جاهز للنشر على Hetzner" -ForegroundColor $GREEN
Write-Host ""



