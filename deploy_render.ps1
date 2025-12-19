# ================================================
# deploy_render.ps1
# 🔹 سكريبت النشر على Render
# ================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🚀 نشر البوت على Render" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من Git
Write-Host "📦 التحقق من Git..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git غير مثبت!" -ForegroundColor Red
    Write-Host "يرجى تثبيت Git من: https://git-scm.com/downloads" -ForegroundColor Yellow
    exit 1
}

$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "⚠️ هناك تغييرات غير محفوظة:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Yellow
    Write-Host ""
    $confirm = Read-Host "هل تريد المتابعة؟ (y/n)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "❌ تم الإلغاء" -ForegroundColor Red
        exit 1
    }
}

# التحقق من الملفات المطلوبة
Write-Host ""
Write-Host "📄 التحقق من الملفات المطلوبة..." -ForegroundColor Yellow

$requiredFiles = @(
    "Dockerfile",
    "requirements.txt",
    "app.py",
    "render.yaml"
)

$allFilesExist = $true
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file غير موجود!" -ForegroundColor Red
        $allFilesExist = $false
    }
}

if (-not $allFilesExist) {
    Write-Host ""
    Write-Host "❌ بعض الملفات المطلوبة غير موجودة!" -ForegroundColor Red
    exit 1
}

# التحقق من قاعدة البيانات
Write-Host ""
Write-Host "💾 التحقق من قاعدة البيانات..." -ForegroundColor Yellow
if (Test-Path "db/medical_reports.db") {
    $dbSize = (Get-Item "db/medical_reports.db").Length / 1MB
    Write-Host "  ✅ قاعدة البيانات موجودة (حجم: $([math]::Round($dbSize, 2)) MB)" -ForegroundColor Green
    
    $uploadDb = Read-Host "هل تريد رفع قاعدة البيانات مع الكود؟ (y/n)"
    if ($uploadDb -eq "y" -or $uploadDb -eq "Y") {
        Write-Host "  📋 نسخ قاعدة البيانات..." -ForegroundColor Yellow
        Copy-Item "db/medical_reports.db" "db/medical_reports_initial.db" -Force
        Write-Host "  ✅ تم نسخ قاعدة البيانات" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️ قاعدة البيانات غير موجودة" -ForegroundColor Yellow
    Write-Host "  ℹ️ سيتم إنشاء قاعدة بيانات جديدة على Render" -ForegroundColor Yellow
}

# إضافة الملفات إلى Git
Write-Host ""
Write-Host "📤 إضافة الملفات إلى Git..." -ForegroundColor Yellow
git add .

# Commit
Write-Host ""
Write-Host "💾 حفظ التغييرات..." -ForegroundColor Yellow
$commitMessage = Read-Host "رسالة الـ Commit (اتركه فارغاً للاستخدام الافتراضي)"
if ([string]::IsNullOrWhiteSpace($commitMessage)) {
    $commitMessage = "نشر على Render - تحديث البيانات"
}

git commit -m $commitMessage

# Push إلى GitHub
Write-Host ""
Write-Host "🚀 رفع إلى GitHub..." -ForegroundColor Yellow
$branch = git branch --show-current
Write-Host "  📌 الفرع الحالي: $branch" -ForegroundColor Cyan

$pushConfirm = Read-Host "هل تريد رفع التغييرات إلى GitHub؟ (y/n)"
if ($pushConfirm -eq "y" -or $pushConfirm -eq "Y") {
    git push origin $branch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ تم الرفع بنجاح!" -ForegroundColor Green
        Write-Host ""
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host "📋 الخطوات التالية:" -ForegroundColor Cyan
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "1. اذهب إلى Render Dashboard:" -ForegroundColor Yellow
        Write-Host "   https://dashboard.render.com" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "2. إذا كان الـ Service موجوداً، سيتم التحديث تلقائياً" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "3. إذا كان جديداً، أنشئ Web Service جديد:" -ForegroundColor Yellow
        Write-Host "   - اختر المستودع من GitHub" -ForegroundColor White
        Write-Host "   - اختر Docker" -ForegroundColor White
        Write-Host "   - أضف متغيرات البيئة من env.yaml" -ForegroundColor White
        Write-Host ""
        Write-Host "4. بعد النشر، أعد إعداد Webhook:" -ForegroundColor Yellow
        Write-Host "   https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<RENDER_URL>/<BOT_TOKEN>" -ForegroundColor Cyan
        Write-Host ""
        
        if ($uploadDb -eq "y" -or $uploadDb -eq "Y") {
            Write-Host "5. بعد النشر، احذف قاعدة البيانات من Git:" -ForegroundColor Yellow
            Write-Host "   git rm db/medical_reports_initial.db" -ForegroundColor Cyan
            Write-Host "   git commit -m 'إزالة قاعدة البيانات من Git'" -ForegroundColor Cyan
            Write-Host "   git push origin $branch" -ForegroundColor Cyan
            Write-Host ""
        }
        
        Write-Host "✅ تم!" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "❌ فشل الرفع!" -ForegroundColor Red
        Write-Host "تحقق من اتصال الإنترنت وإعدادات Git" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "ℹ️ تم الإلغاء - يمكنك رفع التغييرات لاحقاً" -ForegroundColor Yellow
    Write-Host "استخدم: git push origin $branch" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan

