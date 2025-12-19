# ================================================
# restart_render.ps1
# 🔹 إعادة نشر/تشغيل البوت على Render
# ================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🔄 إعادة نشر البوت على Render" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من Git
Write-Host "📦 التحقق من Git..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git غير مثبت!" -ForegroundColor Red
    exit 1
}

# التحقق من حالة Git
$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "⚠️ هناك تغييرات غير محفوظة:" -ForegroundColor Yellow
    Write-Host $gitStatus -ForegroundColor Yellow
    Write-Host ""
    $confirm = Read-Host "هل تريد حفظ التغييرات وإعادة النشر؟ (y/n)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "❌ تم الإلغاء" -ForegroundColor Red
        exit 1
    }
    
    # إضافة وحفظ التغييرات
    Write-Host ""
    Write-Host "💾 حفظ التغييرات..." -ForegroundColor Yellow
    git add .
    $commitMessage = Read-Host "رسالة الـ Commit (اتركه فارغاً للاستخدام الافتراضي)"
    if ([string]::IsNullOrWhiteSpace($commitMessage)) {
        $commitMessage = "تحديث وإعادة نشر على Render"
    }
    git commit -m $commitMessage
}

# التحقق من قاعدة البيانات
Write-Host ""
Write-Host "💾 التحقق من قاعدة البيانات..." -ForegroundColor Yellow
if (Test-Path "db/medical_reports.db") {
    $dbSize = (Get-Item "db/medical_reports.db").Length / 1MB
    Write-Host "  ✅ قاعدة البيانات موجودة (حجم: $([math]::Round($dbSize, 2)) MB)" -ForegroundColor Green
    
    $uploadDb = Read-Host "هل تريد تحديث قاعدة البيانات على Render؟ (y/n)"
    if ($uploadDb -eq "y" -or $uploadDb -eq "Y") {
        Write-Host "  📋 نسخ قاعدة البيانات..." -ForegroundColor Yellow
        Copy-Item "db/medical_reports.db" "db/medical_reports_initial.db" -Force
        Write-Host "  ✅ تم نسخ قاعدة البيانات" -ForegroundColor Green
        git add db/medical_reports_initial.db
    }
} else {
    Write-Host "  ⚠️ قاعدة البيانات غير موجودة" -ForegroundColor Yellow
}

# الحصول على الفرع الحالي
$branch = git branch --show-current
Write-Host ""
Write-Host "📌 الفرع الحالي: $branch" -ForegroundColor Cyan

# رفع إلى GitHub
Write-Host ""
Write-Host "🚀 رفع التغييرات إلى GitHub..." -ForegroundColor Yellow
$pushConfirm = Read-Host "هل تريد رفع التغييرات إلى GitHub؟ (y/n)"
if ($pushConfirm -eq "y" -or $pushConfirm -eq "Y") {
    git push origin $branch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ تم الرفع بنجاح!" -ForegroundColor Green
        Write-Host ""
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host "📋 Render سيعيد النشر تلقائياً" -ForegroundColor Cyan
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "⏳ انتظر بضع دقائق حتى يكتمل النشر..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "📊 يمكنك متابعة النشر من:" -ForegroundColor Yellow
        Write-Host "   https://dashboard.render.com" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🔍 تحقق من Logs للتأكد من نجاح النشر" -ForegroundColor Yellow
        Write-Host ""
        
        if ($uploadDb -eq "y" -or $uploadDb -eq "Y") {
            Write-Host "⚠️ بعد اكتمال النشر، احذف قاعدة البيانات من Git:" -ForegroundColor Yellow
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
    Write-Host "ℹ️ تم الإلغاء" -ForegroundColor Yellow
    Write-Host "يمكنك رفع التغييرات لاحقاً باستخدام:" -ForegroundColor Yellow
    Write-Host "   git push origin $branch" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan

